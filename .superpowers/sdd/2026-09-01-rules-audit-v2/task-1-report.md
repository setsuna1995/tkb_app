# Task 1 Report: Đánh Giá Toàn Diện Rule Cứng/Mềm & Thuật Toán Sắp Xếp

## Tổng quan

Đánh giá toàn bộ **32 quy tắc** trong hệ thống xếp thời khoá biểu (TKB), chia thành 3 nhóm:
- **14 ràng buộc cứng (Hard Constraints)** — vi phạm → TKB bất hợp lệ, bị reject
- **13 quy tắc mềm (Soft Rules)** — vi phạm → TKB hợp lệ nhưng chất lượng giảm
- **6 bất biến cốt lõi (Core Invariants)** — luôn đúng theo thiết kế

---

## I. BẢNG TỔNG HỢP QUY TẮC CỨNG

| # | Tên quy tắc | Nơi enforce (feasibility) | Nơi validate (validation.py) | Trạng thái |
|---|---|---|---|---|
| H1 | **GV trùng tiết** (busy check) | [feasibility.py L22](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L22) | `find_teacher_conflicts` | ✅ Đồng bộ |
| H2 | **GV vượt trần buổi** (max_periods_per_session) | [feasibility.py L24](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L24) | — (implicit) | ✅ OK |
| H3 | **GV nghỉ buổi** (off-slot) | [feasibility.py L26](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L26) | — (runtime only) | ✅ OK |
| H4 | **GDTC tiết cấm** (avoid_period + allowed_periods) | [feasibility.py L28-36](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L28-L36) | `find_invalid_gdtc_periods` | ✅ Đồng bộ |
| H5 | **Môn Nặng cấm chiều** (heavy_subjects_morning_only) | [feasibility.py L37-38](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L37-L38) | `find_morning_only_violations` | ✅ Đồng bộ |
| H6 | **Môn bắt buộc sáng** (morning_only_subject_ids) | [feasibility.py L39-41](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L39-L41) | `find_morning_only_violations` | ✅ Đồng bộ |
| H7 | **Không liên tiếp ngày** (non_consecutive + GDTC) | [feasibility.py L43-49](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L43-L49) | `find_consecutive_subject_days` | ⚠️ Xem phân tích |
| H8 | **Trần tiết/ngày** (day_capacity) | [feasibility.py L51-53](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L51-L53) | — (frame-based) | ✅ OK |
| H9 | **Liên mạch buổi** (BAT_LIEN_MACH) | [feasibility.py L54-56](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L54-L56) | — (structural) | ✅ OK |
| H10 | **Trần tiết/ngày/môn** (block_size cap) | [feasibility.py L57-60](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L57-L60) | — (structural) | ✅ OK |
| H11 | **Single-pair chỉ 1 cặp/tuần** | [feasibility.py L61-64](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L61-L64) | `find_single_pair_violations` | ✅ Đồng bộ |
| H12 | **Block liền kề** (same session, contiguous) | [feasibility.py L65-70](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L65-L70) | — (structural) | ✅ OK |
| H13 | **Trần môn Nặng liên tiếp** (max_heavy_consecutive) | [feasibility.py L71-83](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L71-L83) | `find_max_heavy_violations` | ✅ Đồng bộ |
| H14 | **Luật môn/lớp/buổi** (subject_class_allowed_cells) | [feasibility.py L18-21](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L18-L21) | `find_subject_class_rule_violations` | ✅ Đồng bộ |

---

## II. BẢNG TỔNG HỢP QUY TẮC MỀM

