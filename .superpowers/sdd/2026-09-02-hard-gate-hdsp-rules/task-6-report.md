# Task 6 Report: End-to-End Assertions, Regression Fixtures & Profiling

## Tổng Quan

Đã hoàn thành các bước 1-8 của `task-6-brief.md`: mở rộng test end-to-end
hiện có để assert rằng mọi vi phạm II.3/II.4/II.8/II.14 trên dữ liệu thật
đều được engine tự tránh HOẶC báo cáo minh bạch qua `relaxed_rules` (Step 1-2);
điều tra sâu nguyên nhân II.4 vẫn bị vi phạm dù đã có ngưỡng miễn trừ
(Step 2b — phần quan trọng nhất của task này); viết + chạy 2 test hồi quy
cho đúng 2 bug gốc người dùng báo cáo ngày 2026-09-02 (Step 3-4); đo hiệu
năng 3 lần chạy trên dữ liệu thật và xem xét lại `NGUONG_KHOA` (Step 5);
chạy lại toàn bộ test suite (Step 6); và commit (Step 7).

**Không đụng vào bất kỳ file thuật toán nào** (`engine.py`, `heuristics.py`,
`feasibility.py`, `quality.py`, `swaps.py`, `blocks.py`, `teacher_off.py`,
`placement.py`, `state.py`, `constants.py`) — đúng theo giới hạn phạm vi của
task. `NGUONG_KHOA` được cân nhắc lại ở Step 5 nhưng kết luận là KHÔNG cần
đổi (xem chi tiết).

## Step 1-2: Mở rộng test end-to-end + kết quả chạy

Đã mở rộng `tests/test_mandatory_rules_compliance.py::test_full_schedule_15_criteria_compliance`
đúng theo before/after snippet của brief: thêm import 5 finder mới từ
`core.validation`, và chèn khối assertion 9-12 (II.3/II.4/II.8/II.14) ngay
trước `connection.close()` — không có sai lệch so với brief.

**Kết quả chạy** (`pytest tests/test_mandatory_rules_compliance.py::test_full_schedule_15_criteria_compliance -v --timeout=600`):

```
1 passed in 114.56s (0:01:54)
```

PASS — nhưng đây là **PASS qua nhánh relaxed-fallback**, không phải full
compliance. Xác nhận bằng script chẩn đoán độc lập tái tạo đúng scenario này
(`parity="L", seed=2026`, cùng config — `run()` là deterministic theo seed
nên tái tạo chính xác kết quả pytest đã chạy):

```
success=True relaxed_rules=[{'rule_id': 'II.3'}, {'rule_id': 'II.4'}]
attempts=6000 successes=0 elapsed=114.7s
```

