# Task 4 Report: Generalize the Post-Generation Hard Gate in `engine.py`

## Tổng Quan

Đã hoàn thành toàn bộ 13 bước trong `task-4-brief.md`, theo đúng from TDD
(viết test lỗi trước, xác nhận RED, implement, xác nhận GREEN). Toàn bộ 3
edit points trong `core/scheduler/engine.py` (imports, hàm helper mới, thân
vòng lặp attempt, phần dựng `ScheduleResult` cuối cùng) và 1 edit point
trong `core/scheduler/constants.py` (`NGUONG_KHOA`) đã được transcribe
chính xác theo before/after snippet trong brief — đối chiếu từng dòng, không
có sai lệch nào so với brief.

**Phát hiện quan trọng cần lưu ý ngay từ đầu:** khi đo trực tiếp 4 kịch bản
dữ liệu thật (`sample_school.xlsm`), CẢ 4/4 đều rơi vào nhánh
relaxed-fallback (không đạt full compliance với cả 4 luật hard-gate), và cả
4 đều dùng hết toàn bộ ngân sách 6000 attempts (~110-155 giây mỗi lần gọi
`sched.run()`). Xem mục "Relaxed_rules Non-Empty Scenarios" bên dưới — đây
là input quan trọng cho Task 6.

## Các Thay Đổi Thực Hiện

### 1. `core/scheduler/engine.py`

- **Imports** (Step 3): thêm `SchedulingConfig` vào import từ `core.models`;
  mở rộng import từ `core.scheduler.quality` để lấy thêm
  `_count_teacher_4_consecutive_mornings`, `_count_teacher_lone_days`,
  `_count_teacher_lone_sessions`, `_count_teacher_missing_mandatory_mornings`.
- **Hàm mới `_check_hard_post_generation_rules(inp, state, config) -> list`**
  (Step 4): đặt ngay trên `def run(...)`. Tái sử dụng các counter đã có sẵn
  trong `quality.py` (vốn dùng để tính soft penalty) làm boolean gate:
  - `_count_teacher_missing_mandatory_mornings(...) > 0` → `"II.3"`
    (buổi sáng bắt buộc bị bỏ trống ngoài ý muốn)
  - `avoid_teacher_lone_periods` bật + (`lone_sessions > 0` hoặc
    `lone_days > 0`) → `"II.4"`; `_count_teacher_split_sessions(...) > 0` →
    `"II.8"` (GV dạy sáng 1 tiết + chiều 1 tiết)
  - `avoid_teacher_4_consecutive_morning` bật +
    `_count_teacher_4_consecutive_mornings(...) > 0` → `"II.14"`
- **Khởi tạo biến theo dõi mới trước vòng lặp** (Step 6):
  `best_relaxed_assignment`, `best_relaxed_changed`, `best_relaxed_score`,
  `best_relaxed_violations`, `off_shortfall = {}`.
- **Unpack tuple từ `_assign_off_slots`** (Step 7): sửa
  `state.gv_off_slots = _assign_off_slots(...)` (lỗi cố ý để lại từ Task 2)
  thành `state.gv_off_slots, off_shortfall = _assign_off_slots(...)`.
- **Thay khối chấm điểm thành công** (Step 8): sau khi `done=True`, gọi
  `hard_gate_violations = _check_hard_post_generation_rules(inp, state, config)`.
  Nếu rỗng → tính `successes` như cũ. Nếu KHÔNG rỗng → attempt đó KHÔNG được
  tính là success (không tăng `successes`, vòng lặp tiếp tục như một
  `done=False` bình thường), nhưng được lưu lại làm ứng viên relaxed-fallback
  nếu `relaxed_score = (len(violations), teacher_penalty, cells_changed)`
  tốt hơn ứng viên relaxed hiện có.
- **Thay phần dựng kết quả cuối** (Step 9): nếu `successes == 0` nhưng có
  `best_relaxed_assignment`, trả về `success=True`,
  `successes_found=0` (trung thực: không có attempt nào compliant hoàn
  toàn), và `relaxed_rules` liệt kê các rule_id vi phạm + mục riêng cho
  `off_shortfall` (rule_id `"II.3"`, detail `"off_slot_shortfall"`) nếu có.
  Đường full-success cũng được gắn `relaxed_rules` (populated nếu có
  `off_shortfall`, rỗng nếu không).

### 2. `core/scheduler/constants.py`

