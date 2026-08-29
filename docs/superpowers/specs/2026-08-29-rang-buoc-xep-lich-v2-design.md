# Ràng buộc xếp lịch v2: môn sáng/chiều theo mức độ nặng, nghỉ riêng cho GV, luật môn/lớp theo buổi cụ thể, và trang Hướng dẫn sử dụng

Ngày: 2026-08-29

## Bối cảnh & động lực

Sau khi [spec 2026-08-28](2026-08-28-cau-hinh-xep-lich-design.md) đưa 7 hằng số
"lựa chọn của trường" vào `SchedulingConfig` + trang **Cấu hình xếp lịch**,
hiệu trưởng nêu thêm 4 yêu cầu thực tế mới cho năm học này, cộng 1 yêu cầu
tài liệu:

1. Buổi sáng nên ưu tiên môn nặng kiến thức.
2. Buổi chiều chỉ nên có các môn nhẹ (Nhạc, Mĩ thuật, GDCD, GDĐP, Tin, HĐTN,
   Công nghệ, Thể dục) — buổi chiều Thứ 2/Thứ 6 đã nghỉ mặc định qua
   `reserved_off_weekdays_chieu` nên không cần tính riêng.
3. Một giáo viên Thể dục cụ thể đang ốm, cần được xếp nghỉ nhiều hơn mức
   chung của trường: 1 ngày nghỉ trọn + 1 buổi chiều cố định.
4. Phó hiệu trưởng chỉ đạo: 4 tiết Nhạc của khối 6 và khối 9 phải dồn vào
   đúng 2 buổi chiều cụ thể trong tuần, để buổi sáng trống cho họp/khách.
5. Thêm trang "Hướng dẫn sử dụng" cho toàn bộ app (hiện chưa có trang nào
   như vậy).

Việc phân tích cho thấy yêu cầu #1 sẽ **tự động đạt được** nếu #2 là ràng
buộc cứng (môn không nằm trong danh sách buổi chiều sẽ bị đẩy về buổi sáng)
— nhưng người dùng chọn giữ #2 là ràng buộc **mềm** (linh hoạt hơn, tránh
làm hỏng khả năng tìm lời giải của thuật toán), nên #1 vẫn cần một quy tắc
ưu tiên riêng, độc lập với #2.

4 yêu cầu #1-#4 đụng vào 3 tầng khác nhau (model dữ liệu, thuật toán xếp,
UI cấu hình) và ở 2 mức ràng buộc khác nhau (mềm/cứng). Việc tách thành các
sub-project riêng đã được đề xuất nhưng người dùng chọn gộp tất cả vào một
spec duy nhất — spec này vì vậy có 4 mục kiến trúc độc lập, mỗi mục có thể
implement/test riêng dù nằm chung 1 spec/plan.

## Phạm vi

**Trong phạm vi:**

| # | Tính năng | Loại ràng buộc |
|---|---|---|
| 1+2 | Môn nặng ưu tiên đầu buổi sáng + môn nhẹ ưu tiên buổi chiều | Mềm (scoring) |
| 3 | Override số buổi nghỉ/tuần + ghim buổi nghỉ cụ thể cho 1 GV | Cứng (assignment) |
| 4 | Luật tổng quát: môn X + tập lớp Y chỉ được xếp vào tập ô (thứ, buổi) Z | Cứng (feasibility) |
| 5 | Trang Hướng dẫn sử dụng cho toàn bộ app | Tài liệu, không phải ràng buộc |

**Ngoài phạm vi** (và lý do):

- **Khái niệm "khối" (grade) trong data model** — không cần thiết. Yêu cầu
  #4 tổng quát hoá thành "môn + **danh sách lớp** do người dùng chọn thủ
  công", không cần app hiểu khái niệm khối/suy luận từ tên lớp.
- **Thay đổi hành vi mặc định của trường khác** — mọi field/bảng mới trong
  spec này có giá trị mặc định = tắt tính năng (xem mục "Di trú dữ liệu"),
  đúng nguyên tắc đã thiết lập ở spec trước.
