"""Constraints for school timetable CP-SAT model."""
from __future__ import annotations

from collections import defaultdict
from core.frame import MAX_PERIODS_PER_SESSION
from core.models import SchedulingInput, is_bgh
from core.roles import is_academic_subject, resolve_roles
from core.scheduler.constants import CAP_TIET_NGAY
from core.scheduler.placement import _build_effective_assigned_teacher
from core.scheduler.cpsat.types import CpSatModel
from core.scheduler.hdtn import get_hdtn_pinned_slots_for_class


def _add_teacher_constraints(built: CpSatModel) -> None:
    """5 ràng buộc "GV với chính tuần của mình":
    1. GV không dạy 2 lớp cùng tiết.
    2. GV bận (GV_Bận / inp.ban_busy) -- không được xếp.
    3. Trần tiết/buổi (config.max_periods_per_session).
    4. Trần tiết/ngày (config.max_teacher_periods_per_day).
    5. Buổi nghỉ của GV -- xem _add_off_day_constraints().
    """
    m = built.model
    inp = built.inp
    params = built.params
    slot_by_id = {s.slot_id: s for s in inp.slots}
    effective_assigned = _build_effective_assigned_teacher(inp)

    teacher_of = {}
    for (slot_id, subject_id) in built.x:
        class_id = slot_by_id[slot_id].class_id
        teacher_of[slot_id, subject_id] = effective_assigned[subject_id, class_id]
    built.teacher_of = teacher_of

    role_index = built.role_index
    hdtn_id = role_index.hdtn_id
    if inp.hdtn_thematic_week and hdtn_id is not None:
        vars_by_teacher_ts_hdtn = defaultdict(list)
        vars_by_teacher_ts_other = defaultdict(list)
        all_t_ts = set()
        for (slot_id, subject_id), var in built.x.items():
            t = teacher_of[slot_id, subject_id]
            ts = slot_by_id[slot_id].ts
            all_t_ts.add((t, ts.ts_id))
            if subject_id == hdtn_id:
                vars_by_teacher_ts_hdtn[t, ts.ts_id].append(var)
            else:
                vars_by_teacher_ts_other[t, ts.ts_id].append(var)

        # 1. GV không dạy 2 lớp cùng tiết (ngoại lệ: HĐTN tuần chuyên đề toàn trường cho phép 1 GV phụ trách nhiều lớp)
        act_by_teacher_ts = {}
        for (t, ts_id) in all_t_ts:
            vs_h = vars_by_teacher_ts_hdtn.get((t, ts_id), [])
            vs_o = vars_by_teacher_ts_other.get((t, ts_id), [])
            if vs_h:
                is_h = m.NewBoolVar(f"teach_hdtn_t{t}_ts{ts_id}")
                for v in vs_h:
                    m.Add(v <= is_h)
                m.Add(is_h <= sum(vs_h))
                if vs_o:
                    m.Add(is_h + sum(vs_o) <= 1)
                    if len(vs_o) > 1:
                        m.AddAtMostOne(vs_o)
                    act_var = m.NewBoolVar(f"act_t{t}_ts{ts_id}")
                    m.Add(act_var == is_h + sum(vs_o))
                    act_by_teacher_ts[t, ts_id] = act_var
                else:
                    act_by_teacher_ts[t, ts_id] = is_h
            else:
                if len(vs_o) > 1:
                    m.AddAtMostOne(vs_o)
                if len(vs_o) == 1:
                    act_by_teacher_ts[t, ts_id] = vs_o[0]
                elif vs_o:
                    act_var = m.NewBoolVar(f"act_t{t}_ts{ts_id}")
                    m.Add(act_var == sum(vs_o))
                    act_by_teacher_ts[t, ts_id] = act_var

        vars_by_teacher_session = defaultdict(list)
        vars_by_teacher_day = defaultdict(list)
        ts_by_id = {ts.ts_id: ts for ts in inp.timeslots}
        for (t, ts_id), act in act_by_teacher_ts.items():
            ts = ts_by_id[ts_id]
            vars_by_teacher_session[t, ts.weekday, ts.session].append(act)
            vars_by_teacher_day[t, ts.weekday].append(act)
        built.act_by_teacher_ts = act_by_teacher_ts
    else:
        vars_by_teacher_ts = defaultdict(list)
        vars_by_teacher_session = defaultdict(list)
        vars_by_teacher_day = defaultdict(list)
        for (slot_id, subject_id), var in built.x.items():
            t = teacher_of[slot_id, subject_id]
            ts = slot_by_id[slot_id].ts
            vars_by_teacher_ts[t, ts.ts_id].append(var)
            vars_by_teacher_session[t, ts.weekday, ts.session].append(var)
            vars_by_teacher_day[t, ts.weekday].append(var)

        # 1. GV không dạy 2 lớp cùng tiết.
        for vs in vars_by_teacher_ts.values():
            if len(vs) > 1:
                m.AddAtMostOne(vs)

        act_by_teacher_ts = {}
        for (t, ts_id), vs in vars_by_teacher_ts.items():
            if len(vs) == 1:
                act_by_teacher_ts[t, ts_id] = vs[0]
            elif vs:
                act_var = m.NewBoolVar(f"act_t{t}_ts{ts_id}")
                m.Add(act_var == sum(vs))
                act_by_teacher_ts[t, ts_id] = act_var
        built.act_by_teacher_ts = act_by_teacher_ts

    # 2. GV bận: mọi biến của GV đó tại ts_id bị cấm = 0.
    for (teacher_id, ts_id) in inp.ban_busy:
        for s in built.slots_by_ts.get(ts_id, []):
            for subj in inp.subjects:
                key = (s.slot_id, subj.subject_id)
                if key in built.x and teacher_of.get(key) == teacher_id:
                    m.Add(built.x[key] == 0)

    # 3. Trần tiết/buổi.
    for vs in vars_by_teacher_session.values():
        m.Add(sum(vs) <= params.max_periods_per_session)

    # 4. Trần tiết/ngày. Hậu kiểm đối chứng: core/rules/detectors.py:detect_teacher_day_cap
    for vs in vars_by_teacher_day.values():
        m.Add(sum(vs) <= params.max_teacher_periods_per_day)

    # 5. Buổi nghỉ của GV.
    _add_off_day_constraints(built, vars_by_teacher_session)


