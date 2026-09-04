"""Local search swap-repair and lone period repair routines."""
from __future__ import annotations

from collections import defaultdict
from typing import Optional
from core.models import SchedulingConfig, Slot
from core.scheduler.feasibility import _feasible
from core.scheduler.heuristics import _pick_best_simple
from core.scheduler.placement import _put_at, _remove_at
from core.scheduler.state import _State


def _try_swap_repair(class_id: int, slot: Slot, state: _State, role_index,
                      subjects: list, assigned_teacher: dict,
                      slots_by_class: dict, day_capacity: Optional[dict] = None,
                      config: Optional[SchedulingConfig] = None,
                      subject_class_allowed_cells: Optional[dict] = None) -> bool:
    ts = slot.ts
    for other in slots_by_class[class_id]:
        if other.slot_id == slot.slot_id:
            continue
        if state.assigned.get(other.slot_id, None) in (None, -1) or state.pinned.get(other.slot_id):
            continue
        moved_subject, moved_teacher = _remove_at(state, other, role_index)
        if _feasible(class_id, ts, moved_subject, moved_teacher, state, role_index, day_capacity, config,
                      subject_class_allowed_cells):
            _put_at(state, slot, moved_subject, moved_teacher, role_index)
            refill = _pick_best_simple(class_id, other, state, role_index, subjects, assigned_teacher,
                                        day_capacity, config, subject_class_allowed_cells)
            if refill is not None:
                _put_at(state, other, refill[0], refill[1], role_index)
                return True
            _remove_at(state, slot, role_index)
            _put_at(state, other, moved_subject, moved_teacher, role_index)
        else:
            _put_at(state, other, moved_subject, moved_teacher, role_index)
    return False


def _repair_lone_periods(inp, state: _State, role_index,
                          assigned_teacher: dict, slots_by_class: dict,
                          day_capacity: Optional[dict], config: Optional[SchedulingConfig] = None,
                          subject_class_allowed_cells: Optional[dict] = None) -> None:
    for slot in inp.slots:
        ts = slot.ts
        if ts.period != 2:
            continue
        class_id = slot.class_id
        if not state.occupied.get((class_id, ts.weekday, ts.session, 1), False):
            continue
        current = state.assigned.get(slot.slot_id)
        if current not in (None, -1):
            continue
        if current == -1:
            state.assigned[slot.slot_id] = None
            state.rem_slot_count[class_id] += 1
        pick = _pick_best_simple(class_id, slot, state, role_index, inp.subjects, assigned_teacher,
                                  day_capacity, config, subject_class_allowed_cells)
        if pick is not None:
            _put_at(state, slot, pick[0], pick[1], role_index)
        else:
            _try_swap_repair(class_id, slot, state, role_index, inp.subjects,
                              assigned_teacher, slots_by_class, day_capacity, config,
                              subject_class_allowed_cells)


def _has_lone_period(inp, state: _State) -> bool:
    filled_count: dict = defaultdict(int)
    total_count: dict = defaultdict(int)
    for slot in inp.slots:
        key = (slot.class_id, slot.ts.weekday, slot.ts.session)
        total_count[key] += 1
        if state.assigned.get(slot.slot_id, None) not in (None, -1):
            filled_count[key] += 1
    return any(count == 1 and total_count[key] >= 2 for key, count in filled_count.items())