- **Tối ưu UX 5 trang "Thiết lập dữ liệu"** — đã ghi ngoài phạm vi ở spec
  trước, vẫn ngoài phạm vi ở đây.
- **Tinh chỉnh hệ số scoring hiện có** (`IDLE_DAY_BONUS`, phạt dàn-môn ±50,
  bonus giữ-môn-cũ) — không đụng, chỉ thêm hệ số mới cùng bậc độ lớn.

## Kiến trúc

### 1. Yêu cầu #1+#2 — Ưu tiên môn nặng đầu sáng / môn nhẹ buổi chiều (MỀM)

**`core/models.py`** — `SchedulingConfig` thêm 2 field:

```python
heavy_subject_priority_periods: int = 0   # 0 = tắt; số tiết đầu buổi sáng được cộng điểm ưu tiên môn "Nặng"
afternoon_preferred_subject_ids: frozenset = field(default_factory=frozenset)  # rỗng = tắt
```

Mặc định `0`/rỗng = **tắt hoàn toàn**, không đổi hành vi trường nào cho tới
khi trường đó chủ động cấu hình — nhất quán với nguyên tắc của spec trước.
Trường hiện tại (người yêu cầu) sẽ tự đặt `heavy_subject_priority_periods=2`
và chọn danh sách môn nhẹ qua UI sau khi tính năng lên.

**`data/repository.py`** — `get_scheduling_config`/`set_scheduling_config`
thêm 2 key `app_meta` mới: `sched_heavy_subject_priority_periods` (int
string), `sched_afternoon_preferred_subject_ids` (chuỗi id cách nhau dấu
phẩy, dùng chung helper `_parse_off_cells`-style nhưng đơn giản hơn vì chỉ
là tập số nguyên — viết `_parse_id_set`/`_format_id_set` nhỏ, không tái
dùng `_parse_off_cells` vì đó là parser cho cặp (thứ, buổi) chứ không phải
id đơn).

**`core/scheduler.py`** — `_pick_best_scored()` (dòng 206-243) thêm, ngay
sau khối tính `score` hiện có và trước dòng so `slot.old_subject_id`:

```python
if (subj.subject_id in role_index.heavy_ids and config.heavy_subject_priority_periods > 0
        and ts.session == "S" and ts.period <= config.heavy_subject_priority_periods):
    score += HEAVY_MORNING_BONUS
if (ts.session == "C" and config.afternoon_preferred_subject_ids
        and subj.subject_id not in config.afternoon_preferred_subject_ids):
    score -= AFTERNOON_MISMATCH_PENALTY
```

`HEAVY_MORNING_BONUS = 30`, `AFTERNOON_MISMATCH_PENALTY = 30` (hằng số
module mới, cùng bậc `IDLE_DAY_BONUS = 30` — đủ để phân biệt các ứng viên
gần nhau về `remaining_need`, không đủ để lấn át chênh lệch `remaining_need
* 100`). Hai quy tắc **độc lập, chỉ cộng dồn khi cả hai cùng khớp** — #1
chỉ thưởng điểm cho tiết sáng sớm (không phạt môn nặng ở tiết sáng muộn hay
buổi chiều, tránh chồng lấn với việc #2 đã tự phạt buổi chiều theo danh
sách riêng của nó). Chỉ áp dụng trong `_pick_best_scored` — **không** đụng
`_pick_best_simple`/`_try_swap_repair` (các đường sửa lỗi/dự phòng ưu tiên
tìm được lời giải khả thi hơn là tối ưu sở thích), giữ đúng vai trò "ràng
buộc mềm, best-effort".

