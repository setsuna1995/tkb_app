"""Export the current DB state (or a specific accepted run) to a downloadable
.xlsx, using export_template.xlsm (a copy of the school's own TKB_9lop_moi.xlsm)
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

from core.models import WEEKDAYS
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
                         teacher_names, subject_names) -> None:
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
            # morning/afternoon ở đây là số tiết CHUẨN (chưa trừ ngày lệch) -- dùng để sinh đủ
            # hàng cho mọi tiết có thể xuất hiện trong tuần, kể cả những ngày không phải ngày lệch.
            morning, afternoon, _study_sunday, _allow_saturday, _short_wd, _short_m, _short_a = \
                frame_templates.get(cls.class_id, (5, 3, 0, 0, None, None, None))
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


def export_xlsx(conn, run_id=None) -> bytes:
    classes = repo.list_classes(conn)
    subjects = repo.list_subjects(conn)
    teacher_names = {t.teacher_id: t.name for t in repo.list_teachers(conn)}
    subject_names = {s.subject_id: s.name for s in subjects}
    assignments = repo.get_assignments(conn)
    frame_templates = repo.get_all_frame_templates(conn)

    if run_id is not None:
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
                         teacher_names, subject_names)
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
                             frame_templates, assignments, teacher_names, subject_names)
        for ws in copies.values():
            _autofit_sheet(ws)

    for base_ws in base_sheets.values():
        wb.remove(base_ws)  # chỉ dùng làm khuôn để copy_worksheet, không cần trong output; xoá
        # theo object (không theo tên) vì tên output ("TKB_Mon") đã lệch tên sheet gốc ("TKB_Nhap")

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue(), warnings
