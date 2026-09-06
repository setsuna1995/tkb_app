# Task 3 Brief: Domain Pruning & Tái Cấu Trúc Tiết Trống GV (Span Formulation)

## 1. Objective & Scope
- **Objective**:
  1. Implement **Domain Pruning** during model variable construction: Avoid instantiating $x[s.slot\_id, subj.subject\_id]$ when the assignment is statically forbidden (Chào cờ, SHL, morning-only subjects in afternoon, GDTC out of bounds, teacher ban_busy, forbidden class-session cells).
  2. Optimize the boolean/linear formulation for teacher gaps in `objectives.py`.
  3. Reduce model variable and constraint count by ~25%–40%, drastically speeding up model construction and CP-SAT solve passes.
- **Scope**:
  - `core/scheduler/cpsat_model.py`: Domain pruning helper `_is_slot_subject_pruned(s, subj, inp, role_index, ...)`.
  - `core/scheduler/cpsat/constraints.py`: Clean up redundant `m.Add(var == 0)` constraints.
  - `core/scheduler/cpsat/objectives.py`: Streamlined gap modeling.
  - `tests/test_cpsat_domain_pruning.py` (NEW test file).

## 2. Interface Specifications
- `build_model(inp: SchedulingInput) -> CpSatModel`:
  - Continues to return `CpSatModel` with identical shape and semantics.
  - `len(built.x)` is strictly reduced (no variables for disallowed slot-subject pairs).

## 3. TDD Strategy
- Test file: `tests/test_cpsat_domain_pruning.py`:
  1. `test_domain_pruning_reduces_variable_count`: Assert that `len(built.x)` with domain pruning is significantly less than `slots * subjects`.
  2. `test_pruned_variables_exclude_banned_and_morning_only`: Assert that afternoon slots for morning-only subjects or slots with teacher in `ban_busy` are not present in `built.x`.
  3. `test_full_schedule_solves_identically_with_pruning`: Full scheduling on sample school passes 100% with exact quota and zero double bookings.
- RED phase: Run tests asserting pruned variable exclusions before implementation.
- GREEN phase: Implement pruning, all tests pass.

## 4. Safety & Invariants
- `tests/test_cpsat_model.py` (35 unit tests) must pass 100%.
- Real-data integration tests must continue to pass with 0 quota diff.
