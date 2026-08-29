# GV nghỉ riêng: override số buổi + ghim buổi nghỉ cụ thể Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any teacher be given more days off than the school-wide default — an override on the weekly off-session count, plus an optional full day off and an optional fixed afternoon off — so a school can accommodate a teacher's real situation (illness, reduced capacity) without changing the rule for everyone else.

**Architecture:** 3 new nullable `Teacher` fields ride the existing per-teacher SQLite row (`teachers` table), added via the established `_ensure_column` migration helper. `_assign_off_slots()` in `core/scheduler.py` reads these 3 fields per teacher: pinned cells are guaranteed off first (a full-day pin is the one deliberate exception to the "never a full day off" invariant), then the remaining slots (count = the override if set, else the school-wide default) are chosen at random exactly as before. A conflicting pin (against `forbidden_off_cells` or `must_monday`) is validated and rejected in the UI before save, never silently accepted.

**Tech Stack:** Python 3, Streamlit, SQLite (stdlib `sqlite3`), pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-rang-buoc-xep-lich-v2-design.md` (mục "Kiến trúc" → "2. Yêu cầu #3")

## Global Constraints

- No behavior change for any teacher who doesn't have these 3 fields set — `off_sessions_override=None`, `pinned_full_day_off=None`, `pinned_afternoon_off=None` (all 3 columns default `NULL`) must reproduce `_assign_off_slots`'s current output exactly.
- A full-day pin (`pinned_full_day_off`) is the **only** sanctioned exception to "a teacher never gets both sessions of the same day off" — it must never leak into the random-selection fallback for teachers without this field set.
- A pin that conflicts with `forbidden_off_cells` or `must_monday`/Thứ 2 must never be silently honored by the scheduler — it is dropped in `_assign_off_slots` (defense in depth) **and** rejected up front by UI validation before the row is ever saved.
- This feature applies to **any** teacher, selected by the school through the UI — do not hardcode any teacher name/id anywhere in `core/`, `data/`, or `pages/`.
- No changes to any `sched.run(inp)` call site signature; `_assign_off_slots`'s existing `off_slot_count`/`forbidden_off_cells` parameters keep their current meaning for teachers without an override.
- All existing tests in `tests/test_scheduler.py`, `tests/test_models.py`, `tests/test_repository.py` must keep passing unmodified.

---

## Task 1: `Teacher` gets 3 new optional fields

**Files:**
- Modify: `core/models.py:41-48` (`Teacher` — append 3 fields after `cap`)
- Test: `tests/test_models.py` (extend existing file)

**Interfaces:**
- Produces: `Teacher.off_sessions_override: Optional[int] = None`, `Teacher.pinned_full_day_off: Optional[int] = None`, `Teacher.pinned_afternoon_off: Optional[int] = None`.

- [ ] **Step 1: Write the failing test**

In `tests/test_models.py`, add `Teacher` to the import and add 2 new tests:

```python
from core.models import SchedulingConfig, SchedulingInput, Teacher
```

```python
def test_teacher_defaults_have_no_off_override_or_pins():
    t = Teacher(1, "GV1")
    assert t.off_sessions_override is None
    assert t.pinned_full_day_off is None
    assert t.pinned_afternoon_off is None


def test_teacher_accepts_off_override_and_pins():
    t = Teacher(1, "GV1", off_sessions_override=3, pinned_full_day_off=5, pinned_afternoon_off=3)
    assert t.off_sessions_override == 3
    assert t.pinned_full_day_off == 5
    assert t.pinned_afternoon_off == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — `test_teacher_defaults_have_no_off_override_or_pins` fails with `AttributeError: 'Teacher' object has no attribute 'off_sessions_override'`; `test_teacher_accepts_off_override_and_pins` fails with `TypeError: __init__() got an unexpected keyword argument 'off_sessions_override'`.

- [ ] **Step 3: Add the 3 fields**

In `core/models.py`, append to the end of `Teacher` (currently ending at line 48 with `cap: int = 19`):

