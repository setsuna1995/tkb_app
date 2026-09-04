"""Proof of concept: can a CP-SAT model reach 0 lone sessions AND 0 missing
mandatory mornings on the real week-2 data, where the greedy+repair engine
plateaus at ~1.5 lone sessions and ~2.5 teachers missing a morning?

Models the whole week directly. Hard constraints mirror the current engine's
feasibility rules; II.3 and II.4 become objective terms so we can see how far
down they actually go rather than just asking "feasible or not".
"""
import sys
import time
sys.path.insert(0, ".")
from collections import defaultdict
import data.db as db
from data.repositories.builder import build_scheduling_input, get_assignments
from core.models import is_bgh
from core.roles import resolve_roles
from ortools.sat.python import cp_model

conn = db.get_connection("schools/truong-thcs.db")
inp = build_scheduling_input(conn, parity="C", seed=1, week_no=2)
cfg = inp.config
ri = resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week, cfg.single_pair_subject_ids)
at = {k: v for k, v in get_assignments(conn).items() if v is not None}

MAND = tuple(cfg.mandatory_morning_weekdays)          # (2,5,6)
STRICT = (2, 6)                                        # yeu cau moi: moi GV phai co tiet
MIN_LONE = cfg.min_weekly_periods_for_lone_penalty     # 8
LONE_EXEMPT = set(cfg.lone_session_exempt_teacher_ids) # co Hoa
BGH = {t.teacher_id for t in inp.teachers if is_bgh(t)}
MIN_MAND = cfg.min_weekly_periods_for_mandatory_morning

slots = inp.slots
by_class = defaultdict(list)
for s in slots:
    by_class[s.class_id].append(s)
sessions = sorted({(s.ts.weekday, s.ts.session) for s in slots})

# ---- teacher weekly load is fixed by the assignment table, not by the solver
load = defaultdict(int)
for (sub, cid), n in inp.need.items():
    t = at.get((sub, cid))
    if t:
        load[t] += n

m = cp_model.CpModel()
# x[slot, subject] = 1 if that subject occupies that cell
x = {}
for s in slots:
    for sub in inp.subjects:
        if inp.need.get((sub.subject_id, s.class_id), 0) <= 0:
            continue
        x[s.slot_id, sub.subject_id] = m.NewBoolVar(f"x{s.slot_id}_{sub.subject_id}")

# --- every cell filled exactly once (need == slots, zero slack)
for s in slots:
    vs = [x[s.slot_id, sub.subject_id] for sub in inp.subjects
          if (s.slot_id, sub.subject_id) in x]
    m.AddExactlyOne(vs)

# --- per (subject, class): exactly `need` periods
for (sub, cid), n in inp.need.items():
    if n <= 0:
        continue
    vs = [x[s.slot_id, sub] for s in by_class[cid] if (s.slot_id, sub) in x]
    m.Add(sum(vs) == n)

# --- teacher never in two classes at the same timeslot
by_ts = defaultdict(list)
for s in slots:
    by_ts[s.ts.ts_id].append(s)
for ts_id, ss in by_ts.items():
    per_teacher = defaultdict(list)
    for s in ss:
        for sub in inp.subjects:
            if (s.slot_id, sub.subject_id) in x:
                t = at.get((sub.subject_id, s.class_id))
                if t:
                    per_teacher[t].append(x[s.slot_id, sub.subject_id])
    for t, vs in per_teacher.items():
        if len(vs) > 1:
            m.AddAtMostOne(vs)

# --- teacher busy (GV_Ban)
for (t, ts_id) in inp.ban_busy:
    for s in by_ts.get(ts_id, []):
        for sub in inp.subjects:
            if (s.slot_id, sub.subject_id) in x and at.get((sub.subject_id, s.class_id)) == t:
                m.Add(x[s.slot_id, sub.subject_id] == 0)

# --- a subject appears at most once per class per day (HDTN: twice, per the new rule)
for cid, ss in by_class.items():
    per_day = defaultdict(list)
    for s in ss:
        per_day[s.ts.weekday].append(s)
    for wd, day_slots in per_day.items():
        for sub in inp.subjects:
            vs = [x[s.slot_id, sub.subject_id] for s in day_slots if (s.slot_id, sub.subject_id) in x]
            if not vs:
                continue
            cap = 2 if sub.subject_id == ri.hdtn_id else 1
            m.Add(sum(vs) <= cap)

# --- chao co: HDTN pinned at Monday period 1 in every class
for cid, ss in by_class.items():
    for s in ss:
        if s.ts.weekday == cfg.chao_co_weekday and s.ts.session == "S" and s.ts.period == cfg.chao_co_period:
            if (s.slot_id, ri.hdtn_id) in x:
                m.Add(x[s.slot_id, ri.hdtn_id] == 1)

# --- SHL: HDTN pinned at the class's LAST morning period on Friday (wd 6)
for cid, ss in by_class.items():
    fri = [s for s in ss if s.ts.weekday == 6 and s.ts.session == "S"]
    if fri:
        last = max(fri, key=lambda s: s.ts.period)
        if (last.slot_id, ri.hdtn_id) in x:
            m.Add(x[last.slot_id, ri.hdtn_id] == 1)

