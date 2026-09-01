# Task 1 Brief: Modularize `core/scheduler`

## 1. Objective & Scope
Refactor the 1,131-line monolithic `core/scheduler.py` into a structured, modular package `core/scheduler/` with single-responsibility modules:
- `constants.py`: Engine constants, default scoring weights, failure messages, forbidden cells.
- `state.py`: `_State` class definition.
- `placement.py`: `_put_at()`, `_remove_at()`, `_build_effective_assigned_teacher()`.
- `feasibility.py`: `_feasible()`.
- `teacher_off.py`: `_assign_off_slots()`.
- `heuristics.py`: `_pick_best_scored()`, `_pick_best_simple()`, `_calculate_teacher_gap_penalty()`.
- `blocks.py`: `_try_place_block_atomically()`, `_block_partial_state()`, `_merge_one_block_period()`, `_repair_unpaired_blocks()`, `_has_unpaired_block()`.
- `swaps.py`: `_try_swap_repair()`, `_repair_lone_periods()`, `_has_lone_period()`.
- `quality.py`: `_teacher_quality_penalty()`, `_count_teacher_gaps()`, `_count_teacher_lone_days()`, `_count_teacher_lone_sessions()`, `_count_teacher_split_sessions()`, `_count_teacher_missing_mandatory_mornings()`, `_count_teacher_missing_afternoon_duty()`.
- `engine.py`: `run()`.
- `__init__.py`: Public facade re-exporting all symbols for 100% backward compatibility.

## 2. Interface Specifications
All public functions, internal helper functions tested by unit tests, and constants must remain accessible via `core.scheduler.<name>`:
- `run(inp: SchedulingInput, *, max_attempts: int = SO_LAN_THU, target_successes: int = SO_PA_TOT, lock_threshold: int = NGUONG_KHOA) -> ScheduleResult`
- `_State`
- `_feasible`
- `_put_at`, `_remove_at`, `_build_effective_assigned_teacher`
- `_pick_best_scored`, `_pick_best_simple`, `_calculate_teacher_gap_penalty`
- `_try_place_block_atomically`, `_repair_unpaired_blocks`, `_has_unpaired_block`, `_merge_one_block_period`, `_block_partial_state`
- `_try_swap_repair`, `_repair_lone_periods`, `_has_lone_period`
- `_assign_off_slots`
- `_teacher_quality_penalty`, `_count_teacher_gaps`, `_count_teacher_lone_days`, `_count_teacher_lone_sessions`, `_count_teacher_split_sessions`, `_count_teacher_missing_mandatory_mornings`, `_count_teacher_missing_afternoon_duty`
- Constants: `MAX_GV_BUOI`, `SO_LAN_THU`, `SO_PA_TOT`, `NGUONG_KHOA`, `CAP_TIET_NGAY`, `BAT_NGHI_1_BUOI`, `BAT_LIEN_MACH`, `IDLE_DAY_BONUS`, `HEAVY_MORNING_BONUS`, `AFTERNOON_MISMATCH_PENALTY`, `BLOCK_COMPLETE_BONUS`, `TEACHER_CONSECUTIVE_BONUS`, `TEACHER_GAP_PENALTY`, `TEACHER_SESSION_PAIR_BONUS`, `TEACHER_SPLIT_DAY_PENALTY`, `TEACHER_AFTERNOON_BALANCE_BONUS`, `TEACHER_MANDATORY_MORNING_BONUS`, `FORBIDDEN_OFF_CELLS`, `FAILURE_MESSAGE`.

## 3. TDD Strategy
- Test file: `tests/test_scheduler_modular_imports.py` asserting submodules can be imported individually and via the facade.
- RED Phase: import fails before `core/scheduler/` package is created.
- GREEN Phase: implement all submodules in `core/scheduler/` and ensure all scheduler test suites pass (`test_scheduler.py`, `test_scheduler_constraints.py`, `test_scheduler_teacher_quality.py`).