```python
@dataclass
class Teacher:
    teacher_id: int
    name: str
    role: str = ""              # '', 'GVCN', 'Tổ trưởng', 'Tổ phó', 'Tổng phụ trách'
    must_monday: bool = False
    is_gvcn: bool = False
    cap: int = 19               # computed: 19 - role reduction
    off_sessions_override: Optional[int] = None    # None = dùng config.teacher_off_sessions_per_week chung
    pinned_full_day_off: Optional[int] = None      # thứ (2-7) ghim nghỉ TRỌN NGÀY -- ngoại lệ "không nghỉ trọn ngày"
    pinned_afternoon_off: Optional[int] = None     # thứ ghim nghỉ 1 buổi CHIỀU cố định
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: add per-teacher off-session override and pinned-off-day fields to Teacher"
```

---

## Task 2: Migration + persistence (`data/db.py`, `data/repository.py`)

**Files:**
- Modify: `data/db.py:143-149` (`init_db` — 3 new `_ensure_column` calls)
- Modify: `data/repository.py:78-100` (`list_teachers`, `upsert_teacher`)
- Test: `tests/test_repository.py` (extend existing file)

**Interfaces:**
- Consumes: `Teacher` (Task 1)
- Produces: `list_teachers(conn)` now returns `Teacher` objects with the 3 new fields populated from the DB; `upsert_teacher(conn, ..., off_sessions_override=None, pinned_full_day_off=None, pinned_afternoon_off=None)` — 3 new trailing keyword-only-by-convention params, all optional, existing call sites unaffected.

- [ ] **Step 1: Write the failing test**

In `tests/test_repository.py`, add:

```python
def test_upsert_and_list_teacher_round_trips_off_override_and_pins(conn):
    tid = repo.upsert_teacher(
        conn, "GV The duc", role="", must_monday=False, is_gvcn=False,
        off_sessions_override=3, pinned_full_day_off=5, pinned_afternoon_off=3,
    )
    teachers = {t.teacher_id: t for t in repo.list_teachers(conn)}
    t = teachers[tid]
    assert t.off_sessions_override == 3
    assert t.pinned_full_day_off == 5
    assert t.pinned_afternoon_off == 3


def test_teacher_off_override_and_pins_default_to_none(conn):
    tid = repo.upsert_teacher(conn, "GV Thuong")
    teachers = {t.teacher_id: t for t in repo.list_teachers(conn)}
    t = teachers[tid]
    assert t.off_sessions_override is None
    assert t.pinned_full_day_off is None
    assert t.pinned_afternoon_off is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_repository.py -v`
Expected: FAIL — `test_upsert_and_list_teacher_round_trips_off_override_and_pins` fails with `TypeError: upsert_teacher() got an unexpected keyword argument 'off_sessions_override'`.

- [ ] **Step 3: Add migration + persistence**

In `data/db.py`, add to `init_db` (currently lines 143-149), after the existing `_ensure_column` calls and before the `tuan_config` insert:

```python
def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _ensure_column(conn, "frame_template", "allow_saturday", "allow_saturday INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "frame_template", "short_weekday", "short_weekday INTEGER")
    _ensure_column(conn, "frame_template", "short_morning_periods", "short_morning_periods INTEGER")
    _ensure_column(conn, "frame_template", "short_afternoon_periods", "short_afternoon_periods INTEGER")
    _ensure_column(conn, "teachers", "off_sessions_override", "off_sessions_override INTEGER")
    _ensure_column(conn, "teachers", "pinned_full_day_off", "pinned_full_day_off INTEGER")
    _ensure_column(conn, "teachers", "pinned_afternoon_off", "pinned_afternoon_off INTEGER")
    conn.execute("INSERT OR IGNORE INTO tuan_config (id, seed, parity) VALUES (1, 0, 'C')")
```

In `data/repository.py`, change `list_teachers` (currently lines 78-83):

