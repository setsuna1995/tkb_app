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

# Chuỗi chức vụ nhận diện Ban giám hiệu. Dùng chung cho mọi nơi cần biết "GV này
# là BGH" -- nếu mỗi chỗ tự viết danh sách riêng thì engine và giao diện sẽ lệch
# nhau khi trường đổi cách ghi chức vụ.
BGH_ROLE_KEYWORDS = ("Hiệu trưởng", "Phó hiệu trưởng")


def is_bgh(teacher) -> bool:
    """GV thuộc Ban giám hiệu (hiệu trưởng / hiệu phó)? Họ có tải rất ít nên được
    miễn luật "mọi GV phải có tiết các sáng bắt buộc" -- vẫn có mặt ở trường theo
    lịch quản lý chứ không qua tiết dạy."""
    return bool(teacher and any(k in (getattr(teacher, "role", "") or "") for k in BGH_ROLE_KEYWORDS))
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
    off_sessions_override: Optional[int] = None    # None = dùng config.teacher_off_sessions_per_week chung
    pinned_full_day_off: Optional[int] = None      # thứ (2-7) ghim nghỉ TRỌN NGÀY -- ngoại lệ "không nghỉ trọn ngày"
    pinned_afternoon_off: Optional[int] = None     # thứ ghim nghỉ 1 buổi CHIỀU cố định
    reduction_override: Optional[int] = None       # Số tiết giảm trừ tùy chỉnh trực tiếp cho GV (nếu có)


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
    single_pair_ids: set = field(default_factory=set)  # môn có đúng 1 cặp 2 tiết/tuần + các tiết còn lại là tiết đơn (VD: Ngữ văn)
    block_size: dict = field(default_factory=dict)  # subject_id -> N (contiguous periods required, >=2)
    gdtc_id: Optional[int] = None
    hdtn_id: Optional[int] = None


