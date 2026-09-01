# Task 1 Brief: Core Data & Repository Enhancement for Teacher 35-Week Workload Profile

## 1. Objective & Scope
- **Objective**: Upgrade `get_teacher_quota_view(conn, parity="C", week_no=None)` in `data/repositories/curriculum.py` to calculate full 35-week workload metrics for every teacher:
  - `weekly_loads`: dictionary `{1: p_1, 2: p_2, ..., 35: p_35}`
  - `load_full_year_avg`: average period load across all 35 weeks
  - `load_hk1_avg`: average period load across weeks 1..18 (Semester I)
  - `load_hk2_avg`: average period load across weeks 19..35 (Semester II)
  - `max_week`, `max_load`, `min_week`, `min_load`: peak and lowest teaching load weeks
  - `over_current`: load(week_no) - cap
  - `over_hk1`: load_hk1_avg - cap
  - `over_hk2`: load_hk2_avg - cap
  - `over_year`: load_full_year_avg - cap
  - `under_current`: min_floor - (load(week_no) + reduction)
  - `under_year`: min_floor - (load_full_year_avg + reduction)
  - Detailed `assignments` with per-week periods for each subject/class assignment.
- **Scope**: `data/repositories/curriculum.py` and `tests/test_teacher_weekly_quota.py`.
- **Out of Scope**: UI components (handled in Task 3).

## 2. Interface Specifications
- `get_teacher_quota_view(conn: sqlite3.Connection, parity: str = "C", week_no: Optional[int] = None) -> list[dict]`
- Each item in the returned list contains all legacy fields (`teacher_id`, `name`, `role`, `reduction`, `cap`, `load`, `load_chan`, `load_le`, `load_avg`, `over`, `under`, `assignments`) plus new 35-week profile fields (`weekly_loads`, `load_full_year_avg`, `load_hk1_avg`, `load_hk2_avg`, `max_week`, `max_load`, `min_week`, `min_load`, `over_hk1`, `over_hk2`, `over_year`, `under_year`).

## 3. TDD Strategy
- Create test file: `tests/test_teacher_weekly_quota.py`.
- Test RED: assert new fields exist and reflect exact weekly distributions from imported curriculum.
- Implement GREEN in `data/repositories/curriculum.py`.

## 4. Safety & Invariants
- 100% backward compatible with existing UI and callers.
- If `weekly_curriculum` is empty, gracefully falls back to `periods_per_week` for all 35 weeks based on odd/even week numbers.