**UI** — `pages/10_Cau_hinh_Xep_lich.py` thêm vào subheader "Ngưỡng số
lượng": 1 `number_input` cho `heavy_subject_priority_periods` (0..
`max_p`). Thêm subheader mới "Ưu tiên buổi (mềm)" chứa 1 `multiselect` môn
cho `afternoon_preferred_subject_ids` (options = toàn bộ `repo.list_subjects(conn)`).

**`ui_common.py`** — `sidebar_fixed_rules()` thêm 2 dòng mô tả (chỉ hiện
khi giá trị khác mặc định-tắt, để không làm rối sidebar các trường chưa
dùng tính năng này):

```python
if config.heavy_subject_priority_periods > 0:
    configurable_rules.append(
        f"Môn nặng được ưu tiên (không bắt buộc) vào {config.heavy_subject_priority_periods} tiết đầu buổi sáng"
    )
if config.afternoon_preferred_subject_ids:
    configurable_rules.append("Buổi chiều được ưu tiên (không bắt buộc) cho một số môn đã chọn ở Cấu hình xếp lịch")
```

### 2. Yêu cầu #3 — Override nghỉ + ghim buổi nghỉ riêng cho 1 GV (CỨNG)

**`core/models.py`** — `Teacher` thêm 3 field, áp dụng được cho **bất kỳ**
GV nào (không hardcode tên/id GV Thể dục — trường tự chọn đúng GV qua UI):

```python
off_sessions_override: Optional[int] = None    # None = dùng config.teacher_off_sessions_per_week
pinned_full_day_off: Optional[int] = None       # thứ (2-7) ghim nghỉ TRỌN NGÀY (ngoại lệ luật "không nghỉ trọn ngày")
pinned_afternoon_off: Optional[int] = None      # thứ ghim nghỉ 1 buổi CHIỀU cố định
```

**`data/db.py`** — 3 cột nullable mới trên bảng `teachers`, qua
`_ensure_column()` (dòng 134) trong `init_db()`:

```python
_ensure_column(conn, "teachers", "off_sessions_override", "off_sessions_override INTEGER")
_ensure_column(conn, "teachers", "pinned_full_day_off", "pinned_full_day_off INTEGER")
_ensure_column(conn, "teachers", "pinned_afternoon_off", "pinned_afternoon_off INTEGER")
```

**`data/repository.py`** — `list_teachers`/`upsert_teacher` (dòng 86-100)
đọc/ghi thêm 3 cột này (giá trị `NULL`/`None` giữ nguyên = không override).

**`core/scheduler.py`** — `_assign_off_slots()` (dòng 299-346): với mỗi
`tid`, sau khi tính `forbidden` như hiện tại:

```python
pinned_cells = set()
if t and t.pinned_full_day_off is not None:
    wd = t.pinned_full_day_off
    if (wd, "S") not in forbidden and (wd, "C") not in forbidden:
        pinned_cells |= {(wd, "S"), (wd, "C")}
if t and t.pinned_afternoon_off is not None:
    wd = t.pinned_afternoon_off
    if (wd, "C") not in forbidden:
        pinned_cells.add((wd, "C"))

effective_count = t.off_sessions_override if (t and t.off_sessions_override is not None) else off_slot_count
remaining_count = max(0, effective_count - len(pinned_cells))
# ... chọn ngẫu nhiên remaining_count cell còn lại từ eligible_weekdays/by_weekday
# NGOẠI TRỪ các thứ đã dùng trong pinned_cells (tránh trùng ngày, giữ đúng bất biến
# "không nghỉ trọn ngày" CHO PHẦN NGẪU NHIÊN — pinned_full_day_off là ngoại lệ duy nhất được phép)
gv_off_slots[tid] = pinned_cells | <phần chọn ngẫu nhiên còn lại>
```

Nếu pin xung đột với `forbidden` (VD trùng `forbidden_off_cells` hoặc
`must_monday`), pin đó bị **bỏ qua âm thầm** ở tầng scheduler — vì vậy UI
**bắt buộc validate khi lưu** (xem dưới) để không tạo cấu hình vô nghĩa mà
người dùng tưởng đã có hiệu lực.

