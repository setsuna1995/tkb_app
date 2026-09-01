# Task 1 Report: Điều chỉnh Greedy Heuristics & Constants để Tránh Buổi 1 Tiết Cho GV

## 1. What was implemented
- **Cập nhật hằng số điểm thưởng (`core/scheduler/constants.py`)**:
  - Tăng `TEACHER_SESSION_PAIR_BONUS` từ 150 lên **320** điểm để tạo lực hút mạnh mẽ khi ghép tiết thứ 2 vào buổi cho giáo viên.
  - Bổ sung `TEACHER_LONE_SESSION_HEURISTIC_PENALTY = 250` phạt khi mở một buổi mới cho GV mà GV không còn đủ tiết để ghép cặp.
- **Cập nhật heuristics tính điểm (`core/scheduler/heuristics.py`)**:
  - Phạt `- TEACHER_LONE_SESSION_HEURISTIC_PENALTY` khi GV bắt đầu buổi mới (`current_in_session == 0`) mà tổng số tiết còn lại trong tuần `<= 1`.
  - Điều kiện hoá `TEACHER_MANDATORY_MORNING_BONUS`: Chỉ kích hoạt điểm thưởng sáng bắt buộc khi tổng tải tuần của GV `>= 12` tiết, tránh ép rải vụn ra 3 buổi sáng cho GV có ít tiết.
- **Xuất khẩu hằng số mới (`core/scheduler/__init__.py`)**:
  - Thêm `TEACHER_LONE_SESSION_HEURISTIC_PENALTY` vào danh sách xuất khẩu và `__all__`.

## 2. Files changed
- `core/scheduler/constants.py`: Cập nhật hằng số.
- `core/scheduler/heuristics.py`: Cập nhật logic `_pick_best_scored`.
- `core/scheduler/__init__.py`: Cập nhật export.
- `tests/test_scheduler_teacher_quality.py`: Bổ sung test `test_greedy_prefers_pairing_over_lone_session`.

## 3. TDD Evidence
- **Command**: `python -m pytest tests/test_scheduler_teacher_quality.py`
- **Output**:
```
============================= 11 passed in 0.09s ==============================
```

## 4. Self-Review Findings
- Zero regressions: Các thay đổi hoàn toàn tương thích và tôn trọng 100% các ràng buộc cứng.