```python
def list_teachers(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT teacher_id, name, role, must_monday, is_gvcn, "
        "off_sessions_override, pinned_full_day_off, pinned_afternoon_off FROM teachers ORDER BY name"
    ).fetchall()
    return [Teacher(
        r["teacher_id"], r["name"], r["role"], bool(r["must_monday"]), bool(r["is_gvcn"]),
        off_sessions_override=r["off_sessions_override"],
        pinned_full_day_off=r["pinned_full_day_off"],
        pinned_afternoon_off=r["pinned_afternoon_off"],
    ) for r in rows]
```

Change `upsert_teacher` (currently lines 86-100):

```python
def upsert_teacher(conn: sqlite3.Connection, name: str, role: str = "", must_monday: bool = False,
                    is_gvcn: bool = False, teacher_id=None,
                    off_sessions_override=None, pinned_full_day_off=None, pinned_afternoon_off=None) -> int:
    if teacher_id is not None:
        conn.execute(
            "UPDATE teachers SET name=?, role=?, must_monday=?, is_gvcn=?, "
            "off_sessions_override=?, pinned_full_day_off=?, pinned_afternoon_off=? WHERE teacher_id=?",
            (name, role, int(must_monday), int(is_gvcn),
             off_sessions_override, pinned_full_day_off, pinned_afternoon_off, teacher_id),
        )
        conn.commit()
        return teacher_id
    cur = conn.execute(
        "INSERT INTO teachers (name, role, must_monday, is_gvcn, "
        "off_sessions_override, pinned_full_day_off, pinned_afternoon_off) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, role, int(must_monday), int(is_gvcn),
         off_sessions_override, pinned_full_day_off, pinned_afternoon_off),
    )
    conn.commit()
    return cur.lastrowid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_repository.py -v`
Expected: PASS (all tests)

Also run the full suite once to confirm no existing caller of `upsert_teacher` (e.g. `io_excel/importer.py`, `scripts/build_fixture.py`) broke — they all call it positionally with only the original 5 params, which the 3 new trailing keyword defaults leave untouched:

Run: `python -m pytest -v`
Expected: PASS (entire suite)

- [ ] **Step 5: Commit**

```bash
git add data/db.py data/repository.py tests/test_repository.py
git commit -m "feat: persist per-teacher off-session override and pinned-off-day fields"
```

---

## Task 3: `_assign_off_slots` honors the override and pins

**Files:**
- Modify: `core/scheduler.py:299-346` (`_assign_off_slots`)
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `Teacher.off_sessions_override`/`pinned_full_day_off`/`pinned_afternoon_off` (Task 1)
- Produces: `_assign_off_slots(...)` — unchanged signature; per-teacher behavior now honors the 3 new fields when present.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler.py`, near `test_off_slots_respect_forbidden_cells_gvcn_and_must_monday`:

```python
def test_teacher_pinned_full_day_off():
    rng = random.Random(1)
    teachers_by_id = {1: Teacher(1, "GV The duc", pinned_full_day_off=4)}
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
        assert (4, "S") in offs[1]
        assert (4, "C") in offs[1]


def test_teacher_pinned_afternoon_off():
    rng = random.Random(1)
    teachers_by_id = {1: Teacher(1, "GV Thuong", pinned_afternoon_off=3)}
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
        assert (3, "C") in offs[1]


def test_teacher_off_sessions_override():
    rng = random.Random(1)
    teachers_by_id = {
        1: Teacher(1, "GV The duc", off_sessions_override=3),
        2: Teacher(2, "GV Thuong"),
    }
    for _ in range(50):
        offs = sched._assign_off_slots({1, 2}, teachers_by_id, rng, off_slot_count=1)
        assert len(offs[1]) == 3
        assert len(offs[2]) == 1


def test_teacher_pinned_full_day_and_extra_afternoon_off():
    # Yêu cầu #3 thật: 1 ngày nghỉ trọn + 1 buổi chiều cố định khác ngày = 3 buổi nghỉ/tuần.
    rng = random.Random(1)
    teachers_by_id = {
        1: Teacher(1, "GV The duc", off_sessions_override=3, pinned_full_day_off=4, pinned_afternoon_off=3),
    }
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
        assert len(offs[1]) == 3
        assert (4, "S") in offs[1]
        assert (4, "C") in offs[1]
        assert (3, "C") in offs[1]


