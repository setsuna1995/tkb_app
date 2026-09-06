# Task 2 Brief: Chẩn Đoán Phân Tầng Pass 1 & Mở Rộng Presolve Capacity Screening

## 1. Objective & Scope
- **Objective**: Prevent blanket relaxation of all hard HĐSP rules when Pass 1 encounters tight capacity.
  1. Add analytical pre-solve checks in `_presolve_capacity_screening`: detect mathematical impossibilities in $O(1)$ time for both II.3 and II.4.
  2. Increase diagnosis budget dynamically up to 4.5s.
  3. Implement tiered fallback on `UNKNOWN`: relax `II.4` (the most constrained rule) first instead of immediately throwing out `II.3` and `II.8`.
- **Scope**:
  - `core/scheduler/cpsat/solver.py`: `_presolve_capacity_screening` and `_diagnose_and_solve`.
  - `tests/test_cpsat_tiered_diagnosis.py` (NEW test file).

## 2. Interface Specifications
- `_presolve_capacity_screening(built: CpSatModel) -> set[str]`:
  - Returns set of infeasible rule IDs (e.g. `{"II.3"}`, `{"II.4"}`).
- `_diagnose_and_solve`:
  - On `UNKNOWN`, if `"II.4"` in `hard_rids`, relaxes only `{"II.4"}` to give `II.3` and `II.8` a chance to stay strictly enforced.

## 3. TDD Strategy
- Test file: `tests/test_cpsat_tiered_diagnosis.py`
  1. `test_capacity_screening_detects_ii3_overflow`: When required teachers exceed total morning periods available in the entire school for that weekday, `_presolve_capacity_screening` immediately returns `{"II.3"}`.
  2. `test_capacity_screening_detects_ii4_overflow`: Confirms `{"II.4"}` is returned when $2 \times \text{req\_teachers} > \text{cap}$.
  3. `test_tiered_unknown_relaxes_ii4_first`: Simulates an UNKNOWN feasibility timeout with both II.3 and II.4 active; verifies that II.4 is relaxed first, leaving II.3 active.
- RED phase: Run tests asserting new tiered screening functions and verify failure.
- GREEN phase: Implement logic and verify tests pass.

## 4. Safety & Invariants
- `tests/test_cpsat_pinpoint_diagnosis.py` must stay 100% passing.
- No change to `ScheduleResult` structure.
