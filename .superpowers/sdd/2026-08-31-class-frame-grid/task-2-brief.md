# Task 2: Core Logic Integration (update `build_scheduling_input`)

## Objective & Scope
- Update `data/repository.py`'s `build_scheduling_input` to read from `class_allowed_cells`.
- If a class has explicitly configured `class_allowed_cells`, use those to generate the `slots` for that class.
- If a class does not have `class_allowed_cells`, fall back to the existing `frame_mod.active_cells` calculation based on `frame_template`.

## Interface Specifications
- `build_scheduling_input` output `SchedulingInput.slots` and `SchedulingInput.timeslots` must correctly reflect the explicitly checked cells.

## TDD Strategy
- Create a test in `tests/test_class_frame_grid.py`: `test_build_scheduling_input_uses_allowed_cells`.
- RED Phase: 
  - Create a test DB with a class and explicitly set some `class_allowed_cells`.
  - Call `build_scheduling_input`.
  - Expect it to return the fallback slots (e.g. standard 5 Sáng 3 Chiều) instead of the explicitly set ones.
- GREEN Phase:
  - Implement the change in `repository.py`.
  - Run the test, expect the slots to match exactly the `class_allowed_cells`.

## Safety & Invariants
- Preserve backward compatibility with `frame_template` for existing data or unconfigured classes.
- Ensure `ts_by_key` correctly resolves the explicit coordinates.
