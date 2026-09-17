"""Builders for rule unit tests: a minimal SchedulingInput around hand-placed slots."""
from core.models import ROLE_HDTN, ClassRoom, SchedulingConfig, SchedulingInput, Subject, Teacher
from core.rules.detectors import detect_rule
from core.rules.params import resolve_effective_params
from core.rules.view import build_schedule_view

HDTN_SUBJECT_ID = 9999  # resolve_roles() refuses a subject list without HĐTN


def make_input(slots, *, assigned_teacher=None, subjects=None, used_subject_ids=(), config=None,
               ban_busy=None, need=None, allowed_cells=None, teachers=None) -> SchedulingInput:
    assigned_teacher = dict(assigned_teacher or {})
    need = dict(need or {})
    subjects = list(subjects or [])
    known_ids = {s.subject_id for s in subjects}
    wanted_ids = set(used_subject_ids) | {sid for sid, _cid in assigned_teacher} | {sid for sid, _cid in need}
    subjects += [Subject(sid, f"Môn {sid}") for sid in sorted(wanted_ids - known_ids)]
    if not any(s.role_code == ROLE_HDTN for s in subjects):
        subjects.append(Subject(HDTN_SUBJECT_ID, "HĐTN", ROLE_HDTN))
    real_teacher_ids = sorted({tid for tid in assigned_teacher.values() if tid > 0})
    return SchedulingInput(
        classes=[ClassRoom(cid, f"Lớp {cid}") for cid in sorted({s.class_id for s in slots})],
        subjects=subjects,
        teachers=teachers if teachers is not None else [Teacher(tid, f"GV {tid}") for tid in real_teacher_ids],
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=set(ban_busy or ()),
        slots=list(slots),
        timeslots=sorted({s.ts for s in slots}, key=lambda ts: ts.order_key),
        config=config or SchedulingConfig(),
        subject_class_allowed_cells=dict(allowed_cells or {}),
    )


def view_and_params(slots, assignment, **input_kwargs):
    used = {sid for sid in assignment.values() if sid not in (None, -1)}
    inp = make_input(slots, used_subject_ids=used, **input_kwargs)
    return build_schedule_view(inp, assignment), resolve_effective_params(inp)


def pick(violations, *field_names):
    return [tuple(getattr(v, name) for name in field_names) for v in violations]


def violations_of(rule_id, inp, assignment):
    return detect_rule(rule_id, build_schedule_view(inp, assignment), resolve_effective_params(inp))
