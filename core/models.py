"""Domain dataclasses shared by the scheduler engine, importer/exporter, and UI.

Weekday convention (matches Vietnamese school naming, not ISO weekday numbers):
    2 = Thứ 2 (Monday) ... 7 = Thứ 7 (Saturday). 8 = Chủ nhật, reserved/unused.
Session: "S" = Sáng (morning), "C" = Chiều (afternoon).
Period: 1..5 within a session.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

WEEKDAYS = (2, 3, 4, 5, 6, 7)
WEEKDAY_NAMES = {2: "Thứ 2", 3: "Thứ 3", 4: "Thứ 4", 5: "Thứ 5", 6: "Thứ 6", 7: "Thứ 7", 8: "Chủ nhật"}
SESSIONS = ("S", "C")

# Subject role codes (matches PhanCong "MA" column in the original workbook)
ROLE_THUONG = 0
ROLE_NANG = 1
ROLE_KEP = 2
ROLE_NANG_KEP = 3
ROLE_GDTC = 4
ROLE_HDTN = 5


@dataclass
class ClassRoom:
    class_id: int
    name: str
    sort_order: int = 0


@dataclass
class Subject:
    subject_id: int
    name: str
    role_code: int = ROLE_THUONG
    sort_order: int = 0


@dataclass
class Teacher:
    teacher_id: int
    name: str
    role: str = ""              # '', 'GVCN', 'Tổ trưởng', 'Tổ phó', 'Tổng phụ trách'
    must_monday: bool = False
    is_gvcn: bool = False
    cap: int = 19               # computed: 19 - role reduction


@dataclass(frozen=True)
class TimeSlot:
    ts_id: int
    weekday: int
    session: str
    period: int

    @property
    def order_key(self) -> tuple:
        return (self.weekday, 0 if self.session == "S" else 1, self.period)


@dataclass
class Slot:
    """One fillable (class, timeslot) cell — equivalent to VBA's slotR/slotC/slotCls/slotTs."""
    slot_id: int
    class_id: int
    ts: TimeSlot
    old_subject_id: Optional[int] = None
    assigned: Optional[int] = None   # subject_id, or -1 sentinel for "intentionally left empty"
    pinned: bool = False


@dataclass
class RoleIndex:
    heavy_ids: set = field(default_factory=set)
    kep_ids: set = field(default_factory=set)
    gdtc_id: Optional[int] = None
    hdtn_id: Optional[int] = None


@dataclass
class SchedulingInput:
    classes: list          # list[ClassRoom]
    subjects: list          # list[Subject]
    teachers: list          # list[Teacher]
    need: dict              # (subject_id, class_id) -> periods needed this parity
    assigned_teacher: dict  # (subject_id, class_id) -> teacher_id (synthetic negative id if unassigned)
    ban_busy: set           # {(teacher_id, ts_id)} hard-blocked
    slots: list             # list[Slot] -- universe of fillable cells
    timeslots: list         # list[TimeSlot]
    seed: int = 0            # 0 = random each run
    extra_kep_ids: frozenset = field(default_factory=frozenset)  # subject_id cần xếp kép CHỈ tuần này


@dataclass
class ScheduleResult:
    success: bool
    assignment: dict = field(default_factory=dict)   # slot_id -> Optional[int] subject_id (best attempt)
    cells_changed: int = 0
    cells_total: int = 0
    attempts_tried: int = 0
    successes_found: int = 0
    failure_reason: Optional[str] = None
