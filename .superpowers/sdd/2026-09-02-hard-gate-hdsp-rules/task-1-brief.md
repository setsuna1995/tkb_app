# Task 1: Config Defaults & `ScheduleResult.relaxed_rules`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two config default bugs that silently disable rules II.4 and
II.5's exemption/preference, and add the `relaxed_rules` field to
`ScheduleResult` that later tasks (4, 5) will populate.

**Why (Vietnamese):**
- `min_weekly_periods_for_lone_penalty` mặc định `0` khiến ngoại lệ "miễn trừ
  GV <15 tiết/tuần" của tiêu chí II.4 KHÔNG BAO GIỜ áp dụng trong thực tế —
  vì `SchedulingConfig` luôn có field này nên `getattr(..., 15)` fallback
  trong `quality.py` không bao giờ chạy tới nhánh mặc định của nó.
- `heavy_subject_priority_periods` mặc định `0` (tắt) khiến tiêu chí II.5
  ("GDTC + Toán + Văn ưu tiên buổi sáng") không có tác dụng gì — cơ chế thưởng
  điểm mềm (`HEAVY_MORNING_BONUS`) không bao giờ được kích hoạt.

**Files:**
- Modify: `core/models.py:106` (heavy_subject_priority_periods default), `core/models.py:122` (min_weekly_periods_for_lone_penalty default), `core/models.py:144-152` (ScheduleResult)
- Modify: `pages/10_Cau_hinh_Xep_lich.py:225` (stale fallback literal, cosmetic consistency)
- Modify: `tests/test_mandatory_rules_compliance.py:29-31` (existing test asserts the OLD buggy default — must be updated or it will fail after this task)
- Test: `tests/test_config_defaults.py` (new file)

**Interfaces:**
- Produces: `SchedulingConfig.heavy_subject_priority_periods: int = 4` (was `0`), `SchedulingConfig.min_weekly_periods_for_lone_penalty: int = 15` (was `0`), `ScheduleResult.relaxed_rules: list = field(default_factory=list)` (new field, appended at end of dataclass so existing positional/keyword construction elsewhere in the codebase is unaffected).

---

- [ ] **Step 1: Write the failing test for the new config defaults**

Create `tests/test_config_defaults.py`:

```python
from core.models import ScheduleResult, SchedulingConfig


def test_min_weekly_periods_for_lone_penalty_defaults_to_15():
    """II.4's <15 tiết/tuần exemption must be ON by default, not OFF (0)."""
    config = SchedulingConfig()
    assert config.min_weekly_periods_for_lone_penalty == 15


def test_heavy_subject_priority_periods_defaults_to_4():
    """II.5 (GDTC+Toán+Văn ưu tiên sáng) must have the morning-priority
    bonus enabled by default, covering the whole typical morning session."""
    config = SchedulingConfig()
    assert config.heavy_subject_priority_periods == 4


def test_schedule_result_has_relaxed_rules_field():
    result = ScheduleResult(success=True)
    assert result.relaxed_rules == []

    result_with_relaxation = ScheduleResult(success=True, relaxed_rules=[{"rule_id": "II.3"}])
    assert result_with_relaxation.relaxed_rules == [{"rule_id": "II.3"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config_defaults.py -v`
Expected: 3 FAILs — `AssertionError` on the first two (actual `0` vs expected
`15`/`4`), and a `TypeError: __init__() got an unexpected keyword argument
'relaxed_rules'` on the third.

- [ ] **Step 3: Fix the config defaults in `core/models.py`**

At line 106, change:
```python
    heavy_subject_priority_periods: int = 0   # 0 = tắt; số tiết đầu buổi sáng được cộng điểm ưu tiên môn "Nặng"
```
to:
```python
    heavy_subject_priority_periods: int = 4   # Tiêu chí II.5: 4 tiết đầu buổi sáng ưu tiên môn "Nặng"; 0 = tắt
```

At line 122, change:
```python
    min_weekly_periods_for_lone_penalty: int = 0  # Tiêu chí II.4: 0 = áp dụng phạt lẻ cho tất cả; > 0 = miễn trừ GV có tải < ngưỡng này
```
to:
```python
    min_weekly_periods_for_lone_penalty: int = 15  # Tiêu chí II.4: miễn trừ GV có tải < ngưỡng này; 0 = áp dụng phạt lẻ cho tất cả
```

- [ ] **Step 4: Add `relaxed_rules` to `ScheduleResult` in `core/models.py`**