def _add_off_day_constraints(built: CpSatModel, vars_by_teacher_session: dict) -> None:
    """Luật 5 (buổi nghỉ của GV): bộ giải tự chọn buổi nghỉ sao cho phần còn lại của tuần tối ưu."""
    import math
    from collections import defaultdict

    m = built.model
    inp = built.inp
    config = inp.config
    teachers_by_id = {t.teacher_id: t for t in inp.teachers}
    all_wd_sess = sorted({(ts.weekday, ts.session) for ts in inp.timeslots})
    mandatory_mornings = set(built.params.mandatory_morning_weekdays)
    forbidden_base = set(config.forbidden_off_cells) | {(wd, "S") for wd in mandatory_mornings}

    # Tính tổng số tiết mà mỗi GV được phân công dạy để xét tính khả thi ép cứng
    assigned_teacher = inp.assigned_teacher or {}
    teacher_total_periods = defaultdict(int)
    for (subj_id, class_id), n in inp.need.items():
        t_id = assigned_teacher.get((subj_id, class_id))
        if t_id is not None:
            teacher_total_periods[t_id] += n

    max_p_sess = getattr(built.params, "max_periods_per_session", 4) or 4
    off_mode = getattr(config, "teacher_off_sessions_mode", "soft") or "soft"

    # Sức chứa tiết tối đa của các buổi theo cấu hình thời khoá biểu
    sess_capacities = [
        min(max_p_sess, len({ts.period for ts in inp.timeslots if ts.weekday == wd and ts.session == sess}))
        for (wd, sess) in all_wd_sess
    ]
    sorted_caps_desc = sorted(sess_capacities, reverse=True)

    all_teacher_ids = {t for (t, _wd, _sess) in vars_by_teacher_session}
    off_shortfalls = []
    off_excesses = []
    zero_off_indicators = []

    for teacher_id in all_teacher_ids:
        teacher = teachers_by_id.get(teacher_id)
        forbidden = set(forbidden_base)

        pinned = set()
        pinned_weekdays = set()
        if teacher and teacher.pinned_full_day_off is not None:
            wd = teacher.pinned_full_day_off
            pinned |= {(wd, "S"), (wd, "C")}
            pinned_weekdays.add(wd)
        if teacher and teacher.pinned_afternoon_off is not None:
            wd = teacher.pinned_afternoon_off
            if (wd, "C") not in forbidden and wd not in pinned_weekdays:
                pinned.add((wd, "C"))
                pinned_weekdays.add(wd)

        effective_count = (teacher.off_sessions_override
                           if (teacher and teacher.off_sessions_override is not None)
                           else config.teacher_off_sessions_per_week)
        required_total = max(effective_count, len(pinned))
        if required_total <= 0:
            continue

        eligible_sessions = []
        for (wd, sess) in all_wd_sess:
            teach_vars = vars_by_teacher_session.get((teacher_id, wd, sess), [])
            is_pinned = (wd, sess) in pinned
            # Buổi không có biến dạy và không ghim -> GV vốn không dạy buổi này, không được tính là buổi nghỉ
            if not teach_vars and not is_pinned:
                continue
            if (wd, sess) in forbidden and not is_pinned:
                continue
            eligible_sessions.append((wd, sess))

        if not eligible_sessions:
            continue

        off_vars = []
        for (wd, sess) in eligible_sessions:
            off_var = m.NewBoolVar(f"off_t{teacher_id}_wd{wd}_{sess}")
            off_vars.append(off_var)
            if (wd, sess) in pinned:
                m.Add(off_var == 1)
            teach_vars = vars_by_teacher_session.get((teacher_id, wd, sess), [])
            if teach_vars:
                # off_var == 1 <=> sum(teach_vars) == 0
                m.Add(sum(teach_vars) == 0).OnlyEnforceIf(off_var)
                m.Add(sum(teach_vars) >= 1).OnlyEnforceIf(off_var.Not())

        total_p = teacher_total_periods.get(teacher_id, 0)
        teach_sessions_count = sum(1 for (wd, sess) in all_wd_sess if vars_by_teacher_session.get((teacher_id, wd, sess)))
        avail_sessions = max(0, teach_sessions_count - required_total)
        # Dung lượng các buổi mà GV này thực sự có thể dạy (phù hợp cho cả trường 1 ca và trường 2 ca)
        teacher_sess_caps = [
            min(max_p_sess, len({ts.period for ts in inp.timeslots if ts.weekday == wd and ts.session == sess}))
            for (wd, sess) in eligible_sessions
        ]
        sorted_teacher_caps = sorted(teacher_sess_caps, reverse=True)
        max_workable_periods = sum(sorted_teacher_caps[:avail_sessions])

        # Nếu chọn chế độ bắt buộc tuyệt đối ("hard") và GV đủ điều kiện khả thi:
        is_feasible_hard = (
            off_mode == "hard"
            and len(eligible_sessions) >= required_total
            and total_p <= max_workable_periods
        )

        if is_feasible_hard:
            m.Add(sum(off_vars) >= required_total)
        else:
            # Chế độ ưu tiên mềm ("soft") hoặc fallback khi GV quá tải tiết dạy:
            shortfall = m.NewIntVar(0, required_total, f"off_short_t{teacher_id}")
            m.Add(shortfall >= required_total - sum(off_vars))
            off_shortfalls.append(shortfall)

        # Phạt cực nặng cho người không được nghỉ buổi nào (sum(off_vars) == 0)
        # Chỉ phạt nếu GV về mặt toán học có khả năng nghỉ ít nhất 1 buổi
        can_have_at_least_one_off = (len(eligible_sessions) > 1 and total_p <= sum(sorted_teacher_caps[:-1]))
        if can_have_at_least_one_off:
            zero_off = m.NewBoolVar(f"zero_off_t{teacher_id}")
            m.Add(sum(off_vars) == 0).OnlyEnforceIf(zero_off)
            m.Add(sum(off_vars) >= 1).OnlyEnforceIf(zero_off.Not())
            zero_off_indicators.append(zero_off)

        # Phạt mềm cho người nghỉ quá nhiều buổi (sum(off_vars) > required_total)
        excess = m.NewIntVar(0, len(eligible_sessions), f"off_excess_t{teacher_id}")
        m.Add(excess >= sum(off_vars) - required_total)
        off_excesses.append(excess)

    if off_shortfalls:
        if "_teacher_off" not in built.penalty_terms:
            built.penalty_terms["_teacher_off"] = []
        built.penalty_terms["_teacher_off"].extend(off_shortfalls)

    if zero_off_indicators:
        if "_teacher_zero_off" not in built.penalty_terms:
            built.penalty_terms["_teacher_zero_off"] = []
        built.penalty_terms["_teacher_zero_off"].extend(zero_off_indicators)

    if off_excesses:
        if "_teacher_off_excess" not in built.penalty_terms:
            built.penalty_terms["_teacher_off_excess"] = []
        built.penalty_terms["_teacher_off_excess"].extend(off_excesses)


