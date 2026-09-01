import pytest
from core.load_balance import (
    Suggestion,
    UnresolvedOverload,
    UnresolvedUnderload,
    apply_all_suggestions,
    apply_suggestion_to_assignments,
    compute_teacher_loads,
    suggest_rebalance,
)
from data import db, repository as repo


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test_lb.db"))
    db.init_db(connection)
    yield connection
    connection.close()


def test_compute_teacher_loads():
    # Math=1, 10A1=101, 10A2=102
    assignments = {(1, 101): 1, (1, 102): 1}
    periods_per_week = {
        (1, 101, "C"): 4, (1, 101, "L"): 3,
        (1, 102, "C"): 2, (1, 102, "L"): 2,
    }
    load_c = compute_teacher_loads(assignments, periods_per_week, "C")
    load_l = compute_teacher_loads(assignments, periods_per_week, "L")
    assert load_c[1] == 6
    assert load_l[1] == 5


def test_suggest_rebalance_transfer_whole_class():
    # Teacher 1 has 5 classes of 4 periods each = 20 periods (Cap 19 -> over by 1)
    # Teacher 2 has 3 classes of 4 periods each = 12 periods (Cap 19, Floor 16 -> under by 4)
    # Math subject = 1
    assignments = {
        (1, 101): 1, (1, 102): 1, (1, 103): 1, (1, 104): 1, (1, 105): 1,
        (1, 106): 2, (1, 107): 2, (1, 108): 2,
    }
    periods_per_week = {}
    for c in [101, 102, 103, 104, 105, 106, 107, 108]:
        periods_per_week[(1, c, "C")] = 4
        periods_per_week[(1, c, "L")] = 4

    teacher_caps = {1: 19, 2: 19}
    suggestions, unresolved_over, unresolved_under = suggest_rebalance(
        assignments, periods_per_week, parity="C", teacher_caps=teacher_caps, floor_margin=3
    )

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.action_type == "transfer"
    assert s.over_teacher_id == 1
    assert s.to_teacher_id == 2
    assert s.subject_id == 1
    assert s.class_id in [101, 102, 103, 104, 105]
    assert s.periods == 4.0
    assert s.periods_c == 4
    assert s.periods_l == 4
    assert s.from_teacher_new_load == 16.0
    assert s.to_teacher_new_load == 16.0
    assert len(unresolved_over) == 0
    assert len(unresolved_under) == 0


def test_suggest_rebalance_swap_classes():
    # Teacher 1 has 5 classes of 4 periods = 20 periods (Cap 19 -> over by 1)
    # Teacher 2 has 6 classes of 3 periods = 18 periods (Cap 19 -> slack = 1)
    # 1-way transfer of 4 periods cannot fit in Teacher 2 (18 + 4 = 22 > 19)
    # But SWAPPING 1 class of 4 periods with 1 class of 3 periods results in:
    # Teacher 1: 20 - 4 + 3 = 19 (Cap 19 -> Balanced!)
    # Teacher 2: 18 - 3 + 4 = 19 (Cap 19 -> Balanced!)
    assignments = {
        (1, 101): 1, (1, 102): 1, (1, 103): 1, (1, 104): 1, (1, 105): 1,
        (1, 201): 2, (1, 202): 2, (1, 203): 2, (1, 204): 2, (1, 205): 2, (1, 206): 2,
    }
    periods_per_week = {}
    for c in [101, 102, 103, 104, 105]:
        periods_per_week[(1, c, "C")] = 4
        periods_per_week[(1, c, "L")] = 4
    for c in [201, 202, 203, 204, 205, 206]:
        periods_per_week[(1, c, "C")] = 3
        periods_per_week[(1, c, "L")] = 3

    teacher_caps = {1: 19, 2: 19}
    suggestions, unresolved_over, unresolved_under = suggest_rebalance(
        assignments, periods_per_week, parity="C", teacher_caps=teacher_caps, floor_margin=3, allow_swap=True
    )

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.action_type == "swap"
    assert s.over_teacher_id == 1
    assert s.to_teacher_id == 2
    assert s.subject_id == 1
    assert s.class_id in [101, 102, 103, 104, 105]
    assert s.periods == 4.0
    assert s.swap_subject_id == 1
    assert s.swap_class_id in [201, 202, 203, 204, 205, 206]
    assert s.swap_periods == 3.0
    assert s.from_teacher_new_load == 19.0
    assert s.to_teacher_new_load == 19.0
    assert len(unresolved_over) == 0


