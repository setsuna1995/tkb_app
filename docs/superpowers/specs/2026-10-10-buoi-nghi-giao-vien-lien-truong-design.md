# Khống Chế Buổi Nghỉ & Lịch Dạy Giáo Viên Liên Trường (Tuần 8) — Thiết Kế Kỹ Thuật

> Ngày tạo: 10/10/2026  
> Trạng thái: Đã thống nhất qua Brainstorming  
> Tác giả: Antigravity & Thầy Khu (Admin)  

---

## 1. Bối cảnh & Mục tiêu

Trong bài toán xếp thời khóa biểu Tuần 8 của trường THCS học 2 buổi (8 lớp, 18 giáo viên):
1. **Quy định bất di bất dịch của nhà trường:**
   - Sáng Thứ 2 bắt buộc có mặt (`strict_morning_weekdays = (2,)`).
   - Môn Toán và Ngữ văn bắt buộc học buổi sáng, cấm tiệt buổi chiều (`morning_only_subject_ids = {1, 2}`).
   - Chiều Thứ 5 và Chiều Thứ 6 để trống toàn trường (`reserved_off_weekdays_chieu = (5, 6)`) dành sinh hoạt chuyên môn / bồi dưỡng.
2. **Vấn đề thực tế phát sinh ở kết quả cũ (PA2):**
   - **Thầy Khu (13 tiết):** Bị dồn toàn bộ tiết vào Thứ 2, 3, 4 (cả sáng lẫn chiều), dẫn đến trống trơn cả Sáng T5 lẫn Sáng T6. Kết hợp với Chiều T5, T6 trường nghỉ sẵn, Thầy Khu thành ra nghỉ trọn 4 ngày liên tiếp (T5, T6, T7, CN) $\rightarrow$ gây tị nạnh và dư luận trong trường.
   - **Cô Hoà (7 tiết) & Cô Trang (16 tiết):** Cần đi dạy ở 2 trường. Tuần 8 trường mình chủ động xếp trước, cần đảm bảo:
     - Cô Hoà: được **3 buổi nghỉ** (để đi dạy trường 2). 7 tiết của cô phải gom vào đúng 2 buổi dạy $\ge 2$ tiết, không bị buổi lẻ 1 tiết.
     - Cô Trang: được **2 buổi nghỉ** (để đi dạy trường 2).
   - **Quy tắc tính buổi nghỉ:** Chiều Thứ 5, Chiều Thứ 6 cả trường đã không set lịch dạy sẵn $\rightarrow$ phải né các buổi này ra, không được tính đó là buổi nghỉ của giáo viên được phân phối.
   - **Khống chế trần số buổi nghỉ:** Khi cấu hình chung là 1 buổi nghỉ (`teacher_off_sessions_per_week = 1`), mỗi giáo viên bình thường tối đa chỉ được nghỉ 1 buổi trong 8 buổi trường có học.

---

## 2. Thiết Kế Thuật Toán CP-SAT

### 2.1. Phân định tập buổi xét nghỉ (`eligible_sessions`)
- Trường học 8 buổi: 5 sáng (T2..T6) và 3 chiều (T2..T4).
- Chiều T5, Chiều T6, Thứ 7, Chủ nhật vốn không có timeslot học sinh $\rightarrow$ tự động loại trừ khỏi tập xét buổi nghỉ của giáo viên.

### 2.2. Khống chế trần buổi nghỉ (Upper Bound Cap)
- Với mỗi giáo viên:
  $$effective\_count = \begin{cases} teacher.off\_sessions\_override & \text{nếu có} \\ config.teacher\_off\_sessions\_per\_week & \text{mặc định (1)} \end{cases}$$
- Trần số buổi nghỉ:
  $$max\_allowed\_off = \max(effective\_count, len(pinned))$$
- Với giáo viên có tải $total\_p \ge 12$ tiết và không có lịch bận quá mức:
  $$\sum off\_vars \le max\_allowed\_off$$
- Ngăn chặn triệt để tình trạng một giáo viên đủ tải bị dồn tiết và nghỉ lố buổi.

### 2.3. Rải đều ngày dạy cuối tuần (Chống nghỉ trọn T5 + T6)
- Với giáo viên tải $\ge 12$ tiết (như Thầy Khu 13 tiết), nếu không có ghim nghỉ trọn ngày ở T5 hoặc T6:
  $$off\_var(T5, S) + off\_var(T6, S) \le 1$$
- Buộc giáo viên phải có ít nhất 1 buổi sáng có tiết ở Thứ 5 hoặc Thứ 6, rải đều lịch dạy trong tuần như Tuần 6.

### 2.4. Cô Hoà (7 tiết) và Cô Trang (16 tiết)
- Hỗ trợ 2 chế độ:
  - **Chế độ Tự do (Auto):** Bộ giải tự động gom tiết và tìm 3 buổi nghỉ cho cô Hoà, 2 buổi nghỉ cho cô Trang tối ưu nhất.
  - **Chế độ Cố định (Manual Pin):** Cho phép ghim cụ thể buổi nghỉ (ví dụ Hoà: Chiều T2, Chiều T3, Chiều T4; Trang: Chiều T3, Chiều T4).

---

## 3. Thiết Kế Giao Diện UI Streamlit

1. **Trang Cấu hình Xếp lịch (`pages/10_Cau_hinh_Xep_lich.py`):**
   - Tại Tab 2 ("👨‍🏫 Hiện diện & Nghỉ GV"):
     - Thêm container chuyên biệt: "🎯 Giáo viên dạy liên trường (Cô Hoà, Cô Trang...)"
     - Có selector giáo viên, số buổi nghỉ, và radio button chọn giữa `🤖 Tự do` và `📌 Cố định`.
2. **Trang Khai báo (`pages/01_Khai_bao.py`):**
   - Cột "Nghỉ mấy buổi/tuần" và các cột ghim nghỉ hiển thị đồng bộ, lưu trữ trực tiếp vào SQLite `teachers`.
