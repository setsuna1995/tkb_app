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


def validate_periods(morning_periods: int, afternoon_periods: int,
                      short_morning_periods: int | None = None,
                      short_afternoon_periods: int | None = None) -> None:
    checks = [("sáng", morning_periods), ("chiều", afternoon_periods)]
    if short_morning_periods is not None:
        checks.append(("sáng ngày lệch", short_morning_periods))
    if short_afternoon_periods is not None:
        checks.append(("chiều ngày lệch", short_afternoon_periods))
    for label, value in checks:
        if not (0 <= value <= MAX_PERIODS_PER_SESSION):
            raise ValueError(f"Số tiết buổi {label} phải trong khoảng 0-{MAX_PERIODS_PER_SESSION}.")
        if value == 1:
            raise ValueError(
                f"Số tiết buổi {label} không được để đúng 1 tiết -- để 0 (không học buổi đó) "
                f"hoặc từ 2 tiết trở lên."
            )


def active_cells(morning_periods: int, afternoon_periods: int, study_sunday: bool = False,
                  allow_saturday: bool = False, short_weekday: int | None = None,
                  short_morning_periods: int | None = None,
                  short_afternoon_periods: int | None = None) -> list:
    """Returns [(weekday, session, period), ...] for one class's frame.

    allow_saturday: khi trường học 2 buổi/ngày (afternoon_periods > 0), mặc định
    Thứ 7 nghỉ cùng Chủ nhật; người dùng tự bật allow_saturday=True làm ngoại lệ
    khi cần học bù -- không tự động bật theo định mức.

    short_weekday: nếu có, ngày này dùng short_morning_periods/short_afternoon_periods
    thay vì morning_periods/afternoon_periods chuẩn -- dùng khi định mức tiết/tuần
    không chia hết cho khung đồng nhất, dồn phần chênh lệch vào đúng 1 ngày (thường
    là Thứ 7) thay vì để trống rải rác. None ở 1 trong 2 override nghĩa là buổi đó
    không đổi so với chuẩn. Xem thêm suggest_short_day().
    """
    weekdays = WEEKDAYS + (8,) if study_sunday else WEEKDAYS
    skip_saturday = afternoon_periods > 0 and not allow_saturday

    cells = []
    for wd in weekdays:
        if skip_saturday and wd == 7:
            continue
        day_morning = morning_periods
        day_afternoon = afternoon_periods
        if wd == short_weekday:
            if short_morning_periods is not None:
                day_morning = short_morning_periods
            if short_afternoon_periods is not None:
                day_afternoon = short_afternoon_periods
        for p in range(1, day_morning + 1):
            cells.append((wd, "S", p))
        if wd in RESERVED_OFF_WEEKDAYS_CHIEU:
            continue
        for p in range(1, day_afternoon + 1):
            cells.append((wd, "C", p))
    return cells


def total_cells_per_class(morning_periods: int, afternoon_periods: int, study_sunday: bool = False,
                           allow_saturday: bool = False, short_weekday: int | None = None,
                           short_morning_periods: int | None = None,
                           short_afternoon_periods: int | None = None) -> int:
    return len(active_cells(morning_periods, afternoon_periods, study_sunday, allow_saturday,
                             short_weekday, short_morning_periods, short_afternoon_periods))


def suggest_short_day(morning_periods: int, afternoon_periods: int, quota_total: int,
                       allow_saturday: bool = False) -> tuple[int, int | None, int | None] | None:
    """Đề xuất dồn phần chênh lệch (deficit) giữa khung đồng nhất và định mức thực tế
    vào đúng 1 ngày, ưu tiên Thứ 7 -- thay vì để thuật toán xếp lịch vô tình để trống
    rải rác. Trả về (short_weekday, short_morning_periods, short_afternoon_periods)
    hoặc None nếu không có/không đề xuất được (khung vừa khít, thiếu chỗ, hoặc deficit
    vượt quá số tiết khả dụng của mọi ngày ứng viên).

    Nguyên tắc: TOÀN BỘ deficit dồn vào 1 ngày duy nhất (không rải qua nhiều ngày).
    Ngày ưu tiên là Thứ 7 nếu Thứ 7 đang là ngày học (lớp 1 buổi, hoặc allow_saturday).
    Nếu Thứ 7 không phải ngày học (lớp 2 buổi mặc định nghỉ Thứ 7), dò lần lượt Thứ 6
    -> Thứ 2 -- bỏ qua buổi chiều Thứ 5/Thứ 6 vì RESERVED_OFF_WEEKDAYS_CHIEU luôn khoá
    2 buổi đó bất kể cấu hình, nên không thể "trừ" tiết vào đấy.
    """
    uniform_total = total_cells_per_class(morning_periods, afternoon_periods, allow_saturday=allow_saturday)
    deficit = uniform_total - quota_total
    if deficit <= 0:
        return None

    skip_saturday = afternoon_periods > 0 and not allow_saturday
    candidates = [7] if not skip_saturday else [6, 5, 4, 3, 2]

    for wd in candidates:
        avail_afternoon = 0 if wd in RESERVED_OFF_WEEKDAYS_CHIEU else afternoon_periods
        avail_morning = morning_periods
        # Trừ vào buổi có nhiều tiết khả dụng hơn trước; nếu bằng nhau, trừ buổi sáng.
        order = ("C", "S") if avail_afternoon > avail_morning else ("S", "C")
        avail = {"S": avail_morning, "C": avail_afternoon}
        reduction = {"S": 0, "C": 0}
        remaining = deficit
        for session in order:
            take = min(remaining, avail[session])
            reduction[session] = take
            remaining -= take
            if remaining == 0:
                break
        if remaining == 0:
            short_morning = morning_periods - reduction["S"] if reduction["S"] else None
            short_afternoon = afternoon_periods - reduction["C"] if reduction["C"] else None
            if short_morning == 1 or short_afternoon == 1:
                # Vi phạm luật "không lỗ 1 tiết" của scheduler (_has_lone_period) -- ngày
                # này sẽ luôn xếp thất bại, thử ngày ứng viên tiếp theo thay vì đề xuất sai.
                continue
            return (wd, short_morning, short_afternoon)

    return None


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