def test_apply_suggestion_to_assignments():
    assignments = {(1, 101): 1, (1, 201): 2}

    # Test transfer apply
    s_transfer = Suggestion(
        over_teacher_id=1,
        over_amount=1,
        subject_id=1,
        class_id=101,
        periods=4.0,
        to_teacher_id=2,
        to_teacher_load=12.0,
        to_teacher_cap=19,
        action_type="transfer",
    )
    new_asgn1 = apply_suggestion_to_assignments(assignments, s_transfer)
    assert new_asgn1[(1, 101)] == 2
    assert new_asgn1[(1, 201)] == 2

    # Test swap apply
    s_swap = Suggestion(
        over_teacher_id=1,
        over_amount=1,
        subject_id=1,
        class_id=101,
        periods=4.0,
        to_teacher_id=2,
        to_teacher_load=18.0,
        to_teacher_cap=19,
        action_type="swap",
        swap_subject_id=1,
        swap_class_id=201,
        swap_periods=3.0,
    )
    new_asgn2 = apply_suggestion_to_assignments(assignments, s_swap)
    assert new_asgn2[(1, 101)] == 2
    assert new_asgn2[(1, 201)] == 1


def test_apply_all_suggestions():
    assignments = {(1, 101): 1, (1, 102): 1}
    s1 = Suggestion(
        over_teacher_id=1, over_amount=1, subject_id=1, class_id=101,
        periods=4.0, to_teacher_id=2, to_teacher_load=10.0, to_teacher_cap=19,
        action_type="transfer",
    )
    s2 = Suggestion(
        over_teacher_id=1, over_amount=1, subject_id=1, class_id=102,
        periods=4.0, to_teacher_id=3, to_teacher_load=10.0, to_teacher_cap=19,
        action_type="transfer",
    )
    res = apply_all_suggestions(assignments, [s1, s2])
    assert res[(1, 101)] == 2
    assert res[(1, 102)] == 3


def test_suggest_rebalance_asymmetric_weeks():
    # Class 101 has 3 periods in C, 4 in L (avg 3.5)
    assignments = {(1, 101): 1, (1, 102): 1, (1, 201): 2}
    periods_per_week = {
        (1, 101, "C"): 3, (1, 101, "L"): 4,
        (1, 102, "C"): 17, (1, 102, "L"): 17,
        (1, 201, "C"): 10, (1, 201, "L"): 10,
    }
    teacher_caps = {1: 19, 2: 19}
    suggestions, _, _ = suggest_rebalance(
        assignments, periods_per_week, parity="C", teacher_caps=teacher_caps, floor_margin=3
    )
    assert len(suggestions) >= 1
    s = [x for x in suggestions if x.class_id == 101][0]
    assert s.periods_c == 3
    assert s.periods_l == 4
    assert s.periods == 3.5


def test_apply_suggestions_to_database(conn):
    # Set up DB entities
    s_id = repo.upsert_subject(conn, "Toan")
    c1_id = repo.upsert_class(conn, "10A1")
    c2_id = repo.upsert_class(conn, "10A2")
    t1_id = repo.upsert_teacher(conn, "GV A")
    t2_id = repo.upsert_teacher(conn, "GV B")

    # Initial assignment: GV A teaches both 10A1 and 10A2
    repo.set_assignment(conn, s_id, c1_id, t1_id)
    repo.set_assignment(conn, s_id, c2_id, t1_id)

    s = Suggestion(
        over_teacher_id=t1_id,
        over_amount=4.0,
        subject_id=s_id,
        class_id=c1_id,
        periods=4.0,
        to_teacher_id=t2_id,
        to_teacher_load=0.0,
        to_teacher_cap=19,
        action_type="transfer",
    )

    # Apply to DB
    if s.action_type == "transfer":
        repo.set_assignment(conn, s.subject_id, s.class_id, s.to_teacher_id)
    elif s.action_type == "swap":
        repo.set_assignment(conn, s.subject_id, s.class_id, s.to_teacher_id)
        if s.swap_subject_id is not None and s.swap_class_id is not None:
            repo.set_assignment(conn, s.swap_subject_id, s.swap_class_id, s.over_teacher_id)

    # Verify DB state
    db_assignments = repo.get_assignments(conn)
    assert db_assignments.get((s_id, c1_id)) == t2_id
    assert db_assignments.get((s_id, c2_id)) == t1_id

