# Xếp TKB UI Redesign + "Solve Longer" + Bottleneck Diagnosis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the UI-first slice of the 2026-10-07 UI/UX spec on the scheduling page (`pages/06_Xep_TKB.py`), plus three new capabilities: a working "⏱️ Giải thêm thời gian" button that continues the search from the current timetable, a "🔍 Nút thắt" panel that explains *why* the timetable is not better (time-limited vs. constraint-limited vs. specific teacher/rule), and Excel export of the Studio views — one sheet per class and one sheet per teacher.

**Architecture:** Solver gets three small, backward-compatible additions (search telemetry in `diagnostics`, a `deep=True` mode that disables early stopping, morning-capacity rows in `diagnostics`). A new pure module `core/scheduler/bottleneck.py` turns `ScheduleResult` + detector violations into a ranked list of `Bottleneck` records. The page consumes both; theme gets one role→CSS map for the coloured class grid.

**Tech Stack:** Python 3.14, Streamlit 1.62, OR-Tools CP-SAT, pandas Styler, pytest (`-n auto`, already in `pytest.ini`).

**Spec:** `docs/superpowers/specs/2026-10-07-ui-ux-setting-xep-tkb-design.md` (sections 2.1, 4.1, 4.2 A–E, 7.2). The settings page (spec §3, `pages/10_Cau_hinh_Xep_lich.py`) is **out of scope** — it gets its own plan after this one ships, merged with the CPU auto-tune card from `2026-10-07-portable-desktop-app-and-solver-autotune-design.md` §2.3 (both rewrite the same Tab 5).

## Global Constraints

- Keep 100% of `SchedulingConfig` field names and existing `st.session_state` keys (spec §6 row 1).
- Do not change solver behaviour for existing callers: every new solver parameter is keyword-only with a default that reproduces today's behaviour.
- `ScheduleResult.rule_counts` is "cross-check only, never shown" (`core/models.py:235`) — bottleneck UI must use detector violations, not `rule_counts`.
- All user-facing strings Vietnamese; code/comments follow surrounding file style.
- Extra-time options: +30s / +60s / +120s / +300s (spec Tab 5 range caps at 300s).
- Run `node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .` before editing each solver/page symbol; `solve_to_result` returns `risk: UNKNOWN` (callers go through the `cpsat_model` facade re-export) — 33 text references exist, so the signature change MUST stay backward-compatible.
- Before commit: `node .gitnexus/run.cjs detect-changes --scope all --repo .`.

## Review Focus

