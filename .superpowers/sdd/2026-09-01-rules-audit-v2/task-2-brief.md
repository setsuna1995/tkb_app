# Task 2 Brief: Non-Consecutive Guard in `_try_swap_repair`

## Objective & Scope

**What**: Add a non-consecutive day check after swap-repair places a moved subject into a new slot, so that if the swap creates a consecutive-day violation for a `non_consecutive` or GDTC subject, the swap is rolled back immediately instead of letting the whole attempt pass through greedy only to be rejected by the engine's post-check.

**Out of scope**: Changing the engine post-check (it stays as a safety net).

## Interface Specifications

No new functions. Modify `_try_swap_repair` in `core/scheduler/swaps.py`:

```python
def _try_swap_repair(class_id, slot, state, role_index, subjects, assigned_teacher,
                     slots_by_class, day_capacity=None, config=None,
                     subject_class_allowed_cells=None) -> bool:
```

After a successful `_put_at(state, slot, moved_subject, moved_teacher, ...)` and before accepting the refill, check:
- If `moved_subject` is in `non_consecutive_subject_ids` or is `gdtc_id` (with `avoid_gdtc_consecutive_days`), verify no adjacent weekday has the same subject for the same class.

Similarly, after `refill` is placed, verify the refill subject doesn't create a consecutive violation.

## TDD Strategy

- **Test file**: `tests/test_scheduler.py` (add a targeted test)
- **Test name**: `test_swap_repair_rejects_non_consecutive_violation`
- **RED phase expected**: The test should PASS even without changes (the engine post-check catches it), but we add a focused unit test on `_try_swap_repair` directly to verify it rejects the swap at the swap level.
- **GREEN phase**: After adding the guard, `_try_swap_repair` returns False for the offending swap.

## Safety & Invariants
- No disk writes in tests
- Existing swap behavior unchanged for non-consecutive-exempt subjects
- Post-check in engine.py remains as ultimate safety net
