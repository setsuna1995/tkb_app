# Task 3: Ràng buộc MÔN HỌC

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` syntax.

**Goal:** Add every hard constraint that depends on which subject goes where, and
prove each one with its matching validator from `core/validation.py`.

**Why (Vietnamese):** Đây là nhóm luật sư phạm về môn: môn nào bắt buộc buổi
sáng, GDTC xếp tiết nào và cách nhật ra sao, môn nặng dồn bao nhiêu một buổi.
Chúng là lý do TKB "hợp lý" chứ không chỉ "hợp lệ". Mỗi luật ở đây đều đã có sẵn
một hàm thẩm định trong `core/validation.py` — dùng đúng hàm đó làm test, đừng
tự viết lại logic kiểm tra (tự kiểm tra bằng chính ràng buộc mình vừa viết thì
không chứng minh được gì).

**Files:**
- Modify: `core/scheduler/cpsat_model.py` (`_add_subject_constraints`)
- Modify: `tests/test_cpsat_model.py`

**Interfaces:**
- Consumes: `CpSatModel.x`, `.inp`, `.slots_by_class` (Task 1)
- Produces: không có interface mới; chỉ thêm ràng buộc vào model.
- Cần `role_index = resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week, inp.config.single_pair_subject_ids)`
  — lưu vào `CpSatModel.role_index` để Task 4/5/6 dùng lại, đừng gọi lại nhiều lần.

## Ràng buộc phải thêm

| # | Luật | Nguồn | Hàm thẩm định để test |
|---|---|---|---|
| 1 | Môn bắt buộc buổi sáng | `feasibility.py:44-46`, `config.morning_only_subject_ids` | `find_morning_only_violations` |
| 2 | Môn Nặng cấm buổi chiều (nếu bật) | `feasibility.py:40-41`, `heavy_subjects_morning_only` | — (kiểm bằng assert thủ công) |
| 3 | GDTC: khung tiết sáng/chiều + `gdtc_avoid_period` | `feasibility.py:31-39` | `find_invalid_gdtc_periods` |
| 4 | Môn không xếp liền ngày (gồm GDTC) | `feasibility.py:48-54`, `non_consecutive_subject_ids`, `avoid_gdtc_consecutive_days` | `find_consecutive_subject_days` |
| 5 | Môn nặng tối đa/buổi của lớp | `feasibility.py:76-79`, `max_heavy_per_session` | `find_max_heavy_violations` |
| 6 | Môn nặng không quá N tiết liên tiếp | `feasibility.py:80-91`, `max_heavy_consecutive` | — (assert thủ công) |
| 7 | Môn nặng tiết 3 chiều | `feasibility.py:42-43`, `avoid_heavy_afternoon_period3` | `find_heavy_afternoon_period3_violations` |
| 8 | Luật môn–lớp–buổi | `feasibility.py:18-21`, `inp.subject_class_allowed_cells` | `find_subject_class_rule_violations` |

## Ghi chú mô hình hoá

**Luật 4 (không liền ngày)** trong engine cũ được kiểm ở HAI nơi với ý nghĩa hơi
khác nhau: `_feasible` chặn lúc đặt, còn `engine.py:264-272` kiểm lại sau khi
xếp xong và loại cả lượt thử. Mô hình CP-SAT chỉ cần một dạng: với mỗi
(lớp, môn) và mỗi cặp ngày liền kề `wd, wd+1`, ràng buộc
`sum(biến ngày wd) + sum(biến ngày wd+1) <= 1`. Lưu ý cặp ngày phải lấy từ các
ngày **thực có trong khung của lớp đó**, không phải `range(2, 8)` cứng — lớp
không học Thứ 7 thì Thứ 6 và Thứ 7 không phải "liền kề" theo nghĩa này.

**Luật 6 (nặng liên tiếp)** dùng cửa sổ trượt: với mỗi (lớp, ngày, buổi) và mỗi
vị trí bắt đầu `w`, ràng buộc tổng số biến môn nặng trong cửa sổ
`[w, w + max_heavy_consecutive]` ≤ `max_heavy_consecutive`. Đối chiếu với
`feasibility.py:80-91` để lấy đúng độ dài cửa sổ (`window = max_heavy_consecutive + 1`).

**Luật 8** là ràng buộc cấm cứng: nếu `(subject_id, class_id)` có danh sách ô
cho phép thì mọi ô ngoài danh sách bị ép = 0. `None`/thiếu khoá = không ràng buộc.

## Test

Mỗi luật một test, dùng fixture nhỏ nhất ép được luật đó cắn, và assert bằng hàm
thẩm định tương ứng ở cột cuối bảng trên. Ví dụ cho luật 3:

```python
def test_gdtc_respects_allowed_periods():
    """GDTC chỉ được tiết 1-4 sáng. Cho lớp 5 ô sáng (tiết 1-5) và cần đúng
    1 tiết GDTC -> bộ giải không được chọn tiết 5."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(5)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "GDTC", ROLE_GDTC), Subject(2, "HDTN", ROLE_HDTN),
                Subject(3, "Toan", ROLE_THUONG)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV")],
        need={(1, 101): 1, (3, 101): 4},
        assigned_teacher={(1, 101): 10, (3, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(gdtc_morning_allowed_periods=(1, 2, 3, 4)),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_invalid_gdtc_periods
    assert find_invalid_gdtc_periods(inp.slots, assignment, inp.subjects, inp.config) == []
```

- [ ] Step 1: viết 8 test (mỗi luật 1) → chạy, xác nhận FAIL
- [ ] Step 2: cài `_add_subject_constraints`
- [ ] Step 3: chạy lại → PASS toàn bộ
- [ ] Step 4: `python -m pytest tests/ -q` → vẫn 244 passed, 1 xpassed
- [ ] Step 5: commit `feat(cpsat): subject placement constraints`