# --- morning-only subjects
for s in slots:
    if s.ts.session != "C":
        continue
    for sub_id in cfg.morning_only_subject_ids:
        if (s.slot_id, sub_id) in x:
            m.Add(x[s.slot_id, sub_id] == 0)

# --- GDTC allowed periods + never on consecutive days for a class
if ri.gdtc_id is not None:
    for s in slots:
        if (s.slot_id, ri.gdtc_id) not in x:
            continue
        ok = (s.ts.period in cfg.gdtc_morning_allowed_periods) if s.ts.session == "S" \
            else (s.ts.period in cfg.gdtc_afternoon_allowed_periods)
        if not ok or s.ts.period == cfg.gdtc_avoid_period:
            m.Add(x[s.slot_id, ri.gdtc_id] == 0)
    if cfg.avoid_gdtc_consecutive_days:
        for cid, ss in by_class.items():
            day = defaultdict(list)
            for s in ss:
                if (s.slot_id, ri.gdtc_id) in x:
                    day[s.ts.weekday].append(x[s.slot_id, ri.gdtc_id])
            wds = sorted(day)
            for a, b in zip(wds, wds[1:]):
                if b == a + 1:
                    m.Add(sum(day[a]) + sum(day[b]) <= 1)

# --- heavy subjects per class session
for cid, ss in by_class.items():
    per_sess = defaultdict(list)
    for s in ss:
        for sub_id in ri.heavy_ids:
            if (s.slot_id, sub_id) in x:
                per_sess[(s.ts.weekday, s.ts.session)].append(x[s.slot_id, sub_id])
    for key, vs in per_sess.items():
        if len(vs) > cfg.max_heavy_per_session:
            m.Add(sum(vs) <= cfg.max_heavy_per_session)

# ---- teacher-session occupancy variables -------------------------------------
teachers = sorted(load)
cnt = {}      # (teacher, wd, sess) -> IntVar number of periods
used = {}     # bool: teacher uses that session at all
lone = {}     # bool: exactly 1 period there
for t in teachers:
    for (wd, sess) in sessions:
        vs = []
        for s in slots:
            if s.ts.weekday != wd or s.ts.session != sess:
                continue
            for sub in inp.subjects:
                if (s.slot_id, sub.subject_id) in x and at.get((sub.subject_id, s.class_id)) == t:
                    vs.append(x[s.slot_id, sub.subject_id])
        c = m.NewIntVar(0, cfg.max_periods_per_session, f"c{t}_{wd}{sess}")
        m.Add(c == sum(vs) if vs else c == 0)
        cnt[t, wd, sess] = c
        u = m.NewBoolVar(f"u{t}_{wd}{sess}")
        m.Add(c >= 1).OnlyEnforceIf(u)
        m.Add(c == 0).OnlyEnforceIf(u.Not())
        used[t, wd, sess] = u
        l = m.NewBoolVar(f"l{t}_{wd}{sess}")
        m.Add(c == 1).OnlyEnforceIf(l)
        m.Add(c != 1).OnlyEnforceIf(l.Not())
        lone[t, wd, sess] = l
    # max periods per day
    for wd in sorted({w for (w, _s) in sessions}):
        parts = [cnt[t, wd, ss] for (w, ss) in sessions if w == wd]
        if parts:
            m.Add(sum(parts) <= cfg.max_teacher_periods_per_day)

# ---- objectives --------------------------------------------------------------
lone_terms = [lone[t, wd, sess] for t in teachers for (wd, sess) in sessions
              if load[t] >= MIN_LONE and t not in LONE_EXEMPT]
miss_terms = []
for t in teachers:
    for wd in sorted(set(MAND) | set(STRICT)):
        if (t, wd, "S") not in used:
            continue
        required = (wd in STRICT and t not in BGH) or (wd in MAND and load[t] >= MIN_MAND)
        if required:
            miss = m.NewBoolVar(f"miss{t}_{wd}")
            m.Add(used[t, wd, "S"] == 0).OnlyEnforceIf(miss)
            m.Add(used[t, wd, "S"] == 1).OnlyEnforceIf(miss.Not())
            miss_terms.append(miss)

m.Minimize(100 * sum(miss_terms) + 100 * sum(lone_terms))

solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 240.0
solver.parameters.num_search_workers = 8
t0 = time.perf_counter()
status = solver.Solve(m)
el = time.perf_counter() - t0

print("trang thai      :", solver.StatusName(status))
print(f"thoi gian       : {el:.1f}s")
if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    nm = sum(solver.Value(v) for v in miss_terms)
    nl = sum(solver.Value(v) for v in lone_terms)
    print("so GV thieu sang bat buoc (II.3):", nm, f"/ {len(miss_terms)} rang buoc")
    print("so buoi le (II.4)               :", nl)
    print("can duoi da chung minh          :", solver.BestObjectiveBound())
else:
    print("khong tim duoc loi giai")
