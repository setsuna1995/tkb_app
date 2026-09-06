# Task 1 Report: Dynamic Plateau Early Stopping & Inter-Pass Warm-Start Hinting

## 1. Summary of Changes
- Enhanced `EarlyStoppingCallback` in `core/scheduler/cpsat/solver.py`:
  - Added solution history tracking: `self.history: list[tuple[float, float]]`.
  - Added `_check_plateau()` algorithm: Evaluates objective progress over `plateau_window_s` (4.0s). If improvement is under `min_improvement_rate` (0.03) or `min_improvement_abs` (600.0) after `min_search_s` (3.5s), triggers early stopping to eliminate the LNS long-tail wait.
- Added Inter-Pass Warm-Start Hinting:
  - In `_diagnose_and_solve`, when Pass 1 discovers a feasible assignment, all positive boolean assignments are extracted into `warm_start_hints` and passed via `model.AddHint()` into Pass 2.
- Enabled `solver.parameters.relative_gap_limit = 0.03` (stops search when gap to lower bound is within 3%).
- Improved capacity screening in `_presolve_capacity_screening` by deducting slots occupied by pinned Chào cờ on Monday morning.

## 2. Files Modified
- `core/scheduler/cpsat/solver.py`:
  - `EarlyStoppingCallback` implementation with plateau detection.
  - `_diagnose_and_solve` hint extraction and hint passing.
  - `_presolve_capacity_screening` Chào cờ deduction.
- `tests/test_cpsat_plateau_early_stopping.py`: Unit and integration test suite (NEW).
- `tests/test_cpsat_pinpoint_diagnosis.py`: Minor test fix to genuinely test base model infeasibility.

## 3. TDD Evidence
- **RED Phase Output**:
```
FAILED tests/test_cpsat_plateau_early_stopping.py::test_early_stopping_callback_plateau_init_and_attributes
FAILED tests/test_cpsat_plateau_early_stopping.py::test_early_stopping_plateau_logic_triggers_stop
TypeError: EarlyStoppingCallback.__init__() got an unexpected keyword argument 'plateau_window_s'
```
- **GREEN Phase Output**:
```
tests\test_cpsat_plateau_early_stopping.py ...                           [100%]
============================= 3 passed in 29.01s ==============================
```
- **Real Data Benchmark**:
`tests/test_real_data_schedule.py`: 2 passed in 61.54s (down from 90.16s, ~32% wall-time reduction on full integration test).
- **Pinpoint Diagnosis Suite**:
`tests/test_cpsat_pinpoint_diagnosis.py`: 5 passed in 1.15s (100%).

## 4. Self-Review Findings
- Zero regressions across core CP-SAT test suite.
- Solver gracefully stops when improvements reach diminishing returns without degrading timetable validity.
