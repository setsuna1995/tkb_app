"""Export the current DB state (or a specific accepted run) to a downloadable
.xlsx, using export_template.xlsm (a copy of the school's own sample_school.xlsm)
as the base -- so the output keeps the same fonts, header colors, borders and
alternating row banding as the original workbook. Only the TKB_Mon (subject
only, renamed from the template's TKB_Nhap) / TKB (subject + teacher) /
TKB_GV (per-teacher, conflict-highlighted) sheets are rewritten; column
widths/row heights are auto-fit to content instead of kept from the
template. The bundled template file itself is loaded fresh every call and
never mutated. VBA macros are dropped on load (superseded by this app),
keeping the output a plain .xlsx.
"""
from __future__ import annotations

import io
import os
from collections import defaultdict
from copy import copy

import openpyxl
from openpyxl.styles import PatternFill

from core import frame as frame_mod
from core.models import WEEKDAY_NAMES, WEEKDAYS
from data import repository as repo

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "export_template.xlsm")
RED_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

N_GRID_COLS = 3 + len(WEEKDAYS) + 1  # LỚP HỌC, BUỔI, TIẾT THỨ, Thứ 2..7, CHỦ NHẬT


def _capture_row_style(ws, row_idx: int, n_cols: int) -> list:
    return [
        (copy(c.font), copy(c.fill), copy(c.border), copy(c.alignment), c.number_format)
        for c in (ws.cell(row_idx, col) for col in range(1, n_cols + 1))
    ]


def _apply_row_style(ws, row_idx: int, style: list) -> None:
    for col, (font, fill, border, alignment, number_format) in enumerate(style, start=1):
        cell = ws.cell(row_idx, col)
        cell.font = font
        cell.fill = fill
        cell.border = border
        cell.alignment = alignment
        cell.number_format = number_format


def _detect_banding(ws, first_data_row: int, n_cols: int, max_scan: int = 200) -> tuple:
    """(style_a, style_b): the two alternating row styles the template uses for
    class-block banding (style_a for the first class, style_b for the next...).
    Falls back to (style_a, style_a) -- no banding -- if none is found.
    """
    style_a = _capture_row_style(ws, first_data_row, n_cols)
    for r in range(first_data_row + 1, min(first_data_row + max_scan, ws.max_row) + 1):
        fill = ws.cell(r, 1).fill
        if fill and fill.fill_type == "solid" and fill.fgColor.rgb not in (None, "00000000"):
            return style_a, _capture_row_style(ws, r, n_cols)
    return style_a, style_a


def _clear_values(ws, first_data_row: int) -> None:
    for row in ws.iter_rows(min_row=first_data_row, max_row=ws.max_row):
        for cell in row:
            cell.value = None


def _autofit_sheet(ws, min_width: int = 8, max_width: int = 40, col_padding: int = 2,
                    row_height_per_line: float = 15, min_row_height: float = 15) -> None:
    """Xấp xỉ auto-fit độ rộng cột + chiều cao hàng theo nội dung thực tế (openpyxl không có
    autofit thật vì không render text). Cell nhiều dòng ("môn\\nGV: tên") tính theo dòng dài
    nhất cho độ rộng cột, và theo số dòng cho chiều cao hàng.
    """
    col_widths: dict = {}
    row_lines: dict = {}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            lines = str(cell.value).split("\n")
            longest_line = max(len(line) for line in lines)
            col_widths[cell.column_letter] = max(col_widths.get(cell.column_letter, 0), longest_line)
            row_lines[cell.row] = max(row_lines.get(cell.row, 1), len(lines))
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = max(min_width, min(width + col_padding, max_width))
    for row_idx, n_lines in row_lines.items():
        ws.row_dimensions[row_idx].height = max(min_row_height, n_lines * row_height_per_line)


