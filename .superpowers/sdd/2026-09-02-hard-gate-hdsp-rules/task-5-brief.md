# Task 5: `validation.py` Detail Finders + Save-Gate Wiring in `pages/06_Xep_TKB.py`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Today `core/validation.py`'s `find_*` functions only ever produce
`st.error(...)` warnings in `pages/06_Xep_TKB.py` — none of them block the
"✅ Chấp nhận và lưu làm lịch chính thức" button. Add detail-level finders
for II.3/II.4/II.8/II.14 (mirroring the thresholds Task 4's gate already
enforces, so the UI and the gate can never silently disagree), and make
violations of these specific rules **block the save button** — following the
exact same `disabled=... and not proceed_anyway` pattern the file already
uses for the quota-overload warning (see `pages/06_Xep_TKB.py:60-69,84`).
Also render `result.relaxed_rules` (from Task 4) so the user sees exactly
which rule was relaxed and for which teacher when the engine had to fall
back.

**Prerequisite:** Task 3 (`core/rules_registry.py`) and Task 4 (`engine.py`
gate + `relaxed_rules`) must be complete.

**Note on why this task has no automated UI test:** `pages/*.py` files in
this codebase are Streamlit scripts with no existing unit test coverage
(confirmed: no `tests/test_06*.py` or similar exists) — verification here is
manual, via `streamlit run app.py`, per Step 6 below. The new `core/validation.py`
functions ARE unit tested (Steps 1-4), since that's where the actual logic
lives.

**Files:**
- Modify: `core/validation.py` (add 5 new `find_*` functions)
- Modify: `pages/06_Xep_TKB.py` (imports, new violation-checking block, save-gate wiring)
- Test: `tests/test_validation_hdsp_rules.py` (new file)

**Interfaces:**
- Produces (in `core/validation.py`):
  `find_teacher_missing_mandatory_morning_violations(slots, assignment, assigned_teacher, mandatory_mornings=(2,5,6)) -> list[tuple[int,int]]`,
  `find_teacher_lone_session_violations(slots, assignment, assigned_teacher, min_weekly_periods=15) -> list[tuple[int,int,str]]`,
  `find_teacher_lone_day_violations(slots, assignment, assigned_teacher, min_weekly_periods=15) -> list[tuple[int,int]]`,
  `find_teacher_split_day_violations(slots, assignment, assigned_teacher) -> list[tuple[int,int]]`,
  `find_teacher_4_consecutive_morning_violations(slots, assignment, assigned_teacher, max_load_for_penalty=20) -> list[tuple[int,int]]`.
- Consumes: `core.rules_registry.RULES`, `core.rules_registry.HARD_POST_GENERATION_IDS` (Task 3); `ScheduleResult.relaxed_rules` (Task 1/4).

---

- [ ] **Step 1: Write the failing tests for the new validators**

Create `tests/test_validation_hdsp_rules.py`:

