# Design: Chuyển lõi xếp TKB sang bộ giải ràng buộc (CP-SAT)

- **Date**: 2026-09-04
- **Feature slug**: `cpsat-scheduler`
- **Status**: đề xuất, chưa được duyệt thực hiện
- **Bằng chứng khả thi**: POC đã chạy trên dữ liệu thật Tuần 2 (xem §2)

---

## 1. Vấn đề (Why)

### 1.1 Triệu chứng

Suốt phiên làm việc 2026-09-03/04, mỗi lần siết một tiêu chí HĐSP thì một tiêu
chí khác xấu đi. Không phải ngẫu nhiên — đây là hình thái lỗi lặp lại:

| Việc đã làm | Được | Mất |
|---|---|---|
| Sửa II.3 bằng cách chuyển 1 tiết vào sáng bắt buộc | II.3 giảm | Đẻ ra buổi lẻ II.4 |
| Đổi thành chuyển 2 tiết (all-or-nothing) | Hết đẻ buổi lẻ | II.3 sửa được ít hơn hẳn |
| Bật luật "mọi GV phải có tiết sáng T2/T6" | — | Số GV thiếu **tăng** 2.50 → 3.00 |
| Cho bước sửa lấy nguồn từ buổi chiều | Buổi lẻ giảm | Độ phủ sáng bắt buộc dao động 1→5 |

Ví dụ cụ thể nhất (seed 42): gỡ được cho thầy Thành thì thầy Sơn mất **cả hai**
buổi sáng. Bước sửa chữa là chuỗi hoán đổi cục bộ, mỗi nước đi chỉ nhìn thấy
một GV, nên nó **đẩy vấn đề sang người khác** thay vì giải.

### 1.2 Nguyên nhân gốc

Kiến trúc hiện tại là **tham lam ngẫu nhiên + sửa cục bộ**: dựng lời giải bằng
greedy, rồi chạy vài lượt hoán đổi 1-đổi-1 và xoay vòng 3 chiều, lặp 6000 lần
và giữ phương án tốt nhất.

Cách này **không thể** giải các ràng buộc có tính toàn cục:

- *"Mỗi GV cần ≥1 ô ở sáng T2"* là bài toán **ghép cặp 17 GV × các ô khả dụng**
  — phải giải đồng thời, không thể vá lần lượt.
- *"Buổi nào GV đã dùng thì phải ≥2 tiết"* là ràng buộc **kích thước nhóm**,
  hoán đổi cục bộ luôn có nguy cơ phá nhóm khác.

Một cảnh báo về phương pháp, ghi lại để không lặp lại: trong phiên này tôi đã
nhiều lần kết luận *"đây là giới hạn cấu trúc của dữ liệu"* vì ba cơ chế sửa
độc lập đều dừng ở cùng một con số. **Kết luận đó sai.** Ba cơ chế đó đều là
biến thể của cùng một cách tiếp cận cục bộ nên cùng chung điểm mù. *"Nhiều cách
đều thất bại"* không phải bằng chứng bất khả thi khi các cách ấy cùng một họ.

---

## 2. Bằng chứng: POC đã chạy

Mô hình CP-SAT dựng thẳng toàn bộ Tuần 2 (236 ô, 16 môn, 8 lớp, 17 GV → ~3.776
biến nhị phân), có 8 nhóm ràng buộc cứng + II.3/II.4 làm hàm mục tiêu.

```
trạng thái : OPTIMAL            thời gian: 0.5 giây
II.3 thiếu sáng bắt buộc : 0 / 47 ràng buộc  (gồm luật strict T2+T6 cho MỌI GV)
II.4 buổi lẻ             : 0
cận dưới đã chứng minh   : 0
```

Lời giải được **kiểm chứng độc lập** bằng chính bộ hàm `core/validation.py` mà
giao diện đang dùng — không phải tự bộ giải báo cáo:

| Kiểm tra | Kết quả |
|---|---|
| Đúng định mức tiết mỗi (môn, lớp) | OK |
| GV không trùng giờ | OK |
| Không vượt trần tiết/ngày của GV | OK |
| Môn nặng/buổi | OK |
| GDTC đúng khung tiết | OK |
| Môn bắt buộc sáng không rơi vào chiều | OK |
| GDTC cách nhật | OK |
| GV bận (GV_Bận) | OK |
| II.3 / II.4 / II.8 | 0 / 0 / 0 |

