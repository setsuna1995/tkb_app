# Ưu tiên môn nặng đầu sáng / môn nhẹ buổi chiều (ràng buộc mềm) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 2 soft (best-effort) scoring preferences to the scheduler — heavy ("Nặng") subjects preferentially land in the first N morning periods, and subjects on a configurable list preferentially land in the afternoon — both off by default so no existing school's schedule changes until it explicitly opts in.

**Architecture:** 2 new `SchedulingConfig` fields ride the existing per-school `app_meta` persistence pattern (`data/repository.py`). `_pick_best_scored()` in `core/scheduler.py` gains 2 small scoring adjustments gated on those fields. The adjustments live **only** in the greedy scored path — never in `_feasible()`, `_pick_best_simple()`, or `_try_swap_repair()` — so this feature can never turn a solvable schedule into an unsolvable one. UI adds 1 number input + 1 subject multiselect to the existing "Cấu hình xếp lịch" page, plus 2 conditional lines in the sidebar rules summary.

**Tech Stack:** Python 3, Streamlit, SQLite (stdlib `sqlite3`), pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-rang-buoc-xep-lich-v2-design.md` (mục "Kiến trúc" → "1. Yêu cầu #1+#2")

## Global Constraints

- Defaults `heavy_subject_priority_periods=0` and `afternoon_preferred_subject_ids=frozenset()` must reproduce today's scheduling output byte-for-byte — no scoring adjustment may fire until a school explicitly saves a non-default value (same rule established in the prior scheduling-config plan).
- Soft/best-effort only: the 2 new adjustments touch **only** `_pick_best_scored()`. Never add them to `_feasible()`, `_pick_best_simple()`, or `_try_swap_repair()`.
- Bonus/penalty magnitude is `30` for both (module constants `HEAVY_MORNING_BONUS`, `AFTERNOON_MISMATCH_PENALTY`) — same order of magnitude as the existing `IDLE_DAY_BONUS = 30`, well below any `remaining_need` difference (multiples of 100) and well above the `rng.random()` jitter (< 1), so it's a tiebreaker, never an override.
- The 2 rules are independent and only stack when both conditions are met on the same candidate — do not add a "penalize heavy subject in the afternoon" branch to the morning-priority rule; that's the afternoon rule's job alone (avoids double-penalizing the same subject for two different reasons).
- No changes to any `sched.run(inp)` call site signature.
- All existing tests in `tests/test_scheduler.py`, `tests/test_models.py`, `tests/test_repository.py` must keep passing unmodified.

---

## Task 1: `SchedulingConfig` gets 2 new soft-bias fields

**Files:**
- Modify: `core/models.py:82-97` (`SchedulingConfig` — append 2 fields after `reserved_off_weekdays_chieu`)
- Test: `tests/test_models.py` (extend existing file)

**Interfaces:**
- Produces: `SchedulingConfig.heavy_subject_priority_periods: int = 0`, `SchedulingConfig.afternoon_preferred_subject_ids: frozenset = frozenset()`.

- [ ] **Step 1: Write the failing test**

In `tests/test_models.py`, extend the existing defaults test and add a new one:

```python
def test_scheduling_config_defaults_match_current_hardcoded_behavior():
    config = SchedulingConfig()
    assert config.gdtc_avoid_period == 5
    assert config.chao_co_weekday == 2
    assert config.chao_co_period == 1
    assert config.max_heavy_consecutive == 3
    assert config.max_periods_per_session == 4
    assert config.teacher_off_sessions_per_week == 1
    assert config.forbidden_off_cells == frozenset({(2, "S"), (5, "S"), (6, "S"), (5, "C"), (6, "C")})
    assert config.reserved_off_weekdays_chieu == (5, 6)
    assert config.heavy_subject_priority_periods == 0
    assert config.afternoon_preferred_subject_ids == frozenset()


def test_scheduling_config_accepts_soft_bias_overrides():
    config = SchedulingConfig(heavy_subject_priority_periods=2, afternoon_preferred_subject_ids=frozenset({3, 7}))
    assert config.heavy_subject_priority_periods == 2
    assert config.afternoon_preferred_subject_ids == frozenset({3, 7})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — `test_scheduling_config_defaults_match_current_hardcoded_behavior` fails with `AttributeError: 'SchedulingConfig' object has no attribute 'heavy_subject_priority_periods'`; `test_scheduling_config_accepts_soft_bias_overrides` fails with `TypeError: __init__() got an unexpected keyword argument 'heavy_subject_priority_periods'`.

