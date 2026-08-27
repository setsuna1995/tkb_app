import pytest
from data import db, repository as repo

@pytest.fixture
def conn(tmp_path):
    c = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(c)
    return c

def test_compress_busy_cells_empty():
    assert repo.compress_busy_cells(set()) == []

def test_compress_busy_cells_single():
    assert repo.compress_busy_cells({(3, 'S', 1)}) == [('3', 'S', '1')]

def test_compress_busy_cells_all_week():
    cells = {(w, 'S', 4) for w in range(2, 8)}
    assert repo.compress_busy_cells(cells) == [('*', 'S', '4')]

def test_compress_busy_cells_full_morning():
    cells = {(4, 'S', p) for p in range(1, 6)}
    assert repo.compress_busy_cells(cells) == [('4', 'S', '*')]

def test_compress_busy_cells_full_day():
    cells = {(5, s, p) for s in ['S', 'C'] for p in range(1, 6)}
    assert repo.compress_busy_cells(cells) == [('5', '*', '*')]

def test_set_and_get_teacher_busy_cells_roundtrip(conn):
    t_id = repo.upsert_teacher(conn, 'Khu')
    busy = {(3, 'S', 1), (5, 'S', 1)}
    repo.set_teacher_busy_cells(conn, t_id, busy)
    extracted = repo.get_teacher_busy_cells(conn, t_id)
    assert extracted == busy


    rules = conn.execute('SELECT weekday, session, period FROM teacher_unavailability WHERE teacher_id=?', (t_id,)).fetchall()
    rule_tuples = set((r['weekday'], r['session'], r['period']) for r in rules)
    assert rule_tuples == {('3', 'S', '1'), ('5', 'S', '1')}


def test_wildcard_rule_expansion(conn):
    t_id = repo.upsert_teacher(conn, 'Hong')
    repo.add_unavailability(conn, t_id, '*', 'S', '4')
    repo.add_unavailability(conn, t_id, '*', 'C', '1')

    extracted = repo.get_teacher_busy_cells(conn, t_id)
    assert len(extracted) == 12
    assert (2, 'S', 4) in extracted
    assert (7, 'S', 4) in extracted
    assert (2, 'C', 1) in extracted
    assert (7, 'C', 1) in extracted
