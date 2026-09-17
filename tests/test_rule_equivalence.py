"""Tầng mô hình (CP-SAT) và tầng hậu kiểm (detectors) phải đồng ý về từng luật.

Ba phép kiểm tách bạch (spec 2026-09-17 §6.1):
  model_promise      -- đếm lại trên ngưỡng mô hình đã ép phải khớp số mô hình tự đếm.
  forced_evidence    -- mọi vi phạm FORCED phải kèm bằng chứng.
  unexplained_breach -- BREACH chỉ được phép ở fixture cố ý dựng ra nó.

Bất đồng đã biết nằm trong KNOWN_DRIFT kèm nguyên nhân và plan sẽ sửa.
Không thêm mục nào khi chưa giải thích được vì sao nó đỏ.
"""
from __future__ import annotations

import copy
import functools
import os
from dataclasses import replace

import pytest

from core import scheduler as sched
from core.models import ROLE_HDTN, WEEKDAYS, ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot
from core.rules.detectors import DETECTORS, detect_rule
from core.rules.params import resolve_effective_params
from core.rules.view import build_schedule_view
from core.rules.violations import BREACH, FORCED, classify
from data import db, repository as repo
from io_excel.importer import import_xlsm

pytest.importorskip("ortools")
pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("rule_equivalence")]

SAMPLE_SCHOOL = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")
FIXTURE_TIME_LIMIT_S = 30
OVERSUBSCRIBED_EXTRA_PERIODS = 2
LONE_TEACHER_ID = 10
LONE_CLASS_ID = 101
LONE_HDTN_SUBJECT_ID = 99


@functools.lru_cache(maxsize=None)
def _imported_sample_school() -> SchedulingInput:
    conn = db.get_connection(":memory:")
    db.init_db(conn)
    import_xlsm(conn, SAMPLE_SCHOOL)
    inp = repo.build_scheduling_input(conn, parity="L", seed=2026)
    conn.close()
    return inp


def _sample_school(**config_changes) -> SchedulingInput:
    inp = copy.deepcopy(_imported_sample_school())
    inp.config = replace(inp.config, cpsat_time_limit_seconds=FIXTURE_TIME_LIMIT_S, **config_changes)
    return inp


def _lone_exempt() -> SchedulingInput:
    inp = _sample_school()
    params = resolve_effective_params(inp)
    _load, lightest_gated_teacher = min(
        (load, tid) for tid, load in params.teacher_load.items()
        if load >= params.min_weekly_periods_for_lone_penalty
    )
    inp.config = replace(inp.config, lone_session_exempt_teacher_ids=frozenset({lightest_gated_teacher}))
    return inp


def _single_pair() -> SchedulingInput:
    inp = _sample_school()
    literature = next(s.subject_id for s in inp.subjects if s.name.strip().lower().startswith("ngữ văn"))
    inp.config = replace(inp.config, single_pair_subject_ids=frozenset({literature}))
    return inp


def _oversubscribed() -> SchedulingInput:
    inp = _sample_school()
    class_id = inp.classes[0].class_id
    capacity = sum(1 for s in inp.slots if s.class_id == class_id)
    class_need = {key: n for key, n in inp.need.items() if key[1] == class_id and n > 0}
    inp.need[min(class_need)] += max(0, capacity - sum(class_need.values())) + OVERSUBSCRIBED_EXTRA_PERIODS
    return inp


def _infeasible_ii4() -> SchedulingInput:
    """Một GV, mỗi ngày đúng 1 ô sáng, mỗi môn 1 tiết: mọi buổi của GV buộc là buổi lẻ,
    nên II.4 không thể thỏa. Không có buổi chiều nên không dính II.8; tải 6 < ngưỡng
    sáng bắt buộc 10 nên không dính II.3."""
    timeslots = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate(WEEKDAYS)]
    subjects = [Subject(i + 1, f"Môn {i + 1}") for i in range(len(timeslots))]
    need = {(s.subject_id, LONE_CLASS_ID): 1 for s in subjects}
    return SchedulingInput(
        classes=[ClassRoom(LONE_CLASS_ID, "6A1")],
        subjects=subjects + [Subject(LONE_HDTN_SUBJECT_ID, "HĐTN", ROLE_HDTN)],
        teachers=[Teacher(LONE_TEACHER_ID, "GV A")],
        need=need,
        assigned_teacher={key: LONE_TEACHER_ID for key in need},
        ban_busy=set(),
        slots=[Slot(i + 1, LONE_CLASS_ID, ts) for i, ts in enumerate(timeslots)],
        timeslots=timeslots,
        config=SchedulingConfig(min_weekly_periods_for_lone_penalty=0, teacher_off_sessions_per_week=0,
                                cpsat_time_limit_seconds=FIXTURE_TIME_LIMIT_S),
    )


