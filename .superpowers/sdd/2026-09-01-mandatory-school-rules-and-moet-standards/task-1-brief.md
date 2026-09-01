# Task 1 Brief: Domain Models & Config Extensions for HĐSP & MOET Standards

## 1. Objective & Scope
Extend `SchedulingConfig` in `core/models.py` with standard configurations reflecting the 15 school criteria (HĐSP) and MOET rules:
- `max_teacher_periods_per_day: int = 5` (Tiêu chí II.2: Mỗi GV không quá tải vượt 5 tiết/ngày)
- `max_heavy_per_session: int = 3` (Tiêu chí I.2 & II.13: Tối đa 3 tiết môn nặng trong 1 buổi của 1 lớp)
- `hdtn_period2_afternoon: bool = True` (Tiêu chí II.6: Tiết 2 HĐTN xếp vào buổi chiều)
- `avoid_heavy_afternoon_period3: bool = True` (Tiêu chí II.15: Hạn chế môn nặng tiết 3 chiều)
- `avoid_teacher_4_consecutive_morning: bool = True` (Tiêu chí II.14: Hạn chế GV dạy 4 tiết sáng liên tục nếu tải <= 20 tiết/tuần)
- `min_weekly_periods_for_lone_penalty: int = 15` (Tiêu chí II.4: Ngưỡng tải tối thiểu áp dụng phạt lẻ tiết)

## 2. Interface Specifications
```python
@dataclass
class SchedulingConfig:
    # Existing fields...
    max_teacher_periods_per_day: int = 5
    max_heavy_per_session: int = 3
    hdtn_period2_afternoon: bool = True
    avoid_heavy_afternoon_period3: bool = True
    avoid_teacher_4_consecutive_morning: bool = True
    min_weekly_periods_for_lone_penalty: int = 15
```

## 3. TDD Strategy
- Test file: `tests/test_models.py` or new test in `tests/test_mandatory_rules_compliance.py`
- Assert default values exist and match specifications.
- Expected RED: `AttributeError` or missing fields.
- Minimal implementation: Add fields to `SchedulingConfig` in `core/models.py`.
- Expected GREEN: Config fields instantiate properly with correct defaults.
