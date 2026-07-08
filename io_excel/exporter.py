"""Export the current DB state (or a specific accepted run) to a downloadable
.xlsx, using export_template.xlsm (a copy of the school's own TKB_9lop_moi.xlsm)
as the base -- so the output keeps the exact same fonts, header colors,
borders, alternating row banding, column widths and freeze panes. Only the
TKB_Nhap / TKB / TKB_GV / KiemTra data cells are rewritten; the bundled
template file itself is loaded fresh every call and never mutated. VBA macros
are dropped on load (superseded by this app), keeping the output a plain
.xlsx with the template's exact visual style.
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


def export_xlsx(conn, run_id=None) -> bytes:
    classes = repo.list_classes(conn)
    subjects = repo.list_subjects(conn)
    teacher_names = {t.teacher_id: t.name for t in repo.list_teachers(conn)}
    subject_names = {s.subject_id: s.name for s in subjects}
    assignments = repo.get_assignments(conn)
    frame_templates = repo.get_all_frame_templates(conn)
    periods_per_week = repo.get_periods_per_week(conn)

    if run_id is not None:
        cells = repo.get_tkb_result(conn, run_id)
        run_row = conn.execute("SELECT parity FROM run_log WHERE run_id=?", (run_id,)).fetchone()
        parity = run_row["parity"] if run_row else repo.get_tuan_config(conn)[1]
    else:
        cells = repo.get_tkb_nhap(conn)
        parity = repo.get_tuan_config(conn)[1]

    # find teacher double-bookings (same teacher, same weekday+session+period, across classes)
    slot_teacher_classes = defaultdict(list)
    for (cid, wd, sess, per), subj_id in cells.items():
        if subj_id is None:
            continue
        teacher_id = assignments.get((subj_id, cid))
        if teacher_id is not None:
            slot_teacher_classes[(teacher_id, wd, sess, per)].append(cid)
    conflicts = {key for key, cls_list in slot_teacher_classes.items() if len(cls_list) > 1}

    wb = openpyxl.load_workbook(TEMPLATE_PATH)  # drop VBA -- superseded by this app
    ws_raw = wb["TKB_Nhap"]
    ws_tkb = wb["TKB"]
    ws_gv = wb["TKB_GV"]
    ws_check = wb["KiemTra"]

    # the template also carries PhanCong/SoTiet/DinhMuc_GV/... -- those would be
    # stale (not refreshed from the current DB), so drop everything except the
    # 4 result sheets whose data we actually rewrite below.
    keep = {"TKB_Nhap", "TKB", "TKB_GV", "KiemTra"}
    for name in list(wb.sheetnames):
        if name not in keep:
            del wb[name]

    for ws in (ws_raw, ws_tkb, ws_gv):
        white_style, gray_style = _detect_banding(ws, first_data_row=2, n_cols=N_GRID_COLS)
        _clear_values(ws, first_data_row=2)

        row_idx = 2
        for class_idx, cls in enumerate(classes):
            morning, afternoon, _study_sunday, _allow_saturday = frame_templates.get(cls.class_id, (5, 3, 0, 0))
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

    # KiemTra: title(row1) + blank(row2) + header(row3, already correct) + data(row4+)
    white_style, _gray_style = _detect_banding(ws_check, first_data_row=4, n_cols=1 + len(classes))
    _clear_values(ws_check, first_data_row=4)

    actual_counts = defaultdict(int)
    for (cid, _wd, _sess, _per), subj_id in cells.items():
        if subj_id is not None:
            actual_counts[(subj_id, cid)] += 1

    row_idx = 4
    for subj in subjects:
        _apply_row_style(ws_check, row_idx, white_style)
        ws_check.cell(row_idx, 1).value = subj.name
        for i, cls in enumerate(classes):
            quota = periods_per_week.get((subj.subject_id, cls.class_id, parity), 0)
            diff = actual_counts.get((subj.subject_id, cls.class_id), 0) - quota
            cell = ws_check.cell(row_idx, 2 + i)
            cell.value = diff
            if diff != 0:
                cell.fill = RED_FILL
        row_idx += 1

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