- `NGUONG_KHOA`: 60 → 20, kèm comment giải thích lý do (hard gate mới khiến
  nhiều attempt đầu giống hệt fail giống hệt qua "keep old" bonus; giảm
  ngưỡng để vào chế độ exploration sớm hơn, tận dụng ngân sách `SO_LAN_THU`
  tốt hơn).

### 3. `tests/test_engine_hard_gate.py` (mới)

2 test case đúng như brief chỉ định: `test_check_hard_post_generation_rules_flags_lone_session`
(GV có 16 tiết/tuần với 1 buổi lẻ → phải bị gắn cờ `II.4`, dùng buổi sáng
3-tiết để cô lập II.4, tránh trigger II.14/II.8) và
`test_check_hard_post_generation_rules_empty_when_compliant` (không có gì
được assign → không vi phạm gì).

## Kết Quả Test

### TDD RED/GREEN cho `tests/test_engine_hard_gate.py`

**RED** (trước khi implement Step 3-4):
```
ImportError: cannot import name '_check_hard_post_generation_rules' from 'core.scheduler.engine'
```
Đúng như brief Step 2 dự đoán.

**GREEN** (sau Step 4, và lại một lần nữa sau khi wire đầy đủ vào `run()`
ở Step 5-9):
```
tests/test_engine_hard_gate.py::test_check_hard_post_generation_rules_flags_lone_session PASSED
tests/test_engine_hard_gate.py::test_check_hard_post_generation_rules_empty_when_compliant PASSED
2 passed in 0.06s / 0.08s
```

### Full-suite BEFORE (baseline tại commit `bc17022`, trước Task 4, chạy
trong 1 git worktree cô lập riêng để không đụng vào working tree đang sửa)

```
41 failed, 176 passed, 1 skipped, 1 xfailed in 35.02s (219 tests total)
```

Toàn bộ 41 lỗi đều là `AttributeError: 'tuple' object has no attribute
'get'/'items'` — đúng như mô tả: lỗi cố ý để lại từ Task 2 (call site trong
`engine.py` chưa unpack tuple mới).

### Full-suite AFTER (sau Task 4)

Do một số test end-to-end với dữ liệu thật (`sample_school.xlsm`) giờ tốn
tới ~100-155 giây/lần gọi `sched.run()` (xem phần "Relaxed_rules" bên
dưới), việc chạy `pytest tests/ -v --timeout=600` một lần duy nhất trong
phiên tương tác không khả thi (đã thử, dừng lại sau >30 phút với tiến độ
chậm và có nguy cơ bị bóp CPU do chạy chồng nhiều tiến trình). Đã chia làm
2 lần chạy sạch, không chồng chéo tiến trình (tổng cộng bao phủ đúng 221
test, không thiếu test nào):

**Lần 1 — subset nhanh** (`--ignore=tests/test_exporter.py
--ignore=tests/test_real_data_schedule.py --deselect
tests/test_mandatory_rules_compliance.py::test_full_schedule_15_criteria_compliance`):
```
11 failed, 193 passed, 1 skipped, 1 deselected in 322.42s (0:05:22)
```

**Lần 2 — subset chậm** (đúng 3 file/test vừa loại trừ ở trên, chạy riêng
để không tính giờ chờ vào subset nhanh):
```
15 passed, 1 xpassed in 1678.08s (0:27:58)
```

**Tổng hợp AFTER: 11 failed, 208 passed, 1 skipped, 1 xpassed (221 tests total)**

So sánh trước/sau:
| | Before | After |
|---|---|---|
| failed | 41 | 11 |
| passed | 176 | 208 |
| skipped | 1 | 1 |
| xfailed/xpassed | 1 xfailed | 1 xpassed |
| tổng | 219 | 221 (+2 test mới) |

30 trong số 41 lỗi cũ đã được Task 4 sửa (đúng như brief Step 11 dự đoán —
đây là các test đi qua `engine.run()`, được sửa nhờ Step 7's tuple-unpack
fix). 11 lỗi còn lại (danh sách dưới) là lỗi CŨ, TỒN TẠI TRƯỚC TASK 4 —
cùng tên test, cùng nguyên nhân gốc, xác nhận bằng cách so khớp với danh
sách 41 lỗi baseline.

### 11 lỗi còn tồn đọng (KHÔNG thuộc phạm vi Task 4 — xem "Vấn Đề/Lưu Ý")