def _fill_result_sheets(ws_raw, ws_tkb, ws_gv, cells, classes, frame_templates, assignments,
                         teacher_names, subject_names, all_class_allowed_cells) -> None:
    """Điền dữ liệu 1 tuần (1 parity) vào bộ 3 sheet TKB_Mon (chỉ tên môn)/TKB (môn+GV)/TKB_GV
    (theo GV, tô đỏ trùng lịch) đã cho."""
    # find teacher double-bookings (same teacher, same weekday+session+period, across classes)
    slot_teacher_classes = defaultdict(list)
    for (cid, wd, sess, per), subj_id in cells.items():
        if subj_id is None:
            continue
        teacher_id = assignments.get((subj_id, cid))
        if teacher_id is not None:
            slot_teacher_classes[(teacher_id, wd, sess, per)].append(cid)
    conflicts = {key for key, cls_list in slot_teacher_classes.items() if len(cls_list) > 1}

    for ws in (ws_raw, ws_tkb, ws_gv):
        white_style, gray_style = _detect_banding(ws, first_data_row=2, n_cols=N_GRID_COLS)
        _clear_values(ws, first_data_row=2)

        row_idx = 2
        for class_idx, cls in enumerate(classes):
            morning, afternoon, _study_sunday, _allow_saturday, _short_wd, _short_m, _short_a = \
                frame_templates.get(cls.class_id, (5, 3, 0, 0, None, None, None))
            
            allowed_cells = all_class_allowed_cells.get(cls.class_id)
            if allowed_cells:
                morning_periods = [p for wd, s, p in allowed_cells if s == "S"]
                afternoon_periods = [p for wd, s, p in allowed_cells if s == "C"]
                morning = max(morning_periods) if morning_periods else 0
                afternoon = max(afternoon_periods) if afternoon_periods else 0
                
            sessions = [("S", p) for p in range(1, morning + 1)] + [("C", p) for p in range(1, afternoon + 1)]
            band_style = white_style if class_idx % 2 == 0 else gray_style
            for session, period in sessions:
                _apply_row_style(ws, row_idx, band_style)
                ws.cell(row_idx, 1).value = cls.name
                ws.cell(row_idx, 2).value = session
                ws.cell(row_idx, 3).value = period
                for i, wd in enumerate(WEEKDAYS):
                    subj_id = cells.get((cls.class_id, wd, session, period))
                    subj_name = subject_names.get(subj_id, "") if subj_id else ""
                    teacher_id = assignments.get((subj_id, cls.class_id)) if subj_id else None
                    teacher_name = teacher_names.get(teacher_id, "") if teacher_id else ""
                    col = 4 + i
                    if ws is ws_gv:
                        ws.cell(row_idx, col).value = teacher_name
                        if teacher_id is not None and (teacher_id, wd, session, period) in conflicts:
                            ws.cell(row_idx, col).fill = RED_FILL
                    elif ws is ws_tkb:
                        ws.cell(row_idx, col).value = (
                            f"{subj_name}\nGV: {teacher_name or '(chưa PC GV)'}" if subj_name else ""
                        )
                    else:  # ws_raw
                        ws.cell(row_idx, col).value = subj_name
                row_idx += 1


