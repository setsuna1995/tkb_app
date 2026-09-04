# SDD ledger — plan: .superpowers/sdd/2026-09-04-cpsat-scheduler/ (design.md + task-1..8-brief.md)

# SDD Progress Ledger: CP-SAT Scheduler Core

- **Date**: 2026-09-04
- **Feature**: `cpsat-scheduler`
- **Status**: `planned` — chưa được duyệt thực hiện
- **Design doc**: `design.md` (cùng thư mục)
- **POC**: `poc/cpsat_poc.py` — đã chạy, OPTIMAL 0.5s, 0 vi phạm II.3/II.4/II.8
- **Execution mode**: superpowers:subagent-driven-development. Dispatch từng
  implementer với đúng đường dẫn `task-N-brief.md` tương ứng.
- **Worktree**: nên tạo worktree riêng trước khi bắt đầu (superpowers:using-git-worktrees).
  Đây là thay đổi lõi, không nên làm thẳng trên `main`.

## Why (Bối cảnh)

Xem `design.md` §1. Tóm tắt: kiến trúc tham lam + sửa cục bộ hiện tại không giải
được các ràng buộc toàn cục (ghép cặp GV × buổi sáng bắt buộc; kích thước nhóm
của buổi lẻ). Biểu hiện là mỗi lần siết tiêu chí này thì tiêu chí kia xấu đi —
đã đo được 4 lần liên tiếp trong phiên 2026-09-03/04.

POC chứng minh CP-SAT giải bài toán thật của trường tới **tối ưu tuyệt đối**
(0 vi phạm cả II.3, II.4, II.8, kèm luật strict T2+T6 cho mọi GV) trong 0.5 giây,
trong khi engine hiện tại dừng ở ~1.5 buổi lẻ và ~2.5 GV thiếu sáng bắt buộc.

**Cảnh báo phương pháp ghi lại cho người thực hiện**: trong phiên trước tôi đã
nhiều lần kết luận sai rằng "đây là giới hạn cấu trúc của dữ liệu". Ba cơ chế
sửa độc lập cùng dừng ở một con số KHÔNG chứng minh bài toán bất khả thi khi cả
ba đều thuộc cùng một họ thuật toán cục bộ. Đừng lặp lại lỗi suy luận này khi
gặp một con số cứng đầu.

## Pre-flight Conflict Scan Table

| Tasks | File(s) | What A produces | What B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | `core/scheduler/cpsat_model.py` | Task 1 tạo file + lưới biến + ràng buộc định mức | Task 2 thêm ràng buộc GV vào cùng file | Clean — thứ tự 1 → 2 |
| 2, 3 | `core/scheduler/cpsat_model.py` | Ràng buộc GV | Task 3 thêm ràng buộc môn | Clean — 2 → 3 |
| 3, 4 | `core/scheduler/cpsat_model.py` | Ràng buộc môn | Task 4 thêm ghim + khung lớp | Clean — 3 → 4 |
| 4, 5 | `core/scheduler/cpsat_model.py` | Khung lớp | Task 5 thêm môn kép/1-cặp (cần khung lớp để biết ô liền kề) | Clean — 4 → 5 |
| 5, 6 | `core/scheduler/cpsat_model.py` | Toàn bộ ràng buộc CỨNG | Task 6 thêm hàm mục tiêu | Clean — 5 → 6 |
| 6, 7 | `core/scheduler/cpsat_model.py`, `core/models.py` | Hàm mục tiêu | Task 7 thêm `cells_changed` + dựng `ScheduleResult` | Clean — 6 → 7 |
| 7, 8 | `core/scheduler/engine.py` | `solve_with_cpsat()` hoàn chỉnh | Task 8 nối vào `run()` + fallback | Clean — 7 → 8 |
| 1, 8 | `requirements.txt` | Task 1 thêm `ortools` | Task 8 dùng import mềm | Clean — không chồng dòng |
| 8, — | `pages/10_Cau_hinh_Xep_lich.py` | Task 8 thêm 2 ô cấu hình | — | Chỉ Task 8 đụng file này |

Không cặp task nào khác dùng chung file. Task 1-7 chỉ đụng `cpsat_model.py`
(+ `core/models.py` ở Task 7 cho 2 field config) nên **bắt buộc chạy tuần tự**.

## Task Checklist

- [ ] **Task 1**: Khung mô hình — thêm `ortools`, tạo `core/scheduler/cpsat_model.py`, lưới biến `x[slot, subject]`, ràng buộc "mỗi ô đúng 1 môn" + "đúng định mức mỗi (môn, lớp)". Test: lời giải qua được `compute_quota_diff`. Brief: `task-1-brief.md`
- [ ] **Task 2**: Ràng buộc GIÁO VIÊN — không trùng giờ, GV bận, trần tiết/buổi, trần tiết/ngày, buổi nghỉ. Test: qua `find_teacher_conflicts`, `find_teacher_day_cap_violations`, `find_teacher_unavailability_violations`. Brief: `task-2-brief.md`
- [ ] **Task 3**: Ràng buộc MÔN — môn sáng bắt buộc, GDTC khung tiết + cách nhật, môn không liền ngày, môn nặng (/buổi, liên tiếp, tiết 3 chiều), luật môn–lớp–buổi. Test: qua `find_invalid_gdtc_periods`, `find_morning_only_violations`, `find_max_heavy_violations`, `find_consecutive_subject_days`, `find_subject_class_rule_violations`. Brief: `task-3-brief.md`
- [ ] **Task 4**: Khung LỚP + ghim — ≤1 tiết/môn/ngày (HĐTN 2), chào cờ, SHL, tuần chuyên đề, không hở tiết giữa buổi, trần tiết/ngày của lớp, lớp không có buổi 1 tiết. Brief: `task-4-brief.md`
- [ ] **Task 5**: Môn KÉP và 1-CẶP — khối 2 tiết liền kề, `single_pair_ids`. Task rủi ro cao nhất, tách riêng. Brief: `task-5-brief.md`
- [ ] **Task 6**: HÀM MỤC TIÊU — II.3/II.4/II.7/II.8/II.9/II.14 + dồn buổi lẻ + GV ưu tiên nghỉ nhiều buổi, trọng số lấy đúng từ `quality.py`. Giữ nguyên mọi miễn trừ theo cấu hình. Brief: `task-6-brief.md`
- [ ] **Task 7**: Giữ nguyên tiết cũ + dựng `ScheduleResult` — `cells_changed` thành số hạng mục tiêu; map lời giải sang `assignment`; sinh `relaxed_rules` khi mục tiêu > 0. Brief: `task-7-brief.md`
- [ ] **Task 8**: Nối vào `run()` + fallback + UI — cờ `use_cpsat` (mặc định TẮT), giới hạn thời gian, import mềm, 2 ô cấu hình. **Test song song bắt buộc**: CP-SAT không được thua engine cũ ở bất kỳ tiêu chí nào trên `sample_school.xlsm` và `truong-thcs.db`. Brief: `task-8-brief.md`

## Định nghĩa "xong"

1. Toàn bộ 244 test hiện có vẫn pass với `use_cpsat=False` (mặc định) — chứng
   minh không đụng gì tới đường chạy cũ.
2. Với `use_cpsat=True`, lời giải qua **toàn bộ** hàm trong `core/validation.py`
   trên cả 2 fixture, nhiều seed.
3. Trên Tuần 2 thật: II.3 = 0, II.4 = 0 (không kể GV được miễn), II.8 = 0.
4. Thời gian giải < 10s/tuần; quá hạn thì fallback êm, không lỗi giao diện.

## Execution Log

*(trống — chưa bắt đầu)*
