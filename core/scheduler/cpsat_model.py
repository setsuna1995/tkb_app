"""Mô hình CP-SAT cho bài toán xếp TKB (Facade).

Re-export toàn bộ các symbol từ package `core.scheduler.cpsat` để duy trì
tương thích 100% với các mã nguồn và test suite hiện có, đồng thời chia nhỏ
thành các module chuyên biệt: types, constraints, objectives, solver.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Optional, Sequence

from core.models import SchedulingInput, ScheduleResult
from core.roles import resolve_roles
from core.scheduler.placement import _build_effective_assigned_teacher
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

    config = inp.config
    role_index = resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week,
                               config.single_pair_subject_ids)
    effective_assigned = _build_effective_assigned_teacher(inp)

    morning_only = set(getattr(config, "morning_only_subject_ids", None) or ())
    heavy_morning_only = getattr(config, "heavy_subjects_morning_only", False)
    avoid_p3_heavy = getattr(config, "avoid_heavy_afternoon_period3", True)
    gdtc_id = role_index.gdtc_id
    gdtc_morning_allowed = getattr(config, "gdtc_morning_allowed_periods", (1, 2, 3, 4))
    gdtc_afternoon_allowed = getattr(config, "gdtc_afternoon_allowed_periods", (2, 3))
    gdtc_avoid_period = config.gdtc_avoid_period
    ban_busy = set(inp.ban_busy) if inp.ban_busy else set()
    allowed_cells = inp.subject_class_allowed_cells or {}

    chao_co_slots = set()
    shl_slots = set()
    if not inp.hdtn_thematic_week and role_index.hdtn_id is not None:
        for s in inp.slots:
            if (s.ts.weekday == config.chao_co_weekday and s.ts.session == "S"
                    and s.ts.period == config.chao_co_period
                    and inp.need.get((role_index.hdtn_id, s.class_id), 0) > 0):
                chao_co_slots.add(s.slot_id)

        class_has_chieu = defaultdict(bool)
        for s in inp.slots:
            if s.ts.session == "C":
                class_has_chieu[s.class_id] = True
        for c_id, c_slots in slots_by_class.items():
            if inp.need.get((role_index.hdtn_id, c_id), 0) >= 2:
                target_wd = 6 if class_has_chieu[c_id] else 7
                day_slots = [s for s in c_slots if s.ts.session == "S" and s.ts.weekday == target_wd]
                if day_slots:
                    shl_target = max(day_slots, key=lambda s: s.ts.period)
                    shl_slots.add(shl_target.slot_id)

    x = {}
    for s in inp.slots:
        for subj in inp.subjects:
            s_id = subj.subject_id
            if inp.need.get((s_id, s.class_id), 0) <= 0:
                continue

            # Domain Pruning
            if s.slot_id in chao_co_slots and s_id != role_index.hdtn_id:
                continue
            if s.slot_id in shl_slots and s_id != role_index.hdtn_id:
                continue
            if s_id in morning_only and s.ts.session == "C":
                continue
            if heavy_morning_only and s_id in role_index.heavy_ids and s.ts.session == "C":
                continue
            if avoid_p3_heavy and s_id in role_index.heavy_ids and s.ts.session == "C" and s.ts.period == 3:
                continue
            if s_id == gdtc_id:
                if s.ts.session == "S" and gdtc_morning_allowed and s.ts.period not in gdtc_morning_allowed:
                    continue
                if s.ts.session == "C" and gdtc_afternoon_allowed and s.ts.period not in gdtc_afternoon_allowed:
                    continue
                if s.ts.period == gdtc_avoid_period:
                    continue
            if (s_id, s.class_id) in allowed_cells:
                allowed = allowed_cells[s_id, s.class_id]
                if allowed is not None and (s.ts.weekday, s.ts.session) not in allowed:
                    continue
            t_id = effective_assigned.get((s_id, s.class_id))
            if t_id is not None and (t_id, s.ts.ts_id) in ban_busy:
                continue

            x[s.slot_id, s_id] = m.NewBoolVar(f"x_s{s.slot_id}_m{s_id}")

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
    built.role_index = role_index
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