So với engine hiện tại trên cùng dữ liệu: ~1.5 buổi lẻ, ~2.5 GV thiếu sáng bắt
buộc, và luật strict T2+T6 **không đạt được**.

Script POC: `.superpowers/sdd/2026-09-04-cpsat-scheduler/poc/cpsat_poc.py`.

**Giới hạn của POC — phải nói rõ:** mới mô hình hoá 8 nhóm ràng buộc. Engine
thật còn khoảng 12 luật nữa (§4). POC chứng minh **hướng đi đúng và đủ nhanh**,
KHÔNG chứng minh mô hình đầy đủ cũng cho kết quả như vậy.

---

## 3. Kiến trúc đề xuất

**CP-SAT làm lõi chính, engine hiện tại làm lưới an toàn.**

```
run(inp)
  ├─ nếu bật CP-SAT và ortools import được:
  │     dựng mô hình → giải (có giới hạn thời gian)
  │     ├─ OPTIMAL/FEASIBLE → trả kết quả  (kèm relaxed_rules nếu mục tiêu > 0)
  │     └─ INFEASIBLE/timeout → rơi xuống engine cũ
  └─ ngược lại: engine cũ y như hiện nay
```

Vì sao chọn cách này thay vì thay thế hẳn:

- **Không mất gì đang có.** Nếu mô hình thiếu luật hoặc dữ liệu lạ khiến bộ giải
  bó tay, người dùng vẫn nhận được TKB như hôm nay chứ không phải màn hình lỗi.
- **Chuyển đổi đo được.** Có thể chạy song song hai lõi trên cùng dữ liệu và so,
  đó chính là cách kiểm chứng ở Task 8.
- **`ScheduleResult` giữ nguyên** → toàn bộ giao diện, cơ chế chặn lưu,
  `relaxed_rules` không phải sửa.

**Không** dùng phương án "greedy dựng, CP-SAT đánh bóng vùng lân cận": POC cho
thấy giải thẳng toàn bài chỉ mất 0.5s, nên sự phức tạp của mô hình lân cận
không đổi lại được gì.

---

## 4. Danh mục luật phải mô hình hoá

Đây là phần rủi ro nhất: **bỏ sót một luật = TKB sai mà không ai biết**, vì bộ
giải sẽ vui vẻ trả về lời giải "tối ưu" vi phạm luật đó.

### 4.1 Đã có trong POC (8)

| # | Luật | Nguồn |
|---|---|---|
| 1 | Mỗi ô đúng 1 môn; đúng định mức mỗi (môn, lớp) | `inp.need` |
| 2 | GV không dạy 2 lớp cùng tiết | `_feasible` qua `state.busy` |
| 3 | GV bận (GV_Bận) | `inp.ban_busy` |
| 4 | ≤1 tiết/môn/ngày/lớp (HĐTN được 2) | `feasibility.py:62-75` |
| 5 | Ghim chào cờ + SHL | `engine.py` |
| 6 | Môn bắt buộc buổi sáng | `morning_only_subject_ids` |
| 7 | GDTC: khung tiết + cách nhật | `gdtc_*`, `avoid_gdtc_consecutive_days` |
| 8 | Môn nặng tối đa/buổi | `max_heavy_per_session` |

### 4.2 Còn thiếu — phải bổ sung (12)