def test_pinned_off_conflicts_with_forbidden_are_dropped():
    # Thứ 6 nằm trọn trong FORBIDDEN_OFF_CELLS mặc định (sáng VÀ chiều) -> pin bị bỏ qua,
    # GV vẫn nhận đủ off_slot_count buổi nghỉ ngẫu nhiên như GV thường (không crash, không kẹt).
    rng = random.Random(1)
    teachers_by_id = {1: Teacher(1, "GV", pinned_full_day_off=6)}
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
        assert (6, "S") not in offs[1]
        assert (6, "C") not in offs[1]
        assert len(offs[1]) == 1


def test_off_slots_unchanged_when_no_override_or_pins():
    # Regression: GV không có 3 field mới -> hành vi y hệt trước khi có tính năng này.
    rng = random.Random(1)
    teachers_by_id = {1: Teacher(1, "Normal", cap=19)}
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
        assert len(offs[1]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -k "pinned_full_day_off or pinned_afternoon_off or off_sessions_override or pinned_full_day_and_extra" -v`
Expected: FAIL — `_assign_off_slots` doesn't read the 3 new `Teacher` fields yet, so `test_teacher_pinned_full_day_off`, `test_teacher_pinned_afternoon_off`, `test_teacher_off_sessions_override`, and `test_teacher_pinned_full_day_and_extra_afternoon_off` all fail their assertions (pins never appear; override count is ignored, teacher 1 gets `len(offs[1]) == 1` instead of `3`). `test_pinned_off_conflicts_with_forbidden_are_dropped` and `test_off_slots_unchanged_when_no_override_or_pins` already PASS at this point — expected, they're regression guards for after the change, not RED tests now.

- [ ] **Step 3: Implement**

In `core/scheduler.py`, replace `_assign_off_slots` (currently lines 299-346) with:

```python
def _assign_off_slots(teacher_ids: set, teachers_by_id: dict, rng: random.Random,
                       gvcn_shl_cell: Optional[dict] = None,
                       off_slot_count: int = 1,
                       forbidden_off_cells: frozenset = FORBIDDEN_OFF_CELLS) -> dict:
    """Pick each teacher's off-slot(s) for the week: off_slot_count (weekday, session)
    pairs, each on a DIFFERENT weekday when possible (never 2 off-sessions on the
    same day, i.e. never a full day off), drawn from every cell except
    FORBIDDEN_OFF_CELLS (plus the teacher's own must_monday/is_gvcn exclusions).

    off_slot_count defaults to 1 (a single half-day off/week), and run() always
    calls this with the default -- every teacher gets exactly 1 buổi nghỉ/tuần,
    regardless of whether the school runs a 1- or 2-buổi/ngày model.

    A teacher's own off_sessions_override/pinned_full_day_off/pinned_afternoon_off
    (yêu cầu #3, spec 2026-08-29) override this per teacher: pinned cells are
    guaranteed off first (a full-day pin is the one sanctioned exception to "never
    a full day off"), and the remaining off_sessions_override - len(pinned) slots
    are chosen at random exactly as for any other teacher. A pin that conflicts
    with forbidden_off_cells/must_monday is dropped silently here (defense in
    depth) -- the UI must validate this before ever saving such a pin.

    gvcn_shl_cell: teacher_id -> (weekday, session), the cell holding sinh hoạt lớp
    (tiết cuối buổi sáng: Thứ 6 khi lớp học 2 buổi/ngày, Thứ 7 khi 1 buổi/ngày) for
    that GVCN's own homeroom class -- only that one (weekday, session) is barred,
    not the whole day. Defaults to (7, "C") when unknown, e.g. in isolated tests.
    """
    gvcn_shl_cell = gvcn_shl_cell or {}
    gv_off_slots = {}
    for tid in teacher_ids:
        t = teachers_by_id.get(tid)
        must_monday = t.must_monday if t else False
        is_gvcn = t.is_gvcn if t else False
        forbidden = set(forbidden_off_cells)
        if must_monday:
            forbidden.add((2, "C"))
        if is_gvcn:
            forbidden.add(gvcn_shl_cell.get(tid, (7, "C")))

        pinned_cells = set()
        pinned_weekdays = set()
        if t and t.pinned_full_day_off is not None:
            wd = t.pinned_full_day_off
            if (wd, "S") not in forbidden and (wd, "C") not in forbidden:
                pinned_cells |= {(wd, "S"), (wd, "C")}
                pinned_weekdays.add(wd)
        if t and t.pinned_afternoon_off is not None:
            wd = t.pinned_afternoon_off
            if (wd, "C") not in forbidden and wd not in pinned_weekdays:
                pinned_cells.add((wd, "C"))
                pinned_weekdays.add(wd)

        effective_count = t.off_sessions_override if (t and t.off_sessions_override is not None) else off_slot_count
        remaining_count = max(0, effective_count - len(pinned_cells))

        by_weekday = defaultdict(list)
        for wd in (2, 3, 4, 5, 6, 7):
            if wd in pinned_weekdays:
                continue
            for session in ("S", "C"):
                if (wd, session) not in forbidden:
                    by_weekday[wd].append(session)
        eligible_weekdays = [wd for wd, sessions in by_weekday.items() if sessions]

        if len(eligible_weekdays) >= remaining_count:
            chosen_weekdays = rng.sample(eligible_weekdays, remaining_count)
            gv_off_slots[tid] = pinned_cells | {(wd, rng.choice(by_weekday[wd])) for wd in chosen_weekdays}
        else:
            # not enough distinct eligible days -- take as many off-cells as
            # possible instead of leaving remaining_count unmet (may repeat a
            # weekday with both sessions as a last resort).
            all_eligible_cells = [(wd, s) for wd in eligible_weekdays for s in by_weekday[wd]]
            picks = rng.sample(all_eligible_cells, min(remaining_count, len(all_eligible_cells)))
            gv_off_slots[tid] = pinned_cells | set(picks)
    return gv_off_slots
```

(This is the same function, with `pinned_cells`/`pinned_weekdays` computed up front, `effective_count`/`remaining_count` replacing the raw `off_slot_count` for the random-selection portion, `by_weekday` skipping any already-pinned weekday, and every `gv_off_slots[tid] = ...` assignment now unioned with `pinned_cells`. A teacher with no pins/override produces `pinned_cells = set()`, `remaining_count == off_slot_count`, and a `by_weekday` identical to before — byte-for-byte the same output.)

- [ ] **Step 4: Run tests to verify everything passes**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: PASS — the 6 new tests plus the entire pre-existing suite, including `test_off_slots_respect_forbidden_cells_gvcn_and_must_monday` and `test_off_slot_count_defaults_to_1_buoi_per_week` (teachers there have no pins/override, so behavior is unchanged).

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: honor per-teacher off-session override and pinned off-days in _assign_off_slots"
```

---

## Task 4: UI — Khai báo page, "Giáo viên" tab

**Files:**
- Modify: `pages/01_Khai_bao.py:1-98` (imports, `tab_teachers` block)

**Interfaces:**
- Consumes: `repo.get_scheduling_config` (existing), `repo.list_teachers`/`upsert_teacher` (Task 2), `core.models.WEEKDAY_NAMES`/`WEEKDAYS` (existing)

No automated test — this is a Streamlit UI file, matching this repo's existing convention (pages have no dedicated test files). Verify manually in Step 3.

**Validation design note:** the plan validates **all** edited rows before saving **any** of them (abort-on-any-error, not skip-just-that-row). A per-row skip risks silently deleting an existing teacher whose only problem is an invalid pin (they'd be missing from `kept_ids` and hit the delete branch) — validate-then-commit-atomically avoids that failure mode entirely.

- [ ] **Step 1: Add the import and fetch `config`**

In `pages/01_Khai_bao.py`, change the import block (currently lines 4-6):

```python
import pandas as pd
import streamlit as st

from core.models import WEEKDAY_NAMES, WEEKDAYS
from data import repository as repo
from ui_common import ROLE_CODE_LABELS, ROLE_LABEL_TO_CODE, get_conn, require_auth, require_school, \
    sidebar_backup_export, sidebar_fixed_rules, sidebar_school_switcher
```

Add, right after the existing `conn = get_conn(school_slug)` (currently line 10):

```python
config = repo.get_scheduling_config(conn)
```

- [ ] **Step 2: Rewrite the `tab_teachers` block**

Replace the entire `with tab_teachers:` block (currently lines 68-98) with:

```python
with tab_teachers:
    teachers = repo.list_teachers(conn)
    role_options = ["", "GVCN", "Tổ trưởng", "Tổ phó", "Phó hiệu trưởng", "Tổng phụ trách"]
    weekday_pin_options = [""] + [WEEKDAY_NAMES[wd] for wd in WEEKDAYS]
    df = pd.DataFrame([{
        "teacher_id": t.teacher_id, "Tên GV": t.name, "Chức vụ": t.role,
        "Đi T2": t.must_monday, "GVCN": t.is_gvcn,
        "Nghỉ mấy buổi/tuần": t.off_sessions_override,
        "Nghỉ trọn ngày - Thứ": WEEKDAY_NAMES.get(t.pinned_full_day_off, ""),
        "Nghỉ chiều cố định - Thứ": WEEKDAY_NAMES.get(t.pinned_afternoon_off, ""),
    } for t in teachers])
    edited = st.data_editor(
        df, num_rows="dynamic", key="editor_teachers", hide_index=True,
        column_config={
            "teacher_id": None,
            "Chức vụ": st.column_config.SelectboxColumn(options=role_options),
            "Nghỉ mấy buổi/tuần": st.column_config.NumberColumn(
                min_value=0, max_value=3, step=1, help="Bỏ trống = dùng mặc định chung của trường",
            ),
            "Nghỉ trọn ngày - Thứ": st.column_config.SelectboxColumn(
                options=weekday_pin_options,
                help="Ghim nghỉ CẢ NGÀY -- ngoại lệ so với quy tắc chung \"không nghỉ trọn ngày\"",
            ),
            "Nghỉ chiều cố định - Thứ": st.column_config.SelectboxColumn(options=weekday_pin_options),
        },
    )
    if st.button("Lưu danh sách giáo viên"):
        weekday_name_to_num = {WEEKDAY_NAMES[wd]: wd for wd in WEEKDAYS}
        errors = []
        to_save = []
        for _, row in edited.iterrows():
            name = str(row["Tên GV"] or "").strip()
            if not name:
                continue
            tid = row.get("teacher_id")
            tid = int(tid) if pd.notna(tid) else None
            must_monday = bool(row["Đi T2"])
            is_gvcn = bool(row["GVCN"])
            off_override = row.get("Nghỉ mấy buổi/tuần")
            off_override = int(off_override) if pd.notna(off_override) else None
            full_day_name = str(row.get("Nghỉ trọn ngày - Thứ") or "").strip()
            afternoon_name = str(row.get("Nghỉ chiều cố định - Thứ") or "").strip()
            pinned_full_day_off = weekday_name_to_num.get(full_day_name)
            pinned_afternoon_off = weekday_name_to_num.get(afternoon_name)

            if must_monday and pinned_full_day_off == 2:
                errors.append(f"{name}: đã chọn \"Đi T2\" nên không thể ghim nghỉ trọn ngày Thứ 2.")
            if must_monday and pinned_afternoon_off == 2:
                errors.append(f"{name}: đã chọn \"Đi T2\" nên không thể ghim nghỉ chiều Thứ 2.")
            if pinned_full_day_off is not None and (
                (pinned_full_day_off, "S") in config.forbidden_off_cells
                or (pinned_full_day_off, "C") in config.forbidden_off_cells
            ):
                errors.append(f"{name}: Thứ ghim nghỉ trọn ngày nằm trong \"Buổi cấm chọn làm buổi nghỉ GV\".")
            if pinned_afternoon_off is not None and (pinned_afternoon_off, "C") in config.forbidden_off_cells:
                errors.append(f"{name}: buổi chiều ghim nghỉ nằm trong \"Buổi cấm chọn làm buổi nghỉ GV\".")

            to_save.append((tid, name, str(row["Chức vụ"] or ""), must_monday, is_gvcn,
                             off_override, pinned_full_day_off, pinned_afternoon_off))

        if errors:
            for e in errors:
                st.error(e)
        else:
            existing_ids = {t.teacher_id for t in teachers}
            kept_ids = set()
            for tid, name, role, must_monday, is_gvcn, off_override, full_day_off, afternoon_off in to_save:
                new_id = repo.upsert_teacher(
                    conn, name, role, must_monday, is_gvcn, teacher_id=tid,
                    off_sessions_override=off_override,
                    pinned_full_day_off=full_day_off,
                    pinned_afternoon_off=afternoon_off,
                )
                kept_ids.add(new_id)
            for tid in existing_ids - kept_ids:
                repo.delete_teacher(conn, tid)
            st.success("Đã lưu danh sách giáo viên.")
            st.rerun()
```

- [ ] **Step 3: Manually verify**

Run: `streamlit run app.py`

- Log in, open "Thiết lập dữ liệu" → "Khai báo Lớp / Môn / Giáo viên" → tab "Giáo viên". Confirm 3 new columns appear, all empty/blank for existing teachers.
- Pick a real teacher, set "Nghỉ mấy buổi/tuần" = 3, "Nghỉ trọn ngày - Thứ" = Thứ 5, "Nghỉ chiều cố định - Thứ" = Thứ 3. Click "Lưu danh sách giáo viên" — confirm success and the values persist after reload.
- Try setting "Nghỉ trọn ngày - Thứ" = Thứ 6 for a teacher (Thứ 6 is fully inside the default `forbidden_off_cells`) — confirm a clear error message appears and nothing is saved (reload the page to confirm no partial save happened).
- If any teacher has "Đi T2" checked, try pinning their "Nghỉ chiều cố định - Thứ" = Thứ 2 — confirm the matching error message.
- Go to "Xếp & sửa thời khóa biểu" → "Xếp TKB tự động", run a schedule with the teacher configured in the first bullet — confirm it succeeds and that teacher's resulting timetable shows Thứ 5 fully empty and Thứ 3 chiều empty.
- Revert the demo teacher's 3 new fields back to blank and save again (leave the demo school in its original state).

- [ ] **Step 4: Run the full test suite one final time**

Run: `python -m pytest -v`
Expected: PASS — entire suite, no regressions from any of the 4 tasks.

- [ ] **Step 5: Commit**

```bash
git add pages/01_Khai_bao.py
git commit -m "feat: add per-teacher off-session override and pinned off-day UI to Khai báo page"
```

---

## Self-Review Notes

- **Spec coverage:** Spec section "2. Yêu cầu #3" is fully covered — the 3 `Teacher` fields (Task 1), migration + persistence (Task 2), the `_assign_off_slots` pin/override logic including the "silently dropped on conflict" defense-in-depth behavior the spec calls for (Task 3), and the UI with the exact 2 validation rules the spec names — `must_monday` conflict and `forbidden_off_cells` conflict (Task 4).
- **Placeholder scan:** No task defers logic or references undefined names — every code block is complete, copy-pasteable Python/Streamlit verified against the actual current file contents (`core/models.py:41-48`, `data/db.py:143-149`, `data/repository.py:78-100`, `core/scheduler.py:299-346`, `pages/01_Khai_bao.py:1-98`, all read directly).
- **Type consistency:** `off_sessions_override`/`pinned_full_day_off`/`pinned_afternoon_off` field names and `Optional[int]` type are identical across Tasks 1-4. `_assign_off_slots`'s existing parameters (`teacher_ids`, `teachers_by_id`, `rng`, `gvcn_shl_cell`, `off_slot_count`, `forbidden_off_cells`) keep their exact names, order, and defaults — Task 3 adds no new parameter to this function, only new internal logic keyed off `Teacher` attributes already available via `teachers_by_id`.