def _add_subject_constraints(built: CpSatModel) -> None:
    """8 ràng buộc môn học:
    1. Môn bắt buộc buổi sáng (config.morning_only_subject_ids).
    2. Môn Nặng cấm buổi chiều, nếu bật (config.heavy_subjects_morning_only).
    3. GDTC: khung tiết sáng/chiều được phép + gdtc_avoid_period.
    4. Môn không xếp liền ngày, gồm cả GDTC nếu avoid_gdtc_consecutive_days.
    5. Môn nặng tối đa/buổi của lớp (max_heavy_per_session).
    6. Môn nặng không quá max_heavy_consecutive tiết liên tiếp/buổi.
    7. Môn nặng tránh tiết 3 buổi chiều (avoid_heavy_afternoon_period3).
    8. Luật môn-lớp-buổi (inp.subject_class_allowed_cells).
    """
    m = built.model
    inp = built.inp
    config = inp.config
    x = built.x
    slot_by_id = {s.slot_id: s for s in inp.slots}

    role_index = resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week,
                                config.single_pair_subject_ids)
    built.role_index = role_index
    gdtc_id = role_index.gdtc_id

    # 1. Môn bắt buộc buổi sáng: cấm cứng mọi ô buổi chiều.
    morning_only = set(getattr(config, "morning_only_subject_ids", None) or ())
    if morning_only:
        for (slot_id, subject_id), var in x.items():
            if subject_id in morning_only and slot_by_id[slot_id].ts.session == "C":
                m.Add(var == 0)

    # 2. Môn Nặng cấm buổi chiều (nếu bật)
    if getattr(config, "heavy_subjects_morning_only", False):
        for (slot_id, subject_id), var in x.items():
            if subject_id in role_index.heavy_ids and slot_by_id[slot_id].ts.session == "C":
                m.Add(var == 0)

    # 3. GDTC: khung tiết sáng/chiều + gdtc_avoid_period.
    if gdtc_id is not None:
        morning_allowed = getattr(config, "gdtc_morning_allowed_periods", (1, 2, 3, 4))
        afternoon_allowed = getattr(config, "gdtc_afternoon_allowed_periods", (2, 3))
        for (slot_id, subject_id), var in x.items():
            if subject_id != gdtc_id:
                continue
            ts = slot_by_id[slot_id].ts
            if ts.session == "S" and morning_allowed and ts.period not in morning_allowed:
                m.Add(var == 0)
            elif ts.session == "C" and afternoon_allowed and ts.period not in afternoon_allowed:
                m.Add(var == 0)
            if ts.period == config.gdtc_avoid_period:
                m.Add(var == 0)

    # 4. Môn không xếp liền ngày (gồm GDTC nếu avoid_gdtc_consecutive_days).
    non_consecutive = set(getattr(config, "non_consecutive_subject_ids", None) or ())
    if getattr(config, "avoid_gdtc_consecutive_days", True) and gdtc_id is not None:
        non_consecutive.add(gdtc_id)
    if non_consecutive:
        vars_by_class_subject_day = defaultdict(list)
        days_by_class = defaultdict(set)
        for (slot_id, subject_id), var in x.items():
            if subject_id not in non_consecutive:
                continue
            s = slot_by_id[slot_id]
            vars_by_class_subject_day[s.class_id, subject_id, s.ts.weekday].append(var)
            days_by_class[s.class_id].add(s.ts.weekday)
        for class_id, days in days_by_class.items():
            for d in days:
                if (d + 1) not in days:
                    continue
                for subject_id in non_consecutive:
                    vs_today = vars_by_class_subject_day.get((class_id, subject_id, d), [])
                    vs_next = vars_by_class_subject_day.get((class_id, subject_id, d + 1), [])
                    if vs_today or vs_next:
                        m.Add(sum(vs_today) + sum(vs_next) <= 1)

    # 5 + 6. Môn nặng: tối đa/buổi và không quá N tiết liên tiếp.
    if role_index.heavy_ids:
        vars_by_session = defaultdict(list)
        vars_by_session_period = defaultdict(dict)
        for (slot_id, subject_id), var in x.items():
            if subject_id not in role_index.heavy_ids:
                continue
            s = slot_by_id[slot_id]
            key = (s.class_id, s.ts.weekday, s.ts.session)
            vars_by_session[key].append(var)
            vars_by_session_period[key].setdefault(s.ts.period, []).append(var)

        class_has_afternoon = {s.class_id for s in inp.slots if s.ts.session == "C"}
        is_heavy_morning_only = getattr(config, "heavy_subjects_morning_only", False)
        class_distinct_mornings = defaultdict(set)
        for s in inp.slots:
            if s.ts.session == "S":
                class_distinct_mornings[s.class_id].add(s.ts.weekday)
        class_heavy_need = defaultdict(int)
        for (sid, cid), n in inp.need.items():
            if sid in role_index.heavy_ids:
                class_heavy_need[cid] += n

        def _get_eff_max_heavy(cid, sess):
            base_max = max(getattr(config, "max_heavy_per_session", 3), config.max_heavy_consecutive)
            if sess == "S" and is_heavy_morning_only:
                n_morns = len(class_distinct_mornings.get(cid, ()))
                if n_morns > 0:
                    min_needed = (class_heavy_need[cid] + n_morns - 1) // n_morns
                    return max(base_max, min_needed)
            return base_max

        for (cid, _wd, sess), vs in vars_by_session.items():
            eff_max = _get_eff_max_heavy(cid, sess)
            m.Add(sum(vs) <= eff_max)

        for (cid, _wd, sess), period_vars in vars_by_session_period.items():
            eff_max = _get_eff_max_heavy(cid, sess)
            consec_limit = max(config.max_heavy_consecutive, eff_max) if is_heavy_morning_only else config.max_heavy_consecutive
            window = consec_limit + 1
            last_start = MAX_PERIODS_PER_SESSION - consec_limit
            for w in range(1, last_start + 1):
                window_vars = []
                for offset in range(window):
                    window_vars.extend(period_vars.get(w + offset, []))
                if window_vars:
                    m.Add(sum(window_vars) <= consec_limit)

    # 7. Môn nặng tránh tiết 3 buổi chiều.
    if getattr(config, "avoid_heavy_afternoon_period3", True):
        for (slot_id, subject_id), var in x.items():
            if subject_id in role_index.heavy_ids:
                ts = slot_by_id[slot_id].ts
                if ts.session == "C" and ts.period == 3:
                    m.Add(var == 0)

    # 8. Luật môn-lớp-buổi
    for (subject_id, class_id), allowed in inp.subject_class_allowed_cells.items():
        if allowed is None:
            continue
        for s in built.slots_by_class.get(class_id, []):
            if (s.ts.weekday, s.ts.session) not in allowed:
                key = (s.slot_id, subject_id)
                if key in x:
                    m.Add(x[key] == 0)