def _repair_teacher_lone_sessions(inp, state: _State, role_index,
                                   assigned_teacher: dict, slots_by_class: dict,
                                   day_capacity: Optional[dict] = None,
                                   config: Optional[SchedulingConfig] = None,
                                   subject_class_allowed_cells: Optional[dict] = None,
                                   slot_by_coord: Optional[dict] = None,
                                   min_weekly_periods: int = 0,
                                   exempt_teacher_ids: frozenset = frozenset()) -> None:
    """Finds all teacher sessions with exactly 1 period, and attempts to eliminate them
    either by:
    1. Evacuate: Moving that 1 period to another session where the teacher already teaches,
       leaving the original session with 0 periods (giving the teacher a full session off).
    2. Consolidate: Moving a period of this teacher from another session into this session,
       making this session have >= 2 periods.

    min_weekly_periods (default 0 = "no exemption, repair everyone", same
    default-off convention as quality.py's counters): a teacher whose total
    weekly load is below this threshold is exempt from the II.4 hard gate
    (see engine.py/quality.py) anyway, so their lone sessions are excluded
    from consideration here too -- otherwise this bounded repair loop
    (max_rounds=3, first-improving-move only) wastes attempts on teachers
    who can never violate the gate, leaving fewer rounds for teachers who
    actually count (fix-wave Important #6, 2026-09-03).
    """
    config = config or SchedulingConfig()
    if not getattr(config, "avoid_teacher_lone_periods", True):
        return

    if slot_by_coord is None:
        slot_by_coord = {(s.class_id, s.ts.weekday, s.ts.session, s.ts.period): s for s in inp.slots}

    teacher_totals: dict = defaultdict(int)
    for (tid, _wd, _sess), periods in state.teacher_session_periods.items():
        teacher_totals[tid] += len(periods)

    max_rounds = 3
    # Strategy 3 (3-way rotation) is the expensive one, so it is bounded: at most
    # this many candidate target sessions and third cells per lone session, and a
    # hard ceiling on rotations attempted across the whole call. It only runs at
    # all when both 1-for-1 strategies have already failed for that session.
    max_chain_targets = 3
    max_chain_z = 12
    chain_budget = 240

    for _ in range(max_rounds):
        lone_teacher_sessions = [
            (tid, wd, sess)
            for (tid, wd, sess), periods in list(state.teacher_session_periods.items())
            if len(periods) == 1 and tid > 0
            and (min_weekly_periods <= 0 or teacher_totals[tid] >= min_weekly_periods)
            and tid not in exempt_teacher_ids
        ]
        if not lone_teacher_sessions:
            break

        improved = False
        for tid, wd_lone, sess_lone in lone_teacher_sessions:
            # Per-teacher flag, deliberately separate from the round-level `improved`.
            # They used to be the same variable, which silently crippled the pass:
            # once ANY teacher was repaired in a round, every later teacher in that
            # same round hit `if improved: break` after its FIRST candidate target
            # session and skipped Strategy 2 entirely (its `if not improved:` guard
            # was already False). With a handful of lone sessions that barely showed;
            # once min_weekly_periods_for_lone_penalty was lowered to 8 (2026-09-04)
            # and ~25 sessions came into scope, it capped the pass at roughly one
            # real repair per round (fix 2026-09-04).
            fixed_this = False
            periods_lone = state.teacher_session_periods.get((tid, wd_lone, sess_lone), [])
            if len(periods_lone) != 1:
                continue
            period_lone = periods_lone[0]

            lone_slot = None
            for slot in inp.slots:
                if (slot.ts.weekday == wd_lone and slot.ts.session == sess_lone
                        and slot.ts.period == period_lone and state.slot_teacher.get(slot.slot_id) == tid):
                    lone_slot = slot
                    break

            if lone_slot is None or state.pinned.get(lone_slot.slot_id):
                continue

            cid_lone = lone_slot.class_id
            sid_lone = state.assigned.get(lone_slot.slot_id)
            if sid_lone in (None, -1):
                continue

            block_n = role_index.block_size.get(sid_lone, 1)
            if block_n > 1 and len(state.placed.get((cid_lone, sid_lone, wd_lone), [])) > 1:
                continue

            # Strategy 1: Evacuate lone_slot to another session where teacher `tid` already teaches
            target_sessions = [
                (wd, sess) for (t, wd, sess), pers in state.teacher_session_periods.items()
                if t == tid and (wd != wd_lone or sess != sess_lone)
                and 1 <= len(pers) < config.max_periods_per_session
            ]

            for wd_tgt, sess_tgt in target_sessions:
                for other_slot in slots_by_class[cid_lone]:
                    if (other_slot.ts.weekday != wd_tgt or other_slot.ts.session != sess_tgt
                            or state.pinned.get(other_slot.slot_id)):
                        continue
                    sid_other = state.assigned.get(other_slot.slot_id)
                    if sid_other in (None, -1):
                        continue
                    tid_other = state.slot_teacher.get(other_slot.slot_id)
                    if tid_other is None or tid_other == tid:
                        continue

                    block_n_other = role_index.block_size.get(sid_other, 1)
                    if block_n_other > 1 and len(state.placed.get((cid_lone, sid_other, wd_tgt), [])) > 1:
                        continue

                    _remove_at(state, lone_slot, role_index)
                    _remove_at(state, other_slot, role_index)

                    feas_lone_at_other = _feasible(
                        cid_lone, other_slot.ts, sid_lone, tid, state, role_index,
                        day_capacity, config, subject_class_allowed_cells
                    )
                    feas_other_at_lone = _feasible(
                        cid_lone, lone_slot.ts, sid_other, tid_other, state, role_index,
                        day_capacity, config, subject_class_allowed_cells
                    )

                    if feas_lone_at_other and feas_other_at_lone:
                        _put_at(state, other_slot, sid_lone, tid, role_index)
                        _put_at(state, lone_slot, sid_other, tid_other, role_index)
                        fixed_this = True
                        break
                    else:
                        _put_at(state, lone_slot, sid_lone, tid, role_index)
                        _put_at(state, other_slot, sid_other, tid_other, role_index)

                if fixed_this:
                    break

            # Strategy 2: Consolidate by moving a period of `tid` in another class `cid_other` to (wd_lone, sess_lone)
            if not fixed_this:
                for cls in inp.classes:
                    cid_other = cls.class_id
                    if cid_other == cid_lone:
                        continue
                    # Find a slot in cid_other where `tid` teaches at another session
                    for other_slot in slots_by_class.get(cid_other, []):
                        if (other_slot.ts.weekday == wd_lone and other_slot.ts.session == sess_lone
                                or state.pinned.get(other_slot.slot_id)):
                            continue
                        if state.slot_teacher.get(other_slot.slot_id) != tid:
                            continue
                        sid_other = state.assigned.get(other_slot.slot_id)
                        if sid_other in (None, -1):
                            continue

                        block_n_other = role_index.block_size.get(sid_other, 1)
                        if block_n_other > 1 and len(state.placed.get((cid_other, sid_other, other_slot.ts.weekday), [])) > 1:
                            continue

                        # Find a target slot in cid_other at (wd_lone, sess_lone)
                        for target_slot in slots_by_class.get(cid_other, []):
                            if (target_slot.ts.weekday != wd_lone or target_slot.ts.session != sess_lone
                                    or state.pinned.get(target_slot.slot_id)):
                                continue
                            sid_target = state.assigned.get(target_slot.slot_id)
                            if sid_target in (None, -1):
                                continue
                            tid_target = state.slot_teacher.get(target_slot.slot_id)
                            if tid_target is None or tid_target == tid:
                                continue

                            block_n_target = role_index.block_size.get(sid_target, 1)
                            if block_n_target > 1 and len(state.placed.get((cid_other, sid_target, wd_lone), [])) > 1:
                                continue

                            _remove_at(state, other_slot, role_index)
                            _remove_at(state, target_slot, role_index)

                            feas_other_at_target = _feasible(
                                cid_other, target_slot.ts, sid_other, tid, state, role_index,
                                day_capacity, config, subject_class_allowed_cells
                            )
                            feas_target_at_other = _feasible(
                                cid_other, other_slot.ts, sid_target, tid_target, state, role_index,
                                day_capacity, config, subject_class_allowed_cells
                            )

                            if feas_other_at_target and feas_target_at_other:
                                _put_at(state, target_slot, sid_other, tid, role_index)
                                _put_at(state, other_slot, sid_target, tid_target, role_index)
                                fixed_this = True
                                break
                            else:
                                _put_at(state, other_slot, sid_other, tid, role_index)
                                _put_at(state, target_slot, sid_target, tid_target, role_index)

                        if fixed_this:
                            break
                    if fixed_this:
                        break

            # Strategy 3: 3-way rotation inside the lone period's own class --
            # lone_slot -> slot_y (a cell in a session where this teacher already
            # teaches), slot_y's occupant -> slot_z, slot_z's occupant -> lone_slot.
            # Reaches cases where the plain 1-for-1 swap of Strategy 1 is blocked
            # purely because slot_y's occupant cannot be placed at lone_slot.
            if not fixed_this and chain_budget > 0:
                chain_targets = [
                    (wd, sess) for (t, wd, sess), pers in state.teacher_session_periods.items()
                    if t == tid and (wd != wd_lone or sess != sess_lone)
                    and 1 <= len(pers) < config.max_periods_per_session
                ][:max_chain_targets]

                for wd_tgt, sess_tgt in chain_targets:
                    for slot_y in slots_by_class[cid_lone]:
                        if (slot_y.ts.weekday != wd_tgt or slot_y.ts.session != sess_tgt
                                or state.pinned.get(slot_y.slot_id)):
                            continue
                        sid_y = state.assigned.get(slot_y.slot_id)
                        if sid_y in (None, -1):
                            continue
                        tid_y = state.slot_teacher.get(slot_y.slot_id)
                        if tid_y is None or tid_y == tid:
                            continue
                        if (role_index.block_size.get(sid_y, 1) > 1
                                and len(state.placed.get((cid_lone, sid_y, wd_tgt), [])) > 1):
                            continue

                        tried_z = 0
                        for slot_z in slots_by_class[cid_lone]:
                            if chain_budget <= 0 or tried_z >= max_chain_z:
                                break
                            if slot_z.slot_id in (lone_slot.slot_id, slot_y.slot_id):
                                continue
                            if state.pinned.get(slot_z.slot_id):
                                continue
                            sid_z = state.assigned.get(slot_z.slot_id)
                            if sid_z in (None, -1):
                                continue
                            tid_z = state.slot_teacher.get(slot_z.slot_id)
                            if tid_z is None or tid_z == tid:
                                continue
                            if (role_index.block_size.get(sid_z, 1) > 1
                                    and len(state.placed.get((cid_lone, sid_z, slot_z.ts.weekday), [])) > 1):
                                continue

                            tried_z += 1
                            chain_budget -= 1

                            # Only the sessions of the three teachers actually touched
                            # can gain or lose a lone session, so watching those six
                            # buckets is enough to tell a real fix from a reshuffle.
                            watch_keys = {
                                (tid, wd_lone, sess_lone),
                                (tid, wd_tgt, sess_tgt),
                                (tid_y, wd_tgt, sess_tgt),
                                (tid_y, slot_z.ts.weekday, slot_z.ts.session),
                                (tid_z, slot_z.ts.weekday, slot_z.ts.session),
                                (tid_z, wd_lone, sess_lone),
                            }
                            before_lone = _count_lone_among(state, watch_keys)

                            payload = _rotate_three_slots(
                                state, role_index, cid_lone, lone_slot, slot_y, slot_z,
                                day_capacity, config, subject_class_allowed_cells,
                            )
                            if payload is None:
                                continue
                            if _count_lone_among(state, watch_keys) >= before_lone:
                                # Net zero (or worse) -- the lone session just moved
                                # onto one of the other two teachers. Not a fix.
                                _undo_rotation(state, role_index, payload)
                                continue

                            fixed_this = True
                            break

                        if fixed_this:
                            break
                    if fixed_this:
                        break

            if fixed_this:
                improved = True

        if not improved:
            break