**UI** — `pages/01_Khai_bao.py`, tab "Giáo viên" (dòng 71-97): thêm 3 cột
vào `st.data_editor`:

- `"Nghỉ mấy buổi/tuần (bỏ trống = mặc định trường)"` — number_input
  nullable.
- `"Nghỉ trọn ngày - Thứ"` / `"Nghỉ chiều cố định - Thứ"` — selectbox cho
  phép "Không ghim" + `WEEKDAY_NAMES`.

Validate khi bấm "Lưu danh sách giáo viên": nếu GV có `must_monday=True`
và chọn `pinned_full_day_off`/`pinned_afternoon_off = Thứ 2`, hoặc chọn
thứ nằm trong `config.forbidden_off_cells` cho buổi tương ứng → báo lỗi rõ
ràng (nêu tên GV + lý do), không lưu dòng đó.

### 3. Yêu cầu #4 — Luật môn/lớp theo buổi cụ thể, tổng quát (CỨNG)

**`data/db.py`** — bảng mới trong `SCHEMA`:

```sql
CREATE TABLE IF NOT EXISTS subject_class_slot_rules (
    rule_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(subject_id) ON DELETE CASCADE,
    class_ids  TEXT NOT NULL,   -- "3,7,9" (comma-separated class_id)
    cells      TEXT NOT NULL    -- "3C,6C" (định dạng thứ+buổi giống forbidden_off_cells)
);
```

Mỗi row = 1 luật do người dùng tạo: *"môn X, các lớp Y, CHỈ được xếp vào
các ô (thứ, buổi) Z"*. Ví dụ của phó hiệu trưởng (Nhạc, khối 6+9, 2 buổi
chiều cụ thể) = 1 row duy nhất, `class_ids` liệt kê mọi lớp thuộc khối 6 và
9 (người dùng tự chọn, app không suy luận khối từ tên lớp).

**`data/repository.py`** — hàm mới:

```python
def list_subject_class_rules(conn) -> list[dict]: ...        # đọc thô, cho UI hiển thị/sửa/xoá
def upsert_subject_class_rule(conn, subject_id, class_ids, cells, rule_id=None) -> int: ...
def delete_subject_class_rule(conn, rule_id) -> None: ...
def get_subject_class_allowed_cells(conn) -> dict:
    """(subject_id, class_id) -> frozenset[(weekday, session)], mở rộng mỗi
    row thành N entries (1 mỗi class_id trong class_ids)."""
```

`build_scheduling_input()` (dòng 601+) gọi thêm
`get_subject_class_allowed_cells(conn)` và gán vào field mới của
`SchedulingInput`.

**`core/models.py`** — `SchedulingInput` thêm field mới, song song
`ban_busy` (đây là dữ liệu nhiều-dòng dạng lookup, không phải 1 giá trị
cấu hình đơn nên **không** đặt trong `SchedulingConfig`):

```python
subject_class_allowed_cells: dict = field(default_factory=dict)  # (subject_id, class_id) -> frozenset[(weekday, session)]
```

**`core/scheduler.py`** — `_feasible()` (dòng 80-119) nhận thêm tham số
`subject_class_allowed_cells: Optional[dict] = None`, thêm early-return
ngay đầu hàm (trước hoặc sau check `busy` đều được, đặt sớm cho rẻ):

```python
if subject_class_allowed_cells is not None:
    allowed = subject_class_allowed_cells.get((subject_id, class_id))
    if allowed is not None and (ts.weekday, ts.session) not in allowed:
        return False
```

Tham số này phải truyền xuyên suốt **mọi** lời gọi `_feasible()`:
`_pick_best_scored`, `_pick_best_simple`, `_try_swap_repair`,
`_repair_lone_periods`, và 2 chỗ gọi trực tiếp trong `run()` (ghim chào cờ
dòng 453, ghim SHL dòng 510) — đúng khuôn mẫu tham số `config`/
`day_capacity` đang được truyền hiện tại qua toàn bộ call chain.