- [ ] **Step 3: Add the 2 fields**

In `core/models.py`, append to the end of `SchedulingConfig` (currently ending at line 97 with `reserved_off_weekdays_chieu: tuple = (5, 6)`):

```python
    reserved_off_weekdays_chieu: tuple = (5, 6)
    heavy_subject_priority_periods: int = 0   # 0 = tắt; số tiết đầu buổi sáng được cộng điểm ưu tiên môn "Nặng"
    afternoon_preferred_subject_ids: frozenset = field(default_factory=frozenset)  # rỗng = tắt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: add soft morning/afternoon subject-preference fields to SchedulingConfig"
```

---

## Task 2: Persist the 2 new fields (`data/repository.py`)

**Files:**
- Modify: `data/repository.py:537-575` (add 2 helper functions, extend `get_scheduling_config`/`set_scheduling_config`)
- Test: `tests/test_repository.py` (extend existing file)

**Interfaces:**
- Consumes: `SchedulingConfig` (Task 1), `get_meta`/`set_meta` (existing, `data/repository.py:506-516`)
- Produces: `get_scheduling_config`/`set_scheduling_config` now round-trip the 2 new fields; new private helpers `_parse_id_set`/`_format_id_set`.

- [ ] **Step 1: Write the failing test**

In `tests/test_repository.py`, add after `test_set_then_get_scheduling_config_round_trips`:

```python
def test_set_then_get_scheduling_config_round_trips_soft_bias_fields(conn):
    custom = SchedulingConfig(
        heavy_subject_priority_periods=2,
        afternoon_preferred_subject_ids=frozenset({3, 7}),
    )
    repo.set_scheduling_config(conn, custom)
    assert repo.get_scheduling_config(conn) == custom
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_repository.py -v`
Expected: FAIL — `repo.get_scheduling_config(conn)` comes back with `heavy_subject_priority_periods=0` and `afternoon_preferred_subject_ids=frozenset()` (the dataclass defaults) instead of the saved `2`/`{3, 7}`, because `get_scheduling_config`/`set_scheduling_config` don't read/write the 2 new `sched_*` keys yet.

- [ ] **Step 3: Add persistence**

In `data/repository.py`, add 2 helpers right after the existing `_format_weekday_tuple` (currently ending at line 542):

```python
def _parse_id_set(raw: str) -> frozenset:
    return frozenset(int(x) for x in raw.split(",") if x.strip())


def _format_id_set(ids) -> str:
    return ",".join(str(i) for i in sorted(ids))
```

Change `get_scheduling_config` (currently lines 545-564) to:

```python
def get_scheduling_config(conn: sqlite3.Connection) -> SchedulingConfig:
    default = SchedulingConfig()
    forbidden_raw = get_meta(conn, "sched_forbidden_off_cells")
    reserved_raw = get_meta(conn, "sched_reserved_off_weekdays_chieu")
    afternoon_preferred_raw = get_meta(conn, "sched_afternoon_preferred_subject_ids")
    return SchedulingConfig(
        gdtc_avoid_period=int(get_meta(conn, "sched_gdtc_avoid_period") or default.gdtc_avoid_period),
        chao_co_weekday=int(get_meta(conn, "sched_chao_co_weekday") or default.chao_co_weekday),
        chao_co_period=int(get_meta(conn, "sched_chao_co_period") or default.chao_co_period),
        max_heavy_consecutive=int(get_meta(conn, "sched_max_heavy_consecutive") or default.max_heavy_consecutive),
        max_periods_per_session=int(
            get_meta(conn, "sched_max_periods_per_session") or default.max_periods_per_session
        ),
        teacher_off_sessions_per_week=int(
            get_meta(conn, "sched_teacher_off_sessions_per_week") or default.teacher_off_sessions_per_week
        ),
        forbidden_off_cells=_parse_off_cells(forbidden_raw) if forbidden_raw else default.forbidden_off_cells,
        reserved_off_weekdays_chieu=(
            _parse_weekday_tuple(reserved_raw) if reserved_raw else default.reserved_off_weekdays_chieu
        ),
        heavy_subject_priority_periods=int(
            get_meta(conn, "sched_heavy_subject_priority_periods") or default.heavy_subject_priority_periods
        ),
        afternoon_preferred_subject_ids=(
            _parse_id_set(afternoon_preferred_raw) if afternoon_preferred_raw
            else default.afternoon_preferred_subject_ids
        ),
    )
```

