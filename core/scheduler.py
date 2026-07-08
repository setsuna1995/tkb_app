"""Port of XepTKB.bas: randomized greedy construction + local swap-repair +
best-of-N restart, preserving every constraint from the original VBA macro.

This module is intentionally Streamlit-free and DB-free: it consumes a plain
SchedulingInput and returns a plain ScheduleResult, so it can be unit tested
in isolation (see tests/test_scheduler.py).
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from core.models import ScheduleResult, SchedulingInput, Slot, TimeSlot
from core.roles import resolve_roles

MAX_GV_BUOI = 4          # teacher cap per session (never a "full" 5-period session)
SO_LAN_THU = 6000         # max attempts (nâng từ 2000: ràng buộc "không để lẻ 1 tiết/buổi"
                          # khiến các khung có buổi chiều cần nhiều lượt thử hơn mới ra)
SO_PA_TOT = 25            # stop early once this many valid attempts are found
NGUONG_KHOA = 60          # attempts before shuffling timeslot order / discounting the "keep old" bonus
CAP_TIET_NGAY = 5         # fallback cap khi không tính được theo khung; thực tế trần mỗi
                          # ngày = tổng số ô (sáng+chiều) khung của lớp đó ngày đó (xem
                          # day_capacity trong run()), để không chặn oan khung > 5 tiết/ngày
BAT_NGHI_1_BUOI = True    # every teacher gets exactly 1 half-day-off slot/week
BAT_LIEN_MACH = True      # no gaps within a session for a class
IDLE_DAY_BONUS = 30       # điểm thưởng mềm khi đặt tiết vào ngày GV đang trống hẳn
                          # (< 100 = remaining_need*100 nên không vượt môn thiếu tiết;
                          # < 50 = phạt dàn-môn nên heuristic đó vẫn ưu tiên hơn) --
                          # cố gắng không để GV trống trọn 1 ngày làm việc

# Buổi không được chọn làm buổi nghỉ của GV: sáng Thứ 2/5/6 (hoạt động cố định
# buổi sáng những ngày này), và chiều Thứ 5/6 (đã bị khoá hẳn khỏi TKB ở
# core/frame.py, dành cho ôn bồi dưỡng -- không phải "buổi nghỉ" GV được chọn).
FORBIDDEN_OFF_CELLS = {(2, "S"), (5, "S"), (6, "S"), (5, "C"), (6, "C")}

FAILURE_MESSAGE = (
    "Không xếp được sau {attempts} lần thử. Nguyên nhân hay gặp:\n"
    "(1) GV HDTN (GVCN) trùng nhau giữa 2 lớp - chào cờ & SHL diễn ra đồng thời "
    "nên MỖI LỚP cần GVCN riêng;\n"
    "(2) GV_Bận cấm quá nhiều giờ của GV tải năng;\n"
    "(3) định mức SoTiet vượt khả năng khung tiết."
)


@dataclass
class _State:
    remaining_need: dict
    busy: set
    session_count: dict = field(default_factory=lambda: defaultdict(int))
    placed: dict = field(default_factory=lambda: defaultdict(list))
    day_count: dict = field(default_factory=lambda: defaultdict(int))
    occupied: dict = field(default_factory=dict)
    heavy_at: dict = field(default_factory=dict)
    gv_off_slots: dict = field(default_factory=dict)
    rem_need_count: dict = field(default_factory=lambda: defaultdict(int))
    rem_slot_count: dict = field(default_factory=lambda: defaultdict(int))
    assigned: dict = field(default_factory=dict)     # slot_id -> Optional[int] (-1 = intentionally empty)
    pinned: dict = field(default_factory=dict)        # slot_id -> bool
    slot_teacher: dict = field(default_factory=dict)  # slot_id -> teacher_id
    shl_days: set = field(default_factory=set)        # {(class_id, weekday)} nơi greedy KHÔNG đặt HDTN (dành cho SHL ghim)


def _build_effective_assigned_teacher(inp: SchedulingInput) -> dict:
    """Fill in a synthetic, per-(subject,class)-unique teacher id for any cell
    PhanCong left blank -- mirrors the VBA's '?class#subject' placeholder so the
    subject can still be scheduled without creating a fake cross-class conflict.
    """
    effective = dict(inp.assigned_teacher)
    for subj in inp.subjects:
        for cls in inp.classes:
            key = (subj.subject_id, cls.class_id)
            if inp.need.get(key, 0) > 0 and key not in effective:
                effective[key] = -(subj.subject_id * 100_000 + cls.class_id)
    return effective


def _feasible(class_id: int, ts: TimeSlot, subject_id: int, teacher_id: int,
              state: _State, role_index, day_capacity: Optional[dict] = None) -> bool:
    if (teacher_id, ts.ts_id) in state.busy:
        return False
    if state.session_count[(teacher_id, ts.weekday, ts.session)] >= MAX_GV_BUOI:
        return False
    if BAT_NGHI_1_BUOI and (ts.weekday, ts.session) in state.gv_off_slots.get(teacher_id, ()):
        return False
    if subject_id == role_index.gdtc_id and ts.period == 5:
        return False
    cap_today = day_capacity.get((class_id, ts.weekday), CAP_TIET_NGAY) if day_capacity else CAP_TIET_NGAY
    if state.day_count[(class_id, ts.weekday)] >= cap_today:
        return False
    if BAT_LIEN_MACH and ts.period > 1:
        if not state.occupied.get((class_id, ts.weekday, ts.session, ts.period - 1), False):
            return False
    positions = state.placed[(class_id, subject_id, ts.weekday)]
    cap_d = 2 if subject_id in role_index.kep_ids else 1
    if len(positions) >= cap_d:
        return False
    if len(positions) == 1:
        p_session, p_period = positions[0]
        if p_session != ts.session or abs(p_period - ts.period) != 1:
            return False
    if subject_id in role_index.heavy_ids:
        for w in (1, 2):
            if w <= ts.period <= w + 3:
                all_heavy = True
                for offset in range(4):
                    pos = w + offset
                    if not (state.heavy_at.get((class_id, ts.weekday, ts.session, pos), False) or pos == ts.period):
                        all_heavy = False
                        break
                if all_heavy:
                    return False
    return True


def _put_at(state: _State, slot: Slot, subject_id: int, teacher_id: int, role_index) -> None:
    ts = slot.ts
    state.assigned[slot.slot_id] = subject_id
    state.slot_teacher[slot.slot_id] = teacher_id
    state.remaining_need[(subject_id, slot.class_id)] -= 1
    state.busy.add((teacher_id, ts.ts_id))
    state.session_count[(teacher_id, ts.weekday, ts.session)] += 1
    state.placed[(slot.class_id, subject_id, ts.weekday)].append((ts.session, ts.period))
    state.day_count[(slot.class_id, ts.weekday)] += 1
    state.occupied[(slot.class_id, ts.weekday, ts.session, ts.period)] = True
    if subject_id in role_index.heavy_ids:
        state.heavy_at[(slot.class_id, ts.weekday, ts.session, ts.period)] = True
    state.rem_need_count[slot.class_id] -= 1
    state.rem_slot_count[slot.class_id] -= 1


def _remove_at(state: _State, slot: Slot, role_index) -> tuple:
    subject_id = state.assigned[slot.slot_id]
    teacher_id = state.slot_teacher.pop(slot.slot_id)
    ts = slot.ts
    state.assigned[slot.slot_id] = None
    state.remaining_need[(subject_id, slot.class_id)] += 1
    state.busy.discard((teacher_id, ts.ts_id))
    state.session_count[(teacher_id, ts.weekday, ts.session)] -= 1
    state.placed[(slot.class_id, subject_id, ts.weekday)].remove((ts.session, ts.period))
    state.day_count[(slot.class_id, ts.weekday)] -= 1
    state.occupied[(slot.class_id, ts.weekday, ts.session, ts.period)] = False
    if subject_id in role_index.heavy_ids:
        state.heavy_at[(slot.class_id, ts.weekday, ts.session, ts.period)] = False
    state.rem_need_count[slot.class_id] += 1
    state.rem_slot_count[slot.class_id] += 1
    return subject_id, teacher_id


def _repair_lone_periods(inp: SchedulingInput, state: _State, role_index,
                          assigned_teacher: dict, slots_by_class: dict,
                          day_capacity: Optional[dict]) -> None:
    """Best-effort: for every (class, weekday, session) left with only period 1
    filled (out of >=2 periods available -- BAT_LIEN_MACH means a lone period is
    always period 1), try to also fill period 2 so the session isn't stranded at
    1 period. Cheaper than rejecting the whole attempt; _has_lone_period() is
    still the authoritative check run afterwards in case a fix isn't found here.
    """
    for slot in inp.slots:
        ts = slot.ts
        if ts.period != 2:
            continue
        class_id = slot.class_id
        if not state.occupied.get((class_id, ts.weekday, ts.session, 1), False):
            continue
        current = state.assigned.get(slot.slot_id)
        if current not in (None, -1):
            continue  # period 2 already filled -- fine
        if current == -1:
            state.assigned[slot.slot_id] = None
            state.rem_slot_count[class_id] += 1
        pick = _pick_best_simple(class_id, slot, state, role_index, inp.subjects, assigned_teacher, day_capacity)
        if pick is not None:
            _put_at(state, slot, pick[0], pick[1], role_index)
        else:
            _try_swap_repair(class_id, slot, state, role_index, inp.subjects,
                              assigned_teacher, slots_by_class, day_capacity)


def _has_lone_period(inp: SchedulingInput, state: _State) -> bool:
    """True if any (class, weekday, session) that has 2+ periods available ends up
    with exactly 1 of them filled -- a session with only 1 period available to
    begin with isn't "stranded" by using that 1 period.

    order can get shuffled mid-run (see NGUONG_KHOA), so period 1 of a session
    isn't reliably decided before period 2 -- checking mid-loop can't catch every
    case. Validating the finished attempt here is simple and always correct.
    """
    filled_count: dict = defaultdict(int)
    total_count: dict = defaultdict(int)
    for slot in inp.slots:
        key = (slot.class_id, slot.ts.weekday, slot.ts.session)
        total_count[key] += 1
        if state.assigned.get(slot.slot_id, None) not in (None, -1):
            filled_count[key] += 1
    return any(count == 1 and total_count[key] >= 2 for key, count in filled_count.items())


def _pick_best_scored(class_id: int, slot: Slot, state: _State, role_index,
                       subjects: list, assigned_teacher: dict, pu: float, rng: random.Random,
                       day_capacity: Optional[dict] = None) -> Optional[tuple]:
    ts = slot.ts
    best_subject = None
    best_teacher = None
    best_score = -1.0
    for subj in subjects:
        key = (subj.subject_id, class_id)
        if state.remaining_need.get(key, 0) <= 0:
            continue
        # ngày chứa SHL: không để greedy đặt HDTN (tiết chủ đề) vào đó -- ô SHL đã
        # được giữ chỗ và HDTN cap 1 tiết/ngày nên phải chừa cả ngày cho ô ghim.
        if subj.subject_id == role_index.hdtn_id and (class_id, ts.weekday) in state.shl_days:
            continue
        teacher_id = assigned_teacher[key]
        if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity):
            continue
        score = state.remaining_need[key] * 100 + rng.random()
        if ts.weekday > 2 and state.placed[(class_id, subj.subject_id, ts.weekday - 1)]:
            score -= 50
        if ts.weekday < 7 and state.placed[(class_id, subj.subject_id, ts.weekday + 1)]:
            score -= 50
        # cố gắng không để GV trống trọn ngày làm việc: thưởng nhẹ khi GV này chưa
        # có tiết nào trong ngày (cả sáng lẫn chiều). Best-effort, không cưỡng bức.
        if (state.session_count[(teacher_id, ts.weekday, "S")]
                + state.session_count[(teacher_id, ts.weekday, "C")]) == 0:
            score += IDLE_DAY_BONUS
        if slot.old_subject_id == subj.subject_id and rng.random() > pu:
            score += 1_000_000
        if score > best_score:
            best_score = score
            best_subject = subj.subject_id
            best_teacher = teacher_id
    if best_subject is None:
        return None
    return best_subject, best_teacher


def _pick_best_simple(class_id: int, slot: Slot, state: _State, role_index,
                       subjects: list, assigned_teacher: dict,
                       day_capacity: Optional[dict] = None) -> Optional[tuple]:
    ts = slot.ts
    best_subject = None
    best_teacher = None
    best_remaining = -1
    for subj in subjects:
        key = (subj.subject_id, class_id)
        remaining = state.remaining_need.get(key, 0)
        if remaining <= 0:
            continue
        if subj.subject_id == role_index.hdtn_id and (class_id, ts.weekday) in state.shl_days:
            continue
        teacher_id = assigned_teacher[key]
        if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity):
            continue
        if remaining > best_remaining:
            best_remaining = remaining
            best_subject = subj.subject_id
            best_teacher = teacher_id
    if best_subject is None:
        return None
    return best_subject, best_teacher


def _try_swap_repair(class_id: int, slot: Slot, state: _State, role_index,
                      subjects: list, assigned_teacher: dict,
                      slots_by_class: dict, day_capacity: Optional[dict] = None) -> bool:
    ts = slot.ts
    for other in slots_by_class[class_id]:
        if other.slot_id == slot.slot_id:
            continue
        if state.assigned.get(other.slot_id, None) in (None, -1) or state.pinned.get(other.slot_id):
            continue
        moved_subject, moved_teacher = _remove_at(state, other, role_index)
        if _feasible(class_id, ts, moved_subject, moved_teacher, state, role_index, day_capacity):
            _put_at(state, slot, moved_subject, moved_teacher, role_index)
            refill = _pick_best_simple(class_id, other, state, role_index, subjects, assigned_teacher, day_capacity)
            if refill is not None:
                _put_at(state, other, refill[0], refill[1], role_index)
                return True
            # rollback: undo the move into `slot`, restore `other`
            _remove_at(state, slot, role_index)
            _put_at(state, other, moved_subject, moved_teacher, role_index)
        else:
            _put_at(state, other, moved_subject, moved_teacher, role_index)
    return False


def _assign_off_slots(teacher_ids: set, teachers_by_id: dict, rng: random.Random,
                       gvcn_shl_cell: Optional[dict] = None,
                       off_slot_count: int = 1) -> dict:
    """Pick each teacher's off-slot(s) for the week: off_slot_count (weekday, session)
    pairs, each on a DIFFERENT weekday when possible (never 2 off-sessions on the
    same day, i.e. never a full day off), drawn from every cell except
    FORBIDDEN_OFF_CELLS (plus the teacher's own must_monday/is_gvcn exclusions).

    off_slot_count defaults to 1 (a single half-day off/week), and run() always
    calls this with the default -- every teacher gets exactly 1 buổi nghỉ/tuần,
    regardless of whether the school runs a 1- or 2-buổi/ngày model.

    gvcn_shl_cell: teacher_id -> (weekday, session), the cell holding sinh hoạt lớp
    (tiết cuối buổi sáng: Thứ 6 khi lớp học 2 buổi/ngày, Thứ 7 khi 1 buổi/ngày) for
    that GVCN's own homeroom class -- only that one (weekday, session) is barred,
    not the whole day. Defaults to (7, "C") when unknown, e.g. in isolated tests.
    """
    gvcn_shl_cell = gvcn_shl_cell or {}
    gv_off_slots = {}
    for tid in teacher_ids:
        t = teachers_by_id.get(tid)
        must_monday = t.must_monday if t else False
        is_gvcn = t.is_gvcn if t else False
        forbidden = set(FORBIDDEN_OFF_CELLS)
        if must_monday:
            forbidden.add((2, "C"))
        if is_gvcn:
            forbidden.add(gvcn_shl_cell.get(tid, (7, "C")))

        by_weekday = defaultdict(list)
        for wd in (2, 3, 4, 5, 6, 7):
            for session in ("S", "C"):
                if (wd, session) not in forbidden:
                    by_weekday[wd].append(session)
        eligible_weekdays = [wd for wd, sessions in by_weekday.items() if sessions]

        if len(eligible_weekdays) >= off_slot_count:
            chosen_weekdays = rng.sample(eligible_weekdays, off_slot_count)
            gv_off_slots[tid] = {(wd, rng.choice(by_weekday[wd])) for wd in chosen_weekdays}
        else:
            # not enough distinct eligible days -- take as many off-cells as
            # possible instead of leaving off_slot_count unmet (may repeat a
            # weekday with both sessions as a last resort).
            all_eligible_cells = [(wd, s) for wd in eligible_weekdays for s in by_weekday[wd]]
            picks = rng.sample(all_eligible_cells, min(off_slot_count, len(all_eligible_cells)))
            gv_off_slots[tid] = set(picks)
    return gv_off_slots


def run(inp: SchedulingInput, *, max_attempts: int = SO_LAN_THU,
        target_successes: int = SO_PA_TOT, lock_threshold: int = NGUONG_KHOA) -> ScheduleResult:
    role_index = resolve_roles(inp.subjects)
    assigned_teacher = _build_effective_assigned_teacher(inp)
    teachers_by_id = {t.teacher_id: t for t in inp.teachers}
    all_teacher_ids = set(assigned_teacher.values())

    # sinh hoạt lớp (SHL) = tiết CUỐI buổi sáng của ngày học cuối tuần: Thứ 6 nếu
    # lớp học 2 buổi/ngày (có tiết chiều nên Thứ 7 nghỉ), ngược lại Thứ 7 (1 buổi).
    # SHL là 1 trong 3 tiết HDTN (cùng chào cờ Thứ 2 + 1 tiết chủ đề). Ghim cứng ô
    # này; chỉ ô (weekday, "S") đó của GVCN bị cấm khỏi buổi nghỉ (_assign_off_slots).
    class_has_chieu = defaultdict(bool)
    for slot in inp.slots:
        if slot.ts.session == "C":
            class_has_chieu[slot.class_id] = True

    morning_slots_by_class = defaultdict(list)
    for slot in inp.slots:
        if slot.ts.session == "S":
            morning_slots_by_class[slot.class_id].append(slot)
    shl_target_slot = {}    # class_id -> Slot (ô tiết cuối sáng T6/T7)
    for cls in inp.classes:
        target_wd = 6 if class_has_chieu[cls.class_id] else 7
        day_slots = [s for s in morning_slots_by_class[cls.class_id] if s.ts.weekday == target_wd]
        if day_slots:
            shl_target_slot[cls.class_id] = max(day_slots, key=lambda s: s.ts.period)
    classes_with_shl_target = set(shl_target_slot)
    shl_days = {(cid, slot.ts.weekday) for cid, slot in shl_target_slot.items()}

    gvcn_shl_cell = {}      # teacher_id -> (weekday, "S") ô SHL của lớp GVCN đó
    for cls in inp.classes:
        homeroom_teacher = assigned_teacher.get((role_index.hdtn_id, cls.class_id))
        target = shl_target_slot.get(cls.class_id)
        if homeroom_teacher is not None and target is not None:
            gvcn_shl_cell[homeroom_teacher] = (target.ts.weekday, target.ts.session)

    need_cls = defaultdict(int)
    for (subj_id, cls_id), n in inp.need.items():
        need_cls[cls_id] += n
    slot_cls_n = defaultdict(int)
    slots_by_ts = defaultdict(list)
    slots_by_class = defaultdict(list)
    day_capacity = defaultdict(int)
    for slot in inp.slots:
        slot_cls_n[slot.class_id] += 1
        slots_by_ts[slot.ts.ts_id].append(slot)
        slots_by_class[slot.class_id].append(slot)
        day_capacity[(slot.class_id, slot.ts.weekday)] += 1

    base_order = sorted(inp.timeslots, key=lambda ts: ts.order_key)

    # Group by (weekday, session) so shuffling can reorder *which session* gets
    # visited first without ever reordering periods *within* a session -- period
    # 1 must stay decided before period 2, or the "no lone period" check below
    # can't reason about it correctly (see _has_lone_period's docstring).
    base_groups = []
    for ts in base_order:
        key = (ts.weekday, ts.session)
        if not base_groups or base_groups[-1][0] != key:
            base_groups.append((key, []))
        base_groups[-1][1].append(ts)

    rng = random.Random(inp.seed) if inp.seed else random.Random()

    best_assignment = None
    best_changed = None
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
        state.gv_off_slots = _assign_off_slots(all_teacher_ids, teachers_by_id, rng, gvcn_shl_cell)
        state.shl_days = shl_days

        if attempt > lock_threshold and attempt % 2 == 0:
            groups = list(base_groups)
            rng.shuffle(groups)
            order = [ts for _key, ts_list in groups for ts in ts_list]
        else:
            order = list(base_order)

        done = True

        # Pin Monday-session-S-period-1 to HDTN (chào cờ) for every class, if quota remains.
        for slot in inp.slots:
            if slot.ts.weekday == 2 and slot.ts.session == "S" and slot.ts.period == 1:
                key = (role_index.hdtn_id, slot.class_id)
                if state.remaining_need.get(key, 0) > 0:
                    teacher_id = assigned_teacher.get(key)
                    if teacher_id is not None and _feasible(slot.class_id, slot.ts, role_index.hdtn_id,
                                                              teacher_id, state, role_index, day_capacity):
                        _put_at(state, slot, role_index.hdtn_id, teacher_id, role_index)
                        state.pinned[slot.slot_id] = True

        # Giữ chỗ ô SHL (tiết cuối sáng T6/T7) + giữ lại 1 tiết HDTN cho nó: greedy
        # sẽ bỏ qua ô này (đã ≠ None) và không tiêu tiết HDTN cuối vào chỗ khác. Tiết
        # HDTN thứ 3 (chủ đề) vẫn do greedy xếp ở ngày khác (state.shl_days chặn ngày SHL).
        reserved_shl = []
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
                pick = _pick_best_scored(class_id, slot, state, role_index, inp.subjects,
                                          assigned_teacher, pu, rng, day_capacity)
                # order groups (weekday, session) together with period ascending
                # (see base_groups), so period 1 is always decided before period 2:
                # never cheaply leave period 2 empty right after filling period 1.
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
                                              assigned_teacher, slots_by_class, day_capacity)
                    if not fixed:
                        done = False
                        break
            if not done:
                break

        # Đặt SHL vào ô đã giữ: lúc này các tiết sáng trước nó đã được lấp nên
        # _feasible (liền mạch) mới pass. Không pass => sáng ngày SHL chưa đủ tiết
        # => bỏ lượt, best-of-N thử lại (khung trường thật luôn đầy nên rất ổn định).
        if done:
            for cid, target in reserved_shl:
                key = (role_index.hdtn_id, cid)
                state.assigned[target.slot_id] = None
                state.rem_slot_count[cid] += 1
                state.remaining_need[key] += 1
                state.rem_need_count[cid] += 1
                tid = assigned_teacher[key]
                if _feasible(cid, target.ts, role_index.hdtn_id, tid, state, role_index, day_capacity):
                    _put_at(state, target, role_index.hdtn_id, tid, role_index)
                    state.pinned[target.slot_id] = True
                else:
                    done = False
                    break

        if done:
            _repair_lone_periods(inp, state, role_index, assigned_teacher, slots_by_class, day_capacity)
            if _has_lone_period(inp, state):
                done = False

        if done:
            cells_changed = 0
            for slot in inp.slots:
                final = state.assigned.get(slot.slot_id)
                if final == -1:
                    final = None
                if final != slot.old_subject_id:
                    cells_changed += 1
            successes += 1
            if best_changed is None or cells_changed < best_changed:
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