```python
from core.models import Slot, TimeSlot
from core.validation import (
    find_teacher_4_consecutive_morning_violations, find_teacher_lone_day_violations,
    find_teacher_lone_session_violations, find_teacher_missing_mandatory_morning_violations,
    find_teacher_split_day_violations,
)


def _slots_for(weekday_period_pairs, class_id=101, session="S"):
    return [Slot(i + 1, class_id, TimeSlot(i + 1, wd, session, p)) for i, (wd, p) in enumerate(weekday_period_pairs)]


def test_find_teacher_missing_mandatory_morning_violations():
    # Teacher 1 has 12 periods total but zero on Thursday (wd=5) morning.
    pairs = [(2, p) for p in range(1, 5)] + [(4, p) for p in range(1, 5)] + [(6, p) for p in range(1, 5)]
    slots = _slots_for(pairs)
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    violations = find_teacher_missing_mandatory_morning_violations(slots, assignment, assigned_teacher)
    assert (1, 5) in violations


def test_find_teacher_lone_session_violations_exempts_low_load():
    # Teacher 1: single lone session, but total load (1) < default threshold (15) -> exempt.
    slots = _slots_for([(2, 1)])
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_lone_session_violations(slots, assignment, assigned_teacher, min_weekly_periods=15) == []
    assert find_teacher_lone_session_violations(slots, assignment, assigned_teacher, min_weekly_periods=0) == [(1, 2, "S")]


def test_find_teacher_lone_day_violations():
    slots = _slots_for([(2, 1)])
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_lone_day_violations(slots, assignment, assigned_teacher, min_weekly_periods=0) == [(1, 2)]


def test_find_teacher_split_day_violations():
    slots = _slots_for([(2, 1)], session="S") + _slots_for([(2, 2)], session="C")
    for i, s in enumerate(slots):
        s.slot_id = i + 1
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_split_day_violations(slots, assignment, assigned_teacher) == [(1, 2)]


def test_find_teacher_4_consecutive_morning_violations():
    pairs = [(2, p) for p in range(1, 5)]  # 4 periods on one morning, total load = 4 (<=20)
    slots = _slots_for(pairs)
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_4_consecutive_morning_violations(slots, assignment, assigned_teacher, max_load_for_penalty=20) == [(1, 2)]
    assert find_teacher_4_consecutive_morning_violations(slots, assignment, assigned_teacher, max_load_for_penalty=2) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validation_hdsp_rules.py -v`