**Lưu ý validate quan trọng**: môn HDTN (`role_index.hdtn_id`) đã có vị trí
ghim cứng riêng (chào cờ Thứ 2 sáng + SHL cuối tuần) nằm ngoài luật này —
nếu người dùng tạo luật giới hạn HDTN vào các ô không bao gồm những vị trí
ghim đó, chào cờ/SHL sẽ **luôn thất bại**. UI phải loại HDTN khỏi danh sách
môn có thể chọn khi tạo luật (dùng `role_index.hdtn_id`/role_code=5 để lọc
ra, tương tự cách `resolve_roles` xác định môn HDTN). Môn GDTC vẫn được
phép (không có vị trí ghim tuyệt đối, chỉ né 1 tiết qua
`gdtc_avoid_period`), nhưng nên có `st.caption` cảnh báo 2 ràng buộc này
cộng dồn có thể làm hẹp chỗ xếp.

`FAILURE_MESSAGE` (dòng 39-45) thêm 1 dòng nguyên nhân mới:

```
(4) Luật gán môn/lớp theo buổi (trang Cấu hình xếp lịch) quá chặt so với số tiết/tuần cần xếp.
```

**UI** — `pages/10_Cau_hinh_Xep_lich.py`, subheader mới cuối trang "Ràng
buộc môn/lớp theo buổi cụ thể (tuỳ chọn)":

- Form thêm luật: `selectbox` môn (loại trừ HDTN), `multiselect` lớp,
  `multiselect` ô (thứ, buổi) — tái dùng đúng `format_func` kiểu
  `WEEKDAY_NAMES`/"Sáng"/"Chiều" đã có ở `forbidden_selection`.
- Danh sách luật hiện có (mỗi luật 1 dòng: tên môn, tên lớp, tên ô) kèm nút
  xoá (`repo.delete_subject_class_rule`).

### 4. Trang Hướng dẫn sử dụng

Trang mới `pages/11_Huong_Dan.py` (icon 📖), thêm vào nhóm nav "Tổng quan"
trong `app.py` (cạnh Trang chủ). Nội dung tĩnh (markdown + `st.expander`
theo từng chủ đề, không đọc DB), bám theo đúng thứ tự luồng làm việc thật:

1. Tổng quan luồng: Khai báo → Phân công → Định mức → GV bận → Khung tiết
   → Cấu hình xếp lịch → Xếp TKB tự động → Cân bằng tải → Lịch sử tuần →
   Import/Export.
2. Khai báo Lớp/Môn/Giáo viên — ý nghĩa "Vai trò" môn (Thường/Nặng/Kép/
   Nặng+Kép/GDTC/HDTN), "Đi T2"/"GVCN", và 3 field mới (override + 2 ghim
   nghỉ) từ mục 2 spec này.
3. Phân công chuyên môn, Định mức tiết/tuần, Giáo viên bận, Khung tiết —
   1 đoạn ngắn mỗi trang, tập trung "trang này dùng để làm gì" hơn là dịch
   lại từng nút bấm.
4. Cấu hình xếp lịch — giải thích **từng field** hiện có (7 field cũ) +
   field mới (mục 1: 2 field mềm; mục 3: luật môn/lớp).