def _rotate_three_slots(state: _State, role_index, class_id: int, slot_x, slot_y, slot_z,
                         day_capacity: Optional[dict], config: SchedulingConfig,
                         subject_class_allowed_cells: Optional[dict]):
    """Rotate the contents of three slots of the SAME class: x -> y, y -> z, z -> x.

    This is the 3-cycle generalisation of _exchange_slots, for the common case
    where a straight 1-for-1 swap x <-> y is blocked only because y's occupant
    cannot go to x -- routing y's occupant to a third cell z, and z's occupant
    back to x, can succeed where the 2-cycle fails.

    Keeping all three cells inside one class means the class's multiset of
    subjects is untouched (its per-subject weekly quota still holds); only the
    positions move.

    Feasibility is checked INCREMENTALLY -- each placement is validated against
    the state with the previous placements already applied -- because the three
    moves interact (same class, often the same day). Returns an undo payload on
    success, or None on failure, in which case the state is restored exactly.
    """
    trio = []
    for slot in (slot_x, slot_y, slot_z):
        sid = state.assigned.get(slot.slot_id)
        tid = state.slot_teacher.get(slot.slot_id)
        if sid in (None, -1) or tid is None:
            return None
        trio.append((slot, sid, tid))

    (sx, sid_x, tid_x), (sy, sid_y, tid_y), (sz, sid_z, tid_z) = trio

    _remove_at(state, sx, role_index)
    _remove_at(state, sy, role_index)
    _remove_at(state, sz, role_index)

    placed = []

    def _rollback():
        for slot in placed:
            _remove_at(state, slot, role_index)
        _put_at(state, sx, sid_x, tid_x, role_index)
        _put_at(state, sy, sid_y, tid_y, role_index)
        _put_at(state, sz, sid_z, tid_z, role_index)

    # Refill in ascending (weekday, session, period) order. All three cells are
    # empty at this point, and BAT_LIEN_MACH forbids placing into period p while
    # p-1 of the same class/day/session is empty -- filling low periods first
    # means a hole this rotation opened is always closed again before anything
    # above it is checked. Without this the rotation fails spuriously whenever
    # two of its cells share a session.
    moves = sorted(
        ((sy, sid_x, tid_x), (sz, sid_y, tid_y), (sx, sid_z, tid_z)),
        key=lambda m: (m[0].ts.weekday, 0 if m[0].ts.session == "S" else 1, m[0].ts.period),
    )
    for target, sid, tid in moves:
        if not _feasible(class_id, target.ts, sid, tid, state, role_index,
                          day_capacity, config, subject_class_allowed_cells):
            _rollback()
            return None
        _put_at(state, target, sid, tid, role_index)
        placed.append(target)

    return (sx, sy, sz, sid_x, tid_x, sid_y, tid_y, sid_z, tid_z)


