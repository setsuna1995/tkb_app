"""One normalised reading of a finished schedule, shared by every detector.

Before 2026-09-17 each find_* function filtered teacher ids its own way
(< 0, <= 0, > 0), only quality.py dropped the -1 empty-cell sentinel, and
each picked the raw or the effective teacher map on its own.
build_schedule_view is now the only place those conventions are applied.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterator, Optional

from core.models import RoleIndex, SchedulingInput, Slot
from core.roles import is_academic_subject, resolve_roles
from core.scheduler.placement import _build_effective_assigned_teacher

EMPTY_CELL_SENTINEL = -1


@dataclass(frozen=True)
class ScheduleView:
    slots: list
    assignment: dict       # slot_id -> subject_id, or None for an empty cell
    slot_teacher: dict     # slot_id -> real teacher_id, or None (empty cell / unassigned subject)
    teacher_classes: dict  # teacher_id -> frozenset of class_ids the teacher is assigned to
    ban_busy: frozenset    # {(teacher_id, ts_id)}
    allowed_cells: dict    # (subject_id, class_id) -> frozenset((weekday, session)) | None
    roles: RoleIndex
    academic_ids: frozenset
    class_names: dict
    subject_names: dict
    teacher_names: dict

    def placed(self) -> Iterator[tuple[Slot, int, Optional[int]]]:
        """(slot, subject_id, teacher_id) for every non-empty cell."""
        for slot in self.slots:
            subject_id = self.assignment[slot.slot_id]
            if subject_id is not None:
                yield slot, subject_id, self.slot_teacher[slot.slot_id]

    def class_name(self, class_id: int) -> str:
        return self.class_names.get(class_id, f"Lớp #{class_id}")

    def subject_name(self, subject_id: int) -> str:
        return self.subject_names.get(subject_id, f"Môn #{subject_id}")

    def teacher_name(self, teacher_id: int) -> str:
        return self.teacher_names.get(teacher_id, f"GV #{teacher_id}")


def build_schedule_view(inp: SchedulingInput, assignment: dict) -> ScheduleView:
    effective_teacher = _build_effective_assigned_teacher(inp)
    cells, slot_teacher = {}, {}
    for slot in inp.slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id == EMPTY_CELL_SENTINEL:
            subject_id = None
        teacher_id = effective_teacher.get((subject_id, slot.class_id))
        cells[slot.slot_id] = subject_id
        slot_teacher[slot.slot_id] = teacher_id if teacher_id is not None and teacher_id > 0 else None

    teacher_classes = defaultdict(set)
    for (_subject_id, class_id), teacher_id in effective_teacher.items():
        if teacher_id is not None and teacher_id > 0:
            teacher_classes[teacher_id].add(class_id)

    config = inp.config
    return ScheduleView(
        slots=list(inp.slots),
        assignment=cells,
        slot_teacher=slot_teacher,
        teacher_classes={tid: frozenset(cids) for tid, cids in teacher_classes.items()},
        ban_busy=frozenset(inp.ban_busy or ()),
        allowed_cells=dict(inp.subject_class_allowed_cells or {}),
        roles=resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week,
                            config.single_pair_subject_ids),
        academic_ids=frozenset(s.subject_id for s in inp.subjects if is_academic_subject(s.name)),
        class_names={c.class_id: c.name for c in inp.classes},
        subject_names={s.subject_id: s.name for s in inp.subjects},
        teacher_names={t.teacher_id: t.name for t in inp.teachers},
    )
