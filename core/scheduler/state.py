"""State management for a single scheduling solver attempt."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _State:
    remaining_need: dict
    busy: set
    session_count: dict = field(default_factory=lambda: defaultdict(int))
    placed: dict = field(default_factory=lambda: defaultdict(list))
    day_count: dict = field(default_factory=lambda: defaultdict(int))
    occupied: dict = field(default_factory=dict)
    heavy_at: dict = field(default_factory=dict)
    gv_off_slots: dict = field(default_factory=dict)
    rem_need_count: dict = field(default_factory=lambda: defaultdict(int))
    rem_slot_count: dict = field(default_factory=lambda: defaultdict(int))
    assigned: dict = field(default_factory=dict)     # slot_id -> Optional[int] (-1 = intentionally empty)
    pinned: dict = field(default_factory=dict)        # slot_id -> bool
    slot_teacher: dict = field(default_factory=dict)  # slot_id -> teacher_id
    shl_days: set = field(default_factory=set)        # {(class_id, weekday)} nơi greedy KHÔNG đặt HDTN (dành cho SHL ghim)
    teacher_session_periods: dict = field(default_factory=lambda: defaultdict(list))  # (teacher_id, weekday, session) -> list[period]
    teacher_rem_need: dict = field(default_factory=lambda: defaultdict(int))  # teacher_id -> tổng số tiết CÒN LẠI chưa xếp của GV đó.
    # Bộ đếm này là bản tăng dần của phép cộng mà heuristics.py trước đây tính lại từ đầu
    # (quét toàn bộ remaining_need) cho MỖI môn ứng viên ở MỖI ô -- chiếm ~60% thời gian chạy
    # engine khi đo bằng cProfile (2026-09-04). Được cập nhật trong _put_at/_remove_at, cộng
    # với 2 chỗ engine.py tự sửa remaining_need trực tiếp khi giữ chỗ tiết SHL.
    teacher_week_afternoon_count: dict = field(default_factory=lambda: defaultdict(int)) # teacher_id -> count of afternoon periods
    teacher_day_count: dict = field(default_factory=lambda: defaultdict(int)) # (teacher_id, weekday) -> total periods taught that day
    session_heavy_count: dict = field(default_factory=lambda: defaultdict(int)) # (class_id, weekday, session) -> count of heavy periods
