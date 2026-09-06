"""Objective functions and solution hints for CP-SAT model."""
from __future__ import annotations

from collections import defaultdict
from core.models import SchedulingInput, is_bgh
from core.scheduler.constants import (
    TEACHER_COMPACT_SCHEDULE_PENALTY,
    TEACHER_EXEMPT_LONE_DAY_SOFT_PENALTY,
    TEACHER_EXEMPT_LONE_SESSION_SOFT_PENALTY,
    TEACHER_EXEMPT_SPLIT_DAY_SOFT_PENALTY,
    TEACHER_LONE_SESSION_SPREAD_PENALTY,
    TEACHER_STRICT_MORNING_MISS_PENALTY,
)
from core.scheduler.placement import _build_effective_assigned_teacher
from core.scheduler.cpsat.types import CpSatModel
from core.scheduler.cpsat.constraints import _is_teacher_busy_morning


def _add_change_minimisation(built: CpSatModel) -> None:
    """Theo dõi các ô bị thay đổi so với old_subject_id."""
    m = built.model
    inp = built.inp
    x = built.x

    changed_terms = []
    for slot in inp.slots:
        if slot.old_subject_id is not None:
            old_id = slot.old_subject_id
            if (slot.slot_id, old_id) in x:
                ch = m.NewBoolVar(f"changed_{slot.slot_id}")
                m.Add(ch == 1 - x[slot.slot_id, old_id])
                changed_terms.append(ch)
            else:
                changed_terms.append(m.NewConstant(1))

    built.changed_terms = changed_terms


def _add_solution_hint(built: CpSatModel) -> None:
    """Gợi ý điểm khởi đầu cho CP-SAT từ old_subject_id."""
    m = built.model
    inp = built.inp
    for slot in inp.slots:
        if slot.old_subject_id is not None:
            key = (slot.slot_id, slot.old_subject_id)
            if key in built.x:
                m.AddHint(built.x[key], 1)