@dataclass
class SchedulingConfig:
    """Ràng buộc "lựa chọn của trường" -- khác trường có thể chọn khác, không phải
    bất biến thuật toán. Mọi default dưới đây = đúng hằng số hardcode trước khi có
    cấu hình này, để hành vi không đổi cho tới khi trường chủ động lưu giá trị khác.
    """
    gdtc_avoid_period: int = 5
    gdtc_morning_allowed_periods: tuple = (1, 2, 3, 4)  # GDTC chỉ xếp tiết 1-4 buổi sáng
    gdtc_afternoon_allowed_periods: tuple = (2, 3)     # GDTC chỉ xếp tiết 2-3 buổi chiều
    chao_co_weekday: int = 2
    chao_co_period: int = 1
    max_heavy_consecutive: int = 3
    max_periods_per_session: int = 4
    teacher_off_sessions_per_week: int = 1
    forbidden_off_cells: frozenset = field(
        default_factory=lambda: frozenset({(2, "S"), (5, "S"), (6, "S"), (5, "C"), (6, "C")})
    )
    reserved_off_weekdays_chieu: tuple = (5, 6)
    heavy_subject_priority_periods: int = 4   # Tiêu chí II.5: 4 tiết đầu buổi sáng ưu tiên môn "Nặng"; 0 = tắt
    afternoon_preferred_subject_ids: frozenset = field(default_factory=frozenset)  # rỗng = tắt
    heavy_subjects_morning_only: bool = False   # True = môn Nặng cấm cứng xếp buổi chiều (R3, spec 2026-08-30)
    morning_only_subject_ids: frozenset = field(default_factory=frozenset)  # rỗng = tắt; các môn bị cấm cứng xếp buổi chiều (bất kể role_code)
    non_consecutive_subject_ids: frozenset = field(default_factory=frozenset) # rỗng = tắt; các môn cấm xếp liên tiếp các ngày
    single_pair_subject_ids: frozenset = field(default_factory=frozenset) # rỗng = tắt; các môn bắt buộc có đúng 1 cặp xếp liền nhau (vd: Văn 4 tiết -> 1 cặp 2 tiết liền, 2 tiết đơn lẻ)
    avoid_teacher_gaps: bool = True  # Tránh tiết trống/lủng của GV trong buổi (không để dạy tiết 1 nghỉ 2-3 mới dạy 4)
    avoid_teacher_lone_periods: bool = True  # Tránh GV chỉ có 1 tiết/ngày hoặc sáng 1 tiết + chiều 1 tiết
    balance_afternoon_teachers: bool = True  # Cân đối buổi chiều, tránh GV nghỉ full chiều khi dạy lớp có tiết chiều
    mandatory_morning_weekdays: tuple = (2, 5, 6)  # Các sáng bắt buộc toàn thể GV có mặt/đi làm
    strict_morning_weekdays: tuple = ()
    # Các sáng mà MỌI GV đều phải có tiết dạy, không xét ngưỡng tải
    # (min_weekly_periods_for_mandatory_morning không áp dụng cho các sáng này).
    # Ngoại lệ duy nhất: BGH (Hiệu trưởng / Phó hiệu trưởng) -- tải của họ quá ít
    # để trải đủ các sáng, và họ vẫn có mặt ở trường theo lịch quản lý.
    # Rỗng = tắt (mặc định), giữ nguyên hành vi cũ cho các trường chưa cấu hình.
    min_weekly_periods_for_mandatory_morning: int = 10
    # Tiêu chí II.3 chỉ ép GV có tải >= ngưỡng này phải có mặt các sáng bắt buộc.
    # Trước 2026-09-04 số 10 nằm cứng trong quality.py; tách ra thành cấu hình vì đo
    # thấy ~3.75 GV vẫn vắng sáng Thứ 5 do tải dưới ngưỡng nên luật không chạm tới.
    # 0 = áp dụng cho mọi GV.
    avoid_gdtc_consecutive_days: bool = True  # GDTC của 1 lớp không xếp ở 2 hôm liền kề
    max_teacher_periods_per_day: int = 5  # Tiêu chí II.2: Mỗi GV không quá tải vượt 5 tiết/ngày
    max_heavy_per_session: int = 3  # Tiêu chí I.2 & II.13: Tối đa 3 tiết môn nặng trong 1 buổi của 1 lớp
    hdtn_period2_afternoon: bool = True  # Tiêu chí II.6: Tiết 2 HĐTN xếp vào buổi chiều cho các lớp có học chiều
    avoid_heavy_afternoon_period3: bool = True  # Tiêu chí II.15: Hạn chế môn nặng tiết 3 chiều
    avoid_teacher_4_consecutive_morning: bool = True  # Tiêu chí II.14: Hạn chế GV dạy 4 tiết sáng liên tục nếu tải <= 20
    min_weekly_periods_for_lone_penalty: int = 8  # Tiêu chí II.4: miễn trừ GV có tải < ngưỡng này; 0 = áp dụng phạt lẻ cho tất cả
    lone_session_exempt_teacher_ids: frozenset = field(default_factory=frozenset)
    # GV được MIỄN TRỪ luật buổi lẻ (II.4/II.8) theo tên cụ thể, không theo ngưỡng tải:
    # dành cho GV vốn đã có mặt ở trường vì nhiệm vụ khác (phụ trách thiết bị, thư viện...),
    # nên việc họ chỉ dạy 1 tiết trong một buổi không khiến họ phải đi lại thêm.
    compact_schedule_teacher_ids: frozenset = field(default_factory=frozenset)
    # GV được ƯU TIÊN MỀM gom tiết vào ÍT BUỔI NHẤT có thể, để họ được nghỉ trọn
    # nhiều buổi (sáng hay chiều đều tính) -- vd GV Thể dục cần nghỉ 2 buổi bất kỳ.
    # Chỉ là điểm phạt khi chấm chọn, không phải luật cứng: nếu không còn chỗ thì
    # vẫn xếp bình thường chứ không làm hỏng các tiêu chí khác.
    use_cpsat: bool = True  # Bật bộ giải tối ưu hóa toàn cục CP-SAT
    cpsat_time_limit_seconds: int = 180  # Giới hạn thời gian giải cho CP-SAT (giây). Nâng từ 30
    # lên 180 (2026-09-05): hosting Streamlit Community Cloud free tier CPU rất hạn chế (thường
    # chỉ 1 CPU) -- 30s không đủ để CP-SAT tìm lời giải sạch (0 vi phạm II.3/II.4/II.8) trên dữ
    # liệu thực của trường, phải nới lỏng nhiều luật một cách không cần thiết. Bù bằng cách cho
    # nhiều thời gian hơn thay vì hy sinh chất lượng lịch.
    cpsat_minimize_changes: bool = False  # Ưu tiên giữ tối đa ô TKB cũ (mặc định Tắt để giải tự do)



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
    hdtn_thematic_week: bool = False   # True = tuần chuyên đề CHỈ tuần này (R2, spec 2026-08-30):
                                        # HDTN dồn 3 tiết liền kề, bỏ ghim chào cờ + SHL
    config: SchedulingConfig = field(default_factory=SchedulingConfig)
    subject_class_allowed_cells: dict = field(default_factory=dict)  # (subject_id, class_id) -> frozenset[(weekday, session)]


@dataclass
class ScheduleResult:
    success: bool
    assignment: dict = field(default_factory=dict)   # slot_id -> Optional[int] subject_id (best attempt)
    cells_changed: int = 0
    cells_total: int = 0
    attempts_tried: int = 0
    successes_found: int = 0
    failure_reason: Optional[str] = None
    relaxed_rules: list = field(default_factory=list)  # [{"rule_id": "II.3", ...}] rules that could not be
                                                          # fully satisfied even in the best available attempt
                                                          # (see core/scheduler/engine.py's post-generation gate)
    solver_name: str = "heuristic"
    diagnostics: dict = field(default_factory=dict)  # cpsat_model diagnostic trace; {} for heuristic engine

