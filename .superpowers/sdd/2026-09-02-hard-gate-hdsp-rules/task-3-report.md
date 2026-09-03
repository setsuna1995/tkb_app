# Task 3 Report: Rules Registry

## Tổng Quan

Đã hoàn thành toàn bộ 6 bước được yêu cầu trong task brief:
- Viết test lỗi trước (TDD RED phase)
- Chạy test để xác nhận lỗi
- Tạo module `core/rules_registry.py` với các interface được chỉ định
- Chạy test để xác nhận thành công (TDD GREEN phase)
- Commit các thay đổi
- Viết báo cáo task

## Các Thay Đổi Thực Hiện

### 1. Tệp Mới: tests/test_rules_registry.py

Tạo tệp test với 3 test case:
- `test_registry_contains_all_six_rules()`: Kiểm tra rằng RULES chứa đúng 6 rule ID (II.3, II.4, II.7, II.8, II.9, II.14)
- `test_hard_post_generation_ids_matches_user_confirmed_classification()`: Kiểm tra rằng II.3/II.4/II.8/II.14 là HARD_POST_GENERATION, II.7/II.9 là SOFT
- `test_every_rule_has_a_vietnamese_title()`: Kiểm tra tất cả các rule có `title_vi` là string không rỗng

### 2. Tệp Mới: core/rules_registry.py

Tạo module metadata với các thành phần:

**Enum `RuleTier`:**
- `HARD_POST_GENERATION`: Kiểm tra toàn bộ schedule; từ chối và retry, hoặc báo cáo là nới lỏng
- `SOFT`: Chỉ scoring; không bao giờ chặn nỗ lực hoặc nút lưu

**Dataclass `RuleSpec` (frozen):**
- `id: str` - ID rule (ví dụ: "II.3")
- `title_vi: str` - Tiêu đề tiếng Việt
- `tier: RuleTier` - Tầng enforcement (HARD_POST_GENERATION hoặc SOFT)
- `config_flag: Optional[str] = None` - Cờ SchedulingConfig để bật/tắt rule

**Dict `RULES`:**
```
"II.3": RuleSpec(..., tier=HARD_POST_GENERATION, config_flag=None)
"II.4": RuleSpec(..., tier=HARD_POST_GENERATION, config_flag="avoid_teacher_lone_periods")
"II.7": RuleSpec(..., tier=SOFT, config_flag="avoid_teacher_gaps")
"II.8": RuleSpec(..., tier=HARD_POST_GENERATION, config_flag="avoid_teacher_lone_periods")
"II.9": RuleSpec(..., tier=SOFT, config_flag="balance_afternoon_teachers")
"II.14": RuleSpec(..., tier=HARD_POST_GENERATION, config_flag="avoid_teacher_4_consecutive_morning")
```

**Tuple `HARD_POST_GENERATION_IDS`:**
- Dẫn xuất từ RULES: ("II.3", "II.4", "II.8", "II.14")
- Sử dụng list comprehension để lọc các rule có tier == HARD_POST_GENERATION

## Kết Quả Test

### Bước 2 (RED - Test lỗi):
```
ERROR collecting tests/test_rules_registry.py
E   ModuleNotFoundError: No module named 'core.rules_registry'
```

### Bước 4 (GREEN - Test thành công):
```
tests/test_rules_registry.py::test_registry_contains_all_six_rules PASSED [ 33%]
tests/test_rules_registry.py::test_hard_post_generation_ids_matches_user_confirmed_classification PASSED [ 66%]
tests/test_rules_registry.py::test_every_rule_has_a_vietnamese_title PASSED [100%]

============================== 3 passed in 0.06s ==============================
```

## Commit

Commit được tạo thành công:
```
[worktree-hard-gate-hdsp-rules de70ebd] feat: add rules_registry.py as single source of truth for rule tiers
 2 files changed, 94 insertions(+)
 create mode 100644 core/rules_registry.py
 create mode 100644 tests/test_rules_registry.py
```

## Tự Kiểm Tra

✅ **Hoàn chỉnh** - Tất cả 6 bước đã được thực hiện đúng
✅ **Tuân thủ Interface** - Các tên chính xác (RULES, HARD_POST_GENERATION_IDS, RuleSpec, RuleTier) phù hợp với yêu cầu của Task 5
✅ **Testing** - TDD process: RED → GREEN, cả 3 test pass
✅ **Discipline** - YAGNI: Chỉ bao gồm 6 rule được đề cập trong feature này, không mở rộng
✅ **Metadata Only** - Module không thay thế hay triển khai bất kỳ logic constraint nào

## Các Vấn Đề / Lưu Ý

**Không có vấn đề hoặc lưu ý nào.** Task 3 hoàn tất sạch sẽ:
- Tất cả test pass
- Tất cả interface chính xác
- Code đơn giản, rõ ràng
- Sẵn sàng cho Task 5 (sẽ import `RULES` và `HARD_POST_GENERATION_IDS`)

## Kết Luận

Task 3 hoàn thành thành công. Module `core/rules_registry.py` là "nguồn sự thật duy nhất" (single source of truth) cho việc phân loại tầng enforcement của 6 rule được touched bởi feature hard-gate-hdsp-rules. Task 5 sẽ nhập `HARD_POST_GENERATION_IDS` từ module này để quyết định rule violations nào sẽ chặn nút lưu trong Streamlit UI.
