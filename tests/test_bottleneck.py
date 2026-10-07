from types import SimpleNamespace

from core.models import ScheduleResult, SchedulingInput, Teacher, TimeSlot
from core.rules.violations import Violation
from core.scheduler.bottleneck import analyze_bottlenecks, more_time_can_help, search_headroom


def _inp(ban_busy=frozenset()):
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 3, "S", 1), TimeSlot(3, 3, "S", 2)]
    return SchedulingInput(
        classes=[], subjects=[], teachers=[Teacher(10, "Cô Hà"), Teacher(20, "Thầy Hồng")],
        need={}, assigned_teacher={}, ban_busy=set(ban_busy), slots=[], timeslots=ts,
    )


def _res(diag=None, relaxed=()):
    return ScheduleResult(success=True, diagnostics=diag or {}, relaxed_rules=list(relaxed),
                          effective_params=SimpleNamespace(teacher_load={10: 18, 20: 12}))


def test_time_bottleneck_when_gap_large():
    r = _res({"final_status": "FEASIBLE", "objective": 1000.0, "best_bound": 600.0})
    assert search_headroom(r) == 0.4
    items = analyze_bottlenecks(_inp(), r, [])
    assert items[0].kind == "time"
    assert "40%" in items[0].evidence


def test_more_time_cannot_help_when_optimal_and_nothing_relaxed():
    r = _res({"final_status": "OPTIMAL", "objective": 300.0, "best_bound": 300.0})
    assert search_headroom(r) == 0.0
    assert more_time_can_help(r) is False
    assert all(b.kind != "time" for b in analyze_bottlenecks(_inp(), r, []))


def test_more_time_can_help_when_rule_relaxed_by_timeout():
    r = _res({"final_status": "OPTIMAL"}, relaxed=[{"rule_id": "II.4", "count": 2}])
    assert more_time_can_help(r) is True


def test_capacity_conflict_ranks_first():
    r = _res({"final_status": "FEASIBLE", "objective": 1000.0, "best_bound": 100.0,
              "morning_capacity": [{"weekday": 2, "teachers": 30, "need": 60, "cap": 52}]})
    items = analyze_bottlenecks(_inp(), r, [])
    assert items[0].kind == "capacity" and items[0].rule_id == "II.3"
    assert "Thứ 2" in items[0].title and "52" in items[0].evidence


def test_teacher_hotspot_names_teacher_load_and_busy():
    vs = [Violation("II.4", teacher_id=10) for _ in range(3)] + [Violation("II.4", teacher_id=20)]
    items = analyze_bottlenecks(_inp(ban_busy={(10, 1), (10, 2), (10, 3)}), _res({"final_status": "OPTIMAL"}), vs)
    t = next(b for b in items if b.kind == "teacher")
    assert t.teacher_id == 10 and "Cô Hà" in t.title
    assert "Tải 18" in t.evidence and "báo bận 2 buổi" in t.evidence  # ts 2 & 3 are the same session


def test_teacher_hotspot_ignores_synthetic_teachers():
    vs = [Violation("II.4", teacher_id=-5) for _ in range(5)]
    items = analyze_bottlenecks(_inp(), _res({"final_status": "OPTIMAL"}), vs)
    assert all(b.kind != "teacher" for b in items)


def test_relaxed_rule_not_duplicated_as_hotspot():
    vs = [Violation("II.4", teacher_id=None) for _ in range(3)]
    r = _res({"final_status": "OPTIMAL"}, relaxed=[{"rule_id": "II.4", "count": 3}])
    assert [b.rule_id for b in analyze_bottlenecks(_inp(), r, vs) if b.kind == "rule"] == ["II.4"]


def test_clean_optimal_result_has_no_bottleneck():
    assert analyze_bottlenecks(_inp(), _res({"final_status": "OPTIMAL", "objective": 0.0, "best_bound": 0.0}), []) == []


def test_result_without_diagnostics_does_not_crash():
    r = ScheduleResult(success=True)  # pre-change session_state object / heuristic result
    assert search_headroom(r) is None
    assert more_time_can_help(r) is True
    analyze_bottlenecks(_inp(), r, [Violation("II.7", teacher_id=10)])