Expected: 5 FAILs with `ImportError` (functions don't exist yet).

- [ ] **Step 3: Add the 5 new finder functions to `core/validation.py`**

Append at the end of `core/validation.py` (after `find_heavy_afternoon_period3_violations`):

```python
def find_teacher_missing_mandatory_morning_violations(slots: list, assignment: dict, assigned_teacher: dict,
                                                        mandatory_mornings: tuple = (2, 5, 6)) -> list:
    """Returns [(teacher_id, weekday), ...] for teachers (>=10 periods/week) who end up
    with zero periods on a mandatory morning -- Tiêu chí II.3: catches an accidental
    empty forbidden morning beyond the teacher's one designated off-slot. Mirrors
    core.scheduler.quality._count_teacher_missing_mandatory_mornings exactly, so this
    check and the engine's post-generation gate (core/scheduler/engine.py) never disagree."""
    teacher_morns = defaultdict(lambda: defaultdict(int))
    teacher_totals = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id <= 0:
            continue
        teacher_totals[teacher_id] += 1
        if slot.ts.session == "S" and slot.ts.weekday in mandatory_mornings:
            teacher_morns[teacher_id][slot.ts.weekday] += 1

    violations = []
    for teacher_id, total in teacher_totals.items():
        if total >= 10:
            for wd in mandatory_mornings:
                if teacher_morns[teacher_id][wd] == 0:
                    violations.append((teacher_id, wd))
    return violations


def find_teacher_lone_session_violations(slots: list, assignment: dict, assigned_teacher: dict,
                                          min_weekly_periods: int = 15) -> list:
    """Returns [(teacher_id, weekday, session), ...] for any teacher session with
    exactly 1 period -- Tiêu chí II.4, exempting teachers below min_weekly_periods.
    Mirrors core.scheduler.quality._count_teacher_lone_sessions exactly."""
    t_sess = defaultdict(int)
    teacher_totals = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id <= 0:
            continue
        t_sess[(teacher_id, slot.ts.weekday, slot.ts.session)] += 1
        teacher_totals[teacher_id] += 1

    return [
        (tid, wd, sess) for (tid, wd, sess), count in t_sess.items()
        if count == 1 and teacher_totals[tid] >= min_weekly_periods
    ]


def find_teacher_lone_day_violations(slots: list, assignment: dict, assigned_teacher: dict,
                                      min_weekly_periods: int = 15) -> list:
    """Returns [(teacher_id, weekday), ...] for any teacher day with exactly 1 period
    total -- Tiêu chí II.4, exempting teachers below min_weekly_periods. Mirrors
    core.scheduler.quality._count_teacher_lone_days exactly."""
    teacher_days = defaultdict(int)
    teacher_totals = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id <= 0:
            continue
        teacher_days[(teacher_id, slot.ts.weekday)] += 1
        teacher_totals[teacher_id] += 1

    return [
        (tid, wd) for (tid, wd), count in teacher_days.items()
        if count == 1 and teacher_totals[tid] >= min_weekly_periods
    ]


def find_teacher_split_day_violations(slots: list, assignment: dict, assigned_teacher: dict) -> list:
    """Returns [(teacher_id, weekday), ...] for any teacher day with exactly 1 morning
    period AND exactly 1 afternoon period -- Tiêu chí II.8. Mirrors
    core.scheduler.quality._count_teacher_split_sessions exactly."""
    teacher_day_sessions = defaultdict(lambda: defaultdict(int))
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id <= 0:
            continue
        teacher_day_sessions[(teacher_id, slot.ts.weekday)][slot.ts.session] += 1

    violations = []
    for (teacher_id, wd), sess_counts in teacher_day_sessions.items():
        if sess_counts.get("S", 0) == 1 and sess_counts.get("C", 0) == 1:
            violations.append((teacher_id, wd))
    return violations


def find_teacher_4_consecutive_morning_violations(slots: list, assignment: dict, assigned_teacher: dict,
                                                    max_load_for_penalty: int = 20) -> list:
    """Returns [(teacher_id, weekday), ...] for any teacher with >=4 periods in one
    morning session -- Tiêu chí II.14, exempting teachers above max_load_for_penalty.
    Mirrors core.scheduler.quality._count_teacher_4_consecutive_mornings exactly."""
    t_morn_periods = defaultdict(list)
    teacher_totals = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id <= 0:
            continue
        teacher_totals[teacher_id] += 1
        if slot.ts.session == "S":
            t_morn_periods[(teacher_id, slot.ts.weekday)].append(slot.ts.period)

    violations = []
    for (teacher_id, wd), periods in t_morn_periods.items():
        if len(periods) >= 4 and teacher_totals[teacher_id] <= max_load_for_penalty:
            violations.append((teacher_id, wd))
    return violations
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validation_hdsp_rules.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Wire save-gate blocking into `pages/06_Xep_TKB.py`**

Add to the imports block at the top (extend the existing
`from core.validation import (...)` — line 6-11):
```python
from core.validation import (
    compute_quota_diff, find_consecutive_subject_days, find_heavy_afternoon_period3_violations,
    find_invalid_gdtc_periods, find_max_heavy_violations, find_morning_only_violations,
    find_single_pair_violations, find_subject_class_rule_violations, find_teacher_conflicts,
    find_teacher_day_cap_violations, find_teacher_gaps, find_teacher_unavailability_violations,
    find_teacher_4_consecutive_morning_violations, find_teacher_lone_day_violations,
    find_teacher_lone_session_violations, find_teacher_missing_mandatory_morning_violations,
    find_teacher_split_day_violations,
)
from core.rules_registry import RULES
```

Insert this new block right after the existing "Kiểm tra môn Nặng vào tiết 3
chiều" block (immediately after line 334, `st.error(f"❌ Phát hiện {len(heavy_p3_violations)}...")`, and before the "Đánh giá chất lượng lịch dạy" comment at line 336):

```python
        # Kiểm tra các tiêu chí HĐSP được hard-gate (II.3, II.4, II.8, II.14) -- vi phạm các
        # rule này sẽ CHẶN nút lưu (khác các cảnh báo phía trên chỉ hiển thị thông tin).
        teacher_map = {t.teacher_id: t.name for t in inp.teachers}
        hard_rule_violations = {}

        missing_morning = find_teacher_missing_mandatory_morning_violations(
            inp.slots, result.assignment, inp.assigned_teacher,
            getattr(inp.config, "mandatory_morning_weekdays", (2, 5, 6)),
        )
        if missing_morning:
            hard_rule_violations["II.3"] = missing_morning

        min_lone_load = getattr(inp.config, "min_weekly_periods_for_lone_penalty", 15)
        lone_sessions = find_teacher_lone_session_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
        lone_days = find_teacher_lone_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
        if lone_sessions or lone_days:
            hard_rule_violations["II.4"] = lone_sessions + [(tid, wd, "cả ngày") for tid, wd in lone_days]

        split_days = find_teacher_split_day_violations(inp.slots, result.assignment, inp.assigned_teacher)
        if split_days:
            hard_rule_violations["II.8"] = split_days

        consecutive_morning = find_teacher_4_consecutive_morning_violations(inp.slots, result.assignment, inp.assigned_teacher)
        if consecutive_morning:
            hard_rule_violations["II.14"] = consecutive_morning

        if hard_rule_violations:
            st.error(f"❌ Còn {len(hard_rule_violations)} tiêu chí HĐSP bắt buộc chưa được thỏa mãn (chặn lưu):")
            for rule_id, items in hard_rule_violations.items():
                with st.expander(f"{rule_id}: {RULES[rule_id].title_vi} ({len(items)} trường hợp)", expanded=False):
                    for item in items:
                        tid = item[0]
                        tname = teacher_map.get(tid, f"GV #{tid}")
                        rest = ", ".join(str(x) for x in item[1:])
                        st.write(f"- {tname}: {rest}")

        if result.relaxed_rules:
            st.warning(f"⚠️ Lịch được tạo là phương án khả thi tốt nhất, nhưng {len(result.relaxed_rules)} ràng buộc HĐSP đã phải nới lỏng:")
            for item in result.relaxed_rules:
                rule_id = item.get("rule_id")
                title = RULES[rule_id].title_vi if rule_id in RULES else rule_id
                if item.get("detail") == "off_slot_shortfall":
                    teachers_short = item.get("teachers", {})
                    names = ", ".join(
                        f"{teacher_map.get(tid, f'GV #{tid}')} ({got}/{need} buổi)"
                        for tid, (got, need) in teachers_short.items()
                    )
                    st.write(f"- {rule_id}: {title} — thiếu buổi nghỉ cho: {names}")
                else:
                    st.write(f"- {rule_id}: {title}")

        proceed_with_hard_violations = True
        if hard_rule_violations:
            proceed_with_hard_violations = st.checkbox(
                "Vẫn lưu dù còn vi phạm tiêu chí HĐSP bắt buộc ở trên (không khuyến khích)",
                key="proceed_with_hard_violations",
            )
```

- [ ] **Step 6: Wire `disabled=` on the save button**

Change (line 370):
```python
        if st.button("✅ Chấp nhận và lưu làm lịch chính thức", type="primary"):
```
to:
```python
        if st.button(
            "✅ Chấp nhận và lưu làm lịch chính thức", type="primary",
            disabled=bool(hard_rule_violations) and not proceed_with_hard_violations,
        ):
```

- [ ] **Step 7: Manual verification via the running app**

Run: `streamlit run app.py` (or the project's documented dev-server command
in `README.md` if different).
1. Navigate to "Xếp thời khóa biểu".
2. Run a schedule generation against an existing school (`schools/*.db` via
   the school switcher) or the sample fixture.
3. Confirm: if `hard_rule_violations` is empty, the save button is enabled
   as before (no regression for the common case).
4. If you can reproduce a case with violations (e.g. temporarily set
   `min_weekly_periods_for_lone_penalty=0` in the config page to force some
   real lone sessions to show as violations), confirm the save button is
   disabled, the expander shows the affected teachers by name, and checking
   "Vẫn lưu dù còn vi phạm..." re-enables it.
5. Confirm `result.relaxed_rules` renders correctly for a schedule where it's
   empty (no warning box shown at all).

Record what you observed (with a screenshot if convenient) in
`task-5-report.md`.

- [ ] **Step 8: Commit**

```bash
git add core/validation.py pages/06_Xep_TKB.py tests/test_validation_hdsp_rules.py
git commit -m "feat: block save on unresolved II.3/II.4/II.8/II.14 violations, surface relaxed_rules"
```

- [ ] **Step 9: Write task-5-report.md**

Summarize (Vietnamese) the new validators, test results, and manual
verification observations from Step 7.