`successes_found=0` xác nhận: **không có attempt nào trong 6000 attempt đạt
full compliance** — đúng như phát hiện của Task 4, nhưng có 1 điểm khác biệt
đáng chú ý: Task 4's bảng đo gốc cho đúng scenario này (`parity=L, seed=2026,
config mặc định`) từng ghi nhận `relaxed_rules = [II.3, II.4, II.8, II.14]`
(4 luật). Sau fix round của Task 4 (thêm ngưỡng miễn trừ `min_weekly_periods`
cho `_count_teacher_split_sessions`, tức II.8), lần đo lại này của Task 6 chỉ
còn `[II.3, II.4]` — **II.8 và II.14 không còn bị vi phạm ở scenario này**.
Đây là tín hiệu tốt (fix round của Task 4 có tác dụng thật, không chỉ về mặt
lý thuyết), nhưng tôi không khẳng định fix đó là nguyên nhân TRỰC TIẾP loại
bỏ II.14 (không có liên hệ logic giữa 2 luật) — nhiều khả năng do chuỗi RNG
tiêu thụ khác đi (unpack tuple mới của `_assign_off_slots`, ngưỡng
`NGUONG_KHOA` v.v. đều đổi giữa 2 lần đo) khiến tập "best relaxed attempt"
tìm được khác đi. Dù vậy, kết luận cốt lõi của Task 4 vẫn đúng:
**dữ liệu thật KHÔNG đạt full compliance với cả 4 luật hard-gate, luôn tốn
hết 6000/6000 attempts.**

## Step 2b: Chẩn đoán nguyên nhân II.4 vẫn bị vi phạm dù đã có ngưỡng miễn trừ

Đây là phần quan trọng nhất của task. Tôi lấy `result`/`inp` từ script chẩn
đoán độc lập nói trên (`parity="L", seed=2026`, cùng config với test) và:

1. Gọi trực tiếp `find_teacher_lone_session_violations` +
   `find_teacher_lone_day_violations` → chỉ 2 giáo viên bị vi phạm:
   **teacher_id=7 (Thành)** và **teacher_id=11 (Trung)**.
   ```
   lone_sessions: (7, 3, 'S'), (7, 6, 'S'), (11, 6, 'S')
   lone_days:     (7, 3),      (7, 6),      (11, 6)
   ```
   (mã thứ trong hệ này: 3=Thứ 3/Tuesday, 6=Thứ 6/Friday — xem
   `core/models.py` `WEEKDAY_NAMES`.)

2. Tính tổng tải tuần (`inp.need`) cho cả 2 GV này, so với ngưỡng miễn trừ
   `min_weekly_periods_for_lone_penalty=15`:

   | GV | weekly_need_total | actual_assigned | ngưỡng miễn trừ | EXEMPT? |
   |---|---|---|---|---|
   | 7 (Thành) | **15** | 15 | 15 | **False** |
   | 11 (Trung) | **15** | 15 | 15 | **False** |

   **Cả 2 GV đều đúng bằng 15 — nằm NGAY TẠI ranh giới ngưỡng, không phải
   dưới ngưỡng.** Vì điều kiện miễn trừ trong `_count_teacher_lone_sessions`/
   `_count_teacher_lone_days`/finder tương ứng dùng `>= min_weekly_periods`
   để tính là "phải áp dụng phạt" (tức chỉ miễn trừ khi `< 15` thực sự), 2 GV
   tải đúng 15 tiết/tuần KHÔNG được miễn trừ — đây là hành vi ĐÚNG theo định
   nghĩa ngưỡng (`min_weekly_periods_for_lone_penalty: int = 15  # miễn trừ
   GV có tải < ngưỡng này`), không phải bug. **Kết luận thứ nhất: ngưỡng miễn
   trừ hoạt động chính xác — đây không phải lỗi trong logic
   `_count_teacher_lone_sessions`/`_count_teacher_lone_days` hay gate wiring
   của `engine.py`.** Câu hỏi Task 4 để lại ("ngưỡng miễn trừ có bug không,
   hay đây là giới hạn dữ liệu thật") được trả lời dứt khoát: KHÔNG có bug ở
   ngưỡng miễn trừ.

3. Kiểm tra chi tiết cơ cấu tải của 2 GV này (breakdown theo (môn, lớp,
   số tiết/tuần) và lịch đã xếp thực tế):

   **GV Thành (id=7), 15 tiết/tuần, dạy 9 cặp (môn, lớp) khác nhau:**
   ```
   Ngữ văn — 7A5: 4 tiết
   Lịch sử — 7A4: 2 tiết      Lịch sử — 7A5: 1 tiết
   Lịch sử — 8A5: 2 tiết      Lịch sử — 8A6: 1 tiết
   Lịch sử — 9A5: 2 tiết      Lịch sử — 9A6: 1 tiết
   Nội dung GD địa phương — 9A5: 1 tiết
   Nội dung GD địa phương — 9A6: 1 tiết
   ```
   5 trong 9 cặp chỉ có ĐÚNG 1 tiết/tuần. Lịch đã xếp (nhóm theo buổi):
   ```
   T2 chiều: 3 tiết (Lịch sử 7A4, 7A5, 8A6)      T2 sáng: 2 tiết (Văn 7A5, Lịch sử 8A5)
   T3 sáng: 1 tiết (Văn 7A5)                      <- LẺ
   T4 chiều: 2 tiết (NDGDDP 9A6, Lịch sử 9A6)     T4 sáng: 3 tiết (Lịch sử 8A5, 9A5; NDGDDP 9A5)
   T5 sáng: 3 tiết (Văn 7A5, Lịch sử 7A4, 9A5)
   T6 sáng: 1 tiết (Văn 7A5)                      <- LẺ
   ```
   5/7 buổi được thuật toán ghép thành công (2-3 tiết/buổi, không lẻ). Chỉ
   2/7 buổi (T3 sáng, T6 sáng) còn lẻ — cả 2 đều là 1 trong 4 tiết Ngữ văn
   7A5 (môn này KHÔNG được cấu hình `single_pair_subject_ids` trong test nên
   4 tiết/tuần được xếp thành 4 tiết đơn độc lập, không ghép cặp).

   **GV Trung (id=11), 15 tiết/tuần, dạy Ngoại ngữ cho ĐÚNG 5 lớp, mỗi lớp
   3 tiết/tuần (6A6, 7A4, 7A5, 8A5, 8A6):**
   ```
   T2 chiều: 2, T2 sáng: 2, T3 chiều: 2, T3 sáng: 3, T4 sáng: 2, T5 sáng: 3,
   T6 sáng: 1 (Ngoại ngữ 8A5)                     <- LẺ (duy nhất)
   ```
   Chỉ 1/7 buổi lẻ — tiết Ngoại ngữ thứ 3 của lớp 8A5 (3 tiết/tuần trải trên
   T3 chiều, T5 sáng, T6 sáng — không trùng buổi với tiết nào khác của
   chính GV Trung).

   **Nhận định:** cả 2 trường hợp đều KHÔNG phải "1 tiết/tuần dư ra không
   thể tránh" theo kiểu số học đơn giản (như 1 lớp x môn lẻ tiết) — thuật
   toán ĐÃ ghép thành công phần lớn (5/7 và 6/7 buổi), cho thấy cơ chế
   `_repair_teacher_lone_sessions` (evacuate + consolidate, `swaps.py`) hoạt
   động và có tác dụng thật. Vấn đề chỉ còn sót lại ở 1-2 buổi/tuần/GV.

## Đánh giá: giới hạn dữ liệu thật hay khoảng trống thuật toán?

Tôi không tìm được bằng chứng dứt khoát cho cả 2 phía, nên báo cáo trung
thực cả hai khả năng thay vì khẳng định một chiều:

**Bằng chứng nghiêng về "cơ cấu dữ liệu thật sự khó" (structural):**
- Cả 2 GV đều dạy nhiều môn/lớp khác nhau với số tiết rất nhỏ mỗi cặp
  (GV Thành: 5/9 cặp chỉ 1 tiết/tuần; GV Trung: 5 lớp × 3 tiết đều nhau) —
  đặc trưng thực tế của GV chuyên trách môn phụ dạy nhiều lớp (Lịch sử,
  GD địa phương, Ngoại ngữ), không phải lỗi nhập liệu.
- Lịch của mỗi GV là KẾT QUẢ GIÁN TIẾP của 5-6 thời khoá biểu LỚP khác nhau
  được xếp độc lập (mỗi lớp có ràng buộc riêng: khối ghép môn Kép, quota
  môn khác, GV khác). Muốn dồn 1 tiết lẻ của GV Thành vào buổi khác, phải
  tìm được 1 ô trống HOẶC 1 cặp hoán đổi khả thi đồng thời cho CẢ lớp nguồn
  và lớp đích — không chỉ phụ thuộc vào GV này.
- Ngữ văn 7A5 (4 tiết/tuần) không được cấu hình `single_pair_subject_ids`
  trong config của test này → xếp thành 4 tiết đơn độc lập trên 4 ngày khác
  nhau, tăng số "đơn vị lẻ" cần ghép cho GV Thành.

**Bằng chứng nghiêng về "thuật toán tìm kiếm có thể làm tốt hơn":**
- Vi phạm chỉ còn sót lại RẤT ÍT (1-2 buổi/tuần/GV, trên tổng 7 buổi) sau
  khi phần lớn đã ghép thành công — cho thấy không gian giải pháp không quá
  chật, chỉ là bước ghép cuối cùng chưa tìm ra.
- `_repair_teacher_lone_sessions` (`core/scheduler/swaps.py`) chỉ thực hiện
  hoán đổi 1-đổi-1 (evacuate: đổi vị trí trong CÙNG lớp; consolidate: đổi
  1 tiết ở lớp khác vào buổi lẻ), tối đa 3 vòng lặp, và dừng ở hoán đổi ĐẦU
  TIÊN khả thi tìm được (`if improved: break`) — không thử hoán đổi 3 bước
  (chain swap) khi hoán đổi 1 bước bị chặn ở cả 2 phía. Tôi không loại trừ
  khả năng tồn tại 1 chuỗi hoán đổi 2-3 bước khả thi mà cơ chế hiện tại
  không thử tới.
- Xuyên suốt 6000 attempt (với việc xáo trộn thứ tự timeslot sau attempt 20
  theo `NGUONG_KHOA`), CHÍNH XÁC 2 GV này vẫn là ứng viên "relaxed" tốt nhất
  được giữ lại — nhất quán với cả giả thuyết "tường cấu trúc thật" lẫn giả
  thuyết "thuật toán luôn mắc kẹt ở cùng 1 dạng cục bộ tối ưu."

**Tôi KHÔNG tìm ra một hoán đổi cụ thể (X, Y) chứng minh được resolve được
mà không phá vỡ ràng buộc nào khác** — để làm vậy cần dựng lại toàn bộ thời
khoá biểu của 6 lớp liên quan (7A4, 7A5, 8A5, 8A6, 9A5, 9A6 cho GV Thành) và
xác nhận tồn tại 1 chuỗi hoán đổi hợp lệ, việc này vượt quá ngân sách thời
gian của bước chẩn đoán (đã đo: mỗi lần chạy `sched.run()` trên dữ liệu thật
tốn ~115s, không có cách nào rẻ hơn để thử-sai). Theo đúng hướng dẫn của
brief ("nếu không thể kết luận chắc chắn, báo cáo 'không kết luận được' còn
tốt hơn ép ra 1 câu trả lời sai") — **kết luận của tôi ở đây là NGHIÊNG NHẸ
về khả năng (b): thuật toán tìm kiếm hiện tại (đặc biệt là
`_repair_teacher_lone_sessions`'s single-swap-only strategy) NHIỀU KHẢ NĂNG
có thể làm tốt hơn nếu được tăng cường (chain swap nhiều bước, hoặc một
bước "gom bó" (bin-packing) các cặp (môn,lớp) tải thấp của cùng 1 GV TRƯỚC
khi xếp greedy theo từng lớp), nhưng đây là suy luận có cơ sở, KHÔNG phải
bằng chứng đã được xác minh trực tiếp.** Đề xuất cho công việc tiếp theo
(không thực hiện trong task này, đúng theo giới hạn phạm vi "không sửa
thuật toán tìm kiếm"):
1. Mở rộng `_repair_teacher_lone_sessions` để thử hoán đổi chuỗi 2-3 bước
   khi hoán đổi 1 bước thất bại ở cả 2 chiến lược hiện có.
2. Cân nhắc thêm 1 bước tiền xử lý: gom các cặp (môn, lớp) có `n` tiết/tuần
   rất nhỏ (1-2 tiết) của CÙNG 1 GV lại thành ưu tiên xếp chung buổi ngay từ
   giai đoạn greedy, thay vì chỉ dựa vào điểm thưởng mềm
   (`TEACHER_SESSION_PAIR_BONUS`) và repair hậu kỳ.
3. Không nên hạ ngưỡng `min_weekly_periods_for_lone_penalty` xuống dưới 15
   để "miễn trừ" 2 GV này — họ có tải công việc bình thường (15 tiết/tuần,
   không phải GV bán thời gian), hạ ngưỡng sẽ vô hiệu hoá luật II.4 cho
   nhiều GV có tải tương tự trên toàn trường, không giải quyết gốc vấn đề.

**Ghi chú thêm (II.3, ngoài phạm vi chính của Step 2b nhưng đo được sẵn từ
cùng lần chạy):** vi phạm II.3 trong scenario Step 2/2b thuộc về GV
teacher_id=14 (Khu — thiếu sáng bắt buộc Thứ 2 và Thứ 5) và teacher_id=16
(Hồng — thiếu sáng bắt buộc Thứ 2). Đây là dạng vi phạm KHÁC hẳn II.4 (không
phải "1 tiết lẻ", mà là "trống hẳn 1 buổi sáng bắt buộc do phân bổ lớp tình
cờ không rơi vào ngày đó") — brief chỉ yêu cầu điều tra sâu II.4 nên tôi
không mở rộng phân tích II.3 ở đây, chỉ ghi nhận 2 tên/GV cụ thể để không bỏ
sót dữ liệu đã thu thập được.

## Step 3-4: Test hồi quy cho 2 bug gốc (2026-09-02)

Đã tạo `tests/test_regression_hard_gate_2026_09_02.py` đúng theo nội dung
brief cung cấp — không sửa đổi gì so với snippet gốc (đã xác nhận khớp với
signature thực tế của `_assign_off_slots` trong `core/scheduler/teacher_off.py`
trước khi ghi file).

**Kết quả chạy** (`pytest tests/test_regression_hard_gate_2026_09_02.py -v --timeout=600`):

```
tests/test_regression_hard_gate_2026_09_02.py::test_off_slot_shortfall_is_reported_not_silently_dropped PASSED [ 50%]
tests/test_regression_hard_gate_2026_09_02.py::test_full_schedule_never_silently_drops_lone_session_violations PASSED [100%]
======================== 2 passed in 116.74s (0:01:56) ========================
```

Cả 2 PASS. `test_off_slot_shortfall_is_reported_not_silently_dropped` xác
nhận bug gốc #1 (shortfall bị nuốt âm thầm) đã được Task 2 sửa đúng — GV
Hiệu trưởng xin nghỉ 5 buổi nhưng chỉ còn 4 ô hợp lệ (mọi buổi sáng bị cấm
theo vai trò BGH + 2 buổi chiều T5/T6 bị khoá cứng) → `shortfall[1] = (4, 5)`
được báo cáo đúng, không bị âm thầm cắt còn 4 mà không dấu vết.
`test_full_schedule_never_silently_drops_lone_session_violations` xác nhận
bug gốc #2 (repair GV lẻ tiết không được verify) — chạy trên dữ liệu thật,
tìm thấy đúng các vi phạm lẻ tiết của GV Thành/Trung (giống Step 2b) và xác
nhận `"II.4"` LUÔN có mặt trong `relaxed_rules` khi có vi phạm còn sót —
không có trường hợp "câm" nào.

## Step 5: Đo hiệu năng dữ liệu thật + xem xét `NGUONG_KHOA`

Chạy đúng script ad-hoc brief cung cấp (`parity="L", seed=2026`, KHÔNG gọi
`repo.set_scheduling_config` — dùng nguyên config mặc định của DB), lặp lại
3 lần liên tiếp trong 1 tiến trình (không chạy song song với việc nào khác
để không làm sai lệch phép đo thời gian):

```
run 1/3: success=True relaxed=4 attempts=6000 successes=0 elapsed=102.5s
run 2/3: success=True relaxed=4 attempts=6000 successes=0 elapsed=102.4s
run 3/3: success=True relaxed=4 attempts=6000 successes=0 elapsed=101.6s
```

**Khoảng thời gian đo được: 101.6s – 102.5s** (chênh lệch <1s giữa 3 lần —
hợp lý vì seed=2026 cố định khiến toàn bộ 6000 attempt là deterministic,
chênh lệch nhỏ chỉ do nhiễu hệ thống/CPU, không phải do thuật toán). **Cả 3
lần đều nằm SÂU dưới ngưỡng "~5 phút" brief đặt ra** (101-103s ≈ 1.7 phút,
chưa bằng 1/3 ngưỡng cảnh báo) → **không có regression về hiệu năng, không
cần tăng `NGUONG_KHOA`.** Giữ nguyên giá trị Task 4 đã chọn (`NGUONG_KHOA=20`,
`core/scheduler/constants.py:8`) — **không sửa file này.**

**Phát hiện phụ quan trọng (không phải bug của Task 6, nhưng cần nói rõ để
báo cáo trung thực và không tự mâu thuẫn):** script Step 5 này báo
`relaxed=4` (khớp với 4 luật II.3/II.4/II.8/II.14 trong bảng đo GỐC của
Task 4), trong khi Step 2/2b lại chỉ thấy `relaxed_rules=[II.3, II.4]` (2
luật) cho CÙNG parity/seed. Nguyên nhân: 2 lần đo dùng 2 cách khởi tạo
config KHÁC NHAU tinh vi:
- Step 2/2b (và chính test `test_full_schedule_15_criteria_compliance`) gọi
  `repo.set_scheduling_config(connection, SchedulingConfig(...))` với 1 số
  cờ được set tường minh — các trường KHÔNG được truyền (vd
  `morning_only_subject_ids`) nhận default của dataclass = `frozenset()`
  (rỗng, không môn nào bị khoá cứng buổi sáng).
- Step 5's script (đúng nguyên văn brief) KHÔNG gọi `set_scheduling_config`
  → `repo.get_scheduling_config()` (`data/repositories/config.py:152-158`)
  chạy nhánh "chưa từng lưu config" và **TỰ ĐỘNG tính `morning_only_subject_ids`
  = tập hợp mọi môn có tên chứa "Toán" hoặc "Ngữ văn"/"Văn"** — tức mặc định
  DB coi Toán + Ngữ văn là môn bắt buộc buổi sáng, một policy mặc định hợp
  lý về sư phạm nhưng KHÔNG được set lại nếu người gọi tự dựng
  `SchedulingConfig()` tường minh rồi lưu đè.

  Nói cách khác: **gọi `set_scheduling_config(conn, SchedulingConfig(...))`
  với BẤT KỲ tập tham số tường minh nào (kể cả khi mọi giá trị "trùng
  default") sẽ ÂM THẦM xoá bỏ heuristic Toán/Văn-buổi-sáng mặc định của DB
  mới**, vì trường đó rơi vào default rỗng của dataclass thay vì nhánh
  auto-detect của `get_scheduling_config`. Đây là 1 sự KHÔNG NHẤT QUÁN có
  sẵn từ trước trong `data/repositories/config.py` (không thuộc phạm vi
  tính năng II.3/II.4/II.8/II.14 của feature này, và `config.py` không nằm
  trong Files section của brief Task 6) — tôi KHÔNG sửa, chỉ ghi nhận làm
  khuyến nghị theo dõi. Cả 2 kịch bản đo được đều xác nhận đúng kết luận cốt
  lõi của Task 4: dữ liệu thật luôn rơi vào relaxed-fallback, luôn tốn hết
  6000/6000 attempts, bất kể chi tiết config nào trong 2 biến thể trên.

## Step 6: Kết quả full test suite cuối cùng

Theo đúng gợi ý của brief ("breaking your investigation into smaller
targeted runs rather than one monolithic script"), và theo tiền lệ Task 4
đã dùng (chạy `pytest tests/ -v --timeout=900` một lần duy nhất từng bị
huỷ sau >30 phút vì tiến độ chậm/nguy cơ tranh chấp CPU), tôi chia thành
4 lần chạy KHÔNG chồng lấn (không có test nào chạy 2 lần với rủi ro che
giấu lỗi, không có test nào bị bỏ sót):

| Lần chạy | Phạm vi | Kết quả |
|---|---|---|
| 1 — subset nhanh | toàn bộ `tests/` TRỪ `test_exporter.py`, `test_real_data_schedule.py`, và 2 test nặng bị deselect (đã chạy riêng ở Step 2 & 4) | `212 passed, 1 skipped, 2 deselected in 209.06s` |
| 2 — Step 2 | `test_mandatory_rules_compliance.py::test_full_schedule_15_criteria_compliance` | `1 passed in 114.56s` (đã báo cáo ở trên) |
| 3 — Step 4 | `test_regression_hard_gate_2026_09_02.py` (2 test) | `2 passed in 116.74s` (đã báo cáo ở trên) |
| 4 — subset chậm còn lại | `test_exporter.py` (9 test) + `test_real_data_schedule.py` (6 test) | `14 passed, 1 xpassed in 1031.21s (0:17:11)` |

**Tổng hợp KHÔNG trùng lặp (mỗi test tính đúng 1 lần — test
`test_off_slot_shortfall_is_reported_not_silently_dropped` xuất hiện ở cả
lần 1 và lần 3 nên chỉ tính 1 lần theo lần 1):**

```
230 test tổng cộng (khớp `pytest --collect-only`)
228 passed
1 skipped   (`tests/test_weekly_scheduling_integration.py::test_build_scheduling_input_week_no`
             -- skip vì thiếu file `schools/truong-thcs.db` cục bộ, môi trường-phụ thuộc,
             không liên quan tính năng này, xác nhận bằng `pytest -rs`)
