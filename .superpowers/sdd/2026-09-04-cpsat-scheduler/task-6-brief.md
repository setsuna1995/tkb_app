# Task 6: Hàm mục tiêu (các tiêu chí HĐSP mềm)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` syntax.

**Goal:** Turn every soft HĐSP criterion into a weighted penalty term, keeping the
exact weights and exemption semantics the current engine uses.

**Why (Vietnamese):** Đây là chỗ CP-SAT ăn đứt engine cũ: nó tối ưu **tất cả tiêu
chí cùng lúc** thay vì sửa lần lượt rồi phá lẫn nhau. Nhưng chỉ đúng nếu trọng số
và ngữ nghĩa miễn trừ được chép **chính xác** từ `quality.py` — lệch trọng số là
lặng lẽ đổi thứ tự ưu tiên của trường mà không ai nhận ra.

**Files:**
- Modify: `core/scheduler/cpsat_model.py` (`_add_objective`)
- Modify: `tests/test_cpsat_model.py`

**Interfaces:**
- Consumes: `CpSatModel.x`, `.teacher_of` (Task 2), `.role_index`
- Produces: `CpSatModel.penalty_terms: dict[str, list]` — nhóm biến phạt theo
  mã tiêu chí (`"II.3"`, `"II.4"`, ...). Task 7 dùng để sinh `relaxed_rules`.

## Biến trung gian cần dựng

Với mỗi GV `t` và mỗi buổi `(wd, sess)` thực có:
- `cnt[t, wd, sess]` : IntVar = số tiết của GV đó trong buổi
- `used[t, wd, sess]` : Bool, `cnt >= 1`
- `lone[t, wd, sess]` : Bool, `cnt == 1`

## Các số hạng phạt — trọng số lấy từ `quality.py:_teacher_quality_penalty`

| Tiêu chí | Trọng số | Nguồn | Miễn trừ phải giữ |
|---|---|---|---|
| II.4 buổi lẻ | 500 | `quality.py` | `min_weekly_periods_for_lone_penalty` **và** `lone_session_exempt_teacher_ids` |
| II.8 ngày chia lẻ | 700 | `quality.py` | như trên |
| Ngày lẻ (cả ngày 1 tiết) | 250 | `quality.py` | như trên |
| Dồn buổi lẻ vào 1 GV | `TEACHER_LONE_SESSION_SPREAD_PENALTY` (600) | `constants.py` | như trên; chỉ tính từ buổi lẻ **thứ 2 trở đi** của cùng GV |
| II.3 thiếu sáng bắt buộc | 800 | `quality.py` | `min_weekly_periods_for_mandatory_morning`; **và** `strict_morning_weekdays` áp cho mọi GV trừ BGH (`is_bgh`) |
| II.7 tiết trống giữa buổi | 350 | `quality.py` | `avoid_teacher_gaps` |
| II.14 ≥4 tiết sáng | 300 | `quality.py` | `max_load_for_penalty=20` |
| II.9 nghỉ trọn chiều | 200 | `quality.py` | `balance_afternoon_teachers` |
| GV ưu tiên nghỉ nhiều buổi | `TEACHER_COMPACT_SCHEDULE_PENALTY` (400) × số buổi đã dùng | `constants.py` | `compact_schedule_teacher_ids` |

**Mọi cờ bật/tắt trong config phải được tôn trọng** (`avoid_teacher_lone_periods`,
`avoid_teacher_gaps`, `avoid_teacher_4_consecutive_morning`,
`balance_afternoon_teachers`): tắt thì không sinh số hạng tương ứng.

**Ghi chú về II.7 (tiết trống)**: engine cũ đếm khoảng hở bằng
`span - len(periods)` (`quality.py:_count_teacher_gaps`). Trong CP-SAT dùng biến
`first`/`last` cho mỗi buổi của GV rồi phạt `last - first + 1 - cnt`.

## Test

1. **Trọng số khớp**: dựng 1 lời giải bất kỳ, tính điểm phạt bằng
   `quality.py:_teacher_quality_penalty` và bằng hàm mục tiêu của mô hình trên
   cùng lời giải đó → hai số phải bằng nhau. Đây là test giá trị nhất của task.
2. **Miễn trừ theo tên**: GV trong `lone_session_exempt_teacher_ids` có buổi lẻ
   → không sinh số hạng phạt nào cho họ.
3. **Miễn BGH ở luật strict**: GV có `role="Phó hiệu trưởng"` thiếu sáng T2
   → không bị phạt; GV thường thiếu → bị phạt.
4. **Cờ tắt**: `avoid_teacher_lone_periods=False` → không có số hạng II.4 nào.

- [ ] Step 1: viết 4 test → FAIL
- [ ] Step 2: cài `_add_objective`
- [ ] Step 3: chạy lại → PASS
- [ ] Step 4: `python -m pytest tests/ -q` → 244 passed, 1 xpassed
- [ ] Step 5: commit `feat(cpsat): HĐSP soft criteria as weighted objective`