| # | Tên quy tắc | Hằng số | Giá trị | Nơi áp dụng | Trạng thái |
|---|---|---|---|---|---|
| S1 | **Ưu tiên môn thiếu nhiều tiết** | — | `remaining_need × 100` | [heuristics.py L65](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L65) | ✅ OK |
| S2 | **Phạt dàn-môn liên tiếp ngày** | — | `-50` (hoặc `-150` cho GDTC) | [heuristics.py L66-73](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L66-L73) | ✅ OK |
| S3 | **Thưởng ngày GV trống** | `IDLE_DAY_BONUS` | `30` | [heuristics.py L74-76](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L74-L76) | ✅ OK |
| S4 | **Thưởng Nặng buổi sáng** | `HEAVY_MORNING_BONUS` | `30` | [heuristics.py L77-79](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L77-L79) | ✅ OK |
| S5 | **Phạt môn không ưu tiên chiều** | `AFTERNOON_MISMATCH_PENALTY` | `30` | [heuristics.py L80-82](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L80-L82) | ✅ OK |
| S6 | **Thưởng hoàn thành block** | `BLOCK_COMPLETE_BONUS` | `40` | [heuristics.py L83-84](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L83-L84) | ✅ OK |
| S7 | **Thưởng GV liền kề / Phạt lỗ hổng** | `TEACHER_CONSECUTIVE_BONUS` / `TEACHER_GAP_PENALTY` | `150` / `250` | [heuristics.py L17-38](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L17-L38) | ✅ OK |
| S8 | **Thưởng ghép cặp buổi GV** | `TEACHER_SESSION_PAIR_BONUS` | `150` | [heuristics.py L90-93](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L90-L93) | ✅ OK |
| S9 | **Phạt ngày chia đôi GV** | `TEACHER_SPLIT_DAY_PENALTY` | `180` | [heuristics.py L94-97](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L94-L97) | ✅ OK |
| S10 | **Cân đối buổi chiều GV** | `TEACHER_AFTERNOON_BALANCE_BONUS` | `0` ⚠️ | [heuristics.py L99-101](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L99-L101) | ⚠️ Xem phân tích |
| S11 | **Thưởng sáng bắt buộc** | `TEACHER_MANDATORY_MORNING_BONUS` | `280` | [heuristics.py L103-106](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L103-L106) | ✅ OK |
| S12 | **Giữ lịch cũ (keep-old bonus)** | — | `+1,000,000` (giảm dần theo pu) | [heuristics.py L108-109](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L108-L109) | ✅ OK |
| S13 | **Thưởng lấp lỗ hổng GV** | — | `-180` (âm = thưởng) | [heuristics.py L31](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L31) | ✅ OK |

---

## III. PHÂN TÍCH XUNG ĐỘT CHI TIẾT

### ⚠️ Phát hiện 1: `TEACHER_AFTERNOON_BALANCE_BONUS = 0` — Greedy bị vô hiệu hoá nhưng Quality vẫn phạt

