"""Import an existing TKB .xlsm workbook into the SQLite schema.

Mirrors the VBA's own dynamic header-scanning (never hardcodes row/col
numbers for dimensions) so it stays robust if the school adds a class or
subject later. Skips columns that are Excel-formula-derived in the original
workbook (DinhMuc_GV's Trần/Tải/Vượt) since those are recomputed on read.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import openpyxl

from core.models import ROLE_HDTN
from data import repository as repo
from io_excel.weekly_importer import _find_grade_from_sheet_name, import_weekly_curriculum_from_excel


@dataclass
class ImportReport:
    counts: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def _norm(value) -> str:
    return str(value).strip() if value is not None else ""


def _extract_parity(text: str) -> str:
    return "L" if "[L]" in text.upper() else "C"


def _infer_session_frame(per_weekday: dict) -> tuple:
    """per_weekday: {weekday: max_active_period} cho 1 (lớp, buổi), đọc từ lưới "x" của
    sheet Khung. Trả về (standard_periods, short_weekday, short_periods) -- 2 mục sau là
    None nếu mọi ngày đồng nhất, hoặc nếu có nhiều hơn 1 ngày lệch chuẩn (vượt quá mô hình
    1-ngày-lệch, gọi nơi dùng nên fallback về max() như hành vi cũ).
    """
    values = list(per_weekday.values())
    if not values or max(values) == 0:
        return 0, None, None
    standard = max(set(values), key=values.count)
    outliers = {wd: v for wd, v in per_weekday.items() if v != standard}
    if not outliers:
        return standard, None, None
    if len(outliers) == 1:
        (wd, v), = outliers.items()
        return standard, wd, v
    return max(values), None, None


def _resolve_frame(per_weekday_s: dict, per_weekday_c: dict) -> tuple:
    """Gộp kết quả suy luận của 2 buổi thành 1 frame_template.
    Trả về (morning_periods, afternoon_periods, short_weekday, short_morning, short_afternoon).
    """
    std_s, out_wd_s, out_val_s = _infer_session_frame(per_weekday_s)
    std_c, out_wd_c, out_val_c = _infer_session_frame(per_weekday_c)
    if out_wd_s is not None and out_wd_c is not None and out_wd_s != out_wd_c:
        # Ngày lệch của buổi sáng và buổi chiều khác nhau -- vượt quá mô hình 1 ngày lệch
        # chung cho cả lớp, fallback về khung đồng nhất (dùng periods tối đa từng buổi).
        fallback_s = max(per_weekday_s.values()) if per_weekday_s else 0
        fallback_c = max(per_weekday_c.values()) if per_weekday_c else 0
        return fallback_s, fallback_c, None, None, None
    short_wd = out_wd_s if out_wd_s is not None else out_wd_c
    short_m = out_val_s if out_wd_s is not None else None
    short_a = out_val_c if out_wd_c is not None else None
    return std_s, std_c, short_wd, short_m, short_a


def import_xlsm(conn, path: str) -> ImportReport:
    wb = openpyxl.load_workbook(path, data_only=True)
    report = ImportReport()

    has_phancong = "PhanCong" in wb.sheetnames
    has_weekly = any(_find_grade_from_sheet_name(s) is not None for s in wb.sheetnames)

    if not has_phancong and has_weekly:
        w_rep = import_weekly_curriculum_from_excel(conn, wb)
        report.counts = {
            "classes": len(w_rep.get("classes_updated", [])),
            "subjects": len(w_rep.get("subjects_mapped", [])),
            "teachers": 0,
            "unavailability_rows": 0,
            "tkb_nhap_cells": 0,
            "seed_history_rows": 0,
            "weekly_curriculum_rows": w_rep.get("records_imported", 0),
        }
        report.warnings.append(
            f"Đã nhận diện và nạp thành công định lượng {w_rep['records_imported']} dòng cho {w_rep['weeks_count']} tuần ({', '.join(w_rep['classes_updated'])})."
        )
        return report

    if not has_phancong:
        raise ValueError("File Excel không có sheet 'PhanCong' hoặc định dạng tuần hợp lệ.")

    ws_pc = wb["PhanCong"]
    ws_st = wb["SoTiet"]

    # ---- dims: classes (row 2 from col B), subjects (col A from row 3) ----
    class_names = []
    col = 2
    while True:
        v = _norm(ws_pc.cell(2, col).value)
        if not v or v.upper().startswith("MA") or v.upper().startswith("MÃ"):
            break
        class_names.append(v)
        col += 1
    n_classes = len(class_names)

    subject_rows = []
    row = 3
    while _norm(ws_pc.cell(row, 1).value):
        subject_rows.append((row, _norm(ws_pc.cell(row, 1).value)))
        row += 1
    n_subjects = len(subject_rows)

    if n_classes == 0 or n_subjects == 0:
        raise ValueError(
            "PhanCong rỗng: không đọc được lớp (hàng 2 từ cột B) hoặc môn (cột A từ hàng 3)."
        )

    # ---- role-code ("MA") column: dynamic scan, same as ResolveRoles ----
    code_col = None
    for c in range(2 + n_classes, 2 + n_classes + 6):
        v = _norm(ws_pc.cell(2, c).value).upper()
        if v.startswith("MA") or v.startswith("MÃ"):
            code_col = c
            break
    if code_col is None:
        code_col = 2 + n_classes + 1

    class_ids = {}
    for i, name in enumerate(class_names):
        existing_class_id = repo.get_class_by_name(conn, name)
        class_ids[name] = repo.upsert_class(conn, name, sort_order=i, class_id=existing_class_id)

    subject_ids = {}
    hdtn_present = False
    for i, (row_idx, name) in enumerate(subject_rows):
        role_code = int(ws_pc.cell(row_idx, code_col).value or 0)
        existing_subject_id = repo.get_subject_by_name(conn, name)
        subject_ids[name] = repo.upsert_subject(
            conn, name, role_code=role_code, sort_order=i, subject_id=existing_subject_id
        )
        if role_code == ROLE_HDTN:
            hdtn_present = True
    if not hdtn_present:
        report.warnings.append(
            "Không tìm thấy môn có MÃ = 5 (HDTN) ở cột 'MÃ VAI TRÒ' trên PhanCong. "
            "Xếp TKB sẽ báo lỗi cho tới khi được bổ sung."
        )

    # ---- teacher assignments (PhanCong grid) ----
    teacher_ids = {}

    def get_or_create_teacher(name: str) -> int:
        if name not in teacher_ids:
            existing = repo.get_teacher_by_name(conn, name)
            teacher_ids[name] = existing if existing is not None else repo.upsert_teacher(conn, name)
        return teacher_ids[name]

    for row_idx, subj_name in subject_rows:
        for i, cls_name in enumerate(class_names):
            teacher_name = _norm(ws_pc.cell(row_idx, 2 + i).value)
            teacher_id = get_or_create_teacher(teacher_name) if teacher_name else None
            repo.set_assignment(conn, subject_ids[subj_name], class_ids[cls_name], teacher_id)

    # ---- SoTiet: even (Chẵn) block from col B, odd (Lẻ) block from col (2+n_classes+1) ----
    odd_start_col = None
    for c in range(2 + n_classes, ws_st.max_column + 1):
        v = _norm(ws_st.cell(2, c).value).upper()
        if "[L]" in v or (class_names and v == f"{class_names[0].upper()} L"):
            odd_start_col = c
            break
    if odd_start_col is None:
        odd_start_col = 2 + n_classes + 1

    for row_idx, subj_name in subject_rows:
        for i, cls_name in enumerate(class_names):
            try:
                even_val = int(float(ws_st.cell(row_idx, 2 + i).value or 0))
            except (ValueError, TypeError):
                even_val = 0
            try:
                odd_val = int(float(ws_st.cell(row_idx, odd_start_col + i).value or 0))
            except (ValueError, TypeError):
                odd_val = 0
            repo.set_periods_per_week(conn, subject_ids[subj_name], class_ids[cls_name], "C", even_val)
            repo.set_periods_per_week(conn, subject_ids[subj_name], class_ids[cls_name], "L", odd_val)

    # ---- DinhMuc_GV: only the hand-entered columns (role, Đi T2, GVCN) ----
    n_teachers_from_dm = 0
    if "DinhMuc_GV" in wb.sheetnames:
        ws_dm = wb["DinhMuc_GV"]
        row = 3
        while _norm(ws_dm.cell(row, 1).value):
            name = _norm(ws_dm.cell(row, 1).value)
            if name.lower() in ("stt", "giáo viên", "giao vien", "họ và tên", "tên gv"):
                row += 1
                continue
            role = _norm(ws_dm.cell(row, 2).value)
            try:
                must_monday = bool(int(float(ws_dm.cell(row, 8).value or 0)))
            except (ValueError, TypeError):
                must_monday = True
            try:
                is_gvcn = bool(int(float(ws_dm.cell(row, 9).value or 0)))
            except (ValueError, TypeError):
                is_gvcn = False
            tid = get_or_create_teacher(name)
            repo.upsert_teacher(conn, name, role=role, must_monday=must_monday, is_gvcn=is_gvcn, teacher_id=tid)
            n_teachers_from_dm += 1
            row += 1

        # role -> reduction lookup table, headed by "Chức vụ"/"Giảm" (searched dynamically, not fixed columns)
        role_col_idx = None
        for c in range(1, 25):
            if _norm(ws_dm.cell(1, c).value) == "Chức vụ":
                role_col_idx = c
                break
        if role_col_idx is not None:
            r = 2
            while _norm(ws_dm.cell(r, role_col_idx).value):
                r_name = _norm(ws_dm.cell(r, role_col_idx).value)
                r_reduction = int(ws_dm.cell(r, role_col_idx + 1).value or 0)
                repo.set_role_reduction(conn, r_name, r_reduction)
                r += 1

        # base_cap ("Chuẩn:") / min_floor ("Sàn tối thiểu:") -- dò động như "Chức vụ" ở trên vì vị
        # trí nhãn tùy file cụ thể. Bỏ qua im lặng nếu không có (file Excel gốc/cũ không có 2 ô
        # này) -- không phải lỗi, chỉ đơn giản là app giữ nguyên giá trị mặc định hiện tại.
        for c in range(1, 25):
            label = _norm(ws_dm.cell(1, c).value)
            value = ws_dm.cell(1, c + 1).value
            if value in (None, ""):
                continue
            if label == "Chuẩn:":
                repo.set_base_cap(conn, int(value))
            elif label == "Sàn tối thiểu:":
                repo.set_min_floor(conn, int(value))

    # ---- GV_Ban: skip rows whose name doesn't match a known teacher (also filters instructional rows) ----
    n_unavailability = 0
    if "GV_Ban" in wb.sheetnames:
        repo.clear_unavailability(conn)
        ws_gb = wb["GV_Ban"]
        row = 3
        while _norm(ws_gb.cell(row, 1).value):
            name = _norm(ws_gb.cell(row, 1).value)
            tid = repo.get_teacher_by_name(conn, name)
            if tid is None:
                report.warnings.append(f"GV_Bận dòng {row}: bỏ qua vì không khớp tên GV nào ('{name}').")
            else:
                weekday = _norm(ws_gb.cell(row, 2).value).upper() or "*"
                session = _norm(ws_gb.cell(row, 3).value).upper() or "*"
                period = _norm(ws_gb.cell(row, 4).value) or "*"
                repo.add_unavailability(conn, tid, weekday, session, period)
                n_unavailability += 1
            row += 1

    # ---- TKB_Nhap (baseline grid) + infer frame_template from the real Khung "x" pattern ----
    ws_nh = wb["TKB_Nhap"]
    ws_khung = wb["Khung"] if "Khung" in wb.sheetnames else None
    # Theo dõi period active lớn nhất TỪNG NGÀY (không gộp chung) để phát hiện đúng ngày lệch
    # tiết (vd Thứ 7 chỉ 4 tiết trong khi các ngày khác 5 tiết) thay vì lấy max() rồi áp đồng
    # nhất cho mọi ngày như trước, làm mất thông tin ngày lệch tiết của trường thực tế.
    frame_per_weekday = {
        cid: {"S": {wd: 0 for wd in range(2, 8)}, "C": {wd: 0 for wd in range(2, 8)}}
        for cid in class_ids.values()
    }
    cells = {}
    row = 2
    while _norm(ws_nh.cell(row, 1).value):
        cls_name = _norm(ws_nh.cell(row, 1).value)
        if cls_name not in class_ids:
            row += 1
            continue
        cls_id = class_ids[cls_name]
        session = _norm(ws_nh.cell(row, 2).value).upper()
        period = int(ws_nh.cell(row, 3).value or 0)

        if ws_khung is not None and session in ("S", "C"):
            for wd in range(2, 8):
                if _norm(ws_khung.cell(row, wd + 2).value):
                    per_wd = frame_per_weekday[cls_id][session]
                    per_wd[wd] = max(per_wd[wd], period)

        for wd in range(2, 8):
            val = _norm(ws_nh.cell(row, wd + 2).value)
            subj_id = subject_ids.get(val) if val else None
            cells[(cls_id, wd, session, period)] = subj_id
        row += 1

    repo.bulk_replace_tkb_nhap(conn, cells)
    class_names_by_id = {cid: name for name, cid in class_ids.items()}
    for cls_id, per_session in frame_per_weekday.items():
        morning, afternoon, short_wd, short_m, short_a = _resolve_frame(per_session["S"], per_session["C"])
        try:
            repo.set_frame_template(
                conn, cls_id, morning, afternoon, study_sunday=False,
                short_weekday=short_wd, short_morning_periods=short_m, short_afternoon_periods=short_a,
            )
        except ValueError:
            # Ngày lệch suy ra từ Khung sheet vi phạm luật "không lỗ 1 tiết" -- fallback về
            # khung đồng nhất thay vì làm hỏng cả lượt import vì 1 lớp.
            report.warnings.append(
                f"Lớp '{class_names_by_id.get(cls_id, cls_id)}': ngày lệch tiết suy ra từ sheet Khung "
                f"không hợp lệ (đúng 1 tiết lẻ) -- đã bỏ qua, dùng khung đồng nhất."
            )
            repo.set_frame_template(conn, cls_id, morning, afternoon, study_sunday=False)

    # ---- TuanConfig: current seed/parity + history ----
    n_seed_history = 0
    if "TuanConfig" in wb.sheetnames:
        ws_tc = wb["TuanConfig"]
        seed = int(ws_tc.cell(1, 2).value or 0)
        parity = _norm(ws_tc.cell(2, 2).value).upper() or "C"
        repo.set_tuan_config(conn, seed, parity)
        row = 4
        while _norm(ws_tc.cell(row, 1).value):
            week_no = int(ws_tc.cell(row, 1).value or 0)
            wk_seed = int(ws_tc.cell(row, 2).value or 0)
            created = _norm(ws_tc.cell(row, 3).value)
            repo.add_seed_history(conn, week_no, wk_seed, _extract_parity(created))
            n_seed_history += 1
            row += 1

    n_weekly_rows = 0
    if has_weekly:
        w_rep = import_weekly_curriculum_from_excel(conn, wb)
        n_weekly_rows = w_rep.get("records_imported", 0)
        report.warnings.append(
            f"Đã nạp bổ sung định lượng 35 tuần ({n_weekly_rows} bản ghi)."
        )

    # ---- CauHinh & Luat_Mon_Lop (nếu có trong file backup) ----
    if "CauHinh" in wb.sheetnames:
        try:
            cfg_rep = import_scheduling_config_from_excel(conn, wb)
            report.warnings.append(
                f"Đã khôi phục cấu hình xếp lịch ({cfg_rep.get('config_keys_updated', 0)} mục) "
                f"và {cfg_rep.get('rules_count', 0)} luật riêng môn/lớp từ sheet CauHinh."
            )
        except Exception as e:
            report.warnings.append(f"Không thể đọc sheet CauHinh: {e}")

    report.counts = {
        "classes": n_classes,
        "subjects": n_subjects,
        "teachers": len(teacher_ids),
        "unavailability_rows": n_unavailability,
        "tkb_nhap_cells": len(cells),
        "seed_history_rows": n_seed_history,
        "weekly_curriculum_rows": n_weekly_rows,
    }
    return report


def import_scheduling_config_from_excel(conn, source) -> dict:
    """Khôi phục toàn bộ cấu hình SchedulingConfig và luật riêng môn/lớp từ sheet CauHinh & Luat_Mon_Lop.

    Tham số `source` có thể là đường dẫn file (str), bytes/BytesIO, hoặc openpyxl.Workbook.
    """
    import io
    from core.models import SchedulingConfig
    from data.repositories.config import (
        _parse_bool, _parse_id_set, _parse_int, _parse_off_cells,
        _parse_period_tuple, _parse_weekday_tuple,
    )

    if isinstance(source, openpyxl.Workbook):
        wb = source
    elif isinstance(source, (bytes, bytearray)):
        wb = openpyxl.load_workbook(io.BytesIO(source), data_only=True)
    elif hasattr(source, "read"):
        wb = openpyxl.load_workbook(source, data_only=True)
    elif isinstance(source, str):
        wb = openpyxl.load_workbook(source, data_only=True)
    else:
        raise ValueError(f"Nguồn dữ liệu không hợp lệ: {type(source)}")

    if "CauHinh" not in wb.sheetnames:
        return {"imported": False, "message": "Không tìm thấy sheet 'CauHinh' trong file Excel."}

    ws_cfg = wb["CauHinh"]
    current_cfg = repo.get_scheduling_config(conn)
    fields = getattr(SchedulingConfig, "__dataclass_fields__", {})

    bool_fields = {
        "hdtn_period2_afternoon", "heavy_subjects_morning_only", "avoid_teacher_gaps",
        "avoid_teacher_lone_periods", "balance_afternoon_teachers", "avoid_gdtc_consecutive_days",
        "avoid_heavy_afternoon_period3", "avoid_teacher_4_consecutive_morning", "use_cpsat",
        "cpsat_minimize_changes", "gvcn_monday_period2_enabled", "balance_morning_academic_load",
    }
    int_fields = {
        "gdtc_avoid_period", "chao_co_weekday", "chao_co_period", "hdtn_p1_weekday",
        "hdtn_p1_period", "hdtn_p2_weekday", "hdtn_p2_period", "hdtn_p3_weekday",
        "hdtn_p3_period", "hdtn_thematic_weekday", "hdtn_thematic_start_period",
        "max_heavy_consecutive", "max_periods_per_session", "teacher_off_sessions_per_week",
        "heavy_subject_priority_periods", "min_weekly_periods_for_mandatory_morning",
        "max_teacher_periods_per_day", "max_heavy_per_session", "min_weekly_periods_for_lone_penalty",
        "cpsat_time_limit_seconds", "cpsat_workers", "max_academic_per_morning", "min_academic_per_morning",
    }
    tuple_fields = {
        "gdtc_morning_allowed_periods", "gdtc_afternoon_allowed_periods", "strict_morning_weekdays",
        "reserved_off_weekdays_chieu", "mandatory_morning_weekdays",
    }
    id_set_fields = {
        "gvcn_monday_period2_exempt_class_ids", "afternoon_preferred_subject_ids",
        "morning_only_subject_ids", "lone_session_exempt_teacher_ids", "compact_schedule_teacher_ids",
        "non_consecutive_subject_ids", "single_pair_subject_ids",
    }

    parsed_values = {}
    r = 2
    while _norm(ws_cfg.cell(r, 1).value):
        key = _norm(ws_cfg.cell(r, 1).value)
        val = ws_cfg.cell(r, 3).value
        val_str = _norm(val)

        if key in bool_fields:
            parsed_values[key] = _parse_bool(val, getattr(current_cfg, key, False))
        elif key in int_fields:
            if not val_str:
                parsed_values[key] = None
            else:
                parsed_values[key] = _parse_int(val, getattr(current_cfg, key, 0))
        elif key in tuple_fields:
            parsed_values[key] = _parse_weekday_tuple(val_str)
        elif key in id_set_fields:
            parsed_values[key] = _parse_id_set(val_str)
        elif key == "forbidden_off_cells":
            parsed_values[key] = _parse_off_cells(val_str)
        elif key in fields:
            parsed_values[key] = val_str

        r += 1

    merged_kwargs = {f: getattr(current_cfg, f) for f in fields}
    for k, v in parsed_values.items():
        if k in merged_kwargs:
            merged_kwargs[k] = v

    new_cfg = SchedulingConfig(**merged_kwargs)
    repo.set_scheduling_config(conn, new_cfg)

    # Đọc sheet Luat_Mon_Lop
    rules_count = 0
    if "Luat_Mon_Lop" in wb.sheetnames:
        ws_rules = wb["Luat_Mon_Lop"]
        r = 2
        while _norm(ws_rules.cell(r, 3).value):
            s_id_raw = ws_rules.cell(r, 3).value
            c_ids_raw = ws_rules.cell(r, 5).value
            cells_raw = ws_rules.cell(r, 7).value
            try:
                s_id = int(s_id_raw)
                c_ids = [int(x.strip()) for x in str(c_ids_raw).split(",") if x.strip().isdigit()]
                cells = []
                for t in str(cells_raw).split(","):
                    t = t.strip()
                    if len(t) >= 2 and t[:-1].isdigit() and t[-1] in ("S", "C"):
                        cells.append((int(t[:-1]), t[-1]))
                if c_ids and cells:
                    repo.upsert_subject_class_rule(conn, s_id, c_ids, cells)
                    rules_count += 1
            except Exception:
                pass
            r += 1

    return {
        "imported": True,
        "config_keys_updated": len(parsed_values),
        "rules_count": rules_count,
    }
