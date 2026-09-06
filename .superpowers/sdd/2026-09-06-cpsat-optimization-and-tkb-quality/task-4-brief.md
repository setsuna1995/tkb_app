# Task 4 Brief: Bổ Sung Ràng Buộc Sư Phạm & Công Bằng Giáo Viên

## 1. Objective & Scope
- **Objective**:
  1. Add **Progressive Gap Penalty** (Phạt lũy tiến tiết trống: gap 1 = 350, gap 2 = 700, gap $\ge 3$ = 1500) so CP-SAT actively distributes unavoidable gaps across teachers instead of clustering multiple gaps on a single teacher.
  2. Add **Anti Back-to-Back Shifts** (Chống nhảy ca gắt: penalty 250 when a teacher teaches late afternoon period 4/5 and early morning period 1 the very next day).
  3. Add **Subject Dispersion Preference** (Phân bố đều môn học: soft penalty 200 for 2–3 period/week subjects scheduled on consecutive days, when slot flexibility permits, satisfying "trong điều kiện có thể thôi").
  4. Update `quality.py` to evaluate these quality metrics.
- **Scope**:
  - `core/scheduler/constants.py`: Constants for progressive gap, back-to-back shift, and soft dispersion.
  - `core/scheduler/cpsat/objectives.py`: Objective terms for progressive gap, back-to-back shift, and dispersion.
  - `core/scheduler/quality.py`: Quality functions for tracking.
  - `tests/test_pedagogical_and_fairness_quality.py` (NEW test file).

## 2. Interface Specifications
- `core/scheduler/constants.py`:
  - `TEACHER_GAP_SECOND_PENALTY: int = 700`
  - `TEACHER_GAP_EXCESS_PENALTY: int = 1500`
  - `TEACHER_BACK_TO_BACK_SHIFT_PENALTY: int = 250`
  - `SUBJECT_CONSECUTIVE_DAY_SOFT_PENALTY: int = 200`
- `core/scheduler/cpsat/objectives.py`: `_add_objective(built: CpSatModel)`
  - Adds terms for progressive gap, back-to-back shift, and subject dispersion.

## 3. TDD Strategy
- Test file: `tests/test_pedagogical_and_fairness_quality.py`:
  1. `test_progressive_gap_penalizes_multiple_gaps_more_heavily`: Asserts that 2 gaps on 1 teacher incur higher penalty than 1 gap on 2 teachers.
  2. `test_anti_back_to_back_shift_penalty`: Asserts that teaching late afternoon followed by early next morning is penalized.
  3. `test_subject_dispersion_prefers_spaced_days`: Asserts that soft dispersion prefers spacing a 2-period subject (e.g. T2 and T4) over consecutive days (T2 and T3) when slack exists.
- RED phase: Assertions fail before implementation.
- GREEN phase: Implement in `constants.py`, `objectives.py`, `quality.py`, verify tests pass.

## 4. Safety & Invariants
- All existing hard constraints and tests must remain 100% compliant.
- Soft penalties must not cause infeasibility.
