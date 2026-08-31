import pytest
import sqlite3

from data import repository, db

@pytest.fixture
def memory_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_db(conn)
    yield conn
    conn.close()

def test_class_allowed_cells_crud(memory_db):
    conn = memory_db
    class_id = repository.upsert_class(conn, "Class 1")

    cells = [(2, "S", 1), (2, "S", 2), (5, "C", 1)]
    
    # This should succeed when implemented
    repository.set_class_allowed_cells(conn, class_id, cells)

    # Verify retrieval
    retrieved = repository.get_class_allowed_cells(conn, class_id)
    assert set(retrieved) == set(cells)

    # Verify bulk retrieval
    all_cells = repository.get_all_class_allowed_cells(conn)
    assert class_id in all_cells
    assert set(all_cells[class_id]) == set(cells)

    # Set new cells (should overwrite)
    new_cells = [(3, "S", 1)]
    repository.set_class_allowed_cells(conn, class_id, new_cells)
    retrieved = repository.get_class_allowed_cells(conn, class_id)
    assert set(retrieved) == set(new_cells)

def test_build_scheduling_input_uses_allowed_cells():
    conn = db.get_connection(":memory:")
    db.init_db(conn)
    cid = repository.upsert_class(conn, "6A5")
    
    # 1. Without allowed_cells, should fallback to default (many slots)
    inp_fallback = repository.build_scheduling_input(conn, parity="C")
    fallback_slots = len(inp_fallback.slots)
    assert fallback_slots > 0

    # 2. With allowed_cells, should ONLY use those cells
    repository.set_class_allowed_cells(conn, cid, [
        (2, "S", 1), 
        (2, "S", 2), 
        (3, "C", 1)
    ])
    inp_explicit = repository.build_scheduling_input(conn, parity="C")
    
    assert len(inp_explicit.slots) == 3
    # Check that they match exactly the coordinates
    coords = set((s.ts.weekday, s.ts.session, s.ts.period) for s in inp_explicit.slots)
    assert coords == {(2, "S", 1), (2, "S", 2), (3, "C", 1)}