1. **Sheet names from real data** — class names like `6/2`, two teachers both called "Nguyễn Thị Hà", names > 31 chars. Excel rejects `[]:*?/\`, duplicates (case-insensitive) and > 31 chars; user expects the file to open with every class/teacher present. Tests in Task 9 (`test_class_workbook_one_sheet_per_class_in_order`, `test_teacher_workbook_dedupes_names_and_skips_idle`, `test_sheet_name_truncated_to_31`).
2. **"Solve longer" on a candidate produced by lock-refine** — user expects locked classes/teachers to stay locked. Task 6 stores `locked_slots` on the candidate and re-passes it (manual check 6.8.5).
3. **Extra-time run comes back worse or fails** — user expects never to lose the current timetable. Task 6 keeps the old candidate, adds the new one, auto-selects only if its health score is higher, and shows the delta.
4. **Result without new diagnostics** (a `ScheduleResult` sitting in `st.session_state` from before this change, or a heuristic result) — panel must render, not crash. Test in Task 4 (`test_result_without_diagnostics_does_not_crash`).
5. **Already OPTIMAL result** — pressing "solve longer" is pointless; button must say so instead of burning 60s. Test in Task 4 (`test_more_time_cannot_help_when_optimal_and_nothing_relaxed`).

## Why the existing "Giải sâu hơn (+30s)" button does not help (root cause, read before Task 2)

`pages/06_Xep_TKB.py:1214-1248` already has a deep-solve button, but:
1. `EarlyStoppingCallback` (`core/scheduler/cpsat/solver.py:139`) stops on plateau (<3% or <600 points improvement within 4s) and on 5–7s without a new solution, and `relative_gap_limit = 0.03`. A bigger time limit is therefore mostly **never used** — the run ends at the same moment as before.
2. It restarts from scratch (no `s_reference_assignment`), so it can land on a *worse* timetable.
3. It drops the candidate's strategy (`anti_lone`/`presence`/`pareto`) and its locked slots.
4. The new candidate (id ≥ 4) is invisible: the card grid renders `cand_items[:3]` (`06_Xep_TKB.py:1096`).
5. It is buried inside the "Công cụ tinh chỉnh nâng cao" expander.

Note (not changed here): `solve_three_strategies` caps each strategy at 30s regardless of config (`solver.py:449`). The new button works per-candidate, so this cap no longer limits quality.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `core/scheduler/cpsat/solver.py` | Modify | telemetry in `build_result`; `deep` mode; `_morning_capacity_rows` |
| `core/scheduler/bottleneck.py` | Create | `Bottleneck`, `search_headroom`, `more_time_can_help`, `analyze_bottlenecks` (pure, no Streamlit) |
| `ui_theme.py` | Modify | `ROLE_CELL_CSS`, `role_cell_css()` |
| `pages/06_Xep_TKB.py` | Modify | hero run control, action bar + extra-time, bottleneck panel, coloured grid, exception-only QA, per-class/per-teacher export buttons, delete batch block |
| `io_excel/exporter.py` | Modify | `export_class_sheets_xlsx`, `export_teacher_sheets_xlsx` (pure: no DB, no template) |
| `tests/test_exporter_sheets.py` | Create | per-sheet export tests |
| `tests/test_deep_solve_and_bottleneck.py` | Create | solver telemetry/deep/capacity tests |
| `tests/test_bottleneck.py` | Create | pure analyzer tests |
| `tests/test_ui_theme.py` | Modify | role palette test |

Skipped from spec §2.2 (YAGNI): `render_action_bar`, `render_bento_section`, `render_status_summary_bar`, `render_subject_pill` — `st.columns` + existing `render_card` / `render_status_badge` / `render_callout` cover them. Add when a second page needs the same component.

---

### Task 0: Prep

- [ ] **Step 1:** The working tree has uncommitted WIP (`core/models.py`, `core/rules/*`, `core/scheduler/*`, both pages, tests). Ask the user to commit it or confirm it belongs in this branch. Do not start on top of unknown WIP.
- [ ] **Step 2:** `git checkout -b feat/xep-tkb-ui-deep-solve`
- [ ] **Step 3:** Save the UI spec the user supplied to `docs/superpowers/specs/2026-10-07-ui-ux-setting-xep-tkb-design.md` (fix its `file:///c:/Users/kiennt9/...` links to repo-relative paths).
- [ ] **Step 4:** Baseline: `pytest -q` — record pass/fail counts. Any pre-existing failure is noted, not fixed here.

---

### Task 1: Search telemetry in `diagnostics`

**Files:**
- Modify: `core/scheduler/cpsat/solver.py` (`build_result`, ~line 15-64)
- Test: `tests/test_deep_solve_and_bottleneck.py` (create)

**Interfaces:**
- Produces: `result.diagnostics["final_status"]: str` ("OPTIMAL"|"FEASIBLE"), `["objective"]: float`, `["best_bound"]: float`, `["wall_time_s"]: float`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_deep_solve_and_bottleneck.py
import time

import pytest
from core.models import (
    ROLE_HDTN, ROLE_THUONG, ClassRoom, SchedulingConfig, SchedulingInput,
    Slot, Subject, Teacher, TimeSlot,
)

cpsat = pytest.importorskip("core.scheduler.cpsat_model")
from core.scheduler.cpsat import solver as solver_mod  # noqa: E402


def _tiny_feasible_input():
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5, 6, 7])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    return SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=[Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)],
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 3, (2, 101): 3},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(strict_morning_weekdays=()),
    )


def test_build_result_records_search_telemetry():
    res = cpsat.solve_to_result(cpsat.build_model(_tiny_feasible_input()), time_limit_s=10.0)
    d = res.diagnostics
    assert d["final_status"] in ("OPTIMAL", "FEASIBLE")
    assert d["objective"] >= d["best_bound"] - 1e-6
    assert d["wall_time_s"] >= 0.0
```

- [ ] **Step 2:** `pytest tests/test_deep_solve_and_bottleneck.py::test_build_result_records_search_telemetry -v -n0` → FAIL `KeyError: 'final_status'`.

- [ ] **Step 3: Implement** — in `build_result`, replace the final `diagnostics=diagnostics or {},` usage:

```python
    diag = dict(diagnostics or {})
    diag.update(
        final_status=solver.StatusName(),
        objective=float(solver.ObjectiveValue()),
        best_bound=float(solver.BestObjectiveBound()),
        wall_time_s=float(solver.WallTime()),
    )
```
and pass `diagnostics=diag,` to `ScheduleResult(...)`. Leave the `unsat_core` lookup above it reading `diagnostics` unchanged.

- [ ] **Step 4:** Re-run the test → PASS. Run `pytest tests/test_cpsat_pinpoint_diagnosis.py tests/test_cpsat_model.py -q` → still green.
- [ ] **Step 5:** `git commit -am "feat(solver): record final status, objective and bound in diagnostics"`

---

### Task 2: `deep=True` search mode (no early stopping)

**Files:**
- Modify: `core/scheduler/cpsat/solver.py` (`_diagnose_and_solve` ~line 247, `solve_to_result` ~line 418)
- Test: `tests/test_deep_solve_and_bottleneck.py`

**Interfaces:**
- Produces: `solve_to_result(built, time_limit_s=30.0, workers=None, progress_cb=None, strategy="default", *, deep: bool = False)`; `result.diagnostics["deep"]: bool`.

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_zero_thresholds_never_detect_plateau():
    cb = solver_mod.EarlyStoppingCallback(
        stagnation_s=999.0, plateau_window_s=0.5,
        min_improvement_rate=0.0, min_improvement_abs=0.0, min_search_s=0.2,
    )
    now = time.time()
    cb.start_time = now - 1.0
    cb.history = [(now - 0.6, 1000.0), (now - 0.1, 1000.0)]
    cb.best_obj = 1000.0
    assert cb._check_plateau() is False


def test_deep_mode_disables_early_stop_and_gap(monkeypatch):
    seen = []
    real = solver_mod.EarlyStoppingCallback

    class Spy(real):
        def __init__(self, *a, **kw):
            seen.append(kw)
            super().__init__(*a, **kw)

    monkeypatch.setattr(solver_mod, "EarlyStoppingCallback", Spy)
    res = solver_mod.solve_to_result(cpsat.build_model(_tiny_feasible_input()), time_limit_s=5.0, deep=True)
    assert res is not None and res.diagnostics["deep"] is True
    assert seen[0]["min_improvement_abs"] == 0.0
    assert seen[0]["min_improvement_rate"] == 0.0


def test_default_mode_unchanged(monkeypatch):
    seen = []
    real = solver_mod.EarlyStoppingCallback

    class Spy(real):
        def __init__(self, *a, **kw):
            seen.append(kw)
            super().__init__(*a, **kw)

    monkeypatch.setattr(solver_mod, "EarlyStoppingCallback", Spy)
    res = solver_mod.solve_to_result(cpsat.build_model(_tiny_feasible_input()), time_limit_s=5.0)
    assert res.diagnostics["deep"] is False
    assert "min_improvement_abs" not in seen[0]  # library defaults (600 / 3%) still apply
```

- [ ] **Step 2:** Run → `test_deep_mode_*` FAIL (`unexpected keyword 'deep'`), `test_zero_thresholds_*` PASS already (documents the contract the implementation relies on).

- [ ] **Step 3: Implement**

`_diagnose_and_solve` signature: add `deep: bool = False` after `strategy`. Add `"deep": deep,` and `"morning_capacity": [],` to the initial `diag` dict (the latter is used by Task 3). Replace the block that sets `relative_gap_limit` and builds `cb`:

```python
        solver.parameters.max_time_in_seconds = float(pass_limit)
        solver.parameters.relative_gap_limit = 0.0 if deep else 0.03
        # deep: chỉ dừng khi hết giờ hoặc chứng minh tối ưu -- người dùng đã chủ động trả thêm thời gian
        stop_kw = ({"stagnation_s": float(pass_limit), "min_improvement_abs": 0.0, "min_improvement_rate": 0.0}
                   if deep else {"stagnation_s": stagnation})
        cb = EarlyStoppingCallback(
            progress_cb=progress_cb, pass_no=diag["passes_run"], max_passes=max_passes, **stop_kw
        )
```

`solve_to_result`: add `*, deep: bool = False` to the signature and pass `deep=deep` into `_diagnose_and_solve(...)`. Do not touch `solve`, `solve_three_strategies`, `engine.run`.

- [ ] **Step 4:** Run the three tests → PASS. Run `pytest tests/test_cpsat_plateau_early_stopping.py tests/test_cpsat_tiered_diagnosis.py -q` → green.
- [ ] **Step 5:** `git commit -am "feat(solver): deep search mode that only stops on time limit or optimality"`

---

### Task 3: Morning-capacity rows in `diagnostics`

**Files:**
- Modify: `core/scheduler/cpsat/solver.py` (`_presolve_capacity_screening` ~line 216, `_diagnose_and_solve` pass-1 block)
- Test: `tests/test_deep_solve_and_bottleneck.py`

**Interfaces:**
- Produces: `_morning_capacity_rows(built) -> list[dict]` with keys `weekday:int, teachers:int, need:int, cap:int`; `result.diagnostics["morning_capacity"]` = that list. `_presolve_capacity_screening` keeps its signature and return value.

- [ ] **Step 1: Write the failing test** (append; fixture mirrors `tests/test_cpsat_tiered_diagnosis.py::test_capacity_screening_detects_ii4_overflow`)

```python
def test_morning_capacity_rows_explain_ii3_conflict():
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2), TimeSlot(3, 2, "S", 3)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=[Subject(1, "M1", ROLE_THUONG), Subject(2, "M2", ROLE_THUONG), Subject(99, "HDTN", ROLE_HDTN)],
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B"), Teacher(99, "GV HDTN")],
        need={(1, 101): 10, (2, 101): 10, (99, 101): 0},
        assigned_teacher={(1, 101): 10, (2, 101): 20, (99, 101): 99},
        ban_busy=set(), slots=[Slot(i + 1, 101, t) for i, t in enumerate(ts)], timeslots=ts,
        config=SchedulingConfig(
            mandatory_morning_weekdays=(2,), min_weekly_periods_for_mandatory_morning=10,
            avoid_teacher_lone_periods=True, allow_lone_period_on_mandatory_mornings=False,
        ),
    )
    built = cpsat.build_model(inp)
    rows = solver_mod._morning_capacity_rows(built)
    monday = next(r for r in rows if r["weekday"] == 2)
    assert monday["teachers"] == 2
    assert monday["need"] == 4
    assert monday["need"] > monday["cap"]
    assert solver_mod._presolve_capacity_screening(built) == {"II.3"}
```

- [ ] **Step 2:** Run → FAIL `AttributeError: _morning_capacity_rows`.

- [ ] **Step 3: Implement** — rename the body of `_presolve_capacity_screening` into `_morning_capacity_rows`, with three edits: iterate `for wd in sorted(all_mand):`, start with `rows = []`, and replace the tail

```python
        if cap > 0 and min_needed > cap:
            return {"II.3"}

    return set()
```
with
```python
        rows.append({"weekday": wd, "teachers": len(mand_teacher_ids), "need": min_needed, "cap": cap})

    return rows
```
Then re-add the screening as a thin wrapper:

```python
def _presolve_capacity_screening(built: CpSatModel) -> set[str]:
    """Phân tích giải tích tiền giải (0.001s) để phát hiện mâu thuẫn dung lượng toán học (Pigeonhole)."""
    if any(r["cap"] > 0 and r["need"] > r["cap"] for r in _morning_capacity_rows(built)):
        return {"II.3"}
    return set()
```
In `_diagnose_and_solve`, inside `if diag["passes_run"] == 1:` add as first line:
```python
            diag["morning_capacity"] = _morning_capacity_rows(built)
```

- [ ] **Step 4:** Run new test + `pytest tests/test_cpsat_tiered_diagnosis.py tests/test_mandatory_morning_lone_session.py -q` → green.
- [ ] **Step 5:** `git commit -am "feat(solver): expose per-weekday mandatory-morning capacity in diagnostics"`

---

### Task 4: Bottleneck analyzer (pure module)

**Files:**
- Create: `core/scheduler/bottleneck.py`
- Test: `tests/test_bottleneck.py`

**Interfaces:**
- Consumes: Task 1 keys (`final_status`, `objective`, `best_bound`), Task 3 key (`morning_capacity`), `ScheduleResult.relaxed_rules`, `core.rules.violations.Violation` list (from the page's existing `_schedule_violations(inp, result)`).
- Produces:
  - `Bottleneck(kind: str, severity: float, title: str, evidence: str, action: str, rule_id: str|None=None, teacher_id: int|None=None)` — `kind ∈ {"time","capacity","rule","teacher"}`.
  - `search_headroom(result) -> float | None` — 0.0 optimal, None unknown.
  - `more_time_can_help(result) -> bool`
  - `analyze_bottlenecks(inp, result, violations, limit=5) -> list[Bottleneck]` sorted by severity desc.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bottleneck.py
from types import SimpleNamespace

from core.models import ScheduleResult, SchedulingInput, Teacher, TimeSlot
from core.rules.violations import Violation
from core.scheduler.bottleneck import analyze_bottlenecks, more_time_can_help, search_headroom


def _inp(ban_busy=frozenset()):
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 3, "S", 1), TimeSlot(3, 3, "S", 2)]
    return SchedulingInput(
        classes=[], subjects=[], teachers=[Teacher(10, "Cô Hà"), Teacher(20, "Thầy Hồng")],
        need={}, assigned_teacher={}, ban_busy=set(ban_busy), slots=[], timeslots=ts,
    )


def _res(diag=None, relaxed=()):
    return ScheduleResult(success=True, diagnostics=diag or {}, relaxed_rules=list(relaxed),
                          effective_params=SimpleNamespace(teacher_load={10: 18, 20: 12}))


def test_time_bottleneck_when_gap_large():
    r = _res({"final_status": "FEASIBLE", "objective": 1000.0, "best_bound": 600.0})
    assert search_headroom(r) == 0.4
    items = analyze_bottlenecks(_inp(), r, [])
    assert items[0].kind == "time"
    assert "40%" in items[0].evidence


def test_more_time_cannot_help_when_optimal_and_nothing_relaxed():
    r = _res({"final_status": "OPTIMAL", "objective": 300.0, "best_bound": 300.0})
    assert search_headroom(r) == 0.0
    assert more_time_can_help(r) is False
    assert all(b.kind != "time" for b in analyze_bottlenecks(_inp(), r, []))


def test_more_time_can_help_when_rule_relaxed_by_timeout():
    r = _res({"final_status": "OPTIMAL"}, relaxed=[{"rule_id": "II.4", "count": 2}])
    assert more_time_can_help(r) is True


def test_capacity_conflict_ranks_first():
    r = _res({"final_status": "FEASIBLE", "objective": 1000.0, "best_bound": 100.0,
              "morning_capacity": [{"weekday": 2, "teachers": 30, "need": 60, "cap": 52}]})
    items = analyze_bottlenecks(_inp(), r, [])
    assert items[0].kind == "capacity" and items[0].rule_id == "II.3"
    assert "Thứ 2" in items[0].title and "52" in items[0].evidence


def test_teacher_hotspot_names_teacher_load_and_busy():
    vs = [Violation("II.4", teacher_id=10) for _ in range(3)] + [Violation("II.4", teacher_id=20)]
    items = analyze_bottlenecks(_inp(ban_busy={(10, 1), (10, 2), (10, 3)}), _res({"final_status": "OPTIMAL"}), vs)
    t = next(b for b in items if b.kind == "teacher")
    assert t.teacher_id == 10 and "Cô Hà" in t.title
    assert "Tải 18" in t.evidence and "báo bận 2 buổi" in t.evidence  # ts 2 & 3 are the same session


def test_teacher_hotspot_ignores_synthetic_teachers():
    vs = [Violation("II.4", teacher_id=-5) for _ in range(5)]
    items = analyze_bottlenecks(_inp(), _res({"final_status": "OPTIMAL"}), vs)
    assert all(b.kind != "teacher" for b in items)


def test_relaxed_rule_not_duplicated_as_hotspot():
    vs = [Violation("II.4", teacher_id=None) for _ in range(3)]
    r = _res({"final_status": "OPTIMAL"}, relaxed=[{"rule_id": "II.4", "count": 3}])
    assert [b.rule_id for b in analyze_bottlenecks(_inp(), r, vs) if b.kind == "rule"] == ["II.4"]


def test_clean_optimal_result_has_no_bottleneck():
    assert analyze_bottlenecks(_inp(), _res({"final_status": "OPTIMAL", "objective": 0.0, "best_bound": 0.0}), []) == []


def test_result_without_diagnostics_does_not_crash():
    r = ScheduleResult(success=True)  # pre-change session_state object / heuristic result
    assert search_headroom(r) is None
    assert more_time_can_help(r) is True
    analyze_bottlenecks(_inp(), r, [Violation("II.7", teacher_id=10)])
```

- [ ] **Step 2:** `pytest tests/test_bottleneck.py -v -n0` → FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# core/scheduler/bottleneck.py
"""Chẩn đoán nút thắt: vì sao phương án TKB chưa đẹp hơn được.

Phân biệt 4 loại: thiếu thời gian giải (time), mâu thuẫn dung lượng (capacity),
tiêu chí phải nới lỏng / vi phạm nhiều (rule), và GV tập trung vi phạm (teacher).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

from core.models import ScheduleResult, SchedulingInput
from core.rules import RULES

GAP_WORTH_MORE_TIME = 0.05   # dưới 5% khoảng cách tới cận dưới thì thêm giờ gần như vô ích
TEACHER_MIN_SHARE = 0.15

RULE_KNOBS = {
    "II.3": "Cấu hình → Hiện diện: bớt thứ bắt buộc có mặt, nâng ngưỡng tiết/tuần, hoặc bật 'Cho phép 1 tiết lẻ vào buổi bắt buộc'.",
    "II.4": "Cấu hình → Hiện diện: nâng ngưỡng tiết/tuần phạt lẻ tiết, hoặc thêm GV đặc thù vào danh sách miễn trừ buổi lẻ.",
    "II.8": "Cấu hình → Hiện diện: thêm GV vào danh sách miễn trừ, hoặc giảm lịch báo bận khiến GV phải chia sáng/chiều.",
}
DEFAULT_ACTION = "Xem chi tiết trong mục Kiểm định chất lượng bên dưới."


@dataclass(frozen=True)
class Bottleneck:
    kind: str
    severity: float
    title: str
    evidence: str
    action: str
    rule_id: Optional[str] = None
    teacher_id: Optional[int] = None


def _title(rule_id: str) -> str:
    return RULES[rule_id].title_vi if rule_id in RULES else rule_id


def search_headroom(result: ScheduleResult) -> Optional[float]:
    """Tỉ lệ điểm phạt còn có thể giảm tối đa (theo cận dưới CP-SAT). 0.0 = đã tối ưu, None = không có số liệu."""
    d = result.diagnostics or {}
    if d.get("final_status") == "OPTIMAL":
        return 0.0
    obj, bound = d.get("objective"), d.get("best_bound")
    if obj is None or bound is None:
        return None
    if obj <= 0:
        return 0.0
    return round(max(0.0, (obj - bound) / obj), 4)


def more_time_can_help(result: ScheduleResult) -> bool:
    if any(not r.get("proven_infeasible") for r in result.relaxed_rules):
        return True  # nới lỏng do hết giờ chứ chưa chứng minh bất khả
    gap = search_headroom(result)
    return gap is None or gap > 0.0


def analyze_bottlenecks(inp: SchedulingInput, result: ScheduleResult, violations: list,
                        limit: int = 5) -> list[Bottleneck]:
    # ponytail: severity là thang heuristic cố định; chuyển sang đo "what-if" (giải lại khi nới 1 luật) nếu xếp hạng sai thực tế
    d = result.diagnostics or {}
    found: list[Bottleneck] = []

    gap = search_headroom(result)
    if gap is not None and gap >= GAP_WORTH_MORE_TIME:
        found.append(Bottleneck(
            "time", 50 + 100 * gap, "Bộ giải dừng khi chưa chắc chắn tối ưu",
            f"Điểm phạt {d['objective']:.0f}, cận dưới lý thuyết {d['best_bound']:.0f} "
            f"→ còn có thể cải thiện tối đa ~{gap:.0%}.",
            "Bấm “⏱️ Giải thêm thời gian” — bộ giải tiếp tục từ phương án hiện tại.",
        ))

    for row in d.get("morning_capacity", []):
        if row["cap"] > 0 and row["need"] > row["cap"]:
            found.append(Bottleneck(
                "capacity", 200, f"Sáng Thứ {row['weekday']} không đủ chỗ cho GV bắt buộc có mặt",
                f"{row['teachers']} GV phải có mặt cần tối thiểu {row['need']} tiết, nhưng chỉ có {row['cap']} ô.",
                RULE_KNOBS["II.3"], rule_id="II.3",
            ))

    relaxed = {r["rule_id"] for r in result.relaxed_rules}
    for item in result.relaxed_rules:
        rid, proven = item["rule_id"], item.get("proven_infeasible", False)
        found.append(Bottleneck(
            "rule", 150 if proven else 120, f"Phải nới lỏng {rid}: {_title(rid)}",
            "Đã chứng minh không thể đạt đồng thời với các ràng buộc khác." if proven
            else "Không tìm được nghiệm giữ cứng tiêu chí này trong thời gian cho phép — thử thêm thời gian trước.",
            RULE_KNOBS.get(rid, DEFAULT_ACTION), rule_id=rid,
        ))

    for rid, n in Counter(v.rule_id for v in violations).most_common(3):
        if rid not in relaxed:
            found.append(Bottleneck("rule", float(n), f"{rid}: {_title(rid)}",
                                    f"{n} vi phạm trong phương án này.",
                                    RULE_KNOBS.get(rid, DEFAULT_ACTION), rule_id=rid))

    found.extend(_teacher_hotspots(inp, result, violations))
    return sorted(found, key=lambda b: -b.severity)[:limit]


def _teacher_hotspots(inp: SchedulingInput, result: ScheduleResult, violations: list, top: int = 3) -> list[Bottleneck]:
    per_teacher = defaultdict(list)
    for v in violations:
        if v.teacher_id is not None and v.teacher_id > 0:
            per_teacher[v.teacher_id].append(v.rule_id)
    total = sum(len(r) for r in per_teacher.values())
    if not total:
        return []

    teachers = {t.teacher_id: t for t in inp.teachers}
    ts_by_id = {ts.ts_id: ts for ts in inp.timeslots}
    load = getattr(result.effective_params, "teacher_load", None) or {}
    out = []
    for tid, rids in sorted(per_teacher.items(), key=lambda kv: -len(kv[1]))[:top]:
        share = len(rids) / total
        if len(rids) < 2 or share < TEACHER_MIN_SHARE:
            continue
        t = teachers.get(tid)
        busy = len({(ts_by_id[ts_id].weekday, ts_by_id[ts_id].session)
                    for (b_tid, ts_id) in inp.ban_busy if b_tid == tid and ts_id in ts_by_id})
        day_off = f", ghim nghỉ trọn Thứ {t.pinned_full_day_off}" if t and t.pinned_full_day_off else ""
        rule_txt = ", ".join(f"{r}×{c}" for r, c in Counter(rids).most_common())
        out.append(Bottleneck(
            "teacher", 10.0 * len(rids), f"GV {t.name if t else tid} là điểm nghẽn",
            f"Gánh {len(rids)}/{total} vi phạm ({share:.0%}): {rule_txt}. "
            f"Tải {load.get(tid, '?')} tiết/tuần, báo bận {busy} buổi{day_off}.",
            "Rà lại lịch báo bận / ghim nghỉ của GV này; nếu là GV đặc thù (thiết bị, thư viện) thì thêm vào danh sách miễn trừ.",
            teacher_id=tid,
        ))
    return out
```

- [ ] **Step 4:** `pytest tests/test_bottleneck.py -v -n0` → 9 PASS.
- [ ] **Step 5:** `git add core/scheduler/bottleneck.py tests/test_bottleneck.py && git commit -m "feat: bottleneck analyzer explaining why a timetable is not better"`

---

### Task 5: Subject-role colour palette

**Files:**
- Modify: `ui_theme.py` (append after `render_card`)
- Test: `tests/test_ui_theme.py`

**Interfaces:**
- Produces: `role_cell_css(role_code: int | None) -> str` (CSS declaration string for pandas Styler).

- [ ] **Step 1: Write the failing test** (append)

```python
from core.models import ROLE_GDTC, ROLE_HDTN, ROLE_NANG
from ui_theme import role_cell_css


def test_role_cell_css_palette_and_fallback():
    assert "#EFF6FF" in role_cell_css(ROLE_NANG)
    assert "#FFF7ED" in role_cell_css(ROLE_GDTC)
    assert "#F0FDF4" in role_cell_css(ROLE_HDTN)
    assert role_cell_css(None) == role_cell_css(999)
    assert "#94A3B8" in role_cell_css(None)
```

- [ ] **Step 2:** Run → FAIL `ImportError`.
- [ ] **Step 3: Implement** (spec §2.1 values; text colours pass 4.5:1 on their backgrounds)

```python
from core.models import ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG, ROLE_NANG_KEP, ROLE_THUONG

_NANG_CSS = "background-color:#EFF6FF;color:#1E40AF;font-weight:600"
ROLE_CELL_CSS = {
    ROLE_NANG: _NANG_CSS,
    ROLE_NANG_KEP: _NANG_CSS,
    ROLE_GDTC: "background-color:#FFF7ED;color:#9A3412",
    ROLE_HDTN: "background-color:#F0FDF4;color:#166534",
    ROLE_KEP: "background-color:#FAF5FF;color:#6B21A8",
    ROLE_THUONG: "background-color:#F8FAFC;color:#334155",
}
EMPTY_CELL_CSS = "background-color:#FFFFFF;color:#94A3B8"


def role_cell_css(role_code) -> str:
    """CSS cho 1 ô TKB theo vai trò môn (spec 2.1). Ô trống / môn lạ -> nhạt."""
    return ROLE_CELL_CSS.get(role_code, EMPTY_CELL_CSS)
```
(Put the import at the top of `ui_theme.py` with the other imports.)

- [ ] **Step 4:** `pytest tests/test_ui_theme.py -q -n0` → PASS.
- [ ] **Step 5:** `git commit -am "feat(theme): subject role colour palette for timetable cells"`

---

### Task 6: Page — hero run control, action bar, "⏱️ Giải thêm thời gian"

**Files:**
- Modify: `pages/06_Xep_TKB.py`

**Interfaces:**
- Consumes: `solve_to_result(..., deep=True)` (Task 2), `more_time_can_help`, `search_headroom` (Task 4).
- Produces: candidate dicts gain `"key"` (strategy) on every path and `"locked_slots"` on refine/deep paths.

Run impact first: `_run_single_solver`, `_render_rule_violations` (page-local; confirm with grep).

- [ ] **Step 1: Hero run control.** Wrap the per-week tweaks — from `extra_kep_options = ...` (~line 711) through the end of the `with st.container(border=True):` HĐTN block (~line 880) — in:

```python
    with st.expander("⚙️ Tùy chỉnh riêng cho tuần này (Môn kép tạm thời, Phương án HĐTN)", expanded=False):
```
(indent the block one level; all variables are still assigned because expander bodies always execute). Right after the expander add a one-line summary so the collapsed state is still informative:

```python
    st.caption(
        f"Áp dụng: HĐTN **{'Tuần chuyên đề' if hdtn_thematic_week else 'Tuần chuẩn'}**"
        + (f" • Môn kép tạm thời: **{', '.join(extra_kep_names)}**" if extra_kep_names else "")
    )
```
Spec §4.1 also wants the week status in the hero. In the existing `col_w_head1` block (~line 671), replace the `st.write(f"Tuần đang xếp: ...")` line with (reuse `run_now`, moving its assignment `run_now = repo.get_latest_run_by_week(conn, chosen_week)` above the `st.columns` call):

```python
        st.markdown(
            f"Trạng thái Tuần {chosen_week}: "
            + (f"✅ **Đã có TKB chính thức** (lưu lúc {run_now['created_at']})" if run_now
               else "⏳ **Chưa có TKB chính thức**")
        )
```

- [ ] **Step 2: `_run_single_solver` gets `deep`.** Add `deep=False` as last parameter and pass `deep=deep` to `cpsat_model.solve_to_result(...)` (~line 939).

- [ ] **Step 3: Store strategy + locks on candidates.** Three candidate-creation sites:
  - Seed button (~line 1197): add `"key": "default",`.
  - Single-slot solver (~line 1393, passes `s_locked_slots=computed_locked`): add `"key": "default", "locked_slots": computed_locked,`.
  - Lock-refine (~line 1484, passes `s_locked_slots=computed_locked_slots`): add `"key": "default", "locked_slots": computed_locked_slots,`.

- [ ] **Step 4: Show new candidates.** Replace `cand_items = list(st.session_state.get("candidates", {}).values())` + `cand_items[:3]` with:

```python
            all_cands = list(st.session_state.get("candidates", {}).values())
            active_cid = st.session_state.get("active_candidate_id")
            by_score = sorted(all_cands, key=lambda c: -c["metrics"]["health_score"]["overall_score"])
            cand_items = sorted(
                [c for c in all_cands if c["id"] == active_cid] + [c for c in by_score if c["id"] != active_cid][:2],
                key=lambda c: c["id"],
            )
```
and iterate `for idx, c in enumerate(cand_items):`. If `len(all_cands) > 3`, add `st.caption(f"Đang hiện 3/{len(all_cands)} phương án (phương án đang chọn + 2 phương án điểm cao nhất).")`.

- [ ] **Step 5: Action bar under the cards.** Right after the card loop and the `relaxed_rules` warning, compute gating once:

```python
            violations_curr = _schedule_violations(inp, result)
            has_blocking = any(v.level == BREACH and RULES[v.rule_id].blocks_save for v in violations_curr)
            can_save = not has_blocking or st.session_state.get("proceed_with_hard_violations", False)
```
Move the whole `col_acc1, col_acc2, col_acc3 = st.columns(...)` block (save / download / cancel, ~lines 1647-1700) **verbatim** to here, changing `st.columns([1.2, 1.2, 1])` → `st.columns([1.2, 1.2, 1.4, 0.8])` (cancel moves to `col_acc4`), and `disabled=not proceed_with_hard_violations` → `disabled=not can_save`, with `help="Còn vi phạm tiêu chí bắt buộc — xem mục Kiểm định bên dưới để xác nhận." if not can_save else None`. Delete the old block at the bottom. Keep the bottom `_render_rule_violations(violations_curr, "proceed_with_hard_violations", ...)` call (pass `violations_curr` instead of recomputing) — its checkbox keeps feeding `can_save` through session_state.

- [ ] **Step 6: The extra-time control in `col_acc3`.**

```python
            with col_acc3:
                can_help = more_time_can_help(result)
                extra_s = st.segmented_control(
                    "Giải thêm", [30, 60, 120, 300], default=60,
                    format_func=lambda s: f"+{s}s", key="extra_time_pick",
                    disabled=not can_help, label_visibility="collapsed",
                ) or 60
                gap = search_headroom(result)
                clicked_more = st.button(
                    "⏱️ Giải thêm thời gian" if can_help else "✅ Đã tối ưu với cấu hình này",
                    key="btn_extend_search", disabled=not can_help, width="stretch",
                    help=(f"Tiếp tục tìm kiếm từ phương án hiện tại thêm {extra_s}s. "
                          + (f"Còn có thể cải thiện tối đa ~{gap:.0%}." if gap else ""))
                         if can_help else "Bộ giải đã chứng minh tối ưu. Xem mục 🔍 Nút thắt để biết cần nới cấu hình nào.",
                )
            if clicked_more:
                active_cand = st.session_state["candidates"][st.session_state["active_candidate_id"]]
                strategy = active_cand.get("key") if active_cand.get("key") in ("anti_lone", "presence", "pareto") else "default"
                deep_cfg = dataclasses.replace(active_cand["inp"].config, cpsat_time_limit_seconds=int(extra_s))
                old_score = active_cand["metrics"]["health_score"]["overall_score"]
                inp_new, res_new = _run_single_solver(
                    active_cand["seed"], deep_cfg,
                    s_locked_slots=active_cand.get("locked_slots"),
                    s_reference_assignment=result.assignment,
                    strategy=strategy, deep=True,
                )
                if not res_new.success:
                    st.error(f"Giải thêm không thành công, giữ nguyên phương án hiện tại: {res_new.failure_reason}")
                else:
                    metrics_new = compute_candidate_metrics(inp_new, res_new)
                    new_score = metrics_new["health_score"]["overall_score"]
                    new_id = max(st.session_state["candidates"]) + 1
                    st.session_state["candidates"][new_id] = {
                        "id": new_id, "key": strategy,
                        "name": f"Phương án {new_id} (+{extra_s}s từ PA {active_cand['id']})",
                        "strategy_desc": f"Tiếp tục tối ưu PA {active_cand['id']} thêm {extra_s}s",
                        "seed": active_cand["seed"], "time_limit": int(extra_s),
                        "locked_slots": active_cand.get("locked_slots"),
                        "result": res_new, "inp": inp_new, "metrics": metrics_new,
                    }
                    if new_score >= old_score:
                        st.session_state["active_candidate_id"] = new_id
                        st.session_state["last_result"] = res_new
                        st.session_state["last_input"] = inp_new
                    st.session_state["extend_msg"] = (
                        f"PA {new_id}: {new_score:.1f} điểm ({new_score - old_score:+.1f} so với PA {active_cand['id']})"
                        + ("" if new_score >= old_score else " — giữ nguyên PA cũ vì tốt hơn.")
                    )
                    st.rerun()
```
Above the action bar render the message once: `if msg := st.session_state.pop("extend_msg", None): st.info(msg)`.
Note `new_id = max(...) + 1` (the old `len(...) + 1` collides after cancellations — use `max` here; leave other call sites alone). Import at top: `from core.scheduler.bottleneck import analyze_bottlenecks, more_time_can_help, search_headroom`.

- [ ] **Step 7: Remove the old "⏱️ Giải sâu hơn (+30s)" button** (`col_bar2` block, ~lines 1214-1248); the seed button keeps `col_bar1` — change `st.columns([1, 1])` to a plain `if st.button(...)` without columns.

- [ ] **Step 8: Manual verification** (`streamlit run app.py`, school `truong-thcs-2-buoi`, week 6):
  1. Collapsed expander shows the summary caption; changing HĐTN inside still affects the run.
  2. Run 3 PA → cards + action bar appear directly under cards; save button disabled with help text when a blocking violation exists, enabled after ticking the override checkbox at the bottom.
  3. Press "⏱️ Giải thêm thời gian" +60s on PA 3: progress log shows the run lasting ~60s (not stopping at ~10s), a PA 4 card appears, info message shows the score delta.
  4. On a candidate whose diagnostics are OPTIMAL with no relaxed rule, the button reads "✅ Đã tối ưu…" and is disabled.
  5. Lock class 6A1 via Giai đoạn 2 refine, then extend: 6A1 cells are unchanged in the new PA.
- [ ] **Step 9:** `git commit -am "feat(xep-tkb): hero run control, top action bar and warm-started extra-time search"`

---

### Task 7: Page — "🔍 Nút thắt" panel

**Files:**
- Modify: `pages/06_Xep_TKB.py` (right after the action bar from Task 6)

- [ ] **Step 1: Implement**

```python
            bottlenecks = analyze_bottlenecks(inp, result, violations_curr)
            kind_badge = {"capacity": ("Dung lượng", "danger"), "rule": ("Tiêu chí", "warning"),
                          "teacher": ("Giáo viên", "warning"), "time": ("Thời gian giải", "info")}
            with st.expander(
                f"🔍 Vì sao phương án này chưa đẹp hơn? ({len(bottlenecks)} nút thắt)" if bottlenecks
                else "🔍 Nút thắt: không phát hiện",
                expanded=bool(bottlenecks) and bottlenecks[0].kind != "time",
            ):
                if not bottlenecks:
                    render_callout("Phương án đã tối ưu với cấu hình hiện tại, không có tiêu chí hay GV nào tập trung vi phạm.",
                                   level="success", title="Không có nút thắt")
                for b in bottlenecks:
                    label, status = kind_badge[b.kind]
                    with st.container(border=True):
                        st.markdown(f"{render_status_badge(label, status)} **{b.title}**", unsafe_allow_html=True)
                        st.caption(b.evidence)
                        st.markdown(f"👉 {b.action}")
                        if b.kind in ("capacity", "rule", "teacher"):
                            st.page_link("pages/10_Cau_hinh_Xep_lich.py", label="Mở Cấu hình xếp lịch", icon="⚙️")
```
Import `render_status_badge`, `render_callout` from `ui_theme` if not already imported. `st.page_link` inside a loop needs no key in 1.62; if Streamlit complains about duplicate elements, render one link after the loop instead.

- [ ] **Step 2: Manual verification:** on a real run, panel lists ≤5 items, ranked; a run that relaxed II.3 shows the "Sáng Thứ N không đủ chỗ" item first with numbers; a time-limited run (set extra time aside, time limit 10s in config) shows the "Bộ giải dừng khi chưa chắc chắn tối ưu" item with a percentage.
- [ ] **Step 3:** `git commit -am "feat(xep-tkb): bottleneck panel explaining why the timetable is not better"`

---

### Task 8: Page — coloured class grid + exception-only QA

**Files:**
- Modify: `pages/06_Xep_TKB.py` (studio tab_cls ~line 268-290; QA ~lines 1608-1645)

- [ ] **Step 1: Coloured grid.** In `_render_interactive_timetable_studio`, tab_cls: add `role_of = {s.subject_id: s.role_code for s in subjects}` next to `subj_map`. Build a parallel `styles` list alongside `rows`:

```python
        rows, styles = [], []
        for sess in sessions_to_show:
            sess_name = "Sáng" if sess == "S" else "Chiều"
            for per in range(1, 6):
                row = {"Buổi": sess_name, "Tiết": per}
                style_row = {"Buổi": "", "Tiết": ""}
                has_any = False
                for wd in WEEKDAYS:
                    sid = cells.get((chosen_cls.class_id, wd, sess, per))
                    if sid and sid > 0:
                        s_name = subj_map.get(sid, f"Môn #{sid}")
                        tid = assignments.get((sid, chosen_cls.class_id))
                        t_name = teach_map.get(tid, "")
                        row[WEEKDAY_NAMES[wd]] = f"{s_name} ({t_name})" if t_name else s_name
                        style_row[WEEKDAY_NAMES[wd]] = role_cell_css(role_of.get(sid))
                        has_any = True
                    else:
                        row[WEEKDAY_NAMES[wd]] = "—"
                        style_row[WEEKDAY_NAMES[wd]] = role_cell_css(None)
                if has_any or sess == "S" or a_count > 0:
                    rows.append(row)
                    styles.append(style_row)

        df_cls = pd.DataFrame(rows)
        css = pd.DataFrame(styles, index=df_cls.index, columns=df_cls.columns)
        st.dataframe(df_cls.style.apply(lambda _: css, axis=None), hide_index=True, width="stretch")
        st.caption("🟦 Môn nặng • 🟧 GDTC • 🟩 HĐTN/Chào cờ/SHL • 🟪 Môn kép/Nghệ thuật • ⬜ Môn thường")
```
Import `role_cell_css` from `ui_theme`. (Spec wants GV on a second line — `st.dataframe` cannot render line breaks; kept `Môn (GV)`. Revisit only if users ask.)

- [ ] **Step 2: Exception-only QA.** Quota block: replace the `if non_zero_diffs == 0:` expander with
`render_callout(f"Khớp 100% định mức số tiết chuẩn của Tuần {scheduled_week}.", level="success", title="Định mức")`.
Violations: before the `_render_rule_violations(...)` call add
`if not violations_curr: render_callout("Thời khóa biểu tuân thủ 100% quy chuẩn sư phạm.", level="success", title="Kiểm định HĐSP")`.

- [ ] **Step 3: Manual verification:** grid colours visible in light and dark Streamlit theme (text stays readable because colour is set explicitly); quota/violation sections collapse to one green callout on a clean run.
- [ ] **Step 4:** `git commit -am "feat(xep-tkb): role-coloured class grid and exception-only QA reports"`

---

### Task 9: Export Studio views — 1 sheet per class, 1 sheet per teacher

The existing `export_xlsx` (template-based, all classes stacked in one long `TKB` sheet) stays untouched. Two new **pure** functions take exactly the data the Studio renders (`cells`, `classes`, `subjects`, `teachers`, `assignments`), so the file always matches what the user sees — including the fresh, not-yet-saved candidate and its effective (substitute-aware) teacher map.

**Files:**
- Modify: `io_excel/exporter.py` (append; extend the `openpyxl.styles` import)
- Modify: `pages/06_Xep_TKB.py` (`_render_interactive_timetable_studio`, both call sites)
- Test: `tests/test_exporter_sheets.py` (create)

**Interfaces:**
- Produces:
  - `export_class_sheets_xlsx(cells: dict, classes: list, subjects: list, teachers: list, assignments: dict, title_suffix: str = "") -> bytes`
  - `export_teacher_sheets_xlsx(cells: dict, classes: list, subjects: list, teachers: list, assignments: dict, title_suffix: str = "") -> bytes`
  - `cells`: `(class_id, weekday, session, period) -> subject_id | None`; `assignments`: `(subject_id, class_id) -> teacher_id`.
- Sheet layout (both): row 1 title (merged), row 2 header `Buổi | Tiết | Thứ 2 … Thứ 7`, then Sáng tiết 1–5 and, only if that class/teacher has any afternoon period, Chiều tiết 1–5. Freeze panes at `C3`. Class cell = `"Môn\nGV"` (wrapped); teacher cell = `"Lớp (Môn)"`, comma-joined if > 1 (would be a conflict, shown as-is).
- Teachers with zero periods get no sheet. Empty input still yields a valid workbook with one sheet "Trống".

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_exporter_sheets.py
import io

import openpyxl
from core.models import ROLE_THUONG, ClassRoom, Subject, Teacher
from io_excel.exporter import export_class_sheets_xlsx, export_teacher_sheets_xlsx

CLASSES = [ClassRoom(2, "6/2", 2), ClassRoom(1, "6A1", 1)]
SUBJECTS = [Subject(1, "Toán", ROLE_THUONG), Subject(2, "Văn", ROLE_THUONG)]
TEACHERS = [Teacher(10, "Nguyễn Thị Hà"), Teacher(11, "Nguyễn Thị Hà"), Teacher(12, "GV Không Dạy")]
ASSIGN = {(1, 1): 10, (2, 1): 11, (1, 2): 10}
CELLS = {(1, 2, "S", 1): 1, (1, 2, "S", 2): 2, (2, 3, "C", 2): 1, (2, 2, "S", 1): None}


def _load(data):
    return openpyxl.load_workbook(io.BytesIO(data))


def test_class_workbook_one_sheet_per_class_in_order():
    wb = _load(export_class_sheets_xlsx(CELLS, CLASSES, SUBJECTS, TEACHERS, ASSIGN, title_suffix=" — Tuần 6"))
    assert wb.sheetnames == ["6A1", "6-2"]            # sort_order, "/" sanitised
    ws = wb["6A1"]
    assert ws["A1"].value == "Thời khóa biểu lớp 6A1 — Tuần 6"
    assert [c.value for c in ws[2]][:3] == ["Buổi", "Tiết", "Thứ 2"]
    assert ws["C3"].value == "Toán\nNguyễn Thị Hà"     # Thứ 2, Sáng, tiết 1
    assert ws.max_row == 2 + 5                          # 6A1 has no afternoon -> morning rows only
    assert wb["6-2"].max_row == 2 + 10                  # 6/2 has an afternoon period


def test_teacher_workbook_dedupes_names_and_skips_idle():
    wb = _load(export_teacher_sheets_xlsx(CELLS, CLASSES, SUBJECTS, TEACHERS, ASSIGN))
    assert sorted(wb.sheetnames) == ["Nguyễn Thị Hà", "Nguyễn Thị Hà (2)"]
    texts = {c.value for ws in wb for row in ws.iter_rows() for c in row if c.value}
    assert {"6A1 (Toán)", "6/2 (Toán)", "6A1 (Văn)"} <= texts


def test_sheet_name_truncated_to_31():
    wb = _load(export_class_sheets_xlsx({(1, 2, "S", 1): 1}, [ClassRoom(1, "L" * 40, 1)], SUBJECTS, TEACHERS, {(1, 1): 10}))
    assert len(wb.sheetnames[0]) == 31


def test_empty_input_still_valid_workbook():
    assert _load(export_teacher_sheets_xlsx({}, [], SUBJECTS, [], {})).sheetnames == ["Trống"]
```

- [ ] **Step 2:** `pytest tests/test_exporter_sheets.py -v -n0` → FAIL `ImportError`.

- [ ] **Step 3: Implement** — change the styles import to `from openpyxl.styles import Alignment, Border, Font, PatternFill, Side` and append:

```python
_THIN = Side(style="thin", color="CBD5E1")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADER_FILL = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
_BAD_SHEET_CHARS = str.maketrans({c: "-" for c in "[]:*?/\\"})


def _safe_sheet_name(name, used: set) -> str:
    """Tên sheet hợp lệ cho Excel: <= 31 ký tự, không chứa []:*?/\\, không trùng (không phân biệt hoa thường)."""
    base = (str(name).translate(_BAD_SHEET_CHARS).strip() or "Sheet")[:31]
    candidate, n = base, 2
    while candidate.lower() in used:
        suffix = f" ({n})"
        candidate = base[:31 - len(suffix)] + suffix
        n += 1
    used.add(candidate.lower())
    return candidate


def _write_grid_sheet(ws, title: str, grid: dict) -> None:
    """grid: (weekday, session, period) -> text. Bảng Buổi/Tiết x Thứ giống Studio trang Xếp TKB."""
    headers = ["Buổi", "Tiết"] + [WEEKDAY_NAMES[wd] for wd in WEEKDAYS]
    sessions = ["S", "C"] if any(sess == "C" for (_wd, sess, _p) in grid) else ["S"]
    for col, h in enumerate(headers, 1):
        c = ws.cell(2, col, h)
        c.font, c.fill, c.border = Font(bold=True), _HEADER_FILL, _BORDER
        c.alignment = Alignment(horizontal="center")
    row = 3
    for sess in sessions:
        for per in range(1, frame_mod.MAX_PERIODS_PER_SESSION + 1):
            values = ["Sáng" if sess == "S" else "Chiều", per] + [grid.get((wd, sess, per), "") for wd in WEEKDAYS]
            for col, v in enumerate(values, 1):
                c = ws.cell(row, col, v)
                c.border = _BORDER
                c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
            row += 1
    _autofit_sheet(ws)  # trước khi ghi tiêu đề, để tiêu đề dài không kéo rộng cột A
    ws.cell(1, 1, title).font = Font(bold=True, size=13)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.freeze_panes = "C3"


def _grid_workbook(sheets: list) -> bytes:
    """sheets: [(tên sheet thô, tiêu đề, grid)]."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    used: set = set()
    for name, title, grid in sheets:
        _write_grid_sheet(wb.create_sheet(_safe_sheet_name(name, used)), title, grid)
    if not wb.sheetnames:
        wb.create_sheet("Trống")
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def export_class_sheets_xlsx(cells, classes, subjects, teachers, assignments, title_suffix: str = "") -> bytes:
    """Mỗi lớp 1 sheet, ô = 'Môn\\nGV' (giống tab 'Xem theo lớp' ở Studio)."""
    subj = {s.subject_id: s.name for s in subjects}
    tname = {t.teacher_id: t.name for t in teachers}
    grids = defaultdict(dict)
    for (cid, wd, sess, per), sid in cells.items():
        if sid and sid > 0:
            t = tname.get(assignments.get((sid, cid)), "")
            grids[cid][(wd, sess, per)] = f"{subj.get(sid, sid)}\n{t}" if t else str(subj.get(sid, sid))
    ordered = sorted(classes, key=lambda c: (c.sort_order, c.name))
    return _grid_workbook([(c.name, f"Thời khóa biểu lớp {c.name}{title_suffix}", grids[c.class_id]) for c in ordered])


def export_teacher_sheets_xlsx(cells, classes, subjects, teachers, assignments, title_suffix: str = "") -> bytes:
    """Mỗi GV có tiết dạy 1 sheet, ô = 'Lớp (Môn)' (giống tab 'Tra cứu giáo viên' ở Studio)."""
    subj = {s.subject_id: s.name for s in subjects}
    cname = {c.class_id: c.name for c in classes}
    per_teacher = defaultdict(lambda: defaultdict(list))
    for (cid, wd, sess, per), sid in cells.items():
        tid = assignments.get((sid, cid)) if sid and sid > 0 else None
        if tid is not None and tid > 0:
            per_teacher[tid][(wd, sess, per)].append(f"{cname.get(cid, cid)} ({subj.get(sid, sid)})")
    sheets = []
    for t in sorted(teachers, key=lambda t: t.name):
        slots = per_teacher.get(t.teacher_id)
        if slots:
            total = sum(len(v) for v in slots.values())
            sheets.append((t.name, f"TKB giáo viên {t.name}{title_suffix} — {total} tiết",
                           {k: ", ".join(v) for k, v in slots.items()}))
    return _grid_workbook(sheets)
```

- [ ] **Step 4:** `pytest tests/test_exporter_sheets.py tests/test_exporter.py -q -n0` → all PASS (old export untouched).

- [ ] **Step 5: Page buttons.** Add `file_tag: str = ""` as the last parameter of `_render_interactive_timetable_studio`. Right under its `st.caption(...)` (above `st.tabs`):

```python
    from functools import partial
    from io_excel.exporter import export_class_sheets_xlsx, export_teacher_sheets_xlsx

    xl_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    suffix = f" — {file_tag.replace('_', ' ')}" if file_tag else ""
    export_args = (cells, classes, subjects, teachers, assignments)
    col_x1, col_x2, _ = st.columns([1, 1, 2])
    col_x1.download_button(
        "📗 Xuất TKB lớp (mỗi lớp 1 sheet)",
        data=partial(export_class_sheets_xlsx, *export_args, title_suffix=suffix),
        file_name=f"TKB_Lop_{file_tag or 'hien_tai'}.xlsx", mime=xl_mime,
        key=f"{key_prefix}dl_class_sheets", on_click="ignore", width="stretch",
    )
    col_x2.download_button(
        "📘 Xuất TKB giáo viên (mỗi GV 1 sheet)",
        data=partial(export_teacher_sheets_xlsx, *export_args, title_suffix=suffix),
        file_name=f"TKB_GiaoVien_{file_tag or 'hien_tai'}.xlsx", mime=xl_mime,
        key=f"{key_prefix}dl_teacher_sheets", on_click="ignore", width="stretch",
    )
```
`data` is a callable (supported by the installed Streamlit 1.62 `DownloadButtonDataType`), so the workbooks are built only on click, not on every rerun. `on_click="ignore"` avoids a full page rerun on download.

Call sites: fresh result (~line 1597) pass `file_tag=f"Tuan_{scheduled_week}_PA{st.session_state.get('active_candidate_id')}"`; `_render_saved_tkb` gets a `file_tag: str = ""` parameter forwarded to the studio. Its two callers: ~line 1741 pass `file_tag=f"Tuan_{chosen_week}"`; ~line 2125 (history tab) pass `file_tag=f"Tuan_{selected_view_week}"` — confirm that variable name by reading 10 lines above the call.

- [ ] **Step 6: Manual verification:** on a fresh result, both buttons download; open in Excel — every class has its own sheet in class order, grid matches the "Xem theo lớp" tab cell by cell for 2 sampled classes; teacher file matches the "Tra cứu giáo viên" tab for 2 sampled teachers (including one with a substitute assignment); file opens without Excel repair prompt. Repeat once from the saved-week history tab.
- [ ] **Step 7:** `git add io_excel/exporter.py tests/test_exporter_sheets.py pages/06_Xep_TKB.py && git commit -m "feat(export): per-class and per-teacher sheet workbooks from the Studio view"`

---

### Task 10: Delete the disabled batch-scheduling block

**Files:**
- Modify: `pages/06_Xep_TKB.py` — the `with st.expander("📅 Xếp nhiều tuần cùng lúc (tạm thời tắt)", ...)` block (~line 1753 to just before the `tab_history` section, ~line 2066).

- [ ] **Step 1:** Grep for every name defined only inside that block (`batch_results`, `batch_week_nos`, `batch_sched_config`, `_batch_highlight_nonzero`, `b_*`) and confirm no use outside it: `grep -n "batch_" pages/06_Xep_TKB.py`.
- [ ] **Step 2:** Delete the block. Remove imports that become unused (check with `python -m pyflakes pages/06_Xep_TKB.py` if available, else grep each import name).
- [ ] **Step 3:** `python -c "import ast,sys; ast.parse(open('pages/06_Xep_TKB.py',encoding='utf-8').read())"` and load the page once in the browser.
- [ ] **Step 4:** `git commit -am "refactor(xep-tkb): remove disabled multi-week batch scheduling block"`

---

### Task 11: Full verification

- [ ] **Step 1:** `pytest -q` → same or better than Task 0 baseline; zero new failures.
- [ ] **Step 2:** `node .gitnexus/run.cjs detect-changes --scope all --repo .` — confirm only the files in the File Structure table changed; re-run if `partial`/`truncated`.
- [ ] **Step 3:** Re-run the manual checklists of Tasks 6–9 in one session on a real school DB.
- [ ] **Step 4:** Hand off with superpowers:finishing-a-development-branch.