def _add_objective(built: CpSatModel) -> None:
    """Hàm mục tiêu tối ưu hóa toàn cục các tiêu chí HĐSP mềm."""
    m = built.model
    inp = built.inp
    config = inp.config
    x = built.x
    teacher_of = built.teacher_of
    effective_assigned = _build_effective_assigned_teacher(inp)

    load = defaultdict(int)
    for (subj_id, cls_id), n in inp.need.items():
        if n > 0:
            tid = effective_assigned.get((subj_id, cls_id))
            if tid is not None and tid > 0:
                load[tid] += n

    teachers = sorted(load.keys())
    sessions = sorted({(s.ts.weekday, s.ts.session) for s in inp.slots})
    weekdays = sorted({s.ts.weekday for s in inp.slots})

    cnt = {}
    used = {}
    lone = {}

    for t in teachers:
        for (wd, sess) in sessions:
            sess_slots = [s for s in inp.slots if s.ts.weekday == wd and s.ts.session == sess]
            sess_vars = []
            for s in sess_slots:
                for subj in inp.subjects:
                    if (s.slot_id, subj.subject_id) in x and teacher_of.get((s.slot_id, subj.subject_id)) == t:
                        sess_vars.append(x[s.slot_id, subj.subject_id])

            c = m.NewIntVar(0, config.max_periods_per_session, f"cnt_t{t}_wd{wd}_{sess}")
            m.Add(c == sum(sess_vars) if sess_vars else c == 0)
            cnt[t, wd, sess] = c

            u = m.NewBoolVar(f"used_t{t}_wd{wd}_{sess}")
            m.Add(c >= 1).OnlyEnforceIf(u)
            m.Add(c == 0).OnlyEnforceIf(u.Not())
            used[t, wd, sess] = u

            l = m.NewBoolVar(f"lone_t{t}_wd{wd}_{sess}")
            m.Add(c == 1).OnlyEnforceIf(l)
            m.Add(c != 1).OnlyEnforceIf(l.Not())
            lone[t, wd, sess] = l

    avoid_lone = getattr(config, "avoid_teacher_lone_periods", True)
    min_lone_load = getattr(config, "min_weekly_periods_for_lone_penalty", 8)
    lone_exempt = getattr(config, "lone_session_exempt_teacher_ids", frozenset()) or frozenset()
    mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
    strict_morns = getattr(config, "strict_morning_weekdays", ()) or ()
    min_mand_load = getattr(config, "min_weekly_periods_for_mandatory_morning", 10)
    bgh_ids = frozenset(t.teacher_id for t in inp.teachers if is_bgh(t))
    compact_ids = getattr(config, "compact_schedule_teacher_ids", frozenset()) or frozenset()

    penalty_terms = defaultdict(list)
    lone_sess_terms = []
    lone_day_terms = []
    lone_spread_terms = []
    compact_terms = []
    strict_morning_terms = []
    soft_exempt_lone_terms = []
    soft_exempt_split_terms = []
    soft_exempt_lone_day_terms = []

    # 1. II.4 (Buổi lẻ, Ngày lẻ, Dồn buổi lẻ) & II.8 (Ngày chia lẻ)
    if avoid_lone:
        for t in teachers:
            if load[t] < min_lone_load:
                continue
            is_soft_exempt = t in lone_exempt

            for (wd, sess) in sessions:
                if is_soft_exempt:
                    soft_exempt_lone_terms.append(lone[t, wd, sess])
                    penalty_terms["_exempt_lone_session"].append(lone[t, wd, sess])
                else:
                    lone_sess_terms.append(lone[t, wd, sess])
                    penalty_terms["II.4"].append(lone[t, wd, sess])

            for wd in weekdays:
                if (t, wd, "S") in lone and (t, wd, "C") in lone:
                    l_s = lone[t, wd, "S"]
                    l_c = lone[t, wd, "C"]
                    sp = m.NewBoolVar(f"split_t{t}_wd{wd}")
                    m.Add(sp >= l_s + l_c - 1)
                    m.Add(sp <= l_s)
                    m.Add(sp <= l_c)
                    penalty_terms["II.8"].append(sp)

            for wd in weekdays:
                day_cnts = [cnt[t, wd, sess] for sess in ("S", "C") if (t, wd, sess) in cnt]
                if day_cnts:
                    ld = m.NewBoolVar(f"lone_day_t{t}_wd{wd}")
                    m.Add(sum(day_cnts) == 1).OnlyEnforceIf(ld)
                    m.Add(sum(day_cnts) != 1).OnlyEnforceIf(ld.Not())
                    if is_soft_exempt:
                        soft_exempt_lone_day_terms.append(ld)
                        penalty_terms["_exempt_lone_day"].append(ld)
                    else:
                        lone_day_terms.append(ld)
                        penalty_terms["II.4"].append(ld)

            if is_soft_exempt:
                t_lones = [lone[t, wd, sess] for (wd, sess) in sessions if (t, wd, sess) in lone]
                if t_lones:
                    m.Add(sum(t_lones) <= 2)
                    extra_l = m.NewIntVar(0, len(t_lones), f"extra_lone_exempt_t{t}")
                    m.Add(extra_l >= sum(t_lones) - 1)
                    m.Add(extra_l >= 0)
                    lone_spread_terms.append(extra_l)
                continue

            t_lones = [lone[t, wd, sess] for (wd, sess) in sessions if (t, wd, sess) in lone]
            if t_lones:
                extra_l = m.NewIntVar(0, len(t_lones), f"extra_lone_t{t}")
                m.Add(extra_l >= sum(t_lones) - 1)
                m.Add(extra_l >= 0)
                lone_spread_terms.append(extra_l)

    # 2. II.3 Thiếu sáng bắt buộc
    all_mand_strict = sorted(set(mand_morns) | set(strict_morns))
    for t in teachers:
        for wd in all_mand_strict:
            is_busy = _is_teacher_busy_morning(inp, t, wd)
            is_strict = (wd in strict_morns and t not in bgh_ids and not is_busy)
            is_mand = (wd in mand_morns and wd not in strict_morns and load[t] >= min_mand_load and not is_busy)
            if not (is_strict or is_mand):
                continue
            if (t, wd, "S") in used:
                miss = m.NewBoolVar(f"miss_morn_t{t}_wd{wd}")
                m.Add(used[t, wd, "S"] == 0).OnlyEnforceIf(miss)
                m.Add(used[t, wd, "S"] == 1).OnlyEnforceIf(miss.Not())
                penalty_terms["II.3"].append(miss)
                if is_strict:
                    strict_morning_terms.append(miss)
            else:
                miss = m.NewConstant(1)
                penalty_terms["II.3"].append(miss)
                if is_strict:
                    strict_morning_terms.append(miss)

    # 3. II.7 Tiết trống giữa buổi (gaps)
    if getattr(config, "avoid_teacher_gaps", True):
        for t in teachers:
            for (wd, sess) in sessions:
                slots_sess = [s for s in inp.slots if s.ts.weekday == wd and s.ts.session == sess]
                periods_map = defaultdict(list)
                for s in slots_sess:
                    for subj in inp.subjects:
                        if (s.slot_id, subj.subject_id) in x and teacher_of.get((s.slot_id, subj.subject_id)) == t:
                            periods_map[s.ts.period].append(x[s.slot_id, subj.subject_id])
                active_p = sorted(periods_map.keys())
                if len(active_p) < 2:
                    continue

                u_p = {}
                for p in active_p:
                    v_p = m.NewBoolVar(f"ugap_t{t}_wd{wd}_{sess}_p{p}")
                    m.Add(v_p == sum(periods_map[p]))
                    u_p[p] = v_p

                sess_gaps = []
                for p in active_p[1:-1]:
                    before_vars = [u_p[p_prev] for p_prev in active_p if p_prev < p]
                    after_vars = [u_p[p_next] for p_next in active_p if p_next > p]
                    has_before = m.NewBoolVar(f"has_before_t{t}_wd{wd}_{sess}_p{p}")
                    m.Add(has_before <= sum(before_vars))
                    for bv in before_vars:
                        m.Add(has_before >= bv)

                    has_after = m.NewBoolVar(f"has_after_t{t}_wd{wd}_{sess}_p{p}")
                    m.Add(has_after <= sum(after_vars))
                    for av in after_vars:
                        m.Add(has_after >= av)

                    is_gap = m.NewBoolVar(f"is_gap_t{t}_wd{wd}_{sess}_p{p}")
                    m.Add(is_gap >= has_before + has_after + (1 - u_p[p]) - 2)
                    m.Add(is_gap <= has_before)
                    m.Add(is_gap <= has_after)
                    m.Add(is_gap <= 1 - u_p[p])
                    penalty_terms["II.7"].append(is_gap)
                    sess_gaps.append(is_gap)

                if len(sess_gaps) >= 2:
                    m.Add(sum(sess_gaps) <= 1)

    # 4. II.14 >= 4 tiết sáng liên tiếp
    if getattr(config, "avoid_teacher_4_consecutive_morning", True):
        for t in teachers:
            if load[t] <= 20:
                for wd in weekdays:
                    if (t, wd, "S") in cnt:
                        hm = m.NewBoolVar(f"hm_t{t}_wd{wd}")
                        m.Add(cnt[t, wd, "S"] >= 4).OnlyEnforceIf(hm)
                        m.Add(cnt[t, wd, "S"] <= 3).OnlyEnforceIf(hm.Not())
                        penalty_terms["II.14"].append(hm)

    # 5. II.9 Nghỉ trọn chiều
    if getattr(config, "balance_afternoon_teachers", True):
        classes_with_afternoon = {s.class_id for s in inp.slots if s.ts.session == "C"}
        teacher_classes = defaultdict(set)
        effective_assigned = _build_effective_assigned_teacher(inp)
        for (sub_id, c_id), t_id in effective_assigned.items():
            if t_id is not None and t_id > 0:
                teacher_classes[t_id].add(c_id)

        for t in teachers:
            if load[t] >= 4 and any(c in classes_with_afternoon for c in teacher_classes[t]):
                aft_cnts = [cnt[t, wd, "C"] for (w, sess) in sessions if sess == "C" for wd in (w,) if (t, wd, "C") in cnt]
                if aft_cnts:
                    aft_taught = m.NewBoolVar(f"aft_taught_t{t}")
                    m.Add(sum(aft_cnts) >= 1).OnlyEnforceIf(aft_taught)
                    m.Add(sum(aft_cnts) == 0).OnlyEnforceIf(aft_taught.Not())
                    miss_aft = m.NewBoolVar(f"miss_aft_t{t}")
                    m.Add(miss_aft == aft_taught.Not())
                    penalty_terms["II.9"].append(miss_aft)

    # 6. GV ưu tiên lịch nén (compact schedule)
    for t in compact_ids:
        if t in teachers:
            for (wd, sess) in sessions:
                if (t, wd, sess) in used:
                    compact_terms.append(used[t, wd, sess])

    built.penalty_terms = dict(penalty_terms)

    # 7. Theo dõi và tối thiểu hóa thay đổi ô cũ
    _add_change_minimisation(built)

    # Tổng hợp hàm mục tiêu
    obj_terms = []
    if penalty_terms.get("II.3"):
        obj_terms.append(800 * sum(penalty_terms["II.3"]))
    if strict_morning_terms:
        diff_weight = max(0, TEACHER_STRICT_MORNING_MISS_PENALTY - 800)
        obj_terms.append(diff_weight * sum(strict_morning_terms))
    if penalty_terms.get("II.8"):
        obj_terms.append(700 * sum(penalty_terms["II.8"]))
    if lone_spread_terms:
        obj_terms.append(TEACHER_LONE_SESSION_SPREAD_PENALTY * sum(lone_spread_terms))
    if lone_sess_terms:
        obj_terms.append(500 * sum(lone_sess_terms))
    if compact_terms:
        obj_terms.append(TEACHER_COMPACT_SCHEDULE_PENALTY * sum(compact_terms))
    if penalty_terms.get("II.7"):
        obj_terms.append(350 * sum(penalty_terms["II.7"]))
    if penalty_terms.get("II.14"):
        obj_terms.append(300 * sum(penalty_terms["II.14"]))
    if lone_day_terms:
        obj_terms.append(250 * sum(lone_day_terms))
    if penalty_terms.get("II.9"):
        obj_terms.append(200 * sum(penalty_terms["II.9"]))
    if soft_exempt_lone_terms:
        obj_terms.append(TEACHER_EXEMPT_LONE_SESSION_SOFT_PENALTY * sum(soft_exempt_lone_terms))
    if soft_exempt_split_terms:
        obj_terms.append(TEACHER_EXEMPT_SPLIT_DAY_SOFT_PENALTY * sum(soft_exempt_split_terms))
    if soft_exempt_lone_day_terms:
        obj_terms.append(TEACHER_EXEMPT_LONE_DAY_SOFT_PENALTY * sum(soft_exempt_lone_day_terms))

    has_any_changed = bool(getattr(built, "changed_terms", None))
    minimize_changes_flag = getattr(config, "cpsat_minimize_changes", False)
    if has_any_changed and minimize_changes_flag:
        scale = max(1000, len(inp.slots) + 1)
        total_terms = []
        if obj_terms:
            total_terms.append(scale * sum(obj_terms))
        total_terms.append(sum(built.changed_terms))
        m.Minimize(sum(total_terms))
    else:
        if has_any_changed:
            obj_terms.append(50 * sum(built.changed_terms))
        any_oversubscribed = any(
            sum(inp.need.get((subj.subject_id, c_id), 0) for subj in inp.subjects) > len(built.slots_by_class.get(c_id, []))
            for c_id in built.slots_by_class
        )
        if any_oversubscribed:
            obj_terms.append(-1000 * sum(x.values()))

        if obj_terms:
            m.Minimize(sum(obj_terms))
