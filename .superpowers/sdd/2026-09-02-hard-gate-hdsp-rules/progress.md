# SDD Progress Ledger: Hard-Gate HĐSP Rules (II.3, II.4, II.8, II.14)

- **Date**: 2026-09-02
- **Feature**: `hard-gate-hdsp-rules`
- **Root Context**: Master branch / Working tree
- **Status**: `in-progress`
- **Design doc**: plan approved via Claude Code Plan Mode 2026-09-02 (see chat transcript / `C:\Users\Kien\.claude\plans\c-c-i-u-ki-n-b-t-twinkling-cloud.md`)

## Why (Bối cảnh)

Ledger `2026-09-01-mandatory-school-rules-and-moet-standards/progress.md` marked
II.3/II.7/II.8/II.9 "Verified", but "Verified" there only meant a unit test on
the scoring function passes — no full generated schedule was ever checked
end-to-end. Two concrete bugs cause the symptoms the user (Kien) reported on
2026-09-02 ("vẫn có người được nghỉ sáng T2", "vẫn nhiều buổi lẻ 1 tiết"):

1. `core/scheduler/teacher_off.py` silently assigns FEWER off-sessions than
   required (`min(remaining_count, len(all_eligible_cells))`) when a teacher
   has too many exclusions — never surfaced anywhere.
2. `core/scheduler/swaps.py:_repair_teacher_lone_sessions`'s success is never
   verified — unlike the class-level lone-period check, which already gates
   whether an attempt counts as successful.

Rule classification decision (user-confirmed 2026-09-02): II.3, II.4, II.8,
II.14 become hard-gated (with retry, or explicit `relaxed_rules` reporting
when retry structurally cannot help). II.7 and II.9 stay soft — hard-gating
them alongside II.4 is infeasible for teachers whose weekly afternoon load is
exactly 1 period (forces a lone session, i.e. self-contradicts II.4), and the
project's own conflict-audit doc already documents `TEACHER_AFTERNOON_BALANCE_BONUS=0`
as a deliberate choice to avoid this exact trap for II.7.

## Pre-flight Conflict Scan Table

| Tasks | File(s) | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 4 | `core/models.py`, `core/scheduler/engine.py` | Task 1 fixes config defaults + adds `ScheduleResult.relaxed_rules` | Task 4 populates `relaxed_rules` on the returned result | Clean — strict order 1 -> 4 |
| 2, 4 | `core/scheduler/teacher_off.py`, `core/scheduler/engine.py` | Task 2 changes `_assign_off_slots` to return `(gv_off_slots, shortfall)` | Task 4 unpacks the new tuple at the call site | Clean — strict order 2 -> 4 (Task 4 will not compile until Task 2 lands) |
| 3, 5 | `core/rules_registry.py`, `pages/06_Xep_TKB.py` | Task 3 defines rule tiers (which IDs block save) | Task 5's UI loop reads tier to decide block vs warn | Clean — strict order 3 -> 5 |
| 4, 5 | `core/scheduler/engine.py`, `core/validation.py` + `pages/06_Xep_TKB.py` | Task 4 adds the post-generation hard gate + `relaxed_rules` | Task 5 adds matching `find_*` validators + renders `relaxed_rules` in the UI | Clean — strict order 4 -> 5 |
| 1-5, 6 | all above | Tasks 1-5 change engine/config/UI behavior | Task 6 asserts the new behavior end-to-end + regression fixtures | Clean — Task 6 must run last |

Tasks 1, 2, 3 have no dependencies on each other and can be implemented in
any order (or in parallel by different subagents).

## Task Checklist

- [ ] **Task 1**: Config defaults (`min_weekly_periods_for_lone_penalty`→15, `heavy_subject_priority_periods`→4) + `ScheduleResult.relaxed_rules` field (`core/models.py`, `pages/10_Cau_hinh_Xep_lich.py`, `tests/test_mandatory_rules_compliance.py`). Brief: task-1-brief.md
- [ ] **Task 2**: Fix `teacher_off.py` silent off-slot shortfall — return `(gv_off_slots, shortfall)` instead of truncating silently (`core/scheduler/teacher_off.py`). Brief: task-2-brief.md
- [ ] **Task 3**: New `core/rules_registry.py` — single source of truth for rule tier (which II.x rules are hard-gated vs soft). Brief: task-3-brief.md
- [ ] **Task 4**: Generalize the post-generation hard gate in `engine.py` — reject attempts violating II.3(accidental empty forbidden morning)/II.4/II.8/II.14, add a core-invariant-only fallback path returning `relaxed_rules` instead of silent failure, retune `NGUONG_KHOA`. Brief: task-4-brief.md
- [ ] **Task 5**: `core/validation.py` new `find_*` wrappers for II.3/II.4/II.8/II.14 + wire save-gate blocking and `relaxed_rules` display into `pages/06_Xep_TKB.py`. Brief: task-5-brief.md
- [ ] **Task 6**: Extend `tests/test_mandatory_rules_compliance.py` end-to-end assertions + regression fixtures for both root-cause bugs + profile real fixture before/after. Brief: task-6-brief.md