def _add_class_constraints(built: CpSatModel) -> None:
    """Ràng buộc khung LỚP và ghim chào cờ, sinh hoạt lớp."""
    m = built.model
    inp = built.inp
    config = inp.config
    x = built.x
    role_index = built.role_index
    hdtn_id = role_index.hdtn_id
    slot_by_id = {s.slot_id: s for s in inp.slots}

    # 1. Trần tiết/môn/ngày/lớp.
    vars_by_class_subject_day = defaultdict(list)
    for (slot_id, subject_id), var in x.items():
        s = slot_by_id[slot_id]
        vars_by_class_subject_day[s.class_id, subject_id, s.ts.weekday].append(var)
    pinned_hdtn_by_class = {}
    if not inp.hdtn_thematic_week and hdtn_id is not None:
        for class_id, class_slots in built.slots_by_class.items():
            need_hdtn = inp.need.get((hdtn_id, class_id), 0)
            pinned_hdtn_by_class[class_id] = get_hdtn_pinned_slots_for_class(
                class_id, class_slots, config, need_hdtn, inp.hdtn_thematic_week
            )

    for (class_id, subject_id, weekday), vs in vars_by_class_subject_day.items():
        cap_d = role_index.block_size.get(subject_id, 1)
        if subject_id == hdtn_id:
            day_pinned_cnt = sum(1 for ps in pinned_hdtn_by_class.get(class_id, []) if ps.ts.weekday == weekday)
            cap_d = max(cap_d, 2, day_pinned_cnt)
        m.Add(sum(vs) <= cap_d)

    if not inp.hdtn_thematic_week and hdtn_id is not None:
        # Ghim các tiết HĐTN theo cấu hình
        for class_id, pinned_slots in pinned_hdtn_by_class.items():
            for ps in pinned_slots:
                key = (ps.slot_id, hdtn_id)
                if key in x:
                    m.Add(x[key] == 1)
    elif inp.hdtn_thematic_week and getattr(inp, "hdtn_thematic_mode", "auto") == "fixed" and hdtn_id is not None:
        target_wd = getattr(inp, "hdtn_thematic_weekday", None)
        target_sess = getattr(inp, "hdtn_thematic_session", "S") or "S"
        target_start_p = getattr(inp, "hdtn_thematic_start_period", None)
        if target_wd is not None and target_start_p is not None:
            target_periods = {target_start_p, target_start_p + 1, target_start_p + 2}
            for class_id, class_slots in built.slots_by_class.items():
                if inp.need.get((hdtn_id, class_id), 0) >= 3:
                    for s in class_slots:
                        if s.ts.weekday == target_wd and s.ts.session == target_sess and s.ts.period in target_periods:
                            key = (s.slot_id, hdtn_id)
                            if key in x:
                                m.Add(x[key] == 1)

    # 5. Không hở tiết giữa buổi của lớp.
    slot_by_coord = {(s.class_id, s.ts.weekday, s.ts.session, s.ts.period): s for s in inp.slots}
    for s in inp.slots:
        if s.ts.period <= 1:
            continue
        vars_p = [x[s.slot_id, subj.subject_id] for subj in inp.subjects if (s.slot_id, subj.subject_id) in x]
        if not vars_p:
            continue
        prev = slot_by_coord.get((s.class_id, s.ts.weekday, s.ts.session, s.ts.period - 1))
        vars_prev = ([x[prev.slot_id, subj.subject_id] for subj in inp.subjects
                      if (prev.slot_id, subj.subject_id) in x] if prev is not None else [])
        if vars_prev:
            m.Add(sum(vars_p) <= sum(vars_prev))
        else:
            m.Add(sum(vars_p) == 0)

    # 6. Trần tiết/ngày/lớp = đúng số ô lớp đó có trong ngày.
    count_by_class_day = defaultdict(int)
    for s in inp.slots:
        count_by_class_day[s.class_id, s.ts.weekday] += 1
    vars_by_class_day = defaultdict(list)
    for (slot_id, subject_id), var in x.items():
        s = slot_by_id[slot_id]
        vars_by_class_day[s.class_id, s.ts.weekday].append(var)
    for key, vs in vars_by_class_day.items():
        cap = count_by_class_day.get(key, CAP_TIET_NGAY)
        m.Add(sum(vs) <= cap)

    # 7. Lớp không có buổi chỉ 1 tiết.
    groups = defaultdict(list)
    for s in inp.slots:
        groups[s.class_id, s.ts.weekday, s.ts.session].append(s)
    for (class_id, weekday, session), group_slots in groups.items():
        if len(group_slots) < 2:
            continue
        vs = []
        for s in group_slots:
            vs.extend(x[s.slot_id, subj.subject_id] for subj in inp.subjects
                      if (s.slot_id, subj.subject_id) in x)
        if not vs:
            continue
        used = m.NewBoolVar(f"class_used_c{class_id}_wd{weekday}_{session}")
        m.Add(sum(vs) >= 2 * used)
        m.Add(sum(vs) <= len(group_slots) * used)

    # 8. Cân bằng tải học thuật buổi sáng (trần cứng max_academic_per_morning)
    if getattr(config, "balance_morning_academic_load", True):
        academic_ids = {
            s.subject_id for s in inp.subjects
            if is_academic_subject(s.name)
        }
        if academic_ids:
            morning_slots_by_class_day = defaultdict(list)
            for s in inp.slots:
                if s.ts.session == "S":
                    morning_slots_by_class_day[s.class_id, s.ts.weekday].append(s)

            class_has_afternoon = {s.class_id for s in inp.slots if s.ts.session == "C"}
            class_mornings_count = defaultdict(int)
            for (cid, _wd) in morning_slots_by_class_day.keys():
                class_mornings_count[cid] += 1

            for (class_id, weekday), group_slots in morning_slots_by_class_day.items():
                c_mornings = class_mornings_count[class_id]
                c_academic_need = sum(inp.need.get((sid, class_id), 0) for sid in academic_ids)
                is_heavy_morning_only = getattr(config, "heavy_subjects_morning_only", False)
                must_all_in_morning = (class_id not in class_has_afternoon) or is_heavy_morning_only
                if must_all_in_morning and c_mornings > 0:
                    effective_max = max(config.max_academic_per_morning, (c_academic_need + c_mornings - 1) // c_mornings)
                else:
                    effective_max = config.max_academic_per_morning

                academic_vars = [
                    x[s.slot_id, subj_id]
                    for s in group_slots
                    for subj_id in academic_ids
                    if (s.slot_id, subj_id) in x
                ]
                if academic_vars:
                    if len(group_slots) > effective_max:
                        m.Add(sum(academic_vars) <= effective_max)
                    # Sàn cứng: Buổi sáng có từ 3 tiết trở lên phải có ít nhất 1 môn học thuật cốt lõi
                    if len(group_slots) >= 3 and c_academic_need >= c_mornings and c_mornings > 0:
                        m.Add(sum(academic_vars) >= 1)


def _add_block_constraints(built: CpSatModel) -> None:
    """Ràng buộc tính liền kề cho môn KÉP (block_size >= 2) và môn 1 CẶP (single_pair_ids)."""
    m = built.model
    inp = built.inp
    x = built.x
    role_index = built.role_index
    if not role_index or not role_index.block_size:
        return

    single_pair_ids = getattr(role_index, "single_pair_ids", set()) or set()
    hdtn_id = role_index.hdtn_id
    class_hdtn_blocks = defaultdict(dict)

    for cls in inp.classes:
        class_id = cls.class_id
        class_slots = built.slots_by_class.get(class_id, [])
        if not class_slots:
            continue

        session_slots = defaultdict(dict)
        for s in class_slots:
            session_slots[s.ts.weekday, s.ts.session][s.ts.period] = s

        days_in_class = sorted({s.ts.weekday for s in class_slots})

        for subject_id, block_n in role_index.block_size.items():
            if block_n < 2:
                continue
            total_need = inp.need.get((subject_id, class_id), 0)
            if total_need <= 0:
                continue

            is_single_pair = subject_id in single_pair_ids
            block_starts_by_day = defaultdict(list)
            all_block_starts = []

            for (wd, sess), p_map in session_slots.items():
                session_block_starts_at_p = {}
                for p in sorted(p_map):
                    has_all_slots = True
                    consec_slots = []
                    for offset in range(block_n):
                        target_p = p + offset
                        if target_p not in p_map:
                            has_all_slots = False
                            break
                        target_slot = p_map[target_p]
                        if (target_slot.slot_id, subject_id) not in x:
                            has_all_slots = False
                            break
                        consec_slots.append(target_slot)

                    if has_all_slots:
                        b = m.NewBoolVar(f"blk_c{class_id}_m{subject_id}_wd{wd}_{sess}_p{p}")
                        session_block_starts_at_p[p] = b
                        block_starts_by_day[wd].append(b)
                        all_block_starts.append(b)
                        if subject_id == hdtn_id:
                            class_hdtn_blocks[class_id][wd, sess, p] = b
                        for cs in consec_slots:
                            m.Add(b <= x[cs.slot_id, subject_id])

                for p_check in p_map:
                    covering = [
                        session_block_starts_at_p[p_start]
                        for p_start in session_block_starts_at_p
                        if p_start <= p_check < p_start + block_n
                    ]
                    if len(covering) > 1:
                        m.Add(sum(covering) <= 1)

            if is_single_pair:
                if total_need >= 2:
                    m.Add(sum(all_block_starts) == 1)
                    single_days = []
                    for wd in days_in_class:
                        day_vars = [
                            x[s.slot_id, subject_id]
                            for s in class_slots
                            if s.ts.weekday == wd and (s.slot_id, subject_id) in x
                        ]
                        day_blocks = block_starts_by_day.get(wd, [])
                        single_day = m.NewBoolVar(f"sp_single_c{class_id}_m{subject_id}_wd{wd}")
                        single_days.append(single_day)
                        m.Add(single_day + sum(day_blocks) <= 1)
                        m.Add(sum(day_vars) == single_day + 2 * sum(day_blocks))
                    m.Add(sum(single_days) == total_need - 2)
                else:
                    m.Add(sum(all_block_starts) == 0)
            else:
                rem = total_need % block_n
                full_blocks = total_need // block_n
                m.Add(sum(all_block_starts) == full_blocks)

                partial_days = []
                for wd in days_in_class:
                    day_vars = [
                        x[s.slot_id, subject_id]
                        for s in class_slots
                        if s.ts.weekday == wd and (s.slot_id, subject_id) in x
                    ]
                    day_blocks = block_starts_by_day.get(wd, [])
                    if rem > 0:
                        has_partial = m.NewBoolVar(f"partial_c{class_id}_m{subject_id}_wd{wd}")
                        partial_days.append(has_partial)
                        m.Add(has_partial + sum(day_blocks) <= 1)
                        m.Add(sum(day_vars) == block_n * sum(day_blocks) + rem * has_partial)
                    else:
                        m.Add(sum(day_vars) == block_n * sum(day_blocks))

                if rem > 0:
                    m.Add(sum(partial_days) == 1)

    # Đồng bộ khối HĐTN toàn trường khi ở chế độ tự động (auto)
    thematic_mode = getattr(inp, "hdtn_thematic_mode", "auto")
    if inp.hdtn_thematic_week and thematic_mode == "auto" and hdtn_id is not None:
        p_classes = [cls.class_id for cls in inp.classes if inp.need.get((hdtn_id, cls.class_id), 0) >= 3]
        if len(p_classes) >= 2 and all(cls_id in class_hdtn_blocks for cls_id in p_classes):
            common_coords = set.intersection(*[set(class_hdtn_blocks[c].keys()) for c in p_classes])
            if common_coords:
                school_blk = {
                    coord: m.NewBoolVar(f"school_hdtn_wd{coord[0]}_{coord[1]}_p{coord[2]}")
                    for coord in sorted(common_coords)
                }
                m.Add(sum(school_blk.values()) == 1)
                for c_id in p_classes:
                    for coord in common_coords:
                        m.Add(class_hdtn_blocks[c_id][coord] == school_blk[coord])
                    for coord, b in class_hdtn_blocks[c_id].items():
                        if coord not in common_coords:
                            m.Add(b == 0)
            else:
                by_session_set = defaultdict(list)
                for c_id in p_classes:
                    sess_set = frozenset(coord[1] for coord in class_hdtn_blocks[c_id].keys())
                    by_session_set[sess_set].append(c_id)
                for grp_classes in by_session_set.values():
                    if len(grp_classes) >= 2:
                        grp_common = set.intersection(*[set(class_hdtn_blocks[c].keys()) for c in grp_classes])
                        if grp_common:
                            grp_blk = {
                                coord: m.NewBoolVar(f"grp_hdtn_wd{coord[0]}_{coord[1]}_p{coord[2]}")
                                for coord in sorted(grp_common)
                            }
                            m.Add(sum(grp_blk.values()) == 1)
                            for c_id in grp_classes:
                                for coord in grp_common:
                                    m.Add(class_hdtn_blocks[c_id][coord] == grp_blk[coord])
                                for coord, b in class_hdtn_blocks[c_id].items():
                                    if coord not in grp_common:
                                        m.Add(b == 0)


def _is_teacher_busy_morning(inp: SchedulingInput, teacher_id: int, weekday: int) -> bool:
    """Kiểm tra xem GV có bị bận buổi sáng thứ `weekday` hay không.
    Nếu số tiết rảnh khả dụng của GV trong buổi sáng đó < 2 tiết, coi như bận
    (vì theo II.4 không thể xếp buổi 1 tiết cho GV)."""
    if not inp.ban_busy:
        return False
    morn_slots = [s for s in inp.slots if s.ts.weekday == weekday and s.ts.session == "S"]
    if not morn_slots:
        return False
    eff = _build_effective_assigned_teacher(inp)
    candidate_slots = [
        s for s in morn_slots
        if any(eff.get((subj.subject_id, s.class_id)) == teacher_id for subj in inp.subjects)
    ]
    if not candidate_slots:
        free_periods = {s.ts.period for s in morn_slots if (teacher_id, s.ts.ts_id) not in inp.ban_busy}
        return len(free_periods) < 2
    free_periods = {s.ts.period for s in candidate_slots if (teacher_id, s.ts.ts_id) not in inp.ban_busy}
    return len(free_periods) < 2


def _add_locked_slots_constraints(built: CpSatModel) -> None:
    """Áp đặt ràng buộc CỨNG tuyệt đối cho các ô đã được người dùng khóa."""
    m = built.model
    x = built.x
    locked_slots = getattr(built.inp, "locked_slots", {}) or {}
    for slot_id, subject_id in locked_slots.items():
        if (slot_id, subject_id) in x:
            m.Add(x[slot_id, subject_id] == 1)