def _undo_rotation(state: _State, role_index, payload) -> None:
    """Reverse a _rotate_three_slots that was applied earlier."""
    sx, sy, sz, sid_x, tid_x, sid_y, tid_y, sid_z, tid_z = payload
    _remove_at(state, sx, role_index)
    _remove_at(state, sy, role_index)
    _remove_at(state, sz, role_index)
    _put_at(state, sx, sid_x, tid_x, role_index)
    _put_at(state, sy, sid_y, tid_y, role_index)
    _put_at(state, sz, sid_z, tid_z, role_index)


def _count_lone_among(state: _State, keys) -> int:
    """How many of these (teacher, weekday, session) buckets currently hold
    exactly one period. Used to make sure a rotation does not simply relocate a
    lone session onto one of the other teachers it touches."""
    return sum(1 for key in keys if len(state.teacher_session_periods.get(key, [])) == 1)


def _exchange_slots(state: _State, role_index, class_id: int, slot_a, slot_b,
                     day_capacity: Optional[dict], config: SchedulingConfig,
                     subject_class_allowed_cells: Optional[dict]):
    """Exchange the (subject, teacher) contents of two slots in the SAME class,
    feasibility-checked both ways. Returns an undo payload on success, or None
    on failure -- on failure the state is left byte-for-byte as it was.

    Extracted so a caller can chain several exchanges and roll them all back
    if the combination turns out not to be worth keeping (see
    _repair_teacher_missing_mandatory_mornings's all-or-nothing pairing)."""
    sid_a = state.assigned.get(slot_a.slot_id)
    tid_a = state.slot_teacher.get(slot_a.slot_id)
    sid_b = state.assigned.get(slot_b.slot_id)
    tid_b = state.slot_teacher.get(slot_b.slot_id)
    if sid_a in (None, -1) or sid_b in (None, -1) or tid_a is None or tid_b is None:
        return None

    _remove_at(state, slot_a, role_index)
    _remove_at(state, slot_b, role_index)

    ok = (_feasible(class_id, slot_b.ts, sid_a, tid_a, state, role_index,
                    day_capacity, config, subject_class_allowed_cells)
          and _feasible(class_id, slot_a.ts, sid_b, tid_b, state, role_index,
                        day_capacity, config, subject_class_allowed_cells))
    if ok:
        _put_at(state, slot_b, sid_a, tid_a, role_index)
        _put_at(state, slot_a, sid_b, tid_b, role_index)
        return (slot_a, slot_b, sid_a, tid_a, sid_b, tid_b)

    _put_at(state, slot_a, sid_a, tid_a, role_index)
    _put_at(state, slot_b, sid_b, tid_b, role_index)
    return None