Change `set_scheduling_config` (currently lines 567-575) to:

```python
def set_scheduling_config(conn: sqlite3.Connection, config: SchedulingConfig) -> None:
    set_meta(conn, "sched_gdtc_avoid_period", str(config.gdtc_avoid_period))
    set_meta(conn, "sched_chao_co_weekday", str(config.chao_co_weekday))
    set_meta(conn, "sched_chao_co_period", str(config.chao_co_period))
    set_meta(conn, "sched_max_heavy_consecutive", str(config.max_heavy_consecutive))
    set_meta(conn, "sched_max_periods_per_session", str(config.max_periods_per_session))
    set_meta(conn, "sched_teacher_off_sessions_per_week", str(config.teacher_off_sessions_per_week))
    set_meta(conn, "sched_forbidden_off_cells", _format_off_cells(config.forbidden_off_cells))
    set_meta(conn, "sched_reserved_off_weekdays_chieu", _format_weekday_tuple(config.reserved_off_weekdays_chieu))
    set_meta(conn, "sched_heavy_subject_priority_periods", str(config.heavy_subject_priority_periods))
    set_meta(conn, "sched_afternoon_preferred_subject_ids", _format_id_set(config.afternoon_preferred_subject_ids))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_repository.py -v`
Expected: PASS (all tests, including the pre-existing `test_get_scheduling_config_returns_defaults_when_never_saved` and `test_set_then_get_scheduling_config_round_trips`)

- [ ] **Step 5: Commit**

```bash
git add data/repository.py tests/test_repository.py
git commit -m "feat: persist soft morning/afternoon subject-preference fields per school"
```

---

## Task 3: Scoring adjustments in `core/scheduler.py`

**Files:**
- Modify: `core/scheduler.py:29-37` (2 new module constants), `core/scheduler.py:206-243` (`_pick_best_scored`)
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `SchedulingConfig.heavy_subject_priority_periods`/`afternoon_preferred_subject_ids` (Task 1), `role_index.heavy_ids` (existing, `core/roles.py`)
- Produces: `_pick_best_scored(...)` now biases its choice per the 2 new config fields; unchanged signature.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler.py`, near the other `_pick_best_scored`-adjacent tests (or at the end of the file):

```python
def test_heavy_subject_priority_bonus_only_applies_within_configured_window():
    subjects = [Subject(1, "Toan", ROLE_NANG), Subject(2, "Nhac", ROLE_THUONG), Subject(3, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig(heavy_subject_priority_periods=2)
    assigned_teacher = {(1, 1): 100, (2, 1): 101}

    # Tiết 1 (trong ngưỡng 2 tiết đầu): môn nặng luôn thắng, bất kể seed --
    # bonus (30) > nhiễu rng tối đa (< 1) khi remaining_need bằng nhau.
    for seed in range(10):
        state = _State(remaining_need={(1, 1): 5, (2, 1): 5}, busy=set())
        slot = Slot(1, 1, TimeSlot(1, 2, "S", 1))
        pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                        0.0, random.Random(seed), config=config)
        assert pick == (1, 100), f"seed={seed}: môn nặng phải thắng tiết 1 (trong ngưỡng ưu tiên 2 tiết đầu)"

    # Tiết 3 (ngoài ngưỡng): không còn bonus -> kết quả phải đổi tuỳ seed, không luôn là môn nặng.
    outcomes = set()
    for seed in range(10):
        state = _State(remaining_need={(1, 1): 5, (2, 1): 5}, busy=set())
        state.occupied[(1, 2, "S", 2)] = True  # thoả liền mạch cho tiết 3
        slot = Slot(1, 1, TimeSlot(1, 2, "S", 3))
        pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                        0.0, random.Random(seed), config=config)
        outcomes.add(pick)
    assert len(outcomes) == 2, "tiết 3 nằm ngoài ngưỡng ưu tiên -> không còn thiên vị, cả 2 môn đều có thể thắng"


