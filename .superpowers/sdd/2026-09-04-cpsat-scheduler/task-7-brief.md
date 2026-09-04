# Task 7: Giữ nguyên tiết cũ + dựng `ScheduleResult`

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` syntax.

**Goal:** Add change-minimisation as an objective term and produce a
`ScheduleResult` byte-compatible with what `run()` returns today.

**Why (Vietnamese):** Trường xếp lại TKB giữa năm thì việc **giữ nguyên tiết cũ**
quan trọng gần bằng chất lượng lịch — đổi 200 ô để đẹp hơn 1 chút là không dùng
được. Engine cũ có sẵn cơ chế này (`slot.old_subject_id` + điểm thưởng khổng lồ
`1_000_000` trong `heuristics.py`), mô hình mới phải giữ.

`ScheduleResult` là hợp đồng với toàn bộ giao diện: `assignment`, `cells_changed`,
`successes_found`, `relaxed_rules` đều đang được trang xếp TKB dùng để hiển thị
và **chặn nút Lưu**. Sai kiểu dữ liệu ở đây là hỏng giao diện.

**Files:**
- Modify: `core/scheduler/cpsat_model.py` (`_add_change_minimisation`, `build_result`)
- Modify: `tests/test_cpsat_model.py`

**Interfaces:**
- Consumes: `CpSatModel.penalty_terms` (Task 6), `solve()` (Task 1)
- Produces:
  - `build_result(built, solver) -> ScheduleResult` — dựng kết quả từ một lời
    giải đã có.
  - `solve_to_result(built, time_limit_s: float = 30.0) -> ScheduleResult | None`
    — **đây là cửa vào duy nhất mà `engine.py` gọi ở Task 8**: giải rồi dựng
    kết quả trong một bước, trả `None` khi không giải được để caller fallback.
    Task 1 để lộ `solve()` trả dict thô, tiện cho test; `engine.py` không dùng
    trực tiếp mà đi qua hàm này.

## Nội dung

**Giữ nguyên tiết cũ**: với mỗi ô có `slot.old_subject_id is not None`, thêm biến
`changed[slot_id]` = 1 khi ô không mang đúng môn cũ. Phạt `changed` với trọng số
**lớn hơn tổng mọi số hạng HĐSP cộng lại** để tái hiện ý nghĩa "ưu tiên tuyệt
đối" của `1_000_000` trong engine cũ — nhưng không dùng số quá lớn gây tràn/chậm;
tính trọng số = (tổng trọng số HĐSP tối đa có thể) + 1.

**`build_result`** phải trả:
- `assignment`: `{slot_id: subject_id | None}` — **mọi** slot_id đều có mặt, ô
  trống mang `None` (không phải `-1`; engine cũ đã quy đổi `-1 → None` trước khi
  trả, xem `engine.py:318-320`).
- `cells_changed`: đếm ô khác `old_subject_id`, cùng công thức `engine.py:275-281`.
- `cells_total`: `len(inp.slots)`.
- `successes_found`: `1` nếu tổng phạt HĐSP = 0 (tương đương "phương án tuân thủ
  hoàn toàn"), `0` nếu > 0 → giao diện sẽ hiện cảnh báo nới lỏng thay vì báo
  thành công. Ngữ nghĩa này phải khớp `engine.py:285-306`.
- `relaxed_rules`: `[{"rule_id": "II.4"}, ...]` cho mọi tiêu chí có số hạng phạt
  > 0, lấy từ `penalty_terms` của Task 6. Chỉ gồm các mã đang là hard-gate
  (`core/rules_registry.py:HARD_POST_GENERATION_IDS`) để khớp với thứ giao diện
  dùng chặn lưu.
- `attempts_tried`: `1` (bộ giải không có khái niệm "lượt thử").

## Test

1. Ô có `old_subject_id` và vẫn hợp lệ → lời giải giữ nguyên môn cũ.
2. `cells_changed` khớp với đếm thủ công.
3. Lời giải hoàn hảo → `successes_found == 1`, `relaxed_rules == []`.
4. Lời giải có buổi lẻ → `successes_found == 0` và `"II.4" in relaxed_rules`.
5. `assignment` chứa đủ mọi `slot_id`, ô trống là `None` chứ không phải `-1`.

- [ ] Step 1: viết 5 test → FAIL
- [ ] Step 2: cài `_add_change_minimisation` + `build_result`
- [ ] Step 3: chạy lại → PASS
- [ ] Step 4: `python -m pytest tests/ -q` → 244 passed, 1 xpassed
- [ ] Step 5: commit `feat(cpsat): change minimisation and ScheduleResult mapping`
