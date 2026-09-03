# Task 2 Report: Fix `teacher_off.py` Silent Off-Slot Shortfall

## Summary

Task 2 has been completed successfully. The `_assign_off_slots` function now returns a tuple `(gv_off_slots, shortfall)` instead of silently truncating off-slot assignments. This makes off-slot shortfalls explicit and reportable instead of hidden.

## What Was Implemented

### Modified Files
1. **`core/scheduler/teacher_off.py`**
   - Updated function signature: `_assign_off_slots(...) -> tuple` (was `-> dict`)
   - Added `shortfall` dict initialization at the start
   - Modified the `else` branch (lines 65-68 in original) to track when `assigned_total < effective_count`
   - Returns both `gv_off_slots` and `shortfall` dicts
   - Enhanced docstring to document the new return type

2. **`tests/test_teacher_off.py`** (new file)
   - Created three comprehensive unit tests:
     - `test_assign_off_slots_returns_tuple_with_empty_shortfall_when_feasible`: Verifies normal case with no shortfall
     - `test_assign_off_slots_reports_shortfall_when_teacher_over_excluded`: Verifies shortfall reporting for over-excluded teachers (e.g., TPT/BGH)
     - `test_assign_off_slots_shortfall_is_deterministic_across_rng_seeds`: Verifies shortfall is deterministic based on fixed config, not RNG

## Test Results

### Task 2 Unit Tests (TDD Evidence)

**Step 2 - RED (Tests fail before implementation):**
```
tests/test_teacher_off.py::test_assign_off_slots_returns_tuple_with_empty_shortfall_when_feasible FAILED
tests/test_teacher_off.py::test_assign_off_slots_reports_shortfall_when_teacher_over_excluded FAILED
tests/test_teacher_off.py::test_assign_off_slots_shortfall_is_deterministic_across_rng_seeds FAILED
ValueError: not enough values to unpack (expected 2, got 1)
```

**Step 4 - GREEN (Tests pass after implementation):**
```
tests/test_teacher_off.py::test_assign_off_slots_returns_tuple_with_empty_shortfall_when_feasible PASSED
tests/test_teacher_off.py::test_assign_off_slots_reports_shortfall_when_teacher_over_excluded PASSED
tests/test_teacher_off.py::test_assign_off_slots_shortfall_is_deterministic_across_rng_seeds PASSED
===================== 3 passed in 0.08s =====================
```

### Broader Integration Tests (Step 5 - Expected Breakage)

As documented in the task brief, the change to `_assign_off_slots`'s return type intentionally breaks all existing callers pending fixes in later tasks. 

**Expected breakage categories:**

1. **Direct callers in test code** (tests that call `_assign_off_slots` directly):
   - These tests expect a dict return value but now receive a tuple
   - Error: `AttributeError: 'tuple' object has no attribute 'items'` / `.get()`
   - These are in `tests/test_scheduler.py` and `tests/test_scheduler_teacher_quality.py`

2. **Integration tests calling `engine.py:run()`** (main scheduler workflow):
   - These fail when `engine.py` line 111 tries to unpack the tuple return
   - Error: The actual error type depends on how the assignment happens
   - These include all exporter, real_data_schedule, and full scheduler tests

**Note (Vietnamese):** 
Để `engine.py` không còn lỗi, `Task 4` sẽ cần:
- Sửa dòng 111 trong `core/scheduler/engine.py` để xử lý tuple `(gv_off_slots, shortfall)` 
- Thêm `shortfall` vào `ScheduleResult.relaxed_rules` để báo cáo những giáo viên bị thiếu buổi nghỉ

**Do not fix these in this task** — as per the brief, Task 4 owns the `engine.py` update and will surface the shortfall in the result.

## Self-Review Findings

### Completeness
✓ All 7 steps in the brief completed
✓ Tests pass (RED → GREEN)
✓ New function signature matches brief spec exactly
✓ Shortfall dict format: `{teacher_id: (assigned_count, required_count)}`
✓ Empty dict when no shortfalls (normal case)
✓ Commit message follows convention

### Quality Checks
✓ Function docstring updated with correct return type
✓ Type annotation changed to `-> tuple`
✓ No unrelated code modifications
✓ Tests are independent and deterministic
✓ Shortfall logic only in `else` branch (correct location)

### Potential Concerns
- None. The shortfall tracking logic is correct and deterministic.

## Failing Tests (Expected Temporary Breakage - Task 4 Will Fix)

The following 41 tests fail due to the expected breakage from the return-type change:

### Direct `_assign_off_slots` Callers (Test Code Breaking)
1. tests/test_scheduler.py::test_off_slots_respect_forbidden_cells_gvcn_and_must_monday
2. tests/test_scheduler.py::test_teacher_pinned_full_day_off
3. tests/test_scheduler.py::test_teacher_pinned_afternoon_off
4. tests/test_scheduler.py::test_teacher_off_sessions_override
5. tests/test_scheduler.py::test_teacher_pinned_full_day_and_extra_afternoon_off
6. tests/test_scheduler.py::test_pinned_off_conflicts_with_forbidden_are_dropped
7. tests/test_scheduler.py::test_off_slots_unchanged_when_no_override_or_pins
8. tests/test_scheduler.py::test_off_slot_count_defaults_to_1_buoi_per_week
9. tests/test_scheduler.py::test_assign_off_slots_respects_custom_forbidden_cells_and_count
10. tests/test_scheduler_teacher_quality.py::test_mandatory_morning_weekdays_strictly_enforced

### Integration Tests Calling `engine.py:run()` (Breaking on Caller)
11. tests/test_exporter.py::test_export_accepted_run_no_teacher_conflict_highlight
12. tests/test_exporter.py::test_export_both_parities_warns_when_only_one_accepted
13. tests/test_exporter.py::test_export_both_parities_has_all_6_sheets_when_both_accepted
14. tests/test_exporter.py::test_export_both_parities_preserves_freeze_panes
15. tests/test_real_data_schedule.py::test_real_data_schedules_successfully[C]
16. tests/test_real_data_schedule.py::test_real_data_schedules_successfully[L]
17. tests/test_real_data_schedule.py::test_real_data_schedules_successfully_with_hdtn_thematic_week[C]
18. tests/test_real_data_schedule.py::test_real_data_schedules_successfully_with_hdtn_thematic_week[L]
19. tests/test_real_data_schedule.py::test_real_data_schedules_successfully_with_heavy_subjects_morning_only[L]
20. tests/test_scheduler.py::test_small_synthetic_schedule_succeeds_and_meets_quotas
21. tests/test_scheduler.py::test_subject_class_rule_thread_through_run
22. tests/test_scheduler.py::test_chao_co_position_configurable_in_full_run
23. tests/test_scheduler.py::test_extra_kep_ids_forces_adjacency_in_full_run
24. tests/test_scheduler.py::test_full_run_kep_subject_with_odd_weekly_count_pairs_maximally
25. tests/test_scheduler.py::test_full_run_all_three_rules_combined
26. tests/test_scheduler.py::test_full_run_with_morning_only_subject_ids
27. tests/test_scheduler.py::test_shl_pinned_last_morning_period_2buoi
28. tests/test_scheduler.py::test_hdtn_thematic_week_forms_one_block_and_skips_chao_co_shl_pins
29. tests/test_scheduler.py::test_shl_pinned_last_morning_period_1buoi
30. tests/test_scheduler.py::test_shl_derives_last_period_not_hardcoded
31. tests/test_scheduler.py::test_shl_supports_hdtn_quota_3_with_third_free
32. tests/test_scheduler.py::test_shl_skipped_when_hdtn_quota_one
33. tests/test_scheduler.py::test_change_minimization_keeps_old_baseline_when_feasible
34. tests/test_scheduler.py::test_busy_teacher_period_and_session_never_scheduled
35. tests/test_scheduler.py::test_build_scheduling_input_respects_saved_scheduling_config
36. tests/test_scheduler.py::test_pick_best_scored_unbiased_with_default_config
37. tests/test_scheduler.py::test_full_run_succeeds_with_both_soft_subject_preferences_enabled
38. tests/test_scheduler.py::test_full_run_succeeds_with_teacher_pinned_and_override_off_days
39. tests/test_scheduler.py::test_subject_class_allowed_cells_holds_across_every_placement_in_a_real_run
40. tests/test_scheduler_constraints.py::test_non_consecutive_day_constraint
41. tests/test_scheduler_teacher_quality.py::test_teacher_lone_sessions_heavy_penalty

## Commit Information

- **Commit SHA:** f323c56
- **Commit Message:** fix: report teacher off-slot shortfall instead of silently truncating
- **Files Modified:** 2
  - Modified: `core/scheduler/teacher_off.py`
  - Created: `tests/test_teacher_off.py`

## Conclusion

Task 2 is complete. The function now correctly tracks and reports shortfalls when a teacher's eligible off-slot cells run out due to their fixed-configuration exclusions. The implementation is mechanically correct per the brief, the new unit tests all pass, and the documented test failures are the expected temporary breakage that Task 4 will fix by updating `engine.py` and wiring shortfall into `ScheduleResult.relaxed_rules`.