def export_xlsx(conn, run_id=None, cells=None, week_no=None) -> bytes:
    classes = repo.list_classes(conn)
    subjects = repo.list_subjects(conn)
    teacher_names = {t.teacher_id: t.name for t in repo.list_teachers(conn)}
    subject_names = {s.subject_id: s.name for s in subjects}
    assignments = repo.get_assignments(conn)
    frame_templates = repo.get_all_frame_templates(conn)
    all_class_allowed_cells = repo.get_all_class_allowed_cells(conn)

    if cells is None:
        if week_no is not None:
            w_run = repo.get_latest_run_by_week(conn, week_no)
            if w_run is not None:
                cells = repo.get_tkb_result(conn, w_run["run_id"])
            else:
                cells = repo.get_tkb_nhap(conn)
        elif run_id is not None:
            cells = repo.get_tkb_result(conn, run_id)
        else:
            cells = repo.get_tkb_nhap(conn)

    wb = openpyxl.load_workbook(TEMPLATE_PATH)  # drop VBA -- superseded by this app
    ws_raw = wb["TKB_Nhap"]
    ws_raw.title = "TKB_Mon"
    # sheet môn-only vốn có dropdown chọn môn (cột D:J) trỏ tới defined-name DS_Mon =
    # PhanCong!$A$3:$A$18 -- PhanCong đã bị xoá khỏi file xuất (stale, không refresh từ DB)
    # nên link này hỏng (#REF!/cảnh báo "broken link" khi mở Excel thật). Gỡ bỏ hẳn.
    ws_raw.data_validations.dataValidation.clear()
    if "DS_Mon" in wb.defined_names:
        del wb.defined_names["DS_Mon"]
    ws_tkb = wb["TKB"]
    ws_gv = wb["TKB_GV"]

    # the template also carries PhanCong/SoTiet/DinhMuc_GV/KiemTra/... -- những sheet đó sẽ
    # stale (không refresh từ DB) hoặc không còn dùng, nên xoá hết, chỉ giữ 3 sheet kết quả.
    keep = {"TKB_Mon", "TKB", "TKB_GV"}
    for name in list(wb.sheetnames):
        if name not in keep:
            del wb[name]

    _fill_result_sheets(ws_raw, ws_tkb, ws_gv, cells, classes, frame_templates, assignments,
                         teacher_names, subject_names, all_class_allowed_cells)
    for ws in (ws_raw, ws_tkb, ws_gv):
        _autofit_sheet(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


PARITY_SUFFIX = {"C": "Chan", "L": "Le"}
PARITY_LABEL = {"C": "Chẵn", "L": "Lẻ"}


def export_xlsx_both_parities(conn) -> tuple:
    """Gộp lần chấp nhận gần nhất của MỖI tuần (Chẵn + Lẻ) vào 1 workbook 6 sheet
    (3 sheet hiện có, hậu tố _Chan/_Le). tkb_nhap không dùng được ở đây vì nó chỉ lưu
    1 bản duy nhất, bị ghi đè mỗi lần chấp nhận bất kể tuần nào -- nguồn dữ liệu đúng
    cho từng tuần là run_log/tkb_result (không bao giờ bị xoá, có cột parity).

    Trả về (bytes, warnings) -- warnings liệt kê tuần nào bị bỏ qua vì chưa từng có
    lần xếp nào được chấp nhận. Raise ValueError nếu CẢ 2 tuần đều chưa có gì để xuất.
    """
    classes = repo.list_classes(conn)
    subjects = repo.list_subjects(conn)
    teacher_names = {t.teacher_id: t.name for t in repo.list_teachers(conn)}
    subject_names = {s.subject_id: s.name for s in subjects}
    assignments = repo.get_assignments(conn)
    frame_templates = repo.get_all_frame_templates(conn)
    all_class_allowed_cells = repo.get_all_class_allowed_cells(conn)

    warnings = []
    parity_cells = {}
    for parity in ("C", "L"):
        run = repo.get_latest_run_by_parity(conn, parity)
        if run is None:
            warnings.append(f"Tuần {PARITY_LABEL[parity]}: chưa có lần xếp nào được chấp nhận -- bỏ qua.")
            continue
        parity_cells[parity] = repo.get_tkb_result(conn, run["run_id"])

    if not parity_cells:
        raise ValueError(
            "Chưa có lần xếp nào được chấp nhận cho tuần Chẵn hoặc tuần Lẻ -- không có gì để xuất."
        )

    wb = openpyxl.load_workbook(TEMPLATE_PATH)
    base_sheet_map = {"TKB_Mon": "TKB_Nhap", "TKB": "TKB", "TKB_GV": "TKB_GV"}
    base_sheets = {out_name: wb[tmpl_name] for out_name, tmpl_name in base_sheet_map.items()}
    for name in list(wb.sheetnames):
        if name not in base_sheet_map.values():
            del wb[name]

    # Gỡ link hỏng trên sheet gốc TRƯỚC khi copy, để cả 2 bản copy (Chẵn + Lẻ) đều sạch --
    # xem chú thích tương tự trong export_xlsx().
    base_sheets["TKB_Mon"].data_validations.dataValidation.clear()
    if "DS_Mon" in wb.defined_names:
        del wb.defined_names["DS_Mon"]

    for parity, cells in parity_cells.items():
        suffix = PARITY_SUFFIX[parity]
        copies = {}
        for out_name, base_ws in base_sheets.items():
            new_ws = wb.copy_worksheet(base_ws)
            new_ws.title = f"{out_name}_{suffix}"
            new_ws.freeze_panes = base_ws.freeze_panes  # copy_worksheet không giữ freeze_panes
            copies[out_name] = new_ws
        _fill_result_sheets(copies["TKB_Mon"], copies["TKB"], copies["TKB_GV"], cells, classes,
                             frame_templates, assignments, teacher_names, subject_names, all_class_allowed_cells)
        for ws in copies.values():
            _autofit_sheet(ws)

    for base_ws in base_sheets.values():
        wb.remove(base_ws)  # chỉ dùng làm khuôn để copy_worksheet, không cần trong output; xoá
        # theo object (không theo tên) vì tên output ("TKB_Mon") đã lệch tên sheet gốc ("TKB_Nhap")

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue(), warnings


def export_full_backup_xlsx(conn) -> bytes:
    """Xuất TOÀN BỘ dữ liệu setup (không chỉ lịch) ra 1 file .xlsm mà import_xlsm() đọc lại
    được nguyên vẹn. Khác với export_xlsx()/export_xlsx_both_parities() (chỉ xuất lưới thời
    khóa biểu để in/chia sẻ) -- hàm này dùng cho nút "sao lưu", vì mất DB (vd host free-tier
    restart) mà chỉ có lưới TKB thì không khôi phục lại được lớp/môn/GV/phân công/định mức/
    GV bận/khung tiết/lịch sử tuần, phải nhập tay lại từ đầu.

    Ghi đúng 7 sheet, đúng định dạng io_excel/importer.py::import_xlsm() mong đợi: PhanCong,
    SoTiet, DinhMuc_GV, GV_Ban, Khung, TKB_Nhap, TuanConfig.
    """
    classes = sorted(repo.list_classes(conn), key=lambda c: c.sort_order)
    subjects = sorted(repo.list_subjects(conn), key=lambda s: s.sort_order)
    teachers = repo.list_teachers(conn)
    teacher_names = {t.teacher_id: t.name for t in teachers}
    subject_names = {s.subject_id: s.name for s in subjects}

    assignments = repo.get_assignments(conn)
    periods_per_week = repo.get_periods_per_week(conn)
    role_reduction = repo.get_role_reduction(conn)
    frame_templates = repo.get_all_frame_templates(conn)
    unavailability = repo.list_unavailability(conn)
    tkb_nhap = repo.get_tkb_nhap(conn)
    seed, parity = repo.get_tuan_config(conn)
    seed_history = repo.list_seed_history(conn)
    base_cap = repo.get_base_cap(conn)
    min_floor = repo.get_min_floor(conn)
    config = repo.get_scheduling_config(conn)

    n_classes = len(classes)
    n_subjects = len(subjects)

    wb = openpyxl.load_workbook(TEMPLATE_PATH)
    keep = {"PhanCong", "SoTiet", "DinhMuc_GV", "GV_Ban", "Khung", "TKB_Nhap", "TuanConfig"}
    for name in list(wb.sheetnames):
        if name not in keep:
            del wb[name]

    # ---- PhanCong ----
    ws_pc = wb["PhanCong"]
    _clear_values(ws_pc, first_data_row=2)
    code_col = 2 + n_classes + 1  # để trống 1 cột đệm ở 2+n_classes, khớp quy ước template
    for i, cls in enumerate(classes):
        ws_pc.cell(2, 2 + i).value = cls.name
    ws_pc.cell(2, code_col).value = "MÃ VAI TRÒ"
    for r, subj in enumerate(subjects):
        row = 3 + r
        ws_pc.cell(row, 1).value = subj.name
        ws_pc.cell(row, code_col).value = subj.role_code
        for i, cls in enumerate(classes):
            teacher_id = assignments.get((subj.subject_id, cls.class_id))
            ws_pc.cell(row, 2 + i).value = teacher_names.get(teacher_id, "")

    # ---- SoTiet ----
    ws_st = wb["SoTiet"]
    _clear_values(ws_st, first_data_row=2)
    odd_start_col = 2 + n_classes + 1
    for i, cls in enumerate(classes):
        ws_st.cell(2, 2 + i).value = f"{cls.name} C"
        ws_st.cell(2, odd_start_col + i).value = f"{cls.name} L"
    for r, subj in enumerate(subjects):
        row = 3 + r
        ws_st.cell(row, 1).value = subj.name
        for i, cls in enumerate(classes):
            ws_st.cell(row, 2 + i).value = periods_per_week.get((subj.subject_id, cls.class_id, "C"), 0)
            ws_st.cell(row, odd_start_col + i).value = periods_per_week.get((subj.subject_id, cls.class_id, "L"), 0)

    # ---- DinhMuc_GV ----
    ws_dm = wb["DinhMuc_GV"]
    _clear_values(ws_dm, first_data_row=2)  # row1 (tiêu đề + Chuẩn/Chức vụ) giữ nguyên, ghi đè bên dưới
    ws_dm.cell(1, 8).value = "Chuẩn:"
    ws_dm.cell(1, 9).value = base_cap
    ws_dm.cell(1, 11).value = "Chức vụ"
    ws_dm.cell(1, 12).value = "Giảm"
    # Sàn tối thiểu: quy ước RIÊNG của app (không có trong định dạng VBA gốc) -- đặt ở ô N1/O1,
    # rõ ràng chưa dùng cho mục đích nào khác trong sheet này.
    ws_dm.cell(1, 14).value = "Sàn tối thiểu:"
    ws_dm.cell(1, 15).value = min_floor
    ws_dm.cell(2, 1).value = "Tên GV"
    ws_dm.cell(2, 2).value = "Chức vụ"
    ws_dm.cell(2, 8).value = "Đi T2 (1/0)"
    ws_dm.cell(2, 9).value = "GVCN (1/0)"
    for r, t in enumerate(teachers):
        row = 3 + r
        ws_dm.cell(row, 1).value = t.name
        ws_dm.cell(row, 2).value = t.role
        # cột C-G (Giảm/Trần/Tải Chẵn/Tải Lẻ/Vượt) là công thức Excel, import_xlsm() không đọc
        # lại -- để trống thay vì cố tính lại, tránh hiện số liệu sai/cũ.
        ws_dm.cell(row, 8).value = int(t.must_monday)
        ws_dm.cell(row, 9).value = int(t.is_gvcn)
    for r, (role_name, reduction) in enumerate(role_reduction.items()):
        row = 2 + r
        ws_dm.cell(row, 11).value = role_name
        ws_dm.cell(row, 12).value = reduction

    # ---- GV_Ban ----
    ws_gb = wb["GV_Ban"]
    _clear_values(ws_gb, first_data_row=2)
    ws_gb.cell(2, 1).value = "Giáo viên"
    ws_gb.cell(2, 2).value = "Thứ"
    ws_gb.cell(2, 3).value = "Buổi"
    ws_gb.cell(2, 4).value = "Tiết"
    for r, row_data in enumerate(unavailability):
        row = 3 + r
        ws_gb.cell(row, 1).value = teacher_names.get(row_data["teacher_id"], "")
        ws_gb.cell(row, 2).value = row_data["weekday"]
        ws_gb.cell(row, 3).value = row_data["session"]
        ws_gb.cell(row, 4).value = row_data["period"]

    # ---- Khung + TKB_Nhap (row-aligned, importer đọc Khung theo đúng row của TKB_Nhap) ----
    ws_khung = wb["Khung"]
    ws_nh = wb["TKB_Nhap"]
    _clear_values(ws_khung, first_data_row=2)
    _clear_values(ws_nh, first_data_row=2)
    ws_nh.cell(1, 1).value = "LỚP HỌC"
    ws_nh.cell(1, 2).value = "BUỔI"
    ws_nh.cell(1, 3).value = "TIẾT THỨ"
    for i, wd in enumerate(WEEKDAYS):
        ws_nh.cell(1, 4 + i).value = WEEKDAY_NAMES[wd]
    ws_nh.cell(1, 4 + len(WEEKDAYS)).value = WEEKDAY_NAMES[8]

    row_idx = 2
    for cls in classes:
        morning, afternoon, study_sunday, allow_saturday, short_wd, short_m, short_a = \
            frame_templates.get(cls.class_id, (5, 3, 0, 0, None, None, None))
        # active_cells() đã tự xử lý đúng ngày lệch tiết -- tái dùng thẳng, không tự suy luận lại.
        active_set = set(frame_mod.active_cells(
            morning, afternoon, bool(study_sunday), bool(allow_saturday), short_wd, short_m, short_a,
            reserved_off_weekdays_chieu=config.reserved_off_weekdays_chieu,
        ))
        sessions = [("S", p) for p in range(1, morning + 1)] + [("C", p) for p in range(1, afternoon + 1)]
        for session, period in sessions:
            ws_nh.cell(row_idx, 1).value = cls.name
            ws_nh.cell(row_idx, 2).value = session
            ws_nh.cell(row_idx, 3).value = period
            for i, wd in enumerate(WEEKDAYS):
                col = 4 + i
                subj_id = tkb_nhap.get((cls.class_id, wd, session, period))
                ws_nh.cell(row_idx, col).value = subject_names.get(subj_id, "") if subj_id else ""
                if (wd, session, period) in active_set:
                    ws_khung.cell(row_idx, col).value = "x"
            row_idx += 1

    # Sửa lại defined-name DS_Mon (dropdown chọn môn trên TKB_Nhap) theo đúng số môn thực tế --
    # range cũ trong template (PhanCong!$A$3:$A$18) giả định đúng 16 môn mẫu của trường mẫu.
    if "DS_Mon" in wb.defined_names:
        wb.defined_names["DS_Mon"].value = f"PhanCong!$A$3:$A${2 + n_subjects}"

    # ---- TuanConfig ----
    ws_tc = wb["TuanConfig"]
    _clear_values(ws_tc, first_data_row=4)
    ws_tc.cell(1, 2).value = seed
    ws_tc.cell(2, 2).value = parity
    for r, h in enumerate(seed_history):
        row = 4 + r
        ws_tc.cell(row, 1).value = h["week_no"]
        ws_tc.cell(row, 2).value = h["seed"]
        # _extract_parity() bên importer chỉ dò chuỗi con "[C]"/"[L]" trong text này, không có
        # cột parity riêng -- phải tự chèn tag khi ghi để đọc lại đúng.
        ws_tc.cell(row, 3).value = f"{h['created_at']} [{h['parity']}]"

    # ---- CauHinh & Luat_Mon_Lop ----
    ws_cfg, ws_rules = export_scheduling_config_sheet(wb, conn)

    for ws in (ws_pc, ws_st, ws_dm, ws_gb, ws_khung, ws_nh, ws_tc, ws_cfg, ws_rules):
        _autofit_sheet(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def export_scheduling_config_sheet(wb, conn) -> tuple:
    """Ghi sheet CauHinh và Luat_Mon_Lop vào workbook để sao lưu toàn bộ thiết lập ràng buộc."""
    classes = repo.list_classes(conn)
    subjects = repo.list_subjects(conn)
    teachers = repo.list_teachers(conn)
    teacher_names = {t.teacher_id: t.name for t in teachers}
    subject_names = {s.subject_id: s.name for s in subjects}
    class_names = {c.class_id: c.name for c in classes}
    config = repo.get_scheduling_config(conn)

    ws_cfg = wb.create_sheet("CauHinh")
    headers = ["Mã Cấu Hình", "Tiêu Chuẩn / Ràng Buộc", "Giá Trị", "Diễn Giải / Tên Chi Tiết"]
    for col_idx, h in enumerate(headers, 1):
        cell = ws_cfg.cell(1, col_idx, h)
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill("solid", fgColor="1F497D")

    def _subjs(ids):
        return ", ".join(subject_names[i] for i in sorted(ids) if i in subject_names)

    def _teachers(ids):
        return ", ".join(teacher_names[i] for i in sorted(ids) if i in teacher_names)

    def _classes(ids):
        return ", ".join(class_names[i] for i in sorted(ids) if i in class_names)

    def _cells(cells):
        return ", ".join(f"{w}{s}" for w, s in sorted(cells))

    rows = [
        # Khung & HĐTN
        ("hdtn_mode", "Mô hình tổ chức HĐTN", config.hdtn_mode, "separate: phân bổ 3 tiết | thematic: dồn 3 tiết chuyên đề"),
        ("chao_co_weekday", "Thứ Chào cờ đầu tuần", config.chao_co_weekday, f"Thứ {config.chao_co_weekday}"),
        ("chao_co_session", "Buổi Chào cờ đầu tuần", config.chao_co_session, "Sáng" if config.chao_co_session == "S" else "Chiều"),
        ("chao_co_period", "Tiết Chào cờ đầu tuần", config.chao_co_period, f"Tiết {config.chao_co_period}"),
        ("hdtn_p1_weekday", "HĐTN Tiết 1 (Chào cờ) - Thứ", config.hdtn_p1_weekday, f"Thứ {config.hdtn_p1_weekday}"),
        ("hdtn_p1_session", "HĐTN Tiết 1 (Chào cờ) - Buổi", config.hdtn_p1_session, "Sáng" if config.hdtn_p1_session == "S" else "Chiều"),
        ("hdtn_p1_period", "HĐTN Tiết 1 (Chào cờ) - Tiết", config.hdtn_p1_period, f"Tiết {config.hdtn_p1_period}"),
        ("hdtn_p2_mode", "HĐTN Tiết 2 (Chủ đề) - Chế độ", "fixed" if config.hdtn_p2_weekday is not None else "auto", "fixed: cố định | auto: tự do linh hoạt"),
        ("hdtn_p2_weekday", "HĐTN Tiết 2 (Chủ đề) - Thứ", config.hdtn_p2_weekday or "", f"Thứ {config.hdtn_p2_weekday}" if config.hdtn_p2_weekday else "Tự do"),
        ("hdtn_p2_session", "HĐTN Tiết 2 (Chủ đề) - Buổi", config.hdtn_p2_session or "S", "Sáng" if config.hdtn_p2_session == "S" else "Chiều"),
        ("hdtn_p2_period", "HĐTN Tiết 2 (Chủ đề) - Tiết", config.hdtn_p2_period or "", f"Tiết {config.hdtn_p2_period}" if config.hdtn_p2_period else "Tự do"),
        ("hdtn_period2_afternoon", "HĐTN Tiết 2 ưu tiên xếp chiều", int(config.hdtn_period2_afternoon), "1: Có ưu tiên chiều | 0: Không"),
        ("hdtn_p3_mode", "HĐTN Tiết 3 (SHL) - Chế độ", "fixed" if config.hdtn_p3_weekday is not None else "auto", "fixed: cố định | auto: tự động tiết cuối tuần"),
        ("hdtn_p3_weekday", "HĐTN Tiết 3 (SHL) - Thứ", config.hdtn_p3_weekday or "", f"Thứ {config.hdtn_p3_weekday}" if config.hdtn_p3_weekday else "Tiết cuối tuần"),
        ("hdtn_p3_session", "HĐTN Tiết 3 (SHL) - Buổi", config.hdtn_p3_session or "S", "Sáng" if config.hdtn_p3_session == "S" else "Chiều"),
        ("hdtn_p3_period", "HĐTN Tiết 3 (SHL) - Tiết", config.hdtn_p3_period or "", f"Tiết {config.hdtn_p3_period}" if config.hdtn_p3_period else "Tiết cuối buổi"),
        ("hdtn_thematic_mode", "HĐTN Chuyên đề dồn - Chế độ", config.hdtn_thematic_mode, "auto: tự động tìm dải | fixed: cố định"),
        ("hdtn_thematic_weekday", "HĐTN Chuyên đề dồn - Thứ", config.hdtn_thematic_weekday or "", f"Thứ {config.hdtn_thematic_weekday}" if config.hdtn_thematic_weekday else ""),
        ("hdtn_thematic_session", "HĐTN Chuyên đề dồn - Buổi", config.hdtn_thematic_session or "S", "Sáng" if config.hdtn_thematic_session == "S" else "Chiều"),
        ("hdtn_thematic_start_period", "HĐTN Chuyên đề dồn - Tiết bắt đầu", config.hdtn_thematic_start_period or "", f"Tiết {config.hdtn_thematic_start_period}" if config.hdtn_thematic_start_period else ""),
        ("gvcn_monday_period2_enabled", "Ưu tiên GVCN dạy tiết 2 Thứ 2", int(config.gvcn_monday_period2_enabled), "1: Bật | 0: Tắt"),
        ("gvcn_monday_period2_exempt_class_ids", "Lớp miễn trừ GVCN tiết 2 Thứ 2", ",".join(str(cid) for cid in sorted(config.gvcn_monday_period2_exempt_class_ids)), _classes(config.gvcn_monday_period2_exempt_class_ids)),
        # GDTC
        ("gdtc_avoid_period", "Tiết GDTC tránh xếp", config.gdtc_avoid_period, f"Tiết {config.gdtc_avoid_period}"),
        ("gdtc_morning_allowed_periods", "GDTC: Các tiết sáng được phép", ",".join(map(str, config.gdtc_morning_allowed_periods)), "Tiết " + ", ".join(map(str, config.gdtc_morning_allowed_periods))),
        ("gdtc_afternoon_allowed_periods", "GDTC: Các tiết chiều được phép", ",".join(map(str, config.gdtc_afternoon_allowed_periods)), "Tiết " + ", ".join(map(str, config.gdtc_afternoon_allowed_periods))),
        # Hiện diện & Nghỉ GV
        ("strict_morning_weekdays", "Sáng MỌI GV bắt buộc có tiết dạy", ",".join(map(str, config.strict_morning_weekdays)), ", ".join(f"Thứ {w}" for w in config.strict_morning_weekdays)),
        ("mandatory_morning_weekdays", "Sáng bắt buộc GV có mặt (theo tải)", ",".join(map(str, config.mandatory_morning_weekdays)), ", ".join(f"Thứ {w}" for w in config.mandatory_morning_weekdays)),
        ("min_weekly_periods_for_mandatory_morning", "Ngưỡng tải xét sáng có mặt", config.min_weekly_periods_for_mandatory_morning, f">= {config.min_weekly_periods_for_mandatory_morning} tiết/tuần"),
        ("teacher_off_sessions_per_week", "Số buổi nghỉ của mỗi GV trong tuần", config.teacher_off_sessions_per_week, f"{config.teacher_off_sessions_per_week} buổi"),
        ("teacher_off_sessions_mode", "Mức độ áp dụng buổi nghỉ", config.teacher_off_sessions_mode, "none: Không áp dụng | soft: Ưu tiên cao | hard: Bắt buộc"),
        ("forbidden_off_cells", "Buổi cấm chọn làm buổi nghỉ", _cells(config.forbidden_off_cells), ", ".join(f"Thứ {w} {'Sáng' if s == 'S' else 'Chiều'}" for w, s in sorted(config.forbidden_off_cells))),
        ("reserved_off_weekdays_chieu", "Thứ có buổi chiều luôn trống", ",".join(map(str, config.reserved_off_weekdays_chieu)), ", ".join(f"Chiều Thứ {w}" for w in config.reserved_off_weekdays_chieu)),
        ("lone_session_exempt_teacher_ids", "GV miễn trừ luật tránh 1 tiết/buổi", ",".join(str(tid) for tid in sorted(config.lone_session_exempt_teacher_ids)), _teachers(config.lone_session_exempt_teacher_ids)),
        ("compact_schedule_teacher_ids", "GV ưu tiên gom tiết nghỉ nhiều buổi", ",".join(str(tid) for tid in sorted(config.compact_schedule_teacher_ids)), _teachers(config.compact_schedule_teacher_ids)),
        # Phân luồng môn
        ("heavy_subjects_morning_only", "Môn Nặng bắt buộc xếp buổi sáng (cấm chiều)", int(config.heavy_subjects_morning_only), "1: Bật | 0: Tắt"),
        ("morning_only_subject_ids", "Môn bắt buộc xếp sáng (cấm chiều) cụ thể", ",".join(str(sid) for sid in sorted(config.morning_only_subject_ids)), _subjs(config.morning_only_subject_ids)),
        ("afternoon_preferred_subject_ids", "Môn ưu tiên xếp buổi chiều", ",".join(str(sid) for sid in sorted(config.afternoon_preferred_subject_ids)), _subjs(config.afternoon_preferred_subject_ids)),
        ("non_consecutive_subject_ids", "Môn không xếp liền ngày (cách nhật)", ",".join(str(sid) for sid in sorted(config.non_consecutive_subject_ids)), _subjs(config.non_consecutive_subject_ids)),
        ("single_pair_subject_ids", "Môn xếp 1 cặp liền tiết", ",".join(str(sid) for sid in sorted(config.single_pair_subject_ids)), _subjs(config.single_pair_subject_ids)),
        # Định mức & Tiêu chuẩn sư phạm
        ("max_periods_per_session", "Mỗi GV: tối đa tiết/buổi", config.max_periods_per_session, f"{config.max_periods_per_session} tiết"),
        ("max_teacher_periods_per_day", "Mỗi GV: tối đa tiết/ngày", config.max_teacher_periods_per_day, f"{config.max_teacher_periods_per_day} tiết"),
        ("max_heavy_consecutive", "Môn nặng: tối đa tiết liên tiếp trong buổi", config.max_heavy_consecutive, f"{config.max_heavy_consecutive} tiết"),
        ("max_heavy_per_session", "Tối đa tiết môn nặng/buổi cho 1 lớp", config.max_heavy_per_session, f"{config.max_heavy_per_session} tiết"),
        ("heavy_subject_priority_periods", "Môn nặng ưu tiên N tiết đầu sáng", config.heavy_subject_priority_periods, f"{config.heavy_subject_priority_periods} tiết"),
        ("avoid_teacher_gaps", "Tránh tiết trống / lủng của GV trong buổi", int(config.avoid_teacher_gaps), "1: Bật | 0: Tắt"),
        ("avoid_teacher_lone_periods", "Tránh GV đi dạy chỉ 1 tiết/ngày", int(config.avoid_teacher_lone_periods), "1: Bật | 0: Tắt"),
        ("balance_afternoon_teachers", "Cân đối tiết buổi chiều cho GV", int(config.balance_afternoon_teachers), "1: Bật | 0: Tắt"),
        ("avoid_gdtc_consecutive_days", "GDTC không xếp 2 ngày liên tiếp", int(config.avoid_gdtc_consecutive_days), "1: Bật | 0: Tắt"),
        ("avoid_heavy_afternoon_period3", "Hạn chế môn nặng tiết 3 chiều", int(config.avoid_heavy_afternoon_period3), "1: Bật | 0: Tắt"),
        ("avoid_teacher_4_consecutive_morning", "Hạn chế GV dạy 4 tiết sáng liên tục", int(config.avoid_teacher_4_consecutive_morning), "1: Bật | 0: Tắt"),
        ("min_weekly_periods_for_lone_penalty", "Ngưỡng tiết/tuần phạt lẻ tiết GV", config.min_weekly_periods_for_lone_penalty, f"{config.min_weekly_periods_for_lone_penalty} tiết"),
        # CP-SAT Solver
        ("cpsat_time_limit_seconds", "Giới hạn thời gian giải CP-SAT (giây)", config.cpsat_time_limit_seconds, f"{config.cpsat_time_limit_seconds}s"),
        ("cpsat_workers", "Số luồng CPU (workers) CP-SAT", config.cpsat_workers, "0: tự động" if config.cpsat_workers == 0 else f"{config.cpsat_workers} workers"),
        ("cpsat_minimize_changes", "Ưu tiên giữ nguyên TKB cũ", int(config.cpsat_minimize_changes), "1: Bật | 0: Tắt"),
    ]

    for r_idx, (key, desc, val, detail) in enumerate(rows, 2):
        ws_cfg.cell(r_idx, 1, key)
        ws_cfg.cell(r_idx, 2, desc)
        ws_cfg.cell(r_idx, 3, str(val) if val is not None else "")
        ws_cfg.cell(r_idx, 4, str(detail) if detail is not None else "")

    # Luat_Mon_Lop
    existing_rules = repo.list_subject_class_rules(conn)
    ws_rules = wb.create_sheet("Luat_Mon_Lop")
    rule_headers = ["ID Luật", "Tên Môn Học", "Môn ID", "Danh Sách Lớp", "Lớp IDs", "Thứ - Buổi Được Xếp", "Các Ô"]
    for col_idx, h in enumerate(rule_headers, 1):
        cell = ws_rules.cell(1, col_idx, h)
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill("solid", fgColor="1F497D")

    for r_idx, rule in enumerate(existing_rules, 2):
        s_id = rule["subject_id"]
        s_name = subject_names.get(s_id, str(s_id))
        c_names = ", ".join(class_names.get(cid, str(cid)) for cid in rule["class_ids"])
        c_ids_str = ",".join(str(cid) for cid in rule["class_ids"])
        cells_desc = ", ".join(f"Thứ {wd} {'Sáng' if s == 'S' else 'Chiều'}" for wd, s in sorted(rule["cells"]))
        cells_raw = ",".join(f"{wd}{s}" for wd, s in sorted(rule["cells"]))
        ws_rules.cell(r_idx, 1, rule["rule_id"])
        ws_rules.cell(r_idx, 2, s_name)
        ws_rules.cell(r_idx, 3, s_id)
        ws_rules.cell(r_idx, 4, c_names)
        ws_rules.cell(r_idx, 5, c_ids_str)
        ws_rules.cell(r_idx, 6, cells_desc)
        ws_rules.cell(r_idx, 7, cells_raw)

    return ws_cfg, ws_rules


def export_config_xlsx(conn) -> bytes:
    """Xuất riêng toàn bộ cấu hình xếp lịch và ràng buộc ra 1 file Excel độc lập."""
    wb = openpyxl.Workbook()
    # Xoá sheet mặc định
    default_sheet = wb.active
    ws_cfg, ws_rules = export_scheduling_config_sheet(wb, conn)
    if default_sheet and default_sheet != ws_cfg and default_sheet != ws_rules:
        wb.remove(default_sheet)
    for ws in (ws_cfg, ws_rules):
        _autofit_sheet(ws)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

