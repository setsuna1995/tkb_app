"""Mô hình CP-SAT cho bài toán xếp TKB (Facade).

Re-export toàn bộ các symbol từ package `core.scheduler.cpsat` để duy trì
tương thích 100% với các mã nguồn và test suite hiện có, đồng thời chia nhỏ
thành các module chuyên biệt: types, constraints, objectives, solver.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Optional, Sequence

from core.models import SchedulingInput, ScheduleResult
from core.scheduler.cpsat.types import (
    CpSatModel,
    CpSatUnavailable,
    _HAS_ORTOOLS,
    cp_model,
)
from core.scheduler.cpsat.constraints import (
    _add_teacher_constraints,
    _add_off_day_constraints,
    _add_subject_constraints,
    _add_class_constraints,
    _add_block_constraints,
    _is_teacher_busy_morning,
)
from core.scheduler.cpsat.objectives import (
    _add_objective,
    _add_change_minimisation,
    _add_solution_hint,
)
from core.scheduler.cpsat.solver import (
    build_result,
    _build_gated_model,
    detect_optimal_workers,
    EarlyStoppingCallback,
    _presolve_capacity_screening,
    _diagnose_and_solve,
    solve_to_result,
    solve,
)


def build_model(inp: SchedulingInput) -> CpSatModel:
    """Xây dựng mô hình CP-SAT hoàn chỉnh cho bài toán xếp TKB."""
    if not _HAS_ORTOOLS or cp_model is None:
        raise CpSatUnavailable("ortools chưa được cài")

    m = cp_model.CpModel()

    slots_by_class = defaultdict(list)
    slots_by_ts = defaultdict(list)
    for s in inp.slots:
        slots_by_class[s.class_id].append(s)
        slots_by_ts[s.ts.ts_id].append(s)

    x = {}
    for s in inp.slots:
        for subj in inp.subjects:
            if inp.need.get((subj.subject_id, s.class_id), 0) > 0:
                x[s.slot_id, subj.subject_id] = m.NewBoolVar(
                    f"x_s{s.slot_id}_m{subj.subject_id}")

    for s in inp.slots:
        vs = [x[s.slot_id, subj.subject_id] for subj in inp.subjects
              if (s.slot_id, subj.subject_id) in x]
        if vs:
            m.AddAtMostOne(vs)

    class_cap = {c_id: len(sls) for c_id, sls in slots_by_class.items()}
    class_total_need = defaultdict(int)
    for (_, c_id), n in inp.need.items():
        class_total_need[c_id] += max(0, n)

    for (subject_id, class_id), n in inp.need.items():
        if n <= 0:
            continue
        vs = [x[s.slot_id, subject_id] for s in slots_by_class[class_id]
              if (s.slot_id, subject_id) in x]
        if class_total_need[class_id] > class_cap.get(class_id, 0):
            m.Add(sum(vs) <= n)
        else:
            m.Add(sum(vs) == n)

    built = CpSatModel(model=m, x=x, inp=inp,
                       slots_by_class=dict(slots_by_class),
                       slots_by_ts=dict(slots_by_ts))
    _add_teacher_constraints(built)
    _add_subject_constraints(built)
    _add_class_constraints(built)
    _add_block_constraints(built)
    _add_change_minimisation(built)
    _add_objective(built)
    _add_solution_hint(built)
    return built


__all__ = [
    "CpSatModel",
    "CpSatUnavailable",
    "_HAS_ORTOOLS",
    "cp_model",
    "build_model",
    "build_result",
    "_build_gated_model",
    "detect_optimal_workers",
    "EarlyStoppingCallback",
    "_presolve_capacity_screening",
    "_diagnose_and_solve",
    "solve_to_result",
    "solve",
    "_add_teacher_constraints",
    "_add_off_day_constraints",
    "_add_subject_constraints",
    "_add_class_constraints",
    "_add_block_constraints",
    "_add_objective",
    "_add_change_minimisation",
    "_add_solution_hint",
    "_is_teacher_busy_morning",
]
