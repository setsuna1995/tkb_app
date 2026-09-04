# Task 4: Khung LỚP và các tiết ghim

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` syntax.

**Goal:** Model the constraints that belong to a class's own day/session shape,
plus the two ceremony periods that are pinned by school policy.

**Why (Vietnamese):** Nhóm này quyết định hình dạng ngày học của LỚP: chào cờ ở
đâu, sinh hoạt lớp ở đâu, một môn được mấy tiết trong ngày, buổi học có bị hở
tiết không. Riêng luật HĐTN vừa được trường xác nhận lại ngày 2026-09-04 nên
phải mô hình đúng bản mới, đừng chép theo code cũ đã bị thay.

**Files:**
- Modify: `core/scheduler/cpsat_model.py` (`_add_class_constraints`)
- Modify: `tests/test_cpsat_model.py`

**Interfaces:**
- Consumes: `CpSatModel.x`, `.inp`, `.slots_by_class`, `.role_index` (Task 3)
- Produces: không có interface mới.

## Ràng buộc phải thêm

| # | Luật | Nguồn | Ghi chú |
|---|---|---|---|
| 1 | ≤1 tiết/môn/ngày/lớp | `feasibility.py:62-65`, `role_index.block_size` | Trần = `block_size.get(sid, 1)`; **HĐTN tuần thường = 2** (xem dưới) |
| 2 | Ghim chào cờ | `engine.py:174-186` | HĐTN tại `(chao_co_weekday, "S", chao_co_period)` mọi lớp |
| 3 | Ghim SHL | `engine.py:87-94, 231-245` | HĐTN tại tiết cuối buổi sáng của ngày SHL |
| 4 | Tuần chuyên đề | `hdtn_thematic_week` | HĐTN thành khối 3 tiết liền, **bỏ cả hai ghim trên** |
| 5 | Không hở tiết giữa buổi của lớp | `feasibility.py:59-61` (`BAT_LIEN_MACH`) | Tiết p có môn ⟹ tiết p-1 cùng buổi cũng có môn |
| 6 | Trần tiết/ngày của lớp | `feasibility.py:56-58`, `day_capacity` | |
| 7 | Lớp không có buổi chỉ 1 tiết | `swaps.py:_has_lone_period` | Buổi đã dùng thì ≥2 tiết (khi buổi đó có ≥2 ô) |

## Ghi chú quan trọng

**Luật 1 — HĐTN được 2 tiết/ngày.** Đây là quy định trường xác nhận 2026-09-04:
chào cờ và SHL đã ghim, còn **tiết HĐTN thứ ba được xếp tự do, kể cả cùng ngày
với hai tiết ghim và không cần liền kề chúng**. Xem
`core/scheduler/feasibility.py` (biến `hdtn_free_period`) để lấy đúng ngữ nghĩa.
Trước bản sửa đó, luật chung "1 tiết/môn/ngày" đẩy tiết thứ ba sang ngày khác,
khiến GVCN có ngày đến trường chỉ để dạy đúng 1 tiết chào cờ hoặc 1 tiết SHL —
30% số buổi lẻ còn lại lúc đó chính là hai tiết nghi lễ này.

**Luật 3 — ngày SHL suy ra từ khung lớp**, không cứng: lớp có học chiều thì SHL
ở Thứ 6, lớp chỉ học sáng thì Thứ 7 (`engine.py:87-92`). Lấy tiết cuối cùng của
buổi sáng ngày đó theo `max(period)`.

**Luật 5** hiện tự thoả trên dữ liệu trường này vì dư địa = 0 (mọi ô đều có
tiết). Vẫn phải viết: trường khác có dư ô thì thiếu nó sẽ sinh TKB hở tiết.

**Luật 7** dùng biến phụ `class_used[cid, wd, sess]`, ràng buộc
`count >= 2 * class_used` và `count <= max_ô * class_used`.

## Test

- Chào cờ/SHL: assert ô tương ứng mang đúng `hdtn_id` ở mọi lớp.
- HĐTN 2 tiết/ngày: fixture cho phép tiết thứ ba rơi vào ngày chào cờ → assert
  bộ giải KHÔNG bị chặn (đối lập với hành vi cũ).
- Không hở tiết: fixture có dư địa (số ô > need) → assert không có ô trống nào
  nằm giữa hai ô có tiết trong cùng buổi.
- Buổi 1 tiết của lớp: fixture dư địa → assert mọi buổi đã dùng đều ≥2 tiết.

- [ ] Step 1: viết test → FAIL
- [ ] Step 2: cài `_add_class_constraints`
- [ ] Step 3: chạy lại → PASS
- [ ] Step 4: `python -m pytest tests/ -q` → 244 passed, 1 xpassed
- [ ] Step 5: commit `feat(cpsat): class frame constraints and pinned ceremonies`
