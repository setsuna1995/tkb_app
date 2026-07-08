"""Port of ModKhung.bas: timetable frame/template (which cells are schedulable).

Unlike the VBA version -- which regenerates an "x"-marked Khung sheet sized to
a fixed TKB_Nhap row structure -- the frame here is just two integers per
class (morning_periods, afternoon_periods). The set of active (weekday,
session, period) cells is derived on the fly wherever it's needed, so it can
never drift out of sync with the stored template.
"""
from __future__ import annotations

from core.models import WEEKDAYS

MAX_PERIODS_PER_SESSION = 5

# name -> (morning_periods, afternoon_periods), matching the VBA presets
PRESETS = {
    "S4_C3": (4, 3),   # 42 ô/tuần/lớp
    "S5": (5, 0),      # 30 ô/tuần/lớp
    "S5_C2": (5, 2),   # 42 ô/tuần/lớp
    "S4_C4": (4, 4),   # 48 ô/tuần/lớp
}

# Chiều Thứ 5 & Thứ 6: trường dành riêng 2 buổi này cho ôn bồi dưỡng/phụ đạo
# (diễn ra ngoài TKB) nên không lớp nào được xếp môn học vào đây, bất kể
# afternoon_periods cấu hình bao nhiêu.
RESERVED_OFF_WEEKDAYS_CHIEU = (5, 6)


def validate_periods(morning_periods: int, afternoon_periods: int) -> None:
    for label, value in (("sáng", morning_periods), ("chiều", afternoon_periods)):
        if not (0 <= value <= MAX_PERIODS_PER_SESSION):
            raise ValueError(f"Số tiết buổi {label} phải trong khoảng 0-{MAX_PERIODS_PER_SESSION}.")
        if value == 1:
            raise ValueError(
                f"Số tiết buổi {label} không được để đúng 1 tiết -- để 0 (không học buổi đó) "
                f"hoặc từ 2 tiết trở lên."
            )


def active_cells(morning_periods: int, afternoon_periods: int, study_sunday: bool = False,
                  allow_saturday: bool = False) -> list:
    """Returns [(weekday, session, period), ...] for one class's frame.

    allow_saturday: khi trường học 2 buổi/ngày (afternoon_periods > 0), mặc định
    Thứ 7 nghỉ cùng Chủ nhật; người dùng tự bật allow_saturday=True làm ngoại lệ
    khi cần học bù -- không tự động bật theo định mức.
    """
    weekdays = WEEKDAYS + (8,) if study_sunday else WEEKDAYS
    skip_saturday = afternoon_periods > 0 and not allow_saturday

    cells = []
    for wd in weekdays:
        if skip_saturday and wd == 7:
            continue
        for p in range(1, morning_periods + 1):
            cells.append((wd, "S", p))
        if wd in RESERVED_OFF_WEEKDAYS_CHIEU:
            continue
        for p in range(1, afternoon_periods + 1):
            cells.append((wd, "C", p))
    return cells


def total_cells_per_class(morning_periods: int, afternoon_periods: int, study_sunday: bool = False,
                           allow_saturday: bool = False) -> int:
    return len(active_cells(morning_periods, afternoon_periods, study_sunday, allow_saturday))


def check_capacity(morning_periods: int, afternoon_periods: int, class_quota_totals: dict,
                    study_sunday: bool = False, allow_saturday: bool = False) -> str:
    """class_quota_totals: class_id -> total periods needed (sum over subjects, one parity).
    Mirrors ModKhung.KiemTraDuCho's "will it fit?" warning.
    """
    total_per_class = total_cells_per_class(morning_periods, afternoon_periods, study_sunday, allow_saturday)
    if not class_quota_totals:
        return f">> Đủ chỗ (khung {total_per_class} ô/lớp)."
    max_quota = max(class_quota_totals.values())
    if max_quota > total_per_class:
        return (
            f">> CẢNH BÁO: định mức lớn nhất {max_quota} tiết > {total_per_class} ô/lớp. "
            f"Sẽ KHÔNG xếp đủ - hãy giảm SoTiet hoặc tăng số tiết/buổi."
        )
    return f">> Đủ chỗ (định mức lớn nhất {max_quota} <= {total_per_class} ô/lớp)."
