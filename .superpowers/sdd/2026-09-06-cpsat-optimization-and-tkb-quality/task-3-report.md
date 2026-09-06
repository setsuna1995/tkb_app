# Task 3 Report: Domain Pruning & Tái Cấu Trúc Tiết Trống GV

## 1. Summary of Changes
- Implemented **Domain Pruning** during model variable construction in `core/scheduler/cpsat_model.py`:
  - Automatically identifies and filters out disallowed slot-subject combinations before creating binary decision variables $x[s, subj]$:
    - Pinned Chào cờ & SHL slots are strictly reserved for HDTN when the class requires HDTN.
    - Morning-only subjects (`morning_only_subject_ids`) are excluded from afternoon slots.
    - Heavy subjects under `heavy_subjects_morning_only` are excluded from afternoon slots.
    - Heavy subjects under `avoid_heavy_afternoon_period3` are excluded from afternoon period 3.
    - GDTC out-of-bounds periods and `gdtc_avoid_period` are excluded.
    - Teacher `ban_busy` slots are excluded right at the variable construction phase.
    - Forbidden cell combinations in `subject_class_allowed_cells` are excluded.
  - **Empirical Model Size Reduction on Real School Data (`sample_school.xlsm`)**:
    - Decision variables `len(built.x)`: reduced from 3,480 to **2,948** (-532 variables, ~15.3% reduction).
    - Total variables in Proto: reduced from 5,968 to **5,263** (-705 variables).
    - Total constraints in Proto: reduced from 7,045 to **6,137** (-908 constraints).

## 2. Files Modified
- `core/scheduler/cpsat_model.py`: Domain pruning logic in `build_model()`.
- `tests/test_cpsat_domain_pruning.py` (NEW): Test suite verifying pruned variable exclusions and model size reduction.

## 3. TDD Evidence
- **RED Phase Output**:
```
FAILED tests/test_cpsat_domain_pruning.py::test_domain_pruning_excludes_morning_only_in_afternoon
FAILED tests/test_cpsat_domain_pruning.py::test_domain_pruning_excludes_teacher_ban_busy
FAILED tests/test_cpsat_domain_pruning.py::test_domain_pruning_reduces_sample_school_variables
============================== 3 failed in 2.77s ==============================
```
- **GREEN Phase Output**:
```
tests\test_cpsat_domain_pruning.py ...                                   [100%]
============================== 3 passed in 2.38s ==============================
```
- **Full 52-Test Regression Output**:
```
52 passed in 76.01s (100% passed across all 6 test suites)
```

## 4. Self-Review Findings
- Zero regressions in existing 35 unit tests in `test_cpsat_model.py`.
- Solves accurately and with substantially smaller memory and proto footprint.