```
tests/test_scheduler.py::test_off_slots_respect_forbidden_cells_gvcn_and_must_monday
tests/test_scheduler.py::test_teacher_pinned_full_day_off
tests/test_scheduler.py::test_teacher_pinned_afternoon_off
tests/test_scheduler.py::test_teacher_off_sessions_override
tests/test_scheduler.py::test_teacher_pinned_full_day_and_extra_afternoon_off
tests/test_scheduler.py::test_pinned_off_conflicts_with_forbidden_are_dropped
tests/test_scheduler.py::test_off_slots_unchanged_when_no_override_or_pins
tests/test_scheduler.py::test_off_slot_count_defaults_to_1_buoi_per_week
tests/test_scheduler.py::test_assign_off_slots_respects_custom_forbidden_cells_and_count
tests/test_scheduler_teacher_quality.py::test_mandatory_morning_weekdays_strictly_enforced
tests/test_scheduler_teacher_quality.py::test_teacher_lone_sessions_heavy_penalty
```

Đã đọc code của 2 trong số này để xác nhận nguyên nhân: cả 11 test đều gọi
`sched._assign_off_slots(...)` TRỰC TIẾP (không qua `engine.run()`) và
unpack kết quả như dict cũ (vd `offs.items()`, `offs[1]`), trong khi Task 2
đã đổi hàm này trả về tuple `(gv_off_slots, shortfall)`. Đây là các call
site KHÁC với call site trong `engine.py` mà Step 7 của brief này sửa — và
brief's Files section chỉ liệt kê `core/scheduler/engine.py`,
`core/scheduler/constants.py`, `tests/test_engine_hard_gate.py`, không đề
cập sửa `tests/test_scheduler.py` hay `tests/test_scheduler_teacher_quality.py`.
Theo đúng nguyên tắc "Follow the brief's file structure and edit points
exactly", tôi KHÔNG sửa các file test này. Đây là gap còn sót lại từ Task 2
chưa được brief nào giao rõ ràng — nên cờ cho Task 6 (hoặc một fix riêng
ngoài phạm vi task này).

## Relaxed_rules Non-Empty Scenarios (yêu cầu bắt buộc của brief cho Task 6)

Ngoài 2 test case mới trong `test_engine_hard_gate.py` (test đơn vị, không
sinh `ScheduleResult`), đã đo trực tiếp 4 kịch bản dữ liệu thật
(`io_excel/sample_school.xlsm`, cùng fixture các test end-to-end dùng) bằng
script standalone gọi thẳng `sched.run()` — **CẢ 4/4 đều rơi vào nhánh
relaxed-fallback**, không có kịch bản nào đạt full compliance:

| Kịch bản | attempts_tried | successes_found | relaxed_rules | Thời gian |
|---|---|---|---|---|
| config mặc định, parity=C, seed=111 (đúng scenario của `test_export_both_parities_warns_when_only_one_accepted`) | 6000/6000 | 0 | II.4, II.8, II.14 | 143.9s |
| config mặc định, parity=C, seed=2026 (đúng scenario của `test_real_data_schedules_successfully[C]`) | 6000/6000 | 0 | II.3, II.4, II.8 | 154.8s |
| config mặc định, parity=L, seed=2026 (đúng scenario của `test_real_data_schedules_successfully[L]`) | 6000/6000 | 0 | II.3, II.4, II.8, II.14 | 142.0s |
| `heavy_subjects_morning_only=True`, parity=C, seed=2026 (đúng scenario của `test_real_data_schedules_successfully_with_heavy_subjects_morning_only[C]`) | 6000/6000 | 0 | II.3, II.4, II.8, II.14 | 110.4s |

