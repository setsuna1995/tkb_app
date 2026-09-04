"""Main orchestrator for the randomized greedy + local repair scheduling engine."""
from __future__ import annotations

import random
from collections import defaultdict
from core.models import ScheduleResult, SchedulingConfig, SchedulingInput
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
from core.scheduler.quality import (
    _count_teacher_lone_days, _count_teacher_lone_sessions,
    _count_teacher_missing_mandatory_mornings, _count_teacher_split_sessions,
    _teacher_quality_penalty,
)
from core.scheduler.state import _State
from core.scheduler.swaps import (
    _has_lone_period, _repair_lone_periods, _repair_teacher_lone_sessions,
    _repair_teacher_missing_mandatory_mornings, _try_swap_repair,
)
from core.scheduler.teacher_off import _assign_off_slots


def _check_hard_post_generation_rules(inp: SchedulingInput, state: _State, config: SchedulingConfig) -> tuple[list, int]:
    """Post-generation hard gate for the HĐSP rules that need full-schedule
    visibility (see core/rules_registry.py for tier classification -- as of
    2026-09-03 (third revision, same day), II.3, II.4 and II.8 are
    HARD_POST_GENERATION; II.14 is soft). Reuses the same per-teacher counters
    quality.py uses for soft scoring, but as boolean reject-or-keep gates
    instead of penalty accumulators. Returns (violated_rule_ids, total) where
    violated_rule_ids is a list of *distinct* violated rule IDs, e.g. ["II.4",
    "II.8"] (or [] when fully compliant), and total is the total count of
    individual violation instances across all three rules -- callers that
    rank candidates by "how bad" must use total, not len(violated_rule_ids):
    a candidate with 3 lone-session teachers is objectively worse than one
    with 1 lone-session + 1 split-day teacher, even though the latter spans
    more distinct rule IDs (fix-wave Important #2/#3, 2026-09-03)."""
    violated = []
    total = 0
    mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
    missing = _count_teacher_missing_mandatory_mornings(
        inp.slots, state.assigned, state.slot_teacher, mand_morns,
        min_weekly_periods=getattr(config, "min_weekly_periods_for_mandatory_morning", 10),
    )
    if missing > 0:
        violated.append("II.3")
    total += missing
    if getattr(config, "avoid_teacher_lone_periods", True):
        min_lone_load = getattr(config, "min_weekly_periods_for_lone_penalty", 8)
        # GV được miễn trừ theo tên (vốn có mặt ở trường vì nhiệm vụ khác) phải được
        # bỏ qua ở CẢ cổng cứng này lẫn điểm phạt mềm trong quality.py -- nếu chỉ miễn
        # một bên thì engine vẫn loại phương án vì họ, dù không còn tính điểm phạt.
        lone_exempt = getattr(config, "lone_session_exempt_teacher_ids", frozenset()) or frozenset()
        lone_sessions = _count_teacher_lone_sessions(inp.slots, state.assigned, state.slot_teacher,
                                                     min_weekly_periods=min_lone_load, exempt_teacher_ids=lone_exempt)
        lone_days = _count_teacher_lone_days(inp.slots, state.assigned, state.slot_teacher,
                                              min_weekly_periods=min_lone_load, exempt_teacher_ids=lone_exempt)
        if lone_sessions > 0 or lone_days > 0:
            violated.append("II.4")
        total += lone_sessions + lone_days
        split = _count_teacher_split_sessions(inp.slots, state.assigned, state.slot_teacher,
                                               min_weekly_periods=min_lone_load, exempt_teacher_ids=lone_exempt)
        if split > 0:
            violated.append("II.8")
        total += split
    return violated, total


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
    best_relaxed_assignment = None
    best_relaxed_changed = None
    best_relaxed_score = None
    best_relaxed_violations = None
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
        # Seed the per-teacher remaining-need counter that _pick_best_scored reads.
        # It is kept up to date incrementally from here on (_put_at/_remove_at, plus
        # the SHL reservation below), replacing a full scan of remaining_need per
        # scored candidate.
        for key, n in inp.need.items():
            tid_need = assigned_teacher.get(key)
            if tid_need is not None:
                state.teacher_rem_need[tid_need] += n
        # Shortfall (fewer eligible off-cells than requested) is no longer surfaced
        # into relaxed_rules -- per-week off-slot count is not a hard requirement
        # (user decision 2026-09-03, second revision).
        state.gv_off_slots, _off_shortfall = _assign_off_slots(
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
                    shl_tid = assigned_teacher.get(key)
                    if shl_tid is not None:
                        state.teacher_rem_need[shl_tid] -= 1
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
                state.teacher_rem_need[tid] += 1   # mirror of the reservation above
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
            _repair_teacher_missing_mandatory_mornings(
                inp, state, role_index, assigned_teacher, slots_by_class,
                day_capacity, config, subject_class_allowed_cells, slot_by_coord,
                mandatory_mornings=getattr(config, "mandatory_morning_weekdays", (2, 5, 6)),
                # Tell it which teachers II.4 applies to, so that for those it fills a
                # missing mandatory morning with TWO periods (or leaves it alone)
                # instead of manufacturing a fresh lone session.
                min_lone_load=(getattr(config, "min_weekly_periods_for_lone_penalty", 8)
                                if getattr(config, "avoid_teacher_lone_periods", True) else 0),
            )

        if done:
            _repair_teacher_lone_sessions(inp, state, role_index, assigned_teacher, slots_by_class,
                                          day_capacity, config, subject_class_allowed_cells, slot_by_coord,
                                          min_weekly_periods=getattr(config, "min_weekly_periods_for_lone_penalty", 8),
                                          exempt_teacher_ids=getattr(config, "lone_session_exempt_teacher_ids",
                                                                      frozenset()) or frozenset())

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
            hard_gate_violations, hard_gate_total = _check_hard_post_generation_rules(inp, state, config)

            if not hard_gate_violations:
                solution_score = (teacher_penalty, cells_changed)
                successes += 1
                if best_quality_score is None or solution_score < best_quality_score:
                    best_quality_score = solution_score
                    best_changed = cells_changed
                    best_assignment = dict(state.assigned)
                if successes >= target_successes:
                    break
            else:
                # Rank by the total violation-instance COUNT, not len(hard_gate_violations)
                # (the number of distinct rule IDs violated) -- see
                # _check_hard_post_generation_rules's docstring: a candidate with 3
                # lone-session instances (1 distinct rule) is objectively better than
                # one with 1 lone-session + 1 split-day instance (2 distinct rules),
                # but the old len()-based key ranked it worse (fix-wave Important #2/#3).
                relaxed_score = (hard_gate_total, teacher_penalty, cells_changed)
                if best_relaxed_score is None or relaxed_score < best_relaxed_score:
                    best_relaxed_score = relaxed_score
                    best_relaxed_changed = cells_changed
                    best_relaxed_assignment = dict(state.assigned)
                    best_relaxed_violations = hard_gate_violations

    if successes == 0:
        if best_relaxed_assignment is None:
            return ScheduleResult(
                success=False,
                attempts_tried=attempts_tried,
                successes_found=0,
                cells_total=len(inp.slots),
                failure_reason=FAILURE_MESSAGE.format(attempts=attempts_tried),
            )
        relaxed_rules = [{"rule_id": rid} for rid in best_relaxed_violations]
        final_assignment = {
            slot_id: (None if v == -1 else v) for slot_id, v in best_relaxed_assignment.items()
        }
        return ScheduleResult(
            success=True,
            assignment=final_assignment,
            cells_changed=best_relaxed_changed,
            cells_total=len(inp.slots),
            attempts_tried=attempts_tried,
            successes_found=0,
            relaxed_rules=relaxed_rules,
        )

    relaxed_rules = []
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
        relaxed_rules=relaxed_rules,
    )
