# Task 1 Brief: Dynamic Plateau Early Stopping & Inter-Pass Warm-Start Hinting

## 1. Objective & Scope
- **Objective**: Reduce CP-SAT solve time from ~45s to ~8–15s by preventing the solver from being dragged out by microscopic LNS improvements ("LNS drip"), and transferring feasible solutions found in Pass 1 directly to Pass 2 as warm-start hints.
- **Scope**:
  - `core/scheduler/cpsat/solver.py`:
    - Enhance `EarlyStoppingCallback` with plateau detection (`plateau_window_s`, `min_improvement_rate`, `min_improvement_abs`, `min_search_s`).
    - Enable `solver.parameters.relative_gap_limit = 0.03`.
    - In `_diagnose_and_solve`: extract warm-start hints from Pass 1 when feasible, apply them to Pass 2.
- **Out of Scope**:
  - Constraint modifications (Task 3 & 4).
  - UI changes (Task 5).

## 2. Interface Specifications
```python
class EarlyStoppingCallback(cp_model.CpSolverSolutionCallback if cp_model is not None else object):
    def __init__(
        self,
        stagnation_s: float = 6.0,
        plateau_window_s: float = 3.5,
        min_improvement_rate: float = 0.015,
        min_improvement_abs: float = 250.0,
        min_search_s: float = 3.0,
        progress_cb: Optional[Callable[[dict], None]] = None,
        pass_no: int = 1,
        max_passes: int = 1,
    ):
        ...
```

## 3. TDD Strategy
- Test file: `tests/test_cpsat_plateau_early_stopping.py`
- Tests to include:
  1. `test_early_stopping_plateau_detection`: Unit test verifying `EarlyStoppingCallback` triggers `StopSearch()` when recent improvements fall below plateau thresholds after `min_search_s`.
  2. `test_inter_pass_warm_start_hinting`: Verify that when Pass 1 produces a feasible solution, hints are passed into the Pass 2 model and solving starts with objective bound initialized.
  3. `test_benchmark_solve_time_under_plateau`: Verify real scheduling completes significantly faster than 40s (e.g. within 20s) while maintaining feasibility.
- RED phase: `EarlyStoppingCallback` lacks plateau parameters; test fails with AttributeError or timeout.
- GREEN phase: Implement plateau watcher logic and warm-start extraction, all tests pass.

## 4. Safety & Invariants
- All existing tests in `tests/test_cpsat_model.py` and `tests/test_cpsat_engine_integration.py` must pass 100%.
- If objective <= 0, immediate stop is still preserved.
- No thread leaks: `stop_event` must always be set when solve completes.