def test_afternoon_preferred_subjects_soft_bias():
    subjects = [Subject(1, "Nhac", ROLE_THUONG), Subject(2, "Su", ROLE_THUONG), Subject(3, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig(afternoon_preferred_subject_ids=frozenset({1}))
    assigned_teacher = {(1, 1): 100, (2, 1): 101}

    # Buổi chiều: Nhạc (trong danh sách ưu tiên) luôn thắng Sử (không trong danh sách).
    for seed in range(10):
        state = _State(remaining_need={(1, 1): 5, (2, 1): 5}, busy=set())
        slot = Slot(1, 1, TimeSlot(1, 2, "C", 1))
        pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                        0.0, random.Random(seed), config=config)
        assert pick == (1, 100), f"seed={seed}: Nhạc (afternoon_preferred_subject_ids) phải thắng Sử buổi chiều"

    # Buổi sáng: danh sách ưu tiên buổi chiều không áp dụng -> kết quả phải đổi tuỳ seed.
    outcomes = set()
    for seed in range(10):
        state = _State(remaining_need={(1, 1): 5, (2, 1): 5}, busy=set())
        slot = Slot(1, 1, TimeSlot(1, 2, "S", 1))
        pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                        0.0, random.Random(seed), config=config)
        outcomes.add(pick)
    assert len(outcomes) == 2, "buổi sáng không áp dụng luật ưu tiên buổi chiều -> không còn thiên vị"


def test_pick_best_scored_unbiased_with_default_config():
    # Regression: config=None (mặc định) -> không thiên vị gì, kể cả tiết 1 buổi sáng.
    subjects = [Subject(1, "Toan", ROLE_NANG), Subject(2, "Nhac", ROLE_THUONG), Subject(3, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    assigned_teacher = {(1, 1): 100, (2, 1): 101}

    outcomes = set()
    for seed in range(10):
        state = _State(remaining_need={(1, 1): 5, (2, 1): 5}, busy=set())
        slot = Slot(1, 1, TimeSlot(1, 2, "S", 1))
        pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                        0.0, random.Random(seed))
        outcomes.add(pick)
    assert len(outcomes) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -k "priority_bonus_only_applies or afternoon_preferred_subjects_soft_bias or pick_best_scored_unbiased" -v`
Expected: `test_heavy_subject_priority_bonus_only_applies_within_configured_window` and `test_afternoon_preferred_subjects_soft_bias` FAIL (the first loop's `assert pick == (1, 100)` fails on at least one seed, since no bias exists yet). `test_pick_best_scored_unbiased_with_default_config` already PASSES (there's no bias to begin with) — this is expected; it's the regression guard for later, not a RED test now.

- [ ] **Step 3: Implement the 2 scoring adjustments**

In `core/scheduler.py`, add 2 module constants right after the existing `IDLE_DAY_BONUS` block (currently lines 29-32, immediately before the blank line preceding `FORBIDDEN_OFF_CELLS`):

```python
IDLE_DAY_BONUS = 30       # điểm thưởng mềm khi đặt tiết vào ngày GV đang trống hẳn
                          # (< 100 = remaining_need*100 nên không vượt môn thiếu tiết;
                          # < 50 = phạt dàn-môn nên heuristic đó vẫn ưu tiên hơn) --
                          # cố gắng không để GV trống trọn 1 ngày làm việc
HEAVY_MORNING_BONUS = 30          # điểm thưởng khi môn "Nặng" rơi vào N tiết đầu buổi sáng
                                  # (N = config.heavy_subject_priority_periods, 0 = tắt) -- cùng bậc IDLE_DAY_BONUS
AFTERNOON_MISMATCH_PENALTY = 30   # điểm phạt khi môn KHÔNG nằm trong config.afternoon_preferred_subject_ids
                                  # rơi vào buổi chiều (rỗng = tắt -- không phạt gì)
```

Change `_pick_best_scored` (currently lines 206-243) to:

```python
def _pick_best_scored(class_id: int, slot: Slot, state: _State, role_index,
                       subjects: list, assigned_teacher: dict, pu: float, rng: random.Random,
                       day_capacity: Optional[dict] = None,
                       config: Optional[SchedulingConfig] = None) -> Optional[tuple]:
    config = config or SchedulingConfig()
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
        if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity, config):
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
        # 2 ưu tiên mềm (yêu cầu #1+#2, spec 2026-08-29) -- độc lập, tắt khi config mặc định.
        if (subj.subject_id in role_index.heavy_ids and config.heavy_subject_priority_periods > 0
                and ts.session == "S" and ts.period <= config.heavy_subject_priority_periods):
            score += HEAVY_MORNING_BONUS
        if (ts.session == "C" and config.afternoon_preferred_subject_ids
                and subj.subject_id not in config.afternoon_preferred_subject_ids):
            score -= AFTERNOON_MISMATCH_PENALTY
        if slot.old_subject_id == subj.subject_id and rng.random() > pu:
            score += 1_000_000
        if score > best_score:
            best_score = score
            best_subject = subj.subject_id
            best_teacher = teacher_id
    if best_subject is None:
        return None
    return best_subject, best_teacher
