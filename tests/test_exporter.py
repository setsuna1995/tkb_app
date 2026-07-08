import io
import os

import openpyxl
import pytest

from core import scheduler as sched
from data import db, repository as repo
from io_excel.exporter import export_xlsx
from io_excel.importer import import_xlsm

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "TKB_9lop_moi.xlsm")


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(connection)
    import_xlsm(connection, FIXTURE)
    yield connection
    connection.close()


def test_export_current_baseline_has_expected_sheets(conn):
    data = export_xlsx(conn)
    wb = openpyxl.load_workbook(io.BytesIO(data))
    assert set(wb.sheetnames) == {"TKB_Nhap", "TKB", "TKB_GV", "KiemTra"}


def test_export_accepted_run_kiemtra_all_zero(conn):
    parity = repo.get_tuan_config(conn)[1]
    inp = repo.build_scheduling_input(conn, parity=parity, seed=123)
    result = sched.run(inp)
    assert result.success

    cells = {}
    for slot in inp.slots:
        cells[(slot.class_id, slot.ts.weekday, slot.ts.session, slot.ts.period)] = result.assignment.get(slot.slot_id)
    run_id = repo.save_run(conn, week_no=1, seed=123, parity=parity, cells_changed=result.cells_changed,
                            cells_total=result.cells_total, succeeded=True, message="ok")
    repo.save_tkb_result(conn, run_id, cells)

    data = export_xlsx(conn, run_id=run_id)
    wb = openpyxl.load_workbook(io.BytesIO(data))
    ws = wb["KiemTra"]
    # row 1 = title, row 2 = blank spacer, row 3 = header ("Môn \ Lớp", 6A..9B);
    # actual diff values fill rows 4..4+len(subjects)-1 (see exporter.export_xlsx)
    n_subjects = len(repo.list_subjects(conn))
    for row in ws.iter_rows(min_row=4, max_row=3 + n_subjects, min_col=2):
        for cell in row:
            assert cell.value == 0

    ws_gv = wb["TKB_GV"]
    for row in ws_gv.iter_rows(min_row=2, min_col=4, max_col=9):
        for cell in row:
            # no conflicts on a successful run -- just never the conflict-red fill
            # (cells still carry the template's own white/gray banding fill)
            assert cell.fill.fgColor.rgb != "00FFC7CE"