5. Xếp TKB tự động — cách chạy, đọc kết quả, và ý nghĩa từng nguyên nhân
   trong `FAILURE_MESSAGE` (gồm nguyên nhân #4 mới) khi thất bại.
6. Cân bằng tải giáo viên, Lịch sử tuần, Nhập/Xuất Excel — 1 đoạn ngắn mỗi
   trang.

## Testing

**`tests/test_scheduler.py`** — bộ test hiện có phải pass không đổi khi
gọi với `SchedulingConfig()` mặc định (xác nhận 2 field mới + rules rỗng
không đổi hành vi cũ). Thêm mới:

- `test_heavy_subject_prefers_early_morning_when_configured` — bật
  `heavy_subject_priority_periods=2`, xác nhận môn nặng có xu hướng rơi
  vào tiết 1-2 nhiều hơn baseline (thống kê trên nhiều seed, vì đây là
  ràng buộc mềm — không assert tuyệt đối "luôn luôn").
- `test_afternoon_preferred_subjects_soft_bias` — tương tự, thống kê thiên
  lệch chứ không assert cứng.
- `test_teacher_pinned_full_day_off` — GV có `pinned_full_day_off=Thứ 5`,
  xác nhận cả `(5,"S")` và `(5,"C")` đều nằm trong `gv_off_slots[tid]`.
- `test_teacher_pinned_afternoon_off` — tương tự cho `pinned_afternoon_off`.
- `test_teacher_off_sessions_override` — GV có `off_sessions_override=3`,
  xác nhận tổng số cell nghỉ = 3 dù `config.teacher_off_sessions_per_week`
  vẫn là mặc định 1 cho GV khác.
- `test_pinned_off_conflicts_with_forbidden_are_dropped` — pin trùng
  `forbidden_off_cells`/`must_monday` → pin đó không xuất hiện trong kết
  quả (không crash).
- `test_subject_class_allowed_cells_hard_reject` — `_feasible()` trả `False`
  khi `(ts.weekday, ts.session)` ngoài tập cho phép của
  `(subject_id, class_id)`, `True` khi trong tập, và **không ảnh hưởng**
  cặp (môn, lớp) không có trong dict.
- `test_subject_class_rule_thread_through_run` — chạy `run()` full với 1
  luật giới hạn 1 môn/1 lớp vào đúng 2 ô, xác nhận kết quả cuối cùng không
  vi phạm (test tích hợp, không chỉ unit `_feasible`).

**`tests/test_repository.py`** (hoặc file tương đương đang test
repository) — round-trip cho 2 field `SchedulingConfig` mới, 3 field
`Teacher` mới, và CRUD đầy đủ (`upsert`/`list`/`delete`) cho
`subject_class_slot_rules`.

**Kiểm thử thủ công**: chạy dev server (`/run`), (1) vào Khai báo → gán
override + ghim nghỉ cho 1 GV thật, (2) vào Cấu hình xếp lịch → bật cả 2
field mềm + tạo 1 luật môn/lớp, (3) chạy Xếp TKB tự động, xác nhận không
lỗi và kết quả phản ánh đúng cấu hình, (4) mở trang Hướng dẫn sử dụng, đọc
lướt toàn bộ để đảm bảo không còn đoạn "TBD".

## Di trú dữ liệu

Không cần script migrate — mọi thay đổi đều **mặc định tắt tính năng**,
giữ nguyên hành vi hiện tại cho tới khi người dùng chủ động cấu hình:

- `SchedulingConfig.heavy_subject_priority_periods` mặc định `0` (không
  phải `2` — xem lý do trong mục Kiến trúc #1: một giá trị khác 0 sẽ âm
  thầm đổi lịch của MỌI trường ngay khi deploy, trái nguyên tắc đã lập ở
  spec trước). `afternoon_preferred_subject_ids` mặc định rỗng.
- Cột `teachers.off_sessions_override`/`pinned_full_day_off`/
  `pinned_afternoon_off` mặc định `NULL` qua `_ensure_column` — GV hiện có
  không bị ảnh hưởng.
- Bảng `subject_class_slot_rules` mới, rỗng ban đầu — `get_subject_class_
  allowed_cells()` trả `{}`, `_feasible()` bỏ qua check khi dict rỗng.

Trường trong yêu cầu ban đầu (người đặt ra 4 yêu cầu này) sẽ tự cấu hình cả
4 tính năng qua UI sau khi tính năng lên — không cần seed dữ liệu sẵn cho
GV Thể dục hay luật Nhạc khối 6/9 trong migration.