def _undo_exchange(state: _State, role_index, payload) -> None:
    """Reverse an _exchange_slots that was applied earlier."""
    slot_a, slot_b, sid_a, tid_a, sid_b, tid_b = payload
    _remove_at(state, slot_a, role_index)
    _remove_at(state, slot_b, role_index)
    _put_at(state, slot_a, sid_a, tid_a, role_index)
    _put_at(state, slot_b, sid_b, tid_b, role_index)


def _repair_teacher_missing_mandatory_mornings(inp, state: _State, role_index,
                                                assigned_teacher: dict, slots_by_class: dict,
                                                day_capacity: Optional[dict] = None,
                                                config: Optional[SchedulingConfig] = None,
                                                subject_class_allowed_cells: Optional[dict] = None,
                                                slot_by_coord: Optional[dict] = None,
                                                mandatory_mornings: tuple = (2, 5, 6),
                                                min_weekly_periods: int = 10,
                                                min_lone_load: int = 0) -> None:
    """Finds every teacher whose total weekly load is >= min_weekly_periods (the
    II.3 hard-gate threshold -- see quality.py:_count_teacher_missing_mandatory_mornings)
    and who has ZERO periods on one of the mandatory mornings (mandatory_mornings,
    default Mon/Thu/Fri), and fills it by exchanging periods of that teacher from a
    NON-mandatory weekday into the missing mandatory morning -- same-class 1-for-1
    exchanges with whoever else is teaching those cells, mirroring
    _repair_teacher_lone_sessions's Strategy 1 (Evacuate).

    How many periods it moves depends on whether the teacher is subject to II.4:

    * min_lone_load == 0, or the teacher's weekly load is below it (II.4-exempt):
      ONE period is enough -- a single period in that session cannot be counted
      as a lone session for them.
    * teacher's load >= min_lone_load (II.4 applies): moving a SINGLE period would
      simply trade an II.3 violation for a brand-new II.4 lone session, since the
      teacher would then have exactly 1 period in that morning. So TWO periods are
      moved in, as an all-or-nothing pair: if no compatible second exchange exists,
      the first one is rolled back and the II.3 violation is left standing rather
      than manufacturing a lone session (fix 2026-09-04, after real Tuan 2 data
      showed II.3 repairs inflating the II.4 count).

    Destination slots are PINNED once filled: _repair_teacher_lone_sessions (which
    already skips pinned slots at both ends) runs right after this one in
    engine.py, and without the pin it would be free to evacuate the very periods
    this repair just placed, silently undoing the fix.

    A 1-for-1 exchange never changes either teacher's total weekly period count, so
    teacher_totals (computed once up front, same convention as the sibling function
    above) stays valid for the whole pass.
    """
    config = config or SchedulingConfig()

    teacher_totals: dict = defaultdict(int)
    for (tid, _wd, _sess), periods in state.teacher_session_periods.items():
        teacher_totals[tid] += len(periods)

    # (weekday, session, period) -> slots. Locating "which slot currently holds
    # this teacher's period" is then a small bucket scan rather than a full sweep
    # of inp.slots per candidate -- this whole function runs inside the engine's
    # 6000-attempt loop, so the difference is not academic.
    slots_at: dict = defaultdict(list)
    for slot in inp.slots:
        slots_at[(slot.ts.weekday, slot.ts.session, slot.ts.period)].append(slot)

    max_rounds = 3
    max_first_tries = 3   # bounds the paired search: at most 3 different "first" exchanges

    for _ in range(max_rounds):
        missing_pairs = [
            (tid, wd)
            for tid, total in teacher_totals.items()
            if tid > 0 and total >= min_weekly_periods
            for wd in mandatory_mornings
            if len(state.teacher_session_periods.get((tid, wd, "S"), [])) == 0
        ]
        if not missing_pairs:
            break

        improved = False
        for tid, wd_missing in missing_pairs:
            # Per-(teacher, weekday) flag, separate from the round-level `improved`
            # -- same reason as _repair_teacher_lone_sessions above: a shared flag
            # would let the first successful fix in a round cut every later one
            # short (fix 2026-09-04).
            fixed_this = False

            # Candidate same-class exchanges: move one of this teacher's periods
            # from a non-mandatory weekday morning into the missing morning.
            candidates = []
            for (t, wd_src, sess_src), periods in list(state.teacher_session_periods.items()):
                if t != tid or sess_src != "S" or wd_src in mandatory_mornings:
                    continue
                for period_src in list(periods):
                    source_slot = None
                    for slot in slots_at.get((wd_src, "S", period_src), ()):
                        if state.slot_teacher.get(slot.slot_id) == tid:
                            source_slot = slot
                            break
                    if source_slot is None or state.pinned.get(source_slot.slot_id):
                        continue
                    cid = source_slot.class_id
                    sid_src = state.assigned.get(source_slot.slot_id)
                    if sid_src in (None, -1):
                        continue
                    if (role_index.block_size.get(sid_src, 1) > 1
                            and len(state.placed.get((cid, sid_src, wd_src), [])) > 1):
                        continue
                    for dest_slot in slots_by_class[cid]:
                        if (dest_slot.ts.weekday != wd_missing or dest_slot.ts.session != "S"
                                or state.pinned.get(dest_slot.slot_id)):
                            continue
                        sid_dst = state.assigned.get(dest_slot.slot_id)
                        if sid_dst in (None, -1):
                            continue
                        tid_dst = state.slot_teacher.get(dest_slot.slot_id)
                        if tid_dst is None or tid_dst == tid:
                            continue
                        if (role_index.block_size.get(sid_dst, 1) > 1
                                and len(state.placed.get((cid, sid_dst, wd_missing), [])) > 1):
                            continue
                        candidates.append((cid, source_slot, dest_slot))

            if not candidates:
                continue

            needs_pair = 0 < min_lone_load <= teacher_totals[tid]

            if not needs_pair:
                for cid, src, dst in candidates:
                    if _exchange_slots(state, role_index, cid, src, dst, day_capacity,
                                        config, subject_class_allowed_cells) is not None:
                        state.pinned[dst.slot_id] = True
                        fixed_this = True
                        break
            else:
                for i, (cid1, src1, dst1) in enumerate(candidates):
                    if i >= max_first_tries:
                        break
                    payload1 = _exchange_slots(state, role_index, cid1, src1, dst1, day_capacity,
                                                config, subject_class_allowed_cells)
                    if payload1 is None:
                        continue

                    used = {src1.slot_id, dst1.slot_id}
                    for cid2, src2, dst2 in candidates:
                        if src2.slot_id in used or dst2.slot_id in used:
                            continue
                        # Re-validate against the state as it stands AFTER exchange 1.
                        if state.slot_teacher.get(src2.slot_id) != tid:
                            continue
                        if state.assigned.get(src2.slot_id) in (None, -1):
                            continue
                        if state.assigned.get(dst2.slot_id) in (None, -1):
                            continue
                        tid_dst2 = state.slot_teacher.get(dst2.slot_id)
                        if tid_dst2 is None or tid_dst2 == tid:
                            continue
                        if state.pinned.get(src2.slot_id) or state.pinned.get(dst2.slot_id):
                            continue
                        if _exchange_slots(state, role_index, cid2, src2, dst2, day_capacity,
                                            config, subject_class_allowed_cells) is not None:
                            state.pinned[dst1.slot_id] = True
                            state.pinned[dst2.slot_id] = True
                            fixed_this = True
                            break

                    if fixed_this:
                        break
                    _undo_exchange(state, role_index, payload1)

            if fixed_this:
                improved = True

        if not improved:
            break