Cả 4 test tương ứng vẫn PASS trong pytest vì chúng chỉ assert
`result.success is True` (không assert `relaxed_rules == []`) — engine trả
`success=True` đúng qua nhánh relaxed-fallback (Step 9), không phải qua
full compliance thật sự. Đáng chú ý:
`test_real_data_schedules_successfully_with_heavy_subjects_morning_only[C]`
trước đây được đánh dấu `xfail` (lý do ghi trong test: "Sample school
morning capacity exact-fit in parity C") — giờ chuyển thành **XPASS**
(unexpected pass) vì nhánh relaxed-fallback mới cho phép nó trả về
`success=True` dù không đạt full compliance. XPASS không làm suite fail
(strict=False mặc định), nhưng đáng để Task 6 xem lại marker `xfail` này có
còn hợp lý không.

## Tự Kiểm Tra (Self-Review)

- **Completeness**: Cả 13 bước trong brief đã hoàn thành, đối chiếu
  line-by-line với before/after snippet — không có sai lệch.
- **Quality**: Code transcribe chính xác theo brief; không có control-flow
  nào bị diễn giải lại.
- **Discipline (YAGNI)**: Không thêm gate check hay fallback logic nào
  ngoài 4 rule brief chỉ định (II.3/II.4/II.8/II.14). Không sửa 11 test lỗi
  ngoài phạm vi (xem trên) dù có thể dễ dàng sửa — giữ đúng file scope của
  brief.
- **Testing**: Hành vi hard-gate mới được test thật (không chỉ import rồi
  bỏ đó) — 2 unit test mới + xác nhận trực tiếp bằng 4 kịch bản dữ liệu
  thật cho thấy nhánh relaxed-fallback hoạt động đúng chức năng (không bao
  giờ crash, không bao giờ treo vô hạn, luôn trả kết quả có ý nghĩa trong
  ngân sách `SO_LAN_THU=6000`).
- **Full suite**: KHÔNG pristine — 11 lỗi tồn đọng, nhưng đã xác minh đầy
  đủ là lỗi CŨ (pre-existing, giống hệt trước Task 4), nằm ngoài phạm vi
  brief này.

## Vấn Đề / Lưu Ý (Concerns)

1. **[Quan trọng] Cả 4/4 kịch bản dữ liệu thật đo được đều rơi vào
   relaxed-fallback, luôn tốn hết 6000/6000 attempts (~110-155 giây/lần
   gọi).** Đây không phải bug logic — engine hoạt động đúng thiết kế của
   brief (không crash, không treo, trả kết quả có relaxed_rules rõ ràng).
   Nhưng nó cho thấy 2 khả năng cần Task 6 profile kỹ: (a) dữ liệu
   `sample_school.xlsm` có thể thực sự KHÔNG THỂ thỏa mãn đồng thời cả 4
   luật II.3/II.4/II.8/II.14 (giới hạn cấu trúc dữ liệu thật), hoặc (b)
   heuristic tìm kiếm (greedy + repair) chưa được tinh chỉnh cho gate mới
   nên không tìm ra attempt compliant dù có thể tồn tại. Theo đúng chỉ dẫn
   của brief ("Note any NEW failures... these are expected discovery
   output for Task 6 to triage, not something to silently patch here by
   weakening the gate"), tôi KHÔNG thử nới lỏng gate hay tinh chỉnh
   heuristic — chỉ báo cáo rõ ràng.
2. **11 test lỗi tồn đọng ngoài phạm vi** (xem mục trên) — gọi trực tiếp
   `_assign_off_slots` mà không unpack tuple mới của Task 2. Cần một fix
   riêng (ngoài Task 4) để cập nhật các call site test này.
3. **Chi phí thời gian mỗi lần gọi `sched.run()` trên dữ liệu thật tăng
   đáng kể** (từ gần như tức thời trước đây — vì code cũ chấp nhận attempt
   đầu tiên `done=True` — lên tới ~100-155 giây khi rơi vào relaxed-fallback
   exhaust hết budget). Đây là hệ quả trực tiếp, có chủ đích của việc thêm
   hard gate (đúng như comment giải thích trong `NGUONG_KHOA`), nhưng là
   một cân nhắc UX/hiệu năng thực sự cho môi trường production — nên được
   Task 6 đo và quyết định có cần tối ưu thêm không.
4. **Không tìm thấy sai lệch nào giữa brief và code thực tế** — mọi
   before/after snippet trong brief khớp chính xác với nội dung
   `engine.py`/`constants.py` trước khi sửa.

## Kết Luận

Task 4 hoàn thành đúng theo brief, transcribe chính xác cả 13 bước. Cơ chế
hard-gate + relaxed-fallback hoạt động đúng thiết kế: không crash, không
treo vô hạn, luôn trả về kết quả có `relaxed_rules` minh bạch khi không đạt
full compliance. Tuy nhiên, phát hiện quan trọng nhất của task này KHÔNG
phải là bug trong code, mà là tín hiệu thực nghiệm: với fixture dữ liệu thật
hiện có, engine dường như LUÔN rơi vào relaxed-fallback (4/4 kịch bản đo
được), luôn tốn hết ngân sách attempt. Đây là input trực tiếp, cụ thể cho
Task 6 profile/triage — đúng như vai trò task 6 được giao trong
`progress.md`.

---

## Fix Round (2026-09-02, theo ruling của coordinator trong `progress.md`)

Coordinator xác nhận cả 2 concern đã báo cáo ở trên đều là vấn đề thật, ra
ruling cụ thể, và yêu cầu sửa cả 2 trước khi gửi review. Đã hoàn thành cả
2, cộng thêm 2 phát hiện phụ trong quá trình sửa (nêu rõ bên dưới).

### Fix 1: II.8 thiếu ngưỡng miễn trừ `min_weekly_periods` (lỗi trong chính brief gốc)

`core/scheduler/quality.py:_count_teacher_split_sessions` trước đây KHÔNG
có tham số miễn trừ, khác với 3 hàm chị em (`_count_teacher_lone_sessions`,
`_count_teacher_lone_days`, `_count_teacher_4_consecutive_mornings`) đều
nhận `min_weekly_periods`/`max_load_for_penalty`. Brief gốc của Task 4 gọi
hàm này KHÔNG điều kiện, khiến GV tải thấp (VD: GV môn chuyên biệt như Âm
nhạc, Tin học chỉ dạy vài lớp) bị mắc kẹt cấu trúc trong vi phạm II.8 không
thể tránh được (VD: GV chỉ có 1 tiết sáng + 1 tiết chiều/tuần).

**Đã sửa:**
1. `_count_teacher_split_sessions` nay nhận `min_weekly_periods: int = 0`
   (cùng convention/default với 3 hàm chị em), track `teacher_totals` theo
   đúng pattern các hàm kia, chỉ đếm vi phạm split-day khi
   `teacher_totals[tid] >= min_weekly_periods`.
2. `_teacher_quality_penalty` (quality.py, dòng ~139): truyền
   `min_weekly_periods=min_lone_load` vào lời gọi này — sửa luôn 1 gap tồn
   tại từ trước trong soft scoring (chưa từng ảnh hưởng vì trước đây II.8
   chỉ là soft, giờ đã hard-gate nên bug mới lộ ra).
3. `_check_hard_post_generation_rules` (engine.py): truyền cùng
   `min_weekly_periods=min_lone_load` vào lời gọi cho check II.8.
4. Xác nhận caller cũ duy nhất ngoài quality.py/engine.py
   (`tests/test_scheduler_teacher_quality.py:106`,
   `test_quality_metrics_helpers`) không truyền tham số mới (mặc định 0 =
   không miễn trừ, hành vi y hệt trước đây) — vẫn PASS.
5. Test mới `test_check_hard_post_generation_rules_split_session_respects_lone_penalty_exemption`
   trong `tests/test_engine_hard_gate.py`: xác nhận GV tải thấp (2
   tiết/tuần, 1 sáng + 1 chiều cùng ngày) KHÔNG bị gắn cờ gì cả
   (`violations == []`), còn cùng pattern split-day với GV tải >= 15
   (17 tiết/tuần) THÌ bị gắn cờ `"II.8"` (đồng thời cũng gắn `"II.4"` —
   overlap này là bản chất toán học của định nghĩa: 1 buổi split-day LUÔN
   có ít nhất 1 phía đúng-1-tiết, mà đó CHÍNH LÀ định nghĩa của
   lone-session cho II.4 — không phải bug, đã note rõ trong docstring
   test).

### Fix 2: 11 test cũ gọi trực tiếp `_assign_off_slots`, gãy vì tuple return mới

Đã sửa cả 11 test coordinator liệt kê — thuần túy unpack fix, KHÔNG đổi
assertion nào: `offs = sched._assign_off_slots(...)` →
`offs, _shortfall = sched._assign_off_slots(...)` (dùng tên `_shortfall`
vì không test nào trong 11 test này cần assert gì về shortfall — đúng như
coordinator xác nhận, đó là phạm vi của `tests/test_teacher_off.py`).

**2 phát hiện phụ trong lúc sửa (đã sửa luôn, có ghi chú rõ ràng cho
coordinator xem xét):**

1. **Tìm thấy test thứ 12 cùng loại bug, KHÔNG có trong danh sách 11 của
   coordinator**: `tests/test_scheduler.py::test_gvcn_off_slot_defaults_to_chieu_thu7_when_saturday_session_unknown`
   (dòng 537-542) cũng gọi `_assign_off_slots` và dùng `offs[1]`, nhưng test
   này TRƯỚC KHI SỬA vẫn PASS — không phải vì đúng, mà vì `offs[1]` tình cờ
   là index hợp lệ vào tuple mới (`offs[1]` = `shortfall` dict, key theo
   teacher_id), và assertion `(7, "C") not in offs[1]` vẫn đúng một cách
   tình cờ vì `(7, "C")` không bao giờ khớp key kiểu teacher_id. Đây là
   test "pass sai lý do" (false-negative tiềm ẩn). Đã sửa theo đúng pattern
   unpack như 11 test kia (rủi ro = 0, cùng bug, cùng fix, test đã PASS cả
   trước lẫn sau nên không ảnh hưởng con số "11 test được sửa" của
   coordinator).
2. **`test_teacher_lone_sessions_heavy_penalty` (test_scheduler_teacher_quality.py)
   được coordinator liệt kê trong Fix 2 nhưng THỰC RA không hề gọi
   `_assign_off_slots`** — test này gọi `sched._teacher_quality_penalty(...)`
   và fail vì lý do HOÀN TOÀN KHÁC: Task 1 (task trước, đã complete) đổi
   default `min_weekly_periods_for_lone_penalty` từ 0 lên 15, khiến fixture
   gốc của test này (GV chỉ có 1 tiết/tuần) rơi vào diện miễn trừ (pen=0
   thay vì >=750 như assert). Đây KHÔNG phải "pure unpack fix" — không có
   gì để unpack. Đã sửa bằng cách thêm
   `min_weekly_periods_for_lone_penalty=0` tường minh vào config của test
   (khôi phục đúng ý định gốc: test verify TRỌNG SỐ phạt thô 500/250, không
   phải ngưỡng miễn trừ) — đúng pattern Task 1 đã dùng để tự sửa
   `test_pick_best_scored_unbiased_with_default_config` (xem
   `progress.md` Execution Log, "Process note"). KHÔNG đổi assertion cuối
   (`assert pen >= 750`), chỉ thêm 1 dòng config + comment giải thích.

### Kết Quả Verify

Lệnh yêu cầu:
```
python -m pytest tests/test_scheduler.py tests/test_scheduler_teacher_quality.py tests/test_engine_hard_gate.py -v
```
Kết quả:
```
96 passed in 277.80s (0:04:37)
```
0 FAILED, 0 ERROR. Đã xác nhận riêng từng test trong 2 danh sách (11 test
coordinator yêu cầu + test thứ 12 phát hiện thêm) đều PASSED trong log —
không có test nào bị bỏ sót.

**Xác nhận theo đúng tiêu chí coordinator đặt ra**: 11 test coordinator
liệt kê ĐÚNG LÀ những test trước đó fail nay đã fix (10 qua unpack fix + 1
qua fix ngưỡng min_weekly_periods không liên quan tuple — xem phát hiện #2
ở trên). Không có failure MỚI nào phát sinh ngoài phạm vi 2 fix này — toàn
bộ 96 test trong 3 file mục tiêu đều xanh. (Không chạy lại full suite
chậm với dữ liệu thật theo đúng chỉ dẫn của coordinator — 2 fix này không
đụng tới code path đó.)

### Files Changed (Fix Round)

- `core/scheduler/quality.py` — `_count_teacher_split_sessions` thêm
  `min_weekly_periods`; `_teacher_quality_penalty` truyền ngưỡng vào.
- `core/scheduler/engine.py` — `_check_hard_post_generation_rules` truyền
  ngưỡng vào lời gọi II.8.
- `tests/test_engine_hard_gate.py` — thêm 1 test mới
  (`test_check_hard_post_generation_rules_split_session_respects_lone_penalty_exemption`).
- `tests/test_scheduler.py` — 10 call site unpack fix (9 theo yêu cầu + 1
  phát hiện thêm).
- `tests/test_scheduler_teacher_quality.py` — 1 call site unpack fix
  (`test_mandatory_morning_weekdays_strictly_enforced`) + 1 fix ngưỡng
  không liên quan tuple (`test_teacher_lone_sessions_heavy_penalty`).

Commit: `41d95b0` — "fix: share II.4's min_weekly_periods exemption with
II.8; repair 11 pre-existing tests broken by Task 2's tuple return"