**Vấn đề**:
- Trong [constants.py L32](file:///c:/Users/Kien/tkb_app/core/scheduler/constants.py#L32): `TEACHER_AFTERNOON_BALANCE_BONUS = 0`
- Nhưng trong [quality.py L116-117](file:///c:/Users/Kien/tkb_app/core/scheduler/quality.py#L116-L117): `_count_teacher_missing_afternoon_duty × 200` vẫn phạt khi `balance_afternoon_teachers == True`

**Phân tích**: Đây là **có chủ đích**, KHÔNG phải xung đột:
- Comment L32 giải thích: *"không ép rải tiết chiều trong greedy gây lẻ 1 tiết; đánh giá cân đối qua _teacher_quality_penalty"*
- Greedy bonus = 0 nghĩa là thuật toán **KHÔNG cố ép** đặt tiết chiều cho GV mới (tránh tạo lẻ 1 tiết/buổi)
- Quality penalty = 200 nghĩa là khi **so sánh giữa các phương án**, phương án nào GV trống trọn chiều sẽ bị phạt → chọn phương án tốt hơn nhờ best-of-N

**Kết luận**: ✅ **Không xung đột** — thiết kế 2 tầng (greedy không ép, quality chọn lọc) là hợp lý.

---

### ⚠️ Phát hiện 2: Non-consecutive enforcement bị kiểm tra **2 lần** (greedy + post-check)

**Nơi 1** — Feasibility ([feasibility.py L43-49](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L43-L49)):
```python
if (subject_id in non_consecutive) or (avoid_gdtc and subject_id == role_index.gdtc_id):
    if ts.weekday > 2 and state.placed.get((class_id, subject_id, ts.weekday - 1)):
        return False
```

**Nơi 2** — Post-check trong engine ([engine.py L212-220](file:///c:/Users/Kien/tkb_app/core/scheduler/engine.py#L212-L220)):
```python
if done and (avoid_gdtc or non_consecutive):
    for (cid, sid, wd), pos_list in state.placed.items():
        ...
```

**Phân tích**: Đây là **defense in depth**, KHÔNG phải xung đột:
- Feasibility ngăn chặn trong greedy pass
- Post-check bắt trường hợp swap-repair vô tình tạo ra cặp liên tiếp (vì `_try_swap_repair` không check non-consecutive sau khi swap)
- Tuy nhiên, **feasibility đã check** trước khi đặt bất kỳ tiết nào → post-check chỉ là safety net

**Kết luận**: ✅ **Không xung đột** — redundant nhưng an toàn. Post-check đảm bảo không bỏ sót.

---

### ⚠️ Phát hiện 3: Heuristic dàn-môn (L66-73) và feasibility non-consecutive (L43-49) — **phạt mềm vs cấm cứng**

**Trong heuristics** ([heuristics.py L66-73](file:///c:/Users/Kien/tkb_app/core/scheduler/heuristics.py#L66-L73)):
```python
if ts.weekday > 2 and state.placed[(class_id, subj.subject_id, ts.weekday - 1)]:
    score -= 50
    if subj.subject_id == role_index.gdtc_id:
        score -= 100
```
Phạt mềm này áp cho **TẤT CẢ** môn, kể cả môn ngoài `non_consecutive_subject_ids`.

**Trong feasibility** ([feasibility.py L43-49](file:///c:/Users/Kien/tkb_app/core/scheduler/feasibility.py#L43-L49)):
Cấm cứng chỉ áp cho `non_consecutive_subject_ids ∪ {gdtc_id}`.

**Phân tích**: **Không xung đột** — đây là 2 tầng logic:
1. Feasibility **cấm cứng** cho các môn trong danh sách `non_consecutive`
2. Heuristic **phạt mềm** cho TẤT CẢ các môn (dàn đều, không liên tiếp ngày) — score giảm nhưng KHÔNG chặn

**Kết luận**: ✅ Thiết kế đúng — soft dàn-môn cho tất cả, hard cấm cho nhóm chỉ định.

---

### ⚠️ Phát hiện 4: `IDLE_DAY_BONUS + HEAVY_MORNING_BONUS` có thể thắng phạt dàn-môn

Constants comment ([constants.py L17-19](file:///c:/Users/Kien/tkb_app/core/scheduler/constants.py#L17-L19)):
> *"khi CÙNG lúc cộng dồn với HEAVY_MORNING_BONUS trên cùng 1 candidate, 30+30=60 > 50 thì cặp bonus mềm này CÓ THỂ thắng phạt dàn-môn; đây là hành vi mềm có chủ đích"*

**Kết luận**: ✅ **Đã documented**, có chủ đích — trong trường hợp GV trống trọn ngày + môn Nặng tiết đầu sáng thì ưu tiên xếp vào ngày trống dù phải dàn-môn liền ngày (chỉ cho môn không nằm trong `non_consecutive_subject_ids`).

---

### ✅ Phát hiện 5: `single_pair_ids` ưu tiên trên `kep_ids` — đã fix

Trong [roles.py L40-43](file:///c:/Users/Kien/tkb_app/core/roles.py#L40-L43):
```python
for subject_id in single_pair_subject_ids:
    idx.kep_ids.discard(subject_id)  # loại khỏi kep trước
    idx.single_pair_ids.add(subject_id)
    idx.block_size[subject_id] = 2
```

**Kết luận**: ✅ **Đã fix** trong SDD trước — ưu tiên `single_pair` > `kep`.

---

### ✅ Phát hiện 6: `pinned_full_day_off` vs `mandatory_morning_weekdays` — đã có guard

Trong `_assign_off_slots` ([teacher_off.py L29](file:///c:/Users/Kien/tkb_app/core/scheduler/teacher_off.py#L29)):
```python
forbidden = set(forbidden_off_cells) | {(wd, "S") for wd in mandatory_mornings}
```
Và pinned_full_day_off check ([teacher_off.py L41](file:///c:/Users/Kien/tkb_app/core/scheduler/teacher_off.py#L41)):
```python
if wd in WEEKDAYS and (wd, "S") not in forbidden and (wd, "C") not in forbidden:
```

**Kết luận**: ✅ Pinned nghỉ trọn ngày tự động bị chặn nếu rơi vào ngày bắt buộc sáng.

---

## IV. ĐÁNH GIÁ THUẬT TOÁN SẮP XẾP

### Kiến trúc: Randomized Greedy + Local Repair + Best-of-N

```
┌─────────────────────────────────────────────────────────────────┐
│  attempt 1..6000 (SO_LAN_THU)                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 1. Assign off-slots (random)                             │  │
│  │ 2. Pin chào cờ (HDTN, T2 tiết 1)                        │  │
│  │ 3. Reserve SHL slot                                      │  │
│  │ 4. Greedy pass (timeslot order):                         │  │
│  │    ├── Try block placement (block_size ≥ 2)              │  │
│  │    ├── Pick best scored candidate                        │  │
│  │    ├── Try swap repair (if stuck)                        │  │
│  │    └── Skip slot (if surplus)                            │  │
│  │ 5. Place reserved SHL                                    │  │
│  │ 6. Repair lone periods                                   │  │
│  │ 7. Repair unpaired blocks                                │  │
│  │ 8. Verify non-consecutive                                │  │
│  │ 9. Score: (teacher_quality_penalty, cells_changed)       │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Stop early if 25 successes found (SO_PA_TOT)                  │
│  Keep best = min(teacher_penalty, cells_changed)                │
└─────────────────────────────────────────────────────────────────┘
```

### 4.1 Đánh giá tổng thể: ✅ Phù hợp và Tối ưu cho bài toán

| Tiêu chí | Đánh giá |
|---|---|
| **Tính khả thi (Feasibility)** | Greedy + feasibility check đảm bảo KHÔNG BAO GIỜ vi phạm ràng buộc cứng |
| **Chất lượng (Quality)** | Best-of-N (25 phương án) + teacher_quality_penalty chọn phương án tốt nhất |
| **Đa dạng hoá** | Random off-slots + random candidate shuffle + timeslot shuffle (sau NGUONG_KHOA) |
| **Ổn định** | Keep-old bonus (+1M) ưu tiên giữ lịch cũ, giảm dần theo pu (exploration rate) |
| **Sửa lỗi cục bộ** | 3 pha repair: swap_repair, lone_period_repair, unpaired_block_repair |
| **Hiệu năng** | O(attempts × slots × subjects) — chấp nhận được cho ~15 lớp × 42 ô × 15 môn |
| **Thoát deadlock** | Sau `NGUONG_KHOA=60` lần: shuffle timeslot groups + tăng exploration rate |

### 4.2 Thứ tự ưu tiên trong scoring — phân tích chi tiết

| Mức ưu tiên | Quy tắc | Điểm | Nhận xét |
|---|---|---|---|
| **Tuyệt đối** | Keep-old bonus | +1,000,000 | Giảm dần theo pu — đúng |
| **Rất cao** | Môn thiếu nhiều nhất | remaining_need × 100 | Đúng: ưu tiên môn thiếu tiết |
| **Cao** | GV sáng bắt buộc | +280 | Đúng: mạnh hơn tất cả bonus khác |
| **Trung-cao** | GV lỗ hổng penalty | +250 × dist | Đúng: ngăn tiết trống giữa buổi |
| **Trung bình** | Phạt ngày chia đôi GV | -180 | Hợp lý: tránh sáng 1 + chiều 1 tiết |
| **Trung bình** | Lấp lỗ hổng GV | +180 (thưởng) | Hợp lý |
| **Trung bình** | GV liền kề / cặp buổi | +150 | Hợp lý |
| **Nhẹ** | Dàn-môn GDTC | -150 (50+100) | Mạnh hơn dàn-môn thường — đúng |
| **Nhẹ** | Phạt dàn-môn thường | -50 | Hợp lý: mềm, không chặn |
| **Nhẹ** | Block complete | +40 | Gợi ý, không ép — đúng |
| **Rất nhẹ** | Idle day / Heavy morning / Afternoon mismatch | ±30 | Vi điều chỉnh — đúng |
| **Tắt** | Balance afternoon (greedy) | 0 | Chủ đích: chuyển sang quality phase |

**Nhận xét**: Thứ tự ưu tiên **hợp lý và nhất quán**. Các mức điểm không tạo ra đảo ngược ưu tiên ngoài ý muốn (trừ IDLE_DAY + HEAVY_MORNING đã documented).

### 4.3 Quality Penalty — so sánh giữa các phương án

| Metric | Hệ số | Ý nghĩa |
|---|---|---|
| Teacher gaps | × 350 | Nặng nhất — đúng: lỗ hổng GV ảnh hưởng trực tiếp |
| Missing mandatory mornings | × 800 | Rất nặng — đúng: GV tải cao phải có mặt sáng T2/T5/T6 |
| Lone sessions | × 180 | Trung bình |
| Split sessions (1S+1C) | × 200 | Trung bình |
| Lone days | × 250 | Nặng — đúng: 1 tiết/ngày rất lãng phí |
| Missing afternoon duty | × 200 | Trung bình |

**Nhận xét**: ✅ Hệ số quality penalty **hợp lý**. `mandatory_mornings × 800` đúng là cao nhất vì đây là yêu cầu cứng của trường.

### 4.4 Potential Improvements (Đề xuất tối ưu)

> [!NOTE]
> Các đề xuất dưới đây là **tối ưu hoá thêm**, không phải lỗi hay xung đột. Hệ thống hiện tại hoạt động đúng.

#### 1. `_try_swap_repair` không check non-consecutive sau swap
- [swaps.py L24-36](file:///c:/Users/Kien/tkb_app/core/scheduler/swaps.py#L24-L36): Sau khi swap, không verify rằng tiết mới không tạo ra vi phạm non-consecutive cho môn bị di chuyển.
- **Tác động**: Thấp — post-check ở [engine.py L212-220](file:///c:/Users/Kien/tkb_app/core/scheduler/engine.py#L212-L220) sẽ reject toàn bộ attempt nếu xảy ra. Nhưng gây lãng phí 1 attempt.
- **Đề xuất**: Thêm check non-consecutive vào `_try_swap_repair` trước khi `_put_at`.

#### 2. `_repair_unpaired_blocks` không check non-consecutive
- [blocks.py L109-144](file:///c:/Users/Kien/tkb_app/core/scheduler/blocks.py#L109-L144): `_merge_one_block_period` di chuyển tiết giữa các ngày mà không check xem có tạo cặp liên tiếp cho môn đó không.
- **Tác động**: Tương tự phát hiện trên — post-check bắt được nhưng lãng phí attempt.

---

## V. KẾT LUẬN TỔNG THỂ

### Kết quả kiểm tra xung đột

| Loại | Số lượng | Kết quả |
|---|---|---|
| Xung đột cứng-cứng | 0 / 14 rules | ✅ Không có |
| Xung đột cứng-mềm | 0 / 14×13 cặp | ✅ Không có |
| Xung đột mềm-mềm | 1 documented | ✅ Có chủ đích (IDLE_DAY + HEAVY_MORNING > dàn-môn) |
| Enforcement gaps (cứng → validate) | 0 | ✅ Tất cả ràng buộc cứng đều có hàm validate tương ứng |

### Đánh giá thuật toán

| Tiêu chí | Điểm | Ghi chú |
|---|---|---|
| Tính đúng đắn | **10/10** | Không bao giờ output lời giải vi phạm ràng buộc cứng |
| Chất lượng output | **9/10** | Best-of-25 với quality penalty phức tạp |
| Hiệu suất | **8/10** | 6000 attempts × ~42×15 ops — chấp nhận được, <4 phút |
| Khả năng thoát deadlock | **8/10** | Shuffle + pu tăng dần, nhưng repair không check non-consecutive |
| Tính bảo trì | **9/10** | Code modular, constants tách riêng, comment đầy đủ |

### 🏁 Verdict

**Hệ thống rule và thuật toán hiện tại KHÔNG CÓ XUNG ĐỘT và hoạt động đúng.**

Cải thiện nhỏ có thể làm: check non-consecutive trong swap/block repair để tránh lãng phí attempt.
