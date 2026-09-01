"""Main orchestrator for the randomized greedy + local repair scheduling engine."""
from __future__ import annotations

import random
from collections import defaultdict
from core.models import ScheduleResult, SchedulingInput
from core.roles import resolve_roles
from core.scheduler.blocks import (
    _has_unpaired_block, _repair_unpaired_blocks, _try_place_block_atomically,
)
from core.scheduler.constants import (
    FAILURE_MESSAGE, NGUONG_KHOA, SO_LAN_THU, SO_PA_TOT,
)
from core.scheduler.feasibility import _feasible
from core.scheduler.heuristics import _pick_best_scored
from core.scheduler.placement import (
    _build_effective_assigned_teacher, _put_at,
)
from core.scheduler.quality import _teacher_quality_penalty
from core.scheduler.state import _State
from core.scheduler.swaps import (
    _has_lone_period, _repair_lone_periods, _repair_teacher_lone_sessions,
    _try_swap_repair,
)
from core.scheduler.teacher_off import _assign_off_slots


def run(inp: SchedulingInput, *, max_attempts: int = SO_LAN_THU,
        target_successes: int = SO_PA_TOT, lock_threshold: int = NGUONG_KHOA) -> ScheduleResult:
    role_index = resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week, inp.config.single_pair_subject_ids)
    config = inp.config
    avoid_gdtc = getattr(config, "avoid_gdtc_consecutive_days", True)
    non_consecutive = getattr(config, "non_consecutive_subject_ids", None) or frozenset()
    subject_class_allowed_cells = inp.subject_class_allowed_cells
    assigned_teacher = _build_effective_assigned_teacher(inp)
    teachers_by_id = {t.teacher_id: t for t in inp.teachers}
    all_teacher_ids = set(assigned_teacher.values())

    class_has_chieu = defaultdict(bool)
    for slot in inp.slots:
        if slot.ts.session == "C":
            class_has_chieu[slot.class_id] = True

    morning_slots_by_class = defaultdict(list)
    for slot in inp.slots:
        if slot.ts.session == "S":
            morning_slots_by_class[slot.class_id].append(slot)
    shl_target_slot = {}
    for cls in inp.classes:
        target_wd = 6 if class_has_chieu[cls.class_id] else 7
        day_slots = [s for s in morning_slots_by_class[cls.class_id] if s.ts.weekday == target_wd]
        if day_slots:
            shl_target_slot[cls.class_id] = max(day_slots, key=lambda s: s.ts.period)
    classes_with_shl_target = set(shl_target_slot)
    shl_days = {(cid, slot.ts.weekday) for cid, slot in shl_target_slot.items()}

    gvcn_shl_cell = {}
    for cls in inp.classes:
        homeroom_teacher = assigned_teacher.get((role_index.hdtn_id, cls.class_id))
        target = shl_target_slot.get(cls.class_id)
        if homeroom_teacher is not None and target is not None:
            gvcn_shl_cell[homeroom_teacher] = (target.ts.weekday, target.ts.session)

    if inp.hdtn_thematic_week:
        shl_days = set()
        gvcn_shl_cell = {}

    need_cls = defaultdict(int)
    for (subj_id, cls_id), n in inp.need.items():
        need_cls[cls_id] += n
    slot_cls_n = defaultdict(int)
    slots_by_ts = defaultdict(list)
    slots_by_class = defaultdict(list)
    day_capacity = defaultdict(int)
    slot_by_coord = {}
    for slot in inp.slots:
        slot_cls_n[slot.class_id] += 1
        slots_by_ts[slot.ts.ts_id].append(slot)
        slots_by_class[slot.class_id].append(slot)
        day_capacity[(slot.class_id, slot.ts.weekday)] += 1
        slot_by_coord[(slot.class_id, slot.ts.weekday, slot.ts.session, slot.ts.period)] = slot

    base_order = sorted(inp.timeslots, key=lambda ts: ts.order_key)

    base_groups = []
    for ts in base_order:
        key = (ts.weekday, ts.session)
        if not base_groups or base_groups[-1][0] != key:
            base_groups.append((key, []))
        base_groups[-1][1].append(ts)

    rng = random.Random(inp.seed) if inp.seed else random.Random()

    best_assignment = None
    best_changed = None
    best_quality_score = None
    successes = 0
    attempts_tried = 0

    for attempt in range(1, max_attempts + 1):
        attempts_tried = attempt
        pu = 0.0 if attempt <= lock_threshold else min(0.3, (attempt - lock_threshold) / 1200 * 0.3)

        state = _State(
            remaining_need=dict(inp.need),
            busy=set(inp.ban_busy),
        )
        for cls in inp.classes:
            state.rem_need_count[cls.class_id] = need_cls[cls.class_id]
            state.rem_slot_count[cls.class_id] = slot_cls_n[cls.class_id]
        state.gv_off_slots = _assign_off_slots(
            all_teacher_ids, teachers_by_id, rng, gvcn_shl_cell,
            off_slot_count=config.teacher_off_sessions_per_week,
            forbidden_off_cells=config.forbidden_off_cells,
            mandatory_morning_weekdays=getattr(config, "mandatory_morning_weekdays", (2, 5, 6)),
        )
        state.shl_days = shl_days

        if attempt > lock_threshold and attempt % 2 == 0:
            groups = list(base_groups)
            rng.shuffle(groups)
            order = [ts for _key, ts_list in groups for ts in ts_list]
        else:
            order = list(base_order)

        done = True

        if not inp.hdtn_thematic_week:
            for slot in inp.slots:
                if (slot.ts.weekday == config.chao_co_weekday and slot.ts.session == "S"
                        and slot.ts.period == config.chao_co_period):
                    key = (role_index.hdtn_id, slot.class_id)
                    if state.remaining_need.get(key, 0) > 0:
                        teacher_id = assigned_teacher.get(key)
                        if teacher_id is not None and _feasible(slot.class_id, slot.ts, role_index.hdtn_id,
                                                                  teacher_id, state, role_index, day_capacity,
                                                                  config, subject_class_allowed_cells):
                            _put_at(state, slot, role_index.hdtn_id, teacher_id, role_index)
                            state.pinned[slot.slot_id] = True

        reserved_shl = []
        if not inp.hdtn_thematic_week:
            for cid in classes_with_shl_target:
                key = (role_index.hdtn_id, cid)
                if state.remaining_need.get(key, 0) > 0:
                    target = shl_target_slot[cid]
                    state.assigned[target.slot_id] = -1
                    state.rem_slot_count[cid] -= 1
                    state.remaining_need[key] -= 1
                    state.rem_need_count[cid] -= 1
                    reserved_shl.append((cid, target))

        for ts in order:
            candidates = [s for s in slots_by_ts[ts.ts_id] if state.assigned.get(s.slot_id) is None]
            rng.shuffle(candidates)
            for slot in candidates:
                class_id = slot.class_id
                if state.assigned.get(slot.slot_id) is not None:
                    continue
                if _try_place_block_atomically(class_id, slot, state, role_index, inp.subjects,
                                                assigned_teacher, day_capacity, config,
                                                subject_class_allowed_cells, slot_by_coord):
                    continue
                pick = _pick_best_scored(class_id, slot, state, role_index, inp.subjects,
                                          assigned_teacher, pu, rng, day_capacity, config,
                                          subject_class_allowed_cells)
                would_strand_lone_period = (
                    ts.period == 2 and state.occupied.get((class_id, ts.weekday, ts.session, 1), False)
                )
                if pick is not None:
                    _put_at(state, slot, pick[0], pick[1], role_index)
                elif not would_strand_lone_period and state.rem_slot_count[class_id] > state.rem_need_count[class_id]:
                    state.assigned[slot.slot_id] = -1
                    state.rem_slot_count[class_id] -= 1
                else:
                    fixed = _try_swap_repair(class_id, slot, state, role_index, inp.subjects,
                                              assigned_teacher, slots_by_class, day_capacity, config,
                                              subject_class_allowed_cells)
                    if not fixed:
                        done = False
                        break
            if not done:
                break

        if done:
            for cid, target in reserved_shl:
                key = (role_index.hdtn_id, cid)
                state.assigned[target.slot_id] = None
                state.rem_slot_count[cid] += 1
                state.remaining_need[key] += 1
                state.rem_need_count[cid] += 1
                tid = assigned_teacher[key]
                if _feasible(cid, target.ts, role_index.hdtn_id, tid, state, role_index, day_capacity, config,
                              subject_class_allowed_cells):
                    _put_at(state, target, role_index.hdtn_id, tid, role_index)
                    state.pinned[target.slot_id] = True
                else:
                    done = False
                    break

        if done:
            _repair_lone_periods(inp, state, role_index, assigned_teacher, slots_by_class, day_capacity, config,
                                  subject_class_allowed_cells)
            if _has_lone_period(inp, state):
                done = False

        if done:
            _repair_unpaired_blocks(inp, state, role_index, assigned_teacher, slot_by_coord, day_capacity, config,
                                     subject_class_allowed_cells)
            if _has_unpaired_block(inp, state, role_index):
                done = False

        if done:
            _repair_teacher_lone_sessions(inp, state, role_index, assigned_teacher, slots_by_class,
                                          day_capacity, config, subject_class_allowed_cells, slot_by_coord)

        if done and (avoid_gdtc or non_consecutive):
            for (cid, sid, wd), pos_list in state.placed.items():
                if pos_list and ((sid in non_consecutive) or (avoid_gdtc and sid == role_index.gdtc_id)):
                    if wd > 2 and state.placed.get((cid, sid, wd - 1)):
                        done = False
                        break
                    if wd < 8 and state.placed.get((cid, sid, wd + 1)):
                        done = False
                        break

        if done:
            cells_changed = 0
            for slot in inp.slots:
                final = state.assigned.get(slot.slot_id)
                if final == -1:
                    final = None
                if final != slot.old_subject_id:
                    cells_changed += 1
            teacher_penalty = _teacher_quality_penalty(inp.slots, state.assigned, state.slot_teacher, config)
            solution_score = (teacher_penalty, cells_changed)
            successes += 1
            if best_quality_score is None or solution_score < best_quality_score:
                best_quality_score = solution_score
                best_changed = cells_changed
                best_assignment = dict(state.assigned)
            if successes >= target_successes:
                break

    if successes == 0:
        return ScheduleResult(
            success=False,
            attempts_tried=attempts_tried,
            successes_found=0,
            cells_total=len(inp.slots),
            failure_reason=FAILURE_MESSAGE.format(attempts=attempts_tried),
        )

    final_assignment = {
        slot_id: (None if v == -1 else v) for slot_id, v in best_assignment.items()
    }
    return ScheduleResult(
        success=True,
        assignment=final_assignment,
        cells_changed=best_changed,
        cells_total=len(inp.slots),
        attempts_tried=attempts_tried,
        successes_found=successes,
    )