FIXTURES = {
    "baseline": _sample_school,
    "heavy_morning_only": lambda: _sample_school(heavy_subjects_morning_only=True),
    "oversubscribed": _oversubscribed,
    "lone_exempt": _lone_exempt,
    "off_enabled": lambda: _sample_school(teacher_off_sessions_per_week=2),
    "off_disabled": lambda: _sample_school(teacher_off_sessions_per_week=0),
    "single_pair": _single_pair,
    "infeasible_ii4": _infeasible_ii4,
}
EXPECTED_BREACH_FIXTURES = frozenset({"infeasible_ii4"})
RULE_IDS = tuple(sorted(DETECTORS))
# C.HEAVY_CONSEC và ACAD.MAX hiện pass cả 3 check một cách vacuous (0-vs-0) trên mọi fixture:
# adaptive-cap logic của chúng (_get_eff_max_heavy trong constraints.py, và academic-floor block) tự nới cap cục bộ mà không ghi lại vào EffectiveParams -- rewiring đó là GĐ 5 (Plan 2), nên harness chưa phát hiện được drift thật ở 2 rule này.

# (check, fixture, rule_id) -> "nguyên nhân -- plan sửa". Điền theo quy trình ở Task 11 Step 4.
_RELAXATION_UNSCOPED = "Nới lỏng chưa có phạm vi (relaxed_rules cũ) — Plan 2 (A7 Relaxation)"
KNOWN_DRIFT: dict = {
    ("unexplained_breach", "baseline", "II.4"): _RELAXATION_UNSCOPED,
    ("unexplained_breach", "heavy_morning_only", "II.4"): _RELAXATION_UNSCOPED,
    ("unexplained_breach", "oversubscribed", "II.4"): _RELAXATION_UNSCOPED,
    ("unexplained_breach", "lone_exempt", "II.4"): _RELAXATION_UNSCOPED + " [không tất định]",
    ("unexplained_breach", "off_enabled", "II.4"): _RELAXATION_UNSCOPED,
    ("unexplained_breach", "off_disabled", "II.4"): _RELAXATION_UNSCOPED,
    ("unexplained_breach", "single_pair", "II.4"): _RELAXATION_UNSCOPED,
}


@functools.lru_cache(maxsize=None)
def _solved(fixture: str):
    inp = FIXTURES[fixture]()
    result = sched.run(inp)
    assert result.success, f"{fixture}: {result.failure_reason}"
    return result, build_schedule_view(inp, result.assignment)


def _cases(check: str) -> list:
    return [
        pytest.param(
            fixture, rule_id, id=f"{fixture}-{rule_id}",
            marks=[pytest.mark.xfail(strict=not KNOWN_DRIFT[check, fixture, rule_id].endswith("[không tất định]"),
                                     reason=KNOWN_DRIFT[check, fixture, rule_id])]
            if (check, fixture, rule_id) in KNOWN_DRIFT else [],
        )
        for fixture in FIXTURES for rule_id in RULE_IDS
    ]


@pytest.mark.parametrize("fixture, rule_id", _cases("model_promise"))
def test_model_keeps_its_own_promise(fixture, rule_id):
    result, view = _solved(fixture)
    recounted = len(detect_rule(rule_id, view, result.effective_params.as_effective()))
    modelled = result.rule_counts.get(rule_id, 0)
    assert recounted == modelled, (
        f"{rule_id}: mô hình tự đếm {modelled} trên ngưỡng nó ép, hậu kiểm đếm {recounted} — hai tầng trôi lệch"
    )


@pytest.mark.parametrize("fixture, rule_id", _cases("forced_evidence"))
def test_forced_violation_has_evidence(fixture, rule_id):
    result, view = _solved(fixture)
    params = result.effective_params
    unexplained = [v for v in classify(detect_rule(rule_id, view, params), params)
                   if v.level == FORCED and not v.evidence]
    assert not unexplained, f"{rule_id}: FORCED mà không có bằng chứng — phải là BREACH: {unexplained}"


@pytest.mark.parametrize("fixture, rule_id", _cases("unexplained_breach"))
def test_no_unexplained_breach(fixture, rule_id):
    result, view = _solved(fixture)
    params = result.effective_params
    breaches = [v for v in classify(detect_rule(rule_id, view, params), params) if v.level == BREACH]
    assert not breaches or fixture in EXPECTED_BREACH_FIXTURES, (
        f"{rule_id}: {len(breaches)} vi phạm không giải thích được — bug mô hình hoặc thiếu bằng chứng nới lỏng: "
        f"{[v.detail for v in breaches[:5]]}"
    )
