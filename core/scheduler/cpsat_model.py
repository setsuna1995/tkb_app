"""Mô hình CP-SAT cho bài toán xếp TKB.

Vì sao có file này: kiến trúc tham lam + sửa cục bộ trong engine.py không giải
được các ràng buộc toàn cục (ghép cặp GV với các buổi sáng bắt buộc; ràng buộc
kích thước nhóm của luật buổi lẻ) -- mỗi lần sửa cho GV này lại phá của GV khác.
Xem .superpowers/sdd/2026-09-04-cpsat-scheduler/design.md §1.

File này CHỈ dựng và giải mô hình. Việc chọn dùng nó hay dùng engine cũ nằm ở
engine.py (Task 8).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from core.frame import MAX_PERIODS_PER_SESSION
from core.models import SchedulingInput
from core.roles import resolve_roles
from core.scheduler.constants import CAP_TIET_NGAY
from core.scheduler.placement import _build_effective_assigned_teacher

try:
    from ortools.sat.python import cp_model
    _HAS_ORTOOLS = True
except ImportError:  # pragma: no cover - phụ thuộc mềm
    cp_model = None
    _HAS_ORTOOLS = False


class CpSatUnavailable(RuntimeError):
    """ortools chưa được cài. Caller phải bắt và quay về engine cũ."""


@dataclass
class CpSatModel:
    model: object                      # cp_model.CpModel
    x: dict                            # (slot_id, subject_id) -> BoolVar
    inp: SchedulingInput
    slots_by_class: dict = field(default_factory=dict)
    slots_by_ts: dict = field(default_factory=dict)
    # Các task sau điền thêm vào đây; khai báo sẵn để không phải sửa dataclass
    # nhiều lần và để người đọc thấy trước hình dạng cuối cùng:
    teacher_of: dict = field(default_factory=dict)     # Task 2: (slot_id, subject_id) -> teacher_id
    role_index: object = None                          # Task 3: kết quả resolve_roles()
    penalty_terms: dict = field(default_factory=dict)  # Task 6: mã tiêu chí -> list biến phạt


def build_model(inp: SchedulingInput) -> CpSatModel:
    if not _HAS_ORTOOLS:
        raise CpSatUnavailable("ortools chưa được cài")

    m = cp_model.CpModel()

    slots_by_class = defaultdict(list)
    slots_by_ts = defaultdict(list)
    for s in inp.slots:
        slots_by_class[s.class_id].append(s)
        slots_by_ts[s.ts.ts_id].append(s)

    # Chỉ tạo biến cho cặp (ô, môn) mà lớp của ô đó THỰC SỰ cần môn đó. Bỏ hẳn
    # các cặp vô nghĩa giúp mô hình nhỏ đi nhiều lần.
    x = {}
    for s in inp.slots:
        for subj in inp.subjects:
            if inp.need.get((subj.subject_id, s.class_id), 0) > 0:
                x[s.slot_id, subj.subject_id] = m.NewBoolVar(
                    f"x_s{s.slot_id}_m{subj.subject_id}")

    # Mỗi ô có TỐI ĐA 1 môn -- không phải "đúng 1". Trường có dư địa thì ô thừa
    # được để trống, giống cơ chế gán -1 của engine cũ.
    for s in inp.slots:
        vs = [x[s.slot_id, subj.subject_id] for subj in inp.subjects
              if (s.slot_id, subj.subject_id) in x]
        if vs:
            m.AddAtMostOne(vs)

    # Đúng định mức mỗi (môn, lớp).
    for (subject_id, class_id), n in inp.need.items():
        if n <= 0:
            continue
        vs = [x[s.slot_id, subject_id] for s in slots_by_class[class_id]
              if (s.slot_id, subject_id) in x]
        m.Add(sum(vs) == n)

    built = CpSatModel(model=m, x=x, inp=inp,
                        slots_by_class=dict(slots_by_class),
                        slots_by_ts=dict(slots_by_ts))
    _add_teacher_constraints(built)
    _add_subject_constraints(built)
    _add_class_constraints(built)
    return built


def _add_teacher_constraints(built: CpSatModel) -> None:
    """5 ràng buộc "GV với chính tuần của mình" (task-2-brief.md):
    1. GV không dạy 2 lớp cùng tiết.
    2. GV bận (GV_Bận / inp.ban_busy) -- không được xếp.
    3. Trần tiết/buổi (config.max_periods_per_session).
    4. Trần tiết/ngày (config.max_teacher_periods_per_day).
    5. Buổi nghỉ của GV -- xem _add_off_day_constraints().

    Cũng điền built.teacher_of: (slot_id, subject_id) -> teacher_id, lấy từ
    _build_effective_assigned_teacher() (KHÔNG dùng inp.assigned_teacher trực
    tiếp) vì các cặp (môn, lớp) chưa phân công GV được gán id âm tổng hợp ở đó
    -- bỏ qua bước này thì các cặp chưa phân công sẽ không có ràng buộc GV nào
    cả (id âm không xuất hiện trong teacher_of).
    """
    m = built.model
    inp = built.inp
    config = inp.config
    slot_by_id = {s.slot_id: s for s in inp.slots}
    effective_assigned = _build_effective_assigned_teacher(inp)

    teacher_of = {}
    for (slot_id, subject_id) in built.x:
        class_id = slot_by_id[slot_id].class_id
        teacher_of[slot_id, subject_id] = effective_assigned[subject_id, class_id]
    built.teacher_of = teacher_of

    # Gom biến theo GV để dùng chung cho luật 1, 3, 4 (và luật 5 tái dùng
    # vars_by_teacher_session).
    vars_by_teacher_ts = defaultdict(list)       # (teacher_id, ts_id) -> [x]      -- luật 1
    vars_by_teacher_session = defaultdict(list)  # (teacher_id, wd, sess) -> [x]   -- luật 3, 5
    vars_by_teacher_day = defaultdict(list)      # (teacher_id, wd) -> [x]         -- luật 4
    for (slot_id, subject_id), var in built.x.items():
        t = teacher_of[slot_id, subject_id]
        ts = slot_by_id[slot_id].ts
        vars_by_teacher_ts[t, ts.ts_id].append(var)
        vars_by_teacher_session[t, ts.weekday, ts.session].append(var)
        vars_by_teacher_day[t, ts.weekday].append(var)

    # 1. GV không dạy 2 lớp cùng tiết.
    for vs in vars_by_teacher_ts.values():
        if len(vs) > 1:
            m.AddAtMostOne(vs)

    # 2. GV bận: mọi biến của GV đó tại ts_id bị cấm = 0.
    for (teacher_id, ts_id) in inp.ban_busy:
        for s in built.slots_by_ts.get(ts_id, []):
            for subj in inp.subjects:
                key = (s.slot_id, subj.subject_id)
                if key in built.x and teacher_of.get(key) == teacher_id:
                    m.Add(built.x[key] == 0)

    # 3. Trần tiết/buổi.
    for vs in vars_by_teacher_session.values():
        m.Add(sum(vs) <= config.max_periods_per_session)

    # 4. Trần tiết/ngày.
    max_teacher_day = getattr(config, "max_teacher_periods_per_day", 5)
    for vs in vars_by_teacher_day.values():
        m.Add(sum(vs) <= max_teacher_day)

    # 5. Buổi nghỉ của GV.
    _add_off_day_constraints(built, vars_by_teacher_session)


def _add_off_day_constraints(built: CpSatModel, vars_by_teacher_session: dict) -> None:
    """Luật 5 (buổi nghỉ của GV) -- xem ghi chú task-2-brief.md.

    Engine cũ (teacher_off.py) BỐC NGẪU NHIÊN off-slot của mỗi GV trước khi
    biết gì về khả năng xếp được của tuần đó, rồi coi ô đã bốc là cấm cứng
    trong _feasible(). CP-SAT không có khái niệm "lượt thử" nên không mô
    phỏng y hệt được -- thay vào đó, ta thêm biến off[t, wd, sess] và để BỘ
    GIẢI TỰ CHỌN buổi nghỉ sao cho phần còn lại của tuần vẫn tối ưu. Đây là
    cải thiện so với random draw, không phải mô phỏng lại (xem brief).

    Với mỗi GV t: TỐI ĐA `required_total` ô (wd, sess) được đánh dấu off,
    không ô nào rơi vào forbidden_off_cells / sáng bắt buộc / ghim nghỉ riêng
    của GV. off[t,wd,sess]=1 kéo theo GV không có tiết nào ở buổi đó.

    Cố ý dùng "<=" (tối đa) chứ KHÔNG phải "==" (đúng bằng): ghim riêng của GV
    (pinned_full_day_off, pinned_afternoon_off) LUÔN được ép off=1 cứng --
    khớp teacher_off.py's pinned_cells, luôn được tôn trọng đầy đủ, không bao
    giờ bị "hụt". Nhưng phần TỰ CHỌN còn lại (effective_count trừ số ô đã
    ghim) chỉ là mức TRẦN, không bắt buộc đạt đủ: engine.py có quyết định gần
    đây (2026-09-03, "per-week off-slot count is not a hard requirement") rằng
    số buổi nghỉ hụt không phải lỗi cứng. Dùng "==" ở đây từng khiến ngay cả
    các bài test cũ (off_sessions_per_week mặc định = 1) trở thành KHÔNG GIẢI
    ĐƯỢC bất cứ khi nào khung giờ test chỉ có 1-2 ngày -- không đủ ô (wd,
    sess) hợp lệ để "đúng bằng" 1 mà không đụng ràng buộc định mức khác.
    """
    m = built.model
    inp = built.inp
    config = inp.config
    teachers_by_id = {t.teacher_id: t for t in inp.teachers}
    all_wd_sess = sorted({(ts.weekday, ts.session) for ts in inp.timeslots})
    mandatory_mornings = set(getattr(config, "mandatory_morning_weekdays", (2, 5, 6)))
    forbidden_base = set(config.forbidden_off_cells) | {(wd, "S") for wd in mandatory_mornings}

    all_teacher_ids = {t for (t, _wd, _sess) in vars_by_teacher_session}
    for teacher_id in all_teacher_ids:
        teacher = teachers_by_id.get(teacher_id)
        forbidden = set(forbidden_base)

        # Ghim nghỉ riêng của GV: các ô này CHẮC CHẮN nghỉ (không phải lựa
        # chọn của bộ giải) -- mirror teacher_off.py's pinned_cells, kể cả
        # việc bỏ qua ghim nếu nó rơi vào ô đã bị cấm.
        pinned = set()
        pinned_weekdays = set()
        if teacher and teacher.pinned_full_day_off is not None:
            wd = teacher.pinned_full_day_off
            if (wd, "S") not in forbidden and (wd, "C") not in forbidden:
                pinned |= {(wd, "S"), (wd, "C")}
                pinned_weekdays.add(wd)
        if teacher and teacher.pinned_afternoon_off is not None:
            wd = teacher.pinned_afternoon_off
            if (wd, "C") not in forbidden and wd not in pinned_weekdays:
                pinned.add((wd, "C"))
                pinned_weekdays.add(wd)

        effective_count = (teacher.off_sessions_override
                           if (teacher and teacher.off_sessions_override is not None)
                           else config.teacher_off_sessions_per_week)
        required_total = max(effective_count, len(pinned))
        if required_total <= 0:
            continue

        off_vars = []
        for (wd, sess) in all_wd_sess:
            if (wd, sess) in forbidden:
                continue
            off_var = m.NewBoolVar(f"off_t{teacher_id}_wd{wd}_{sess}")
            off_vars.append(off_var)
            if (wd, sess) in pinned:
                m.Add(off_var == 1)
            teach_vars = vars_by_teacher_session.get((teacher_id, wd, sess), [])
            if teach_vars:
                m.Add(sum(teach_vars) == 0).OnlyEnforceIf(off_var)
        m.Add(sum(off_vars) <= required_total)


def _add_subject_constraints(built: CpSatModel) -> None:
    """8 ràng buộc "môn học" (task-3-brief.md), mirror của `_feasible()` trong
    feasibility.py:

    1. Môn bắt buộc buổi sáng (config.morning_only_subject_ids).
    2. Môn Nặng cấm buổi chiều, nếu bật (config.heavy_subjects_morning_only).
    3. GDTC: khung tiết sáng/chiều được phép + gdtc_avoid_period.
    4. Môn không xếp liền ngày, gồm cả GDTC nếu avoid_gdtc_consecutive_days.
    5. Môn nặng tối đa/buổi của lớp (max_heavy_per_session).
    6. Môn nặng không quá max_heavy_consecutive tiết liên tiếp/buổi.
    7. Môn nặng tránh tiết 3 buổi chiều (avoid_heavy_afternoon_period3).
    8. Luật môn-lớp-buổi (inp.subject_class_allowed_cells) -- cấm cứng ô
       ngoài danh sách cho phép.

    Cũng tính role_index = resolve_roles(...) ĐÚNG MỘT LẦN ở đây và lưu vào
    built.role_index để Task 4/5/6 dùng lại (đừng gọi lại resolve_roles nhiều
    lần -- xem task-3-brief.md).
    """
    m = built.model
    inp = built.inp
    config = inp.config
    x = built.x
    slot_by_id = {s.slot_id: s for s in inp.slots}

    role_index = resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week,
                                config.single_pair_subject_ids)
    built.role_index = role_index
    gdtc_id = role_index.gdtc_id

    # 1. Môn bắt buộc buổi sáng: cấm cứng mọi ô buổi chiều.
    morning_only = set(getattr(config, "morning_only_subject_ids", None) or ())
    if morning_only:
        for (slot_id, subject_id), var in x.items():
            if subject_id in morning_only and slot_by_id[slot_id].ts.session == "C":
                m.Add(var == 0)

    # 2. Môn Nặng cấm buổi chiều (nếu bật) -- luật riêng, không phụ thuộc luật 1.
    if getattr(config, "heavy_subjects_morning_only", False):
        for (slot_id, subject_id), var in x.items():
            if subject_id in role_index.heavy_ids and slot_by_id[slot_id].ts.session == "C":
                m.Add(var == 0)

    # 3. GDTC: khung tiết sáng/chiều + gdtc_avoid_period.
    if gdtc_id is not None:
        morning_allowed = getattr(config, "gdtc_morning_allowed_periods", (1, 2, 3, 4))
        afternoon_allowed = getattr(config, "gdtc_afternoon_allowed_periods", (2, 3))
        for (slot_id, subject_id), var in x.items():
            if subject_id != gdtc_id:
                continue
            ts = slot_by_id[slot_id].ts
            if ts.session == "S" and morning_allowed and ts.period not in morning_allowed:
                m.Add(var == 0)
            elif ts.session == "C" and afternoon_allowed and ts.period not in afternoon_allowed:
                m.Add(var == 0)
            if ts.period == config.gdtc_avoid_period:
                m.Add(var == 0)

    # 4. Môn không xếp liền ngày (gồm GDTC nếu avoid_gdtc_consecutive_days).
    # Chỉ cần dạng "tổng 2 ngày liền kề <= 1" -- xem ghi chú task-3-brief.md
    # về vì sao KHÔNG dùng range(2, 8) cứng: cặp ngày phải lấy từ các ngày
    # THỰC CÓ trong khung của từng lớp, nếu không một lớp không học Thứ 7 sẽ
    # bị ép "tổng Thứ 6 <= 1" một cách vô lý (vế Thứ 7 luôn = 0).
    non_consecutive = set(getattr(config, "non_consecutive_subject_ids", None) or ())
    if getattr(config, "avoid_gdtc_consecutive_days", True) and gdtc_id is not None:
        non_consecutive.add(gdtc_id)
    if non_consecutive:
        vars_by_class_subject_day = defaultdict(list)
        days_by_class = defaultdict(set)
        for (slot_id, subject_id), var in x.items():
            if subject_id not in non_consecutive:
                continue
            s = slot_by_id[slot_id]
            vars_by_class_subject_day[s.class_id, subject_id, s.ts.weekday].append(var)
            days_by_class[s.class_id].add(s.ts.weekday)
        for class_id, days in days_by_class.items():
            for d in days:
                if (d + 1) not in days:
                    continue
                for subject_id in non_consecutive:
                    vs_today = vars_by_class_subject_day.get((class_id, subject_id, d), [])
                    vs_next = vars_by_class_subject_day.get((class_id, subject_id, d + 1), [])
                    if vs_today or vs_next:
                        m.Add(sum(vs_today) + sum(vs_next) <= 1)

    # 5 + 6. Môn nặng: tối đa/buổi (5) và không quá N tiết liên tiếp (6).
    if role_index.heavy_ids:
        vars_by_session = defaultdict(list)                # (class,wd,sess) -> [var]
        vars_by_session_period = defaultdict(dict)          # (class,wd,sess) -> {period: [var]}
        for (slot_id, subject_id), var in x.items():
            if subject_id not in role_index.heavy_ids:
                continue
            s = slot_by_id[slot_id]
            key = (s.class_id, s.ts.weekday, s.ts.session)
            vars_by_session[key].append(var)
            vars_by_session_period[key].setdefault(s.ts.period, []).append(var)

        # Luật 5: cùng công thức max(...) với feasibility.py để trần/buổi
        # không bao giờ nhỏ hơn cửa sổ liên tiếp của luật 6, tránh vô tình
        # làm luật 6 không bao giờ chạm tới được.
        max_heavy_sess = max(getattr(config, "max_heavy_per_session", 3), config.max_heavy_consecutive)
        for vs in vars_by_session.values():
            m.Add(sum(vs) <= max_heavy_sess)

        # Luật 6: cửa sổ trượt độ dài (max_heavy_consecutive + 1) -- đối chiếu
        # feasibility.py:80-91. Với mỗi vị trí bắt đầu w, tổng biến môn nặng
        # trong [w, w + max_heavy_consecutive] <= max_heavy_consecutive
        # (tương đương "không cho cả cửa sổ đều là môn nặng").
        window = config.max_heavy_consecutive + 1
        last_start = MAX_PERIODS_PER_SESSION - config.max_heavy_consecutive
        for period_vars in vars_by_session_period.values():
            for w in range(1, last_start + 1):
                window_vars = []
                for offset in range(window):
                    window_vars.extend(period_vars.get(w + offset, []))
                if window_vars:
                    m.Add(sum(window_vars) <= config.max_heavy_consecutive)

    # 7. Môn nặng tránh tiết 3 buổi chiều.
    if getattr(config, "avoid_heavy_afternoon_period3", True):
        for (slot_id, subject_id), var in x.items():
            if subject_id in role_index.heavy_ids:
                ts = slot_by_id[slot_id].ts
                if ts.session == "C" and ts.period == 3:
                    m.Add(var == 0)

    # 8. Luật môn-lớp-buổi: (subject_id, class_id) có danh sách ô cho phép thì
    # mọi ô ngoài danh sách bị ép = 0. None/thiếu khoá = không ràng buộc.
    for (subject_id, class_id), allowed in inp.subject_class_allowed_cells.items():
        if allowed is None:
            continue
        for s in built.slots_by_class.get(class_id, []):
            if (s.ts.weekday, s.ts.session) not in allowed:
                key = (s.slot_id, subject_id)
                if key in x:
                    m.Add(x[key] == 0)


def _add_class_constraints(built: CpSatModel) -> None:
    """7 ràng buộc "khung LỚP" (task-4-brief.md) cộng 2 tiết ghim theo chính
    sách trường (chào cờ, sinh hoạt lớp -- SHL):

    1. Trần tiết/môn/ngày/lớp = role_index.block_size.get(subject_id, 1).
       Riêng HĐTN ở tuần THƯỜNG (không phải tuần chuyên đề, tức không nằm
       trong block_size) được nâng trần lên 2: chào cờ (ghim, luật 2) + SHL
       (ghim, luật 3) + đúng 1 tiết "chủ đề" tự do. Xác nhận trường
       2026-09-04: tiết tự do này ĐƯỢC PHÉP rơi cùng ngày với 1 trong 2 tiết
       ghim và KHÔNG cần liền kề chúng -- xem feasibility.py's hdtn_free_period
       và "Ghi chú quan trọng" của brief. Việc ép các môn khối (KEP, HĐTN tuần
       chuyên đề với block_size=3) thành khối LIỀN KỀ là việc của Task 5, cố
       tình không làm ở đây.
    2. Ghim chào cờ: ô (chao_co_weekday, "S", chao_co_period) = HĐTN, mọi lớp
       có ô đó và có nhu cầu HĐTN > 0 (else không tạo biến, tự bỏ qua).
    3. Ghim SHL: tiết CUỐI (max period) của buổi sáng ngày SHL. Ngày SHL suy
       ra từ khung riêng từng lớp, KHÔNG hardcode: lớp có ít nhất 1 ô buổi
       chiều bất kỳ trong tuần -> Thứ 6; lớp chỉ học sáng -> Thứ 7 (mirror
       engine.py:87-94, KHÔNG phải "Thứ 6 vì có tiết chiều hôm đó" -- chỉ cần
       CÓ buổi chiều ở đâu đó trong tuần).
       Luật 2 + 3 chỉ áp dụng khi KHÔNG phải tuần chuyên đề
       (inp.hdtn_thematic_week) -- mirror "if not inp.hdtn_thematic_week" của
       engine.py.
    4. Tuần chuyên đề: không có ràng buộc riêng ở đây ngoài việc BỎ ghim (2+3
       ở trên) -- luật 1 tự đọc block_size[hdtn_id]=3 do resolve_roles() đã
       ghi đè, nâng trần lên 3/ngày mà không cần code riêng. Phần "xếp thành
       khối 3 tiết LIỀN KỀ" là Task 5.
    5. Không hở tiết giữa buổi của lớp (BAT_LIEN_MACH, feasibility.py:59-61):
       tiết p có môn ⟹ tiết (p-1) cùng buổi/ngày/lớp cũng phải có môn. Trường
       này hiện dư địa = 0 (mọi ô đều có tiết) nên luật tự thoả, nhưng vẫn
       viết tường minh cho trường/khung khác có dư ô.
    6. Trần tiết/ngày/lớp = đúng số ô lớp đó có trong ngày (day_capacity của
       engine.py, luôn = đếm số ô, KHÔNG phải một giá trị cấu hình riêng) --
       luôn tự thoả trong mô hình này (AtMostOne mỗi ô => số tiết xếp được
       trong ngày không thể vượt số ô ngày đó), viết tường minh để khớp bảng
       luật + phòng trường hợp sau này day_capacity không còn = đúng số ô.
    7. Lớp không có buổi chỉ 1 tiết (swaps.py's _has_lone_period): biến phụ
       class_used[cid, wd, sess], ràng buộc count >= 2*used và
       count <= (số ô buổi đó)*used -- buộc count là 0 hoặc >= 2. Chỉ áp dụng
       cho buổi có >= 2 ô (buổi 1-ô-duy-nhất không thể "lẻ" theo nghĩa này).
    """
    m = built.model
    inp = built.inp
    config = inp.config
    x = built.x
    role_index = built.role_index
    hdtn_id = role_index.hdtn_id
    slot_by_id = {s.slot_id: s for s in inp.slots}

    # 1. Trần tiết/môn/ngày/lớp.
    vars_by_class_subject_day = defaultdict(list)
    for (slot_id, subject_id), var in x.items():
        s = slot_by_id[slot_id]
        vars_by_class_subject_day[s.class_id, subject_id, s.ts.weekday].append(var)
    for (class_id, subject_id, weekday), vs in vars_by_class_subject_day.items():
        cap_d = role_index.block_size.get(subject_id, 1)
        if subject_id == hdtn_id and cap_d == 1:
            cap_d = 2
        m.Add(sum(vs) <= cap_d)

    if not inp.hdtn_thematic_week and hdtn_id is not None:
        # 2. Ghim chào cờ.
        for s in inp.slots:
            if (s.ts.weekday == config.chao_co_weekday and s.ts.session == "S"
                    and s.ts.period == config.chao_co_period):
                key = (s.slot_id, hdtn_id)
                if key in x:
                    m.Add(x[key] == 1)

        # 3. Ghim SHL -- ngày suy ra từ khung riêng của lớp (có buổi chiều ở
        # bất kỳ đâu trong tuần -> Thứ 6, chỉ học sáng -> Thứ 7), tiết ghim là
        # tiết CUỐI (period lớn nhất) của buổi sáng ngày đó.
        class_has_chieu = defaultdict(bool)
        for s in inp.slots:
            if s.ts.session == "C":
                class_has_chieu[s.class_id] = True
        for class_id, class_slots in built.slots_by_class.items():
            target_wd = 6 if class_has_chieu[class_id] else 7
            day_slots = [s for s in class_slots if s.ts.session == "S" and s.ts.weekday == target_wd]
            if not day_slots:
                continue
            target = max(day_slots, key=lambda s: s.ts.period)
            key = (target.slot_id, hdtn_id)
            if key in x:
                m.Add(x[key] == 1)

    # 5. Không hở tiết giữa buổi của lớp.
    slot_by_coord = {(s.class_id, s.ts.weekday, s.ts.session, s.ts.period): s for s in inp.slots}
    for s in inp.slots:
        if s.ts.period <= 1:
            continue
        vars_p = [x[s.slot_id, subj.subject_id] for subj in inp.subjects if (s.slot_id, subj.subject_id) in x]
        if not vars_p:
            continue
        prev = slot_by_coord.get((s.class_id, s.ts.weekday, s.ts.session, s.ts.period - 1))
        vars_prev = ([x[prev.slot_id, subj.subject_id] for subj in inp.subjects
                      if (prev.slot_id, subj.subject_id) in x] if prev is not None else [])
        if vars_prev:
            m.Add(sum(vars_p) <= sum(vars_prev))
        else:
            # Ô tiết p-1 không tồn tại trong khung của lớp -- không có gì để
            # "liền mạch" theo, nên ô p không được có môn (mirror
            # feasibility.py: occupied.get(...) mặc định False => return False).
            m.Add(sum(vars_p) == 0)

    # 6. Trần tiết/ngày/lớp = đúng số ô lớp đó có trong ngày.
    count_by_class_day = defaultdict(int)
    for s in inp.slots:
        count_by_class_day[s.class_id, s.ts.weekday] += 1
    vars_by_class_day = defaultdict(list)
    for (slot_id, subject_id), var in x.items():
        s = slot_by_id[slot_id]
        vars_by_class_day[s.class_id, s.ts.weekday].append(var)
    for key, vs in vars_by_class_day.items():
        cap = count_by_class_day.get(key, CAP_TIET_NGAY)
        m.Add(sum(vs) <= cap)

    # 7. Lớp không có buổi chỉ 1 tiết.
    groups = defaultdict(list)
    for s in inp.slots:
        groups[s.class_id, s.ts.weekday, s.ts.session].append(s)
    for (class_id, weekday, session), group_slots in groups.items():
        if len(group_slots) < 2:
            continue
        vs = []
        for s in group_slots:
            vs.extend(x[s.slot_id, subj.subject_id] for subj in inp.subjects
                      if (s.slot_id, subj.subject_id) in x)
        if not vs:
            continue
        used = m.NewBoolVar(f"class_used_c{class_id}_wd{weekday}_{session}")
        m.Add(sum(vs) >= 2 * used)
        m.Add(sum(vs) <= len(group_slots) * used)


def solve(built: CpSatModel, time_limit_s: float = 10.0,
          workers: int = 8) -> Optional[dict]:
    """Trả {slot_id: subject_id} cho các ô CÓ môn, hoặc None nếu không giải được.
    Ô để trống không xuất hiện trong dict."""
    if not _HAS_ORTOOLS:
        raise CpSatUnavailable("ortools chưa được cài")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    solver.parameters.num_search_workers = int(workers)
    status = solver.Solve(built.model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    assignment = {}
    for (slot_id, subject_id), var in built.x.items():
        if solver.Value(var):
            assignment[slot_id] = subject_id
    return assignment
