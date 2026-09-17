from core.models import Slot, TimeSlot
from core.rules.view import build_schedule_view
from tests.rule_helpers import make_input


def _two_morning_slots():
    return [Slot(1, 101, TimeSlot(1, 2, "S", 1)), Slot(2, 101, TimeSlot(2, 2, "S", 2))]


def test_empty_sentinel_and_missing_cells_become_none():
    inp = make_input(_two_morning_slots(), assigned_teacher={(7, 101): 10})
    view = build_schedule_view(inp, {1: -1})
    assert view.assignment == {1: None, 2: None}
    assert view.slot_teacher == {1: None, 2: None}
    assert list(view.placed()) == []


def test_unassigned_subject_never_yields_a_teacher():
    """PhanCong bỏ trống -> id GV tổng hợp âm. View quy về None một lần,
    thay vì mỗi detector tự lọc bằng < 0, <= 0 hay > 0."""
    inp = make_input(_two_morning_slots(), need={(7, 101): 2})
    view = build_schedule_view(inp, {1: 7, 2: 7})
    assert [(slot.slot_id, subject_id, teacher_id) for slot, subject_id, teacher_id in view.placed()] == [
        (1, 7, None), (2, 7, None),
    ]


def test_teacher_and_teacher_classes_come_from_effective_map():
    inp = make_input(_two_morning_slots(), assigned_teacher={(7, 101): 10})
    view = build_schedule_view(inp, {1: 7})
    assert view.slot_teacher == {1: 10, 2: None}
    assert view.teacher_classes == {10: frozenset({101})}
    assert view.teacher_name(10) == "GV 10"
    assert view.class_name(404) == "Lớp #404"