Change (around line 144-152):
```python
@dataclass
class ScheduleResult:
    success: bool
    assignment: dict = field(default_factory=dict)   # slot_id -> Optional[int] subject_id (best attempt)
    cells_changed: int = 0
    cells_total: int = 0
    attempts_tried: int = 0
    successes_found: int = 0
    failure_reason: Optional[str] = None
```
to:
```python
@dataclass
class ScheduleResult:
    success: bool
    assignment: dict = field(default_factory=dict)   # slot_id -> Optional[int] subject_id (best attempt)
    cells_changed: int = 0
    cells_total: int = 0
    attempts_tried: int = 0
    successes_found: int = 0
    failure_reason: Optional[str] = None
    relaxed_rules: list = field(default_factory=list)  # [{"rule_id": "II.3", ...}] rules that could not be
                                                          # fully satisfied even in the best available attempt
                                                          # (see core/scheduler/engine.py's post-generation gate)
```

- [ ] **Step 5: Fix the stale UI fallback literal in `pages/10_Cau_hinh_Xep_lich.py`**

At line 223-227, change:
```python
min_weekly_periods_for_lone_penalty = c_hdsp6.number_input(
    "Ngưỡng tiết/tuần áp dụng phạt lẻ tiết GV (0 = phạt toàn bộ, 15 = miễn trừ GV <15 tiết)",
    0, 30, getattr(config, "min_weekly_periods_for_lone_penalty", 0),
    help="Tiêu chí II.4: Hạn chế tối đa GV dạy 1 tiết/buổi hoặc 1 tiết/ngày, nhưng miễn trừ cho GV ít tiết (< 15 tiết/tuần).",
)
```
to:
```python
min_weekly_periods_for_lone_penalty = c_hdsp6.number_input(
    "Ngưỡng tiết/tuần áp dụng phạt lẻ tiết GV (0 = phạt toàn bộ, 15 = miễn trừ GV <15 tiết)",
    0, 30, getattr(config, "min_weekly_periods_for_lone_penalty", 15),
    help="Tiêu chí II.4: Hạn chế tối đa GV dạy 1 tiết/buổi hoặc 1 tiết/ngày, nhưng miễn trừ cho GV ít tiết (< 15 tiết/tuần).",
)
```
(This `getattr(..., 15)` fallback only matters if some caller ever passes an
object without the attribute at all — the dataclass default from Step 3 is
what actually governs real usage. Kept for consistency so the two defaults
never silently disagree again.)

- [ ] **Step 6: Update the existing test that asserts the old default**

In `tests/test_mandatory_rules_compliance.py`, lines 29-31, change:
```python
    # Tiêu chí II.4: Cấu hình ngưỡng tải miễn trừ phạt lẻ tiết cho GV (default 0 = áp dụng toàn bộ)
    assert hasattr(config, "min_weekly_periods_for_lone_penalty")
    assert config.min_weekly_periods_for_lone_penalty == 0
```
to:
```python
    # Tiêu chí II.4: Cấu hình ngưỡng tải miễn trừ phạt lẻ tiết cho GV (default 15 = miễn trừ GV <15 tiết/tuần)
    assert hasattr(config, "min_weekly_periods_for_lone_penalty")
    assert config.min_weekly_periods_for_lone_penalty == 15
```

- [ ] **Step 7: Run the full config test files to verify everything passes**

Run: `python -m pytest tests/test_config_defaults.py tests/test_mandatory_rules_compliance.py -v`
Expected: all PASS. Note `test_full_schedule_15_criteria_compliance` in that
same file will now run the scheduler with the NEW stricter defaults
(`min_weekly_periods_for_lone_penalty=15` instead of 0) — if it fails at this
step (before Tasks 2-4 land), that is expected and will be revisited in Task
6; do not attempt to fix scheduler behavior in this task.

- [ ] **Step 8: Run the full existing test suite to check for regressions**

Run: `python -m pytest tests/ -v --timeout=600`
Note which tests fail (if any) due to the changed defaults — record them in
`task-1-report.md` for Task 6 to address; do not fix scheduler-behavior
regressions in this task, only config/model-level ones.

- [ ] **Step 9: Commit**

```bash
git add core/models.py pages/10_Cau_hinh_Xep_lich.py tests/test_config_defaults.py tests/test_mandatory_rules_compliance.py
git commit -m "fix: correct II.4/II.5 config defaults, add ScheduleResult.relaxed_rules"
```

- [ ] **Step 10: Write task-1-report.md**

Summarize (in Vietnamese, per project convention): what changed, test
results from Steps 7-8, and a list of any pre-existing tests that now fail
because of the stricter default (to be picked up by Task 6).