| # | Luật | Nguồn | Ghi chú mô hình hoá |
|---|---|---|---|
| 9 | Trần tiết/buổi và tiết/ngày của GV | `max_periods_per_session`, `max_teacher_periods_per_day` | POC có phần tiết/ngày; cần kiểm lại tiết/buổi |
| 10 | Buổi nghỉ của GV (`gv_off_slots`) | `teacher_off.py` | Trường này đang đặt 0 nhưng luật vẫn phải có |
| 11 | Luật môn–lớp–buổi | `subject_class_allowed_cells` | Cấm cứng ô ngoài danh sách |
| 12 | Không hở tiết giữa buổi của lớp | `BAT_LIEN_MACH` | Hiện tự thoả vì dư địa = 0; **vẫn phải mô hình** cho trường có dư địa |
| 13 | Môn kép: khối 2 tiết liền kề | `role_index.block_size` | Ràng buộc liền kề, khó nhất |
| 14 | Môn 1 cặp liền tiết | `single_pair_ids` | |
| 15 | Môn nặng liên tiếp | `max_heavy_consecutive` | |
| 16 | Môn nặng tiết 3 chiều | `avoid_heavy_afternoon_period3` | |
| 17 | Môn không xếp liền ngày | `non_consecutive_subject_ids` | Tổng quát hoá luật GDTC |
| 18 | Tuần chuyên đề (HĐTN khối 3) | `hdtn_thematic_week` | Bỏ ghim chào cờ/SHL |
| 19 | Lớp không có buổi chỉ 1 tiết | `_has_lone_period` | |
| 20 | Trần tiết/ngày của lớp | `day_capacity` | |

### 4.3 Mục tiêu (mềm)

Tất cả thành số hạng phạt trong hàm mục tiêu, trọng số lấy đúng từ
`quality.py:_teacher_quality_penalty` để không đổi thứ tự ưu tiên:

II.4 buổi lẻ (500) · II.8 ngày chia lẻ (700) · ngày lẻ (250) · dồn buổi lẻ vào
1 GV (600) · II.3 thiếu sáng bắt buộc (800) · II.7 tiết trống (350) · II.14 4
tiết sáng liên tiếp (300) · II.9 nghỉ trọn chiều (200) · GV ưu tiên nghỉ nhiều
buổi (400/buổi) · **giữ nguyên tiết cũ** (`cells_changed`).

Các miễn trừ theo cấu hình phải giữ nguyên ngữ nghĩa: `lone_session_exempt_teacher_ids`,
`min_weekly_periods_for_lone_penalty`, `min_weekly_periods_for_mandatory_morning`,
`strict_morning_weekdays` + miễn BGH, `compact_schedule_teacher_ids`.

---

## 5. Cách giữ an toàn

Nguyên tắc: **không tin bộ giải, chỉ tin bộ thẩm định độc lập.**

1. **Mỗi task kết thúc bằng một test đối chiếu**: lời giải CP-SAT phải qua được
   đúng bộ hàm `core/validation.py` mà giao diện dùng — không dùng lại chính
   ràng buộc đã viết trong mô hình để tự kiểm tra mình.
2. **Test song song (Task 8)**: chạy cả hai lõi trên `sample_school.xlsm` và
   trên `truong-thcs.db` nhiều seed, khẳng định CP-SAT **không thua** engine cũ
   ở bất kỳ tiêu chí nào.
3. **Cờ bật/tắt**: `SchedulingConfig.use_cpsat: bool = False` — mặc định TẮT.
   Bật khi trường sẵn sàng; tắt là quay lại hành vi hôm nay ngay lập tức.
4. **Giới hạn thời gian**: quá hạn thì rơi xuống engine cũ, không treo giao diện.

---

## 6. Rủi ro

| Rủi ro | Mức | Xử lý |
|---|---|---|
| Bỏ sót luật → TKB sai mà "tối ưu" | **Cao** | §5.1 + §5.2; danh mục §4.2 là checklist bắt buộc |
| Mô hình môn kép (liền kề) viết sai | Cao | Task riêng (Task 5), test riêng cho từng hình dạng |
| `ortools` ~100MB, thêm phụ thuộc | Trung bình | Import mềm; thiếu thư viện thì chạy engine cũ |
| Dữ liệu chật hơn → bộ giải chậm | Thấp | Giới hạn thời gian + fallback. POC: 0.5s trên bài thật |
| Mất tính năng "giữ nguyên tiết cũ" | Trung bình | Là số hạng mục tiêu, có test riêng (Task 7) |

---

## 7. Phạm vi KHÔNG làm

- Không bỏ engine cũ. Nó là fallback lâu dài.
- Không đụng giao diện ngoài 1 ô bật/tắt + 1 ô giới hạn thời gian.
- Không đổi `ScheduleResult`, không đổi cơ chế `relaxed_rules`/chặn lưu.
- Không xử lý việc bỏ logic tuần Chẵn/Lẻ (việc riêng, đang để dành).
