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

from core.models import SchedulingInput
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
