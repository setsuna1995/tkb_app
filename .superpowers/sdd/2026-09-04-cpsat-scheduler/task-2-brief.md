# Task 2: Ràng buộc GIÁO VIÊN

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` syntax.

**Goal:** Add every hard constraint that concerns a teacher's own week, and prove
the solution passes the app's teacher validators.

**Why (Vietnamese):** Nhóm ràng buộc này là thứ khiến TKB "dùng được" chứ không
chỉ "đúng định mức": một GV không thể có mặt ở hai lớp cùng một tiết, không được
dạy quá tải trong ngày, và phải tôn trọng giờ bận đã khai báo. Bỏ sót bất kỳ cái
nào thì bộ giải sẽ vui vẻ sinh ra TKB xếp cô A dạy 2 lớp cùng lúc.

**Files:**
- Modify: `core/scheduler/cpsat_model.py` (thêm hàm `_add_teacher_constraints`, gọi từ `build_model`)
- Modify: `tests/test_cpsat_model.py`

**Interfaces:**
- Consumes: `CpSatModel.x`, `.inp`, `.slots_by_ts` (Task 1)
- Produces: `CpSatModel.teacher_of: dict[tuple[int, int], int]` — `(slot_id, subject_id) -> teacher_id`,
  dùng lại ở Task 6 (hàm mục tiêu). Lấy từ `core.scheduler.placement._build_effective_assigned_teacher(inp)`
  chứ KHÔNG dùng `inp.assigned_teacher` trực tiếp — cặp (môn, lớp) chưa phân công
  được gán id âm tổng hợp, bỏ qua bước này sẽ mất ràng buộc cho các cặp đó.

## Ràng buộc phải thêm

| # | Luật | Nguồn trong engine cũ | Cách mô hình |
|---|---|---|---|
| 1 | GV không dạy 2 lớp cùng tiết | `_feasible` qua `state.busy` | Với mỗi `ts_id`, mỗi GV: `AddAtMostOne` các biến của GV đó tại các ô cùng `ts_id` |
| 2 | GV bận (GV_Bận) | `feasibility.py:22-23`, `inp.ban_busy` | Với `(t, ts_id) in inp.ban_busy`: ép mọi biến của GV `t` tại `ts_id` = 0 |
| 3 | Trần tiết/buổi | `feasibility.py:24-25`, `config.max_periods_per_session` | Tổng biến của GV trong mỗi `(wd, session)` ≤ ngưỡng |
| 4 | Trần tiết/ngày | `feasibility.py:26-28`, `config.max_teacher_periods_per_day` | Tổng biến của GV trong mỗi `wd` ≤ ngưỡng |
| 5 | Buổi nghỉ của GV | `feasibility.py:29-30` + `teacher_off.py` | **Xem ghi chú dưới** |

**Ghi chú về buổi nghỉ (quan trọng):** `gv_off_slots` trong engine cũ được bốc
**ngẫu nhiên mỗi lượt thử** bằng `rng` — nó không phải dữ liệu đầu vào cố định.
Trong mô hình CP-SAT không có "lượt thử" nên không thể bắt chước y hệt. Cách
đúng: **để bộ giải tự chọn buổi nghỉ** — thêm biến `off[t, wd, sess]` và ràng
buộc "mỗi GV có đúng `effective_count` buổi nghỉ, không rơi vào ô bị cấm
(`forbidden_off_cells`, sáng bắt buộc, ghim riêng của GV)", rồi nối
`off[t,wd,sess] = 1 → GV không có tiết nào ở buổi đó`.

Đây là một **cải thiện chứ không phải mô phỏng**: engine cũ bốc thăm trước khi
biết gì về lịch, còn ở đây bộ giải chọn buổi nghỉ sao cho phần còn lại tối ưu —
đúng ý "buổi nghỉ chỉ là ưu tiên nếu đã thoả các điều kiện trên" mà trường đã
yêu cầu ngày 2026-09-04. Trường hiện đặt `teacher_off_sessions_per_week = 0` nên
phần này không kích hoạt, nhưng vẫn phải viết cho đúng với trường khác.

## Test

Thêm vào `tests/test_cpsat_model.py`. Fixture: 2 lớp cùng khung giờ, 1 GV dạy cả
hai lớp — nếu thiếu ràng buộc 1 thì bộ giải sẽ xếp trùng.

```python
def test_teacher_never_double_booked():
    """2 lớp, cùng 4 ô sáng T2; 1 GV dạy cả 2 lớp mỗi lớp 2 tiết. Nếu thiếu
    ràng buộc trùng giờ, bộ giải có thể xếp GV đó vào cùng ts_id ở 2 lớp."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(4)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)] + \
            [Slot(i + 5, 102, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1"), ClassRoom(102, "6A2")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 2, (1, 102): 2},
        assigned_teacher={(1, 101): 10, (1, 102): 10},
        ban_busy=set(), slots=slots, timeslots=ts, config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_teacher_conflicts
    assert find_teacher_conflicts(inp.slots, assignment, inp.assigned_teacher) == []
```

Thêm test tương tự cho: GV bận (`find_teacher_unavailability_violations`), trần
tiết/ngày (`find_teacher_day_cap_violations` với `max_teacher_periods_per_day=2`
và 4 ô để ép ràng buộc phải cắn).

- [ ] Step 1: viết 3 test trên → chạy, xác nhận FAIL
- [ ] Step 2: cài `_add_teacher_constraints`, gọi trong `build_model`
- [ ] Step 3: chạy lại → PASS
- [ ] Step 4: `python -m pytest tests/ -q` → vẫn 244 passed, 1 xpassed
- [ ] Step 5: commit `feat(cpsat): teacher conflict, busy, and load constraints`