1 xpassed   (tests/test_real_data_schedule.py::test_real_data_schedules_successfully_with_heavy_subjects_morning_only[C]
             -- xem "Vấn đề/Khuyến nghị" bên dưới)
0 failed
```

**Không có test nào FAIL** — toàn bộ 230 test của suite đều xanh (pass hoặc
xpass/skip có chủ đích), bao gồm cả 2 test mới của Task 6 lẫn toàn bộ test
của Task 1-5. Không phát hiện lỗi mới nào phát sinh từ thay đổi của Task 6.

## Files Changed

- `tests/test_mandatory_rules_compliance.py` — mở rộng
  `test_full_schedule_15_criteria_compliance` (import 5 finder mới + khối
  assertion 9-12).
- `tests/test_regression_hard_gate_2026_09_02.py` — file mới, 2 test hồi quy.
- `core/scheduler/constants.py` — **KHÔNG sửa** (đã cân nhắc ở Step 5,
  `NGUONG_KHOA=20` của Task 4 vẫn tốt, thời gian đo được 101-117s nằm sâu
  dưới ngưỡng 5 phút, không có cơ sở để tăng).

Không file thuật toán nào khác (`engine.py`, `heuristics.py`,
`feasibility.py`, `quality.py`, `swaps.py`, `blocks.py`, `teacher_off.py`,
`placement.py`, `state.py`) bị đụng tới — đúng giới hạn phạm vi của task.

## Tự Kiểm Tra (Self-Review)

- **Completeness**: Cả 8 bước của brief đã hoàn thành, kể cả Step 2b (bước
  chẩn đoán quan trọng nhất) — không bỏ qua hay làm hời hợt.
- **Discipline (không đụng thuật toán)**: `git diff --stat` xác nhận chỉ 1
  file bị sửa (`tests/test_mandatory_rules_compliance.py`, +23 dòng) và 1
  file mới (`tests/test_regression_hard_gate_2026_09_02.py`) trước khi
  commit. Không file nào trong `core/scheduler/` bị đụng tới, kể cả
  `constants.py` (quyết định giữ nguyên `NGUONG_KHOA=20` sau khi đo, không
  phải bỏ qua bước cân nhắc).
- **Testing quality**: Cả 2 test mới trong Step 1 và Step 3 đều assert hành
  vi CỤ THỂ (không phải chỉ "chạy không crash") — Step 1's assertion sẽ FAIL
  thật nếu có vi phạm không được báo cáo qua `relaxed_rules` (đã tự kiểm
  chứng logic bằng cách đối chiếu từng dòng brief trước khi ghi file, và xác
  nhận cả 2 lần chạy độc lập cho cùng kết quả nhất quán).
- **Trung thực trong chẩn đoán (Step 2b)**: nêu tên/số liệu cụ thể (GV
  Thành id=7, GV Trung id=11, breakdown 9 cặp môn/lớp, lịch xếp chi tiết
  từng buổi) thay vì chỉ nói "có thể do dữ liệu". Trình bày CẢ 2 khả năng
  (structural vs algorithm gap) với bằng chứng cho từng bên, không ép ra 1
  kết luận không có cơ sở — kết luận cuối "nghiêng nhẹ" có ghi rõ đây là suy
  luận, không phải đã xác minh trực tiếp.
- **Phát hiện phụ**: phát hiện sự không nhất quán trong
  `data/repositories/config.py`'s `morning_only_subject_ids` auto-detect
  (Toán/Văn) bị mất khi caller tự dựng `SchedulingConfig()` tường minh — ghi
  nhận rõ ràng thay vì bỏ qua sự khác biệt 2-vs-4 relaxed rules giữa 2 lần
  đo, dù việc này không bắt buộc bởi brief.

## Vấn Đề / Khuyến Nghị

1. **[Quan trọng] Dữ liệu thật KHÔNG đạt full compliance với 4 luật hard-gate
   (II.3/II.4/II.8/II.14), luôn tốn hết 6000/6000 attempts (~101-117s/lần
   gọi `sched.run()`)** — xác nhận lại phát hiện của Task 4, KHÔNG phải do
   Task 6 gây ra và KHÔNG được Task 6 "sửa" (đúng phạm vi được giao). Chẩn
   đoán Step 2b cho thấy vi phạm II.4 còn sót lại tập trung vào 2 GV có tải
   ĐÚNG 15 tiết/tuần (ranh giới ngưỡng miễn trừ) với cơ cấu môn/lớp phân
   mảnh — không phải bug ở ngưỡng miễn trừ, nhiều khả năng (nhưng chưa xác
   minh chắc chắn) là do `_repair_teacher_lone_sessions`'s chiến lược hoán
   đổi 1-bước-đơn còn hạn chế.
2. **UX/an toàn**: `pages/06_Xep_TKB.py` (dòng 372-402) CHẶN nút lưu khi còn
   `hard_rule_violations` và bắt người dùng chủ động tick "vẫn lưu dù còn vi
   phạm" — nghĩa là dù engine luôn rơi vào relaxed-fallback trên dữ liệu
   thật hiện tại, UI KHÔNG âm thầm để qua; trường vẫn phải xác nhận thủ công
   trước khi lưu lịch chưa hoàn toàn tuân thủ. Đây là điểm tích cực cho việc
   đánh giá "sẵn sàng triển khai".
3. **Không nên hạ `min_weekly_periods_for_lone_penalty`** để "giải quyết"
   II.4 — xem giải thích ở Step 2b, đây là né tránh vấn đề chứ không giải
   quyết gốc.
4. **Follow-up đề xuất** (KHÔNG thực hiện trong task này — ngoài phạm vi
   "không sửa thuật toán tìm kiếm" của Task 6):
   - Mở rộng `_repair_teacher_lone_sessions` với hoán đổi chuỗi nhiều bước.
   - Cân nhắc bước tiền xử lý gom nhóm (môn,lớp) tải thấp cùng 1 GV.
   - Xem xét lại marker `xfail` của
     `test_real_data_schedules_successfully_with_heavy_subjects_morning_only[C]`
     (`tests/test_real_data_schedule.py:65`) — test này giờ XPASS qua nhánh
     relaxed-fallback thay vì fail hẳn như lý do xfail gốc mô tả
     ("Sample school morning capacity exact-fit"). File này KHÔNG nằm trong
     Files section của `task-6-brief.md` nên tôi không tự ý sửa, chỉ ghi
     nhận cho quyết định của bước tiếp theo.
   - Xem xét sự không nhất quán của `morning_only_subject_ids` auto-detect
     trong `data/repositories/config.py` (mục Step 5) — không khẩn cấp
     nhưng có thể gây bất ngờ cho người viết test/script sau này.
5. **Khuyến nghị triển khai thực tế**: tính năng hard-gate + relaxed-fallback
   hoạt động ĐÚNG như thiết kế (không crash, không treo, luôn minh bạch —
   không còn vi phạm "câm" nào, đã xác nhận qua cả test end-to-end lẫn 2 test
   hồi quy). Nhưng vì dữ liệu thật hiện có CHƯA từng đạt full compliance ở
   bất kỳ lần đo nào (Task 4: 4/4 kịch bản, Task 6: xác nhận lại), nhà trường
   NÊN được thông báo trước rằng: (a) thời gian xếp lịch trên dữ liệu thật sẽ
   luôn mất ~1.5-2 phút (không phải tức thời như trước), và (b) ở thời điểm
   hiện tại, lịch xếp ra gần như chắc chắn sẽ cần họ xem qua cảnh báo
   `relaxed_rules` và tick "vẫn lưu" — đây là hành vi có chủ đích (minh bạch)
   chứ không phải lỗi, nhưng cần được truyền đạt rõ khi bàn giao/đào tạo
   người dùng cuối.

**Kết luận cuối cùng — sẵn sàng triển khai hay chưa?** Tính năng ĐÃ SẴN
SÀNG triển khai xét về mặt CORRECTNESS/AN TOÀN: toàn bộ 230 test xanh, cả 2
bug gốc người dùng báo cáo đã có test hồi quy xác nhận đã sửa, gate không
bao giờ để lọt vi phạm "câm", và UI chặn lưu + yêu cầu xác nhận thủ công khi
còn vi phạm. Xét về mặt HIỆU QUẢ THỰC TẾ (liệu lịch xếp ra có thực sự tuân
thủ đầy đủ 4 luật HĐSP hay không), tính năng CHƯA đạt mục tiêu ban đầu trên
dữ liệu trường mẫu hiện có — nên khuyến nghị triển khai NHƯNG kèm 2 điều
kiện: (1) đào tạo người dùng cuối hiểu rõ ý nghĩa cảnh báo `relaxed_rules`
trước khi bàn giao, và (2) đưa 3 đề xuất follow-up ở trên (đặc biệt là
tăng cường `_repair_teacher_lone_sessions`) vào backlog kỹ thuật kế tiếp,
không nên coi vấn đề này là "đã đóng."