```

- [ ] **Step 4: Run tests to verify everything passes**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: PASS — the 3 new tests plus the entire pre-existing suite (default `config=None`/`SchedulingConfig()` produces zero score change, since `heavy_subject_priority_periods=0` and `afternoon_preferred_subject_ids=frozenset()` both gate their `if` off).

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: soft-score heavy subjects toward early morning, preferred subjects toward afternoon"
```

---

## Task 4: UI — Cấu hình xếp lịch page + sidebar summary

**Files:**
- Modify: `pages/10_Cau_hinh_Xep_lich.py` (add 1 number input, 1 subject multiselect, wire into save)
- Modify: `ui_common.py` (`sidebar_fixed_rules` — 2 conditional summary lines)

**Interfaces:**
- Consumes: `repo.get_scheduling_config`/`set_scheduling_config` (Task 2), `repo.list_subjects` (existing)

No automated test — these are Streamlit UI files, matching this repo's existing convention (pages have no dedicated test files). Verify manually in Step 3.

- [ ] **Step 1: Add the 2 new controls to the config page**

In `pages/10_Cau_hinh_Xep_lich.py`, after the existing 3 "Ngưỡng số lượng" fields (`max_heavy_consecutive`, `max_periods_per_session`, `teacher_off_sessions_per_week`) and before the `st.subheader("Buổi/ngày khoá cứng")` line, add:

```python
heavy_subject_priority_periods = st.number_input(
    "Môn nặng: ưu tiên (không bắt buộc) mấy tiết đầu buổi sáng (0 = tắt)", 0, max_p,
    config.heavy_subject_priority_periods,
    help="Chỉ là gợi ý cho thuật toán -- không cấm tuyệt đối, không làm hỏng khả năng tìm lời giải.",
)
```

After the existing `reserved_weekdays_selection` multiselect block and before the `if st.button("💾 Lưu cấu hình", ...)` line, add:

```python
st.subheader("Ưu tiên buổi (mềm, không bắt buộc)")
st.caption(
    "Các môn dưới đây được ưu tiên xếp vào buổi chiều (không cấm tuyệt đối môn khác, "
    "chỉ là gợi ý cho thuật toán). Để trống = tắt tính năng này."
)
all_subjects = repo.list_subjects(conn)
subject_names = {s.subject_id: s.name for s in all_subjects}
afternoon_preferred_selection = st.multiselect(
    "Môn ưu tiên buổi chiều",
    options=[s.subject_id for s in all_subjects],
    default=[sid for sid in config.afternoon_preferred_subject_ids if sid in subject_names],
    format_func=lambda sid: subject_names.get(sid, str(sid)),
    label_visibility="collapsed",
)
```

Change the `new_config = SchedulingConfig(...)` block inside the save button handler to add the 2 new keyword arguments:

```python
if st.button("💾 Lưu cấu hình", type="primary"):
    new_config = SchedulingConfig(
        gdtc_avoid_period=int(gdtc_avoid_period),
        chao_co_weekday=int(chao_co_weekday),
        chao_co_period=int(chao_co_period),
        max_heavy_consecutive=int(max_heavy_consecutive),
        max_periods_per_session=int(max_periods_per_session),
        teacher_off_sessions_per_week=int(teacher_off_sessions_per_week),
        forbidden_off_cells=frozenset(forbidden_selection),
        reserved_off_weekdays_chieu=tuple(sorted(reserved_weekdays_selection)),
        heavy_subject_priority_periods=int(heavy_subject_priority_periods),
        afternoon_preferred_subject_ids=frozenset(afternoon_preferred_selection),
    )
    repo.set_scheduling_config(conn, new_config)
    st.success("Đã lưu cấu hình xếp lịch.")
    st.rerun()
```

- [ ] **Step 2: Update the sidebar rules summary**

In `ui_common.py`, inside `sidebar_fixed_rules`, after the existing `configurable_rules = [...]` list and before `with st.sidebar:`, add:

```python
    if config.heavy_subject_priority_periods > 0:
        configurable_rules.append(
            f"Môn nặng được ưu tiên (không bắt buộc) vào {config.heavy_subject_priority_periods} tiết đầu buổi sáng"
        )
    if config.afternoon_preferred_subject_ids:
        configurable_rules.append(
            "Buổi chiều được ưu tiên (không bắt buộc) cho một số môn đã chọn ở trang Cấu hình xếp lịch"
        )
```

- [ ] **Step 3: Manually verify**

Run: `streamlit run app.py`

- Log in, open "Thiết lập dữ liệu" → "Cấu hình xếp lịch". Confirm the new "Môn nặng: ưu tiên..." number input shows `0` and the new "Ưu tiên buổi (mềm...)" multiselect shows empty, with no other field changed.
- Set the number input to `2`, select 2-3 light subjects (e.g. Nhạc, Mĩ thuật) in the multiselect, click "Lưu cấu hình" — confirm success message and that the page reloads showing the saved values.
- Open the sidebar "📐 Quy tắc xếp lịch" expander — confirm 2 new lines now appear describing the soft preferences.
- Go to "Xếp & sửa thời khóa biểu" → "Xếp TKB tự động", run a schedule — confirm it still succeeds.
- Reset both fields back to `0`/empty and save again (leave the demo school in its original state).

- [ ] **Step 4: Run the full test suite one final time**

Run: `python -m pytest -v`
Expected: PASS — entire suite, no regressions from any of the 4 tasks.

- [ ] **Step 5: Commit**

```bash
git add pages/10_Cau_hinh_Xep_lich.py ui_common.py
git commit -m "feat: add UI for soft morning/afternoon subject-preference config"
```

---

## Self-Review Notes

- **Spec coverage:** Both halves of spec section "1. Yêu cầu #1+#2" are covered — the 2 `SchedulingConfig` fields (Task 1), their `app_meta` persistence (Task 2), the `_pick_best_scored` scoring changes with the "independent, no double-penalty" rule from the spec's fix (Task 3), and the UI + sidebar summary (Task 4). The spec's explicit note that these rules apply "chỉ trong `_pick_best_scored`, không đụng `_pick_best_simple`/`_try_swap_repair`" is preserved — no task touches those functions.
- **Placeholder scan:** No task defers logic or references undefined names — every code block is complete, copy-pasteable Python verified against the actual current file contents (line numbers read directly from `core/models.py`, `data/repository.py`, `core/scheduler.py`, `pages/10_Cau_hinh_Xep_lich.py`, `ui_common.py`, `tests/test_models.py`, `tests/test_repository.py`, `tests/test_scheduler.py`).
- **Type consistency:** `heavy_subject_priority_periods`/`afternoon_preferred_subject_ids` field names and types are identical across Tasks 1-4 (`int`/`frozenset`). `HEAVY_MORNING_BONUS`/`AFTERNOON_MISMATCH_PENALTY` constant names match between their definition (Task 3 Step 3) and the tests that don't reference them directly (tests only assert on `_pick_best_scored`'s return value, not the constants).
