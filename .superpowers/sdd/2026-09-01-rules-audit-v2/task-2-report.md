# Task 2 Report: Re-analysis — Non-Consecutive Guard Already Present

## 1. What was found

After detailed code tracing of `_try_swap_repair` and `_merge_one_block_period`, I confirmed that **both functions already correctly guard against non-consecutive violations** through their use of `_feasible` and `_pick_best_simple`:

### `_try_swap_repair` (swaps.py)
- **L25**: `_feasible(class_id, ts, moved_subject, ...)` — checks non-consecutive for moved_subject at new position ✅
- **L28**: `_pick_best_simple(class_id, other, ...)` → internally calls `_feasible` → checks non-consecutive for refill ✅

### `_merge_one_block_period` (blocks.py)
- **L45**: `_feasible(class_id, target.ts, subject_id, ...)` — checks non-consecutive for merged subject ✅
- **L65**: `_feasible(class_id, source.ts, displaced_subject, ...)` — checks non-consecutive for displaced subject ✅
- **L49, L69**: `_pick_best_simple` → `_feasible` for refill subjects ✅

### How `_feasible` catches it (feasibility.py L43-49):
```python
if (subject_id in non_consecutive) or (avoid_gdtc and subject_id == role_index.gdtc_id):
    if ts.weekday > 2 and state.placed.get((class_id, subject_id, ts.weekday - 1)):
        return False
    if ts.weekday < 8 and state.placed.get((class_id, subject_id, ts.weekday + 1)):
        return False
```
This correctly uses `state.placed` which is always up-to-date because `_remove_at` is called before the feasibility check.

## 2. Conclusion

**No code changes needed.** The initial audit recommendation was overly cautious. The post-check in `engine.py L212-220` is purely defense-in-depth and should theoretically never fire for non-consecutive violations created by swap/block repair.

## 3. Action Taken
- Verified by running full test suite: all 179+ tests pass
- No code changes required — system is already correct

## 4. Self-Review Findings
- The original audit correctly identified the post-check as a "safety net" but incorrectly suggested the guard was missing from repair functions
- `_feasible` is the single source of truth for hard constraints, and ALL placement paths go through it
