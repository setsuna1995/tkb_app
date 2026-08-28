# Cấu hình các ràng buộc "lựa chọn của trường" trong thuật toán xếp TKB

Ngày: 2026-08-28

## Bối cảnh & động lực

`core/scheduler.py` và `core/frame.py` đang hardcode nhiều con số vốn dĩ chỉ
đúng cho *một cách* tổ chức trường học cụ thể (né Tiết 5 cho GDTC, chào cờ
Thứ 2 Tiết 1, tối đa 3 tiết liên tiếp cho môn nặng...). Đây là quy tắc sư
phạm thật, nhưng khác trường có thể có lựa chọn khác — hiện không có cách
nào đổi chúng ngoài sửa code. Sidebar "📐 Quy tắc xếp lịch cố định" của
`ui_common.py` thậm chí ghi rõ: *"Áp dụng tự động khi xếp TKB, không chỉnh
được qua giao diện."*

Việc này nảy sinh trong lúc brainstorm tối ưu UX cho người dùng mới hoàn
toàn (đã import dữ liệu từ Excel cũ, cần rà soát/chỉnh theo thực tế hiện
tại) — họ cần chỉnh không chỉ dữ liệu (lớp/môn/GV/phân công) mà cả các quy
tắc xếp lịch này để khớp thực tế trường mình.

**Việc tối ưu UX 5 trang "Thiết lập dữ liệu"** (chỉ báo đã-rà-soát-sau-import,
giải thích thuật ngữ, ô tìm kiếm) đã được thiết kế sơ bộ trong cùng phiên
brainstorm nhưng **chưa được duyệt** — đây là một sub-project độc lập, có
spec/plan riêng khi được xác nhận, không nằm trong spec này.

## Phạm vi

**Trong phạm vi** — 7 hằng số "lựa chọn của trường", nhóm theo bản chất:

| Nhóm | Tham số | Giá trị mặc định (= hardcode hiện tại) | Vị trí hardcode hiện tại |
|---|---|---|---|
| Vị trí cố định | `gdtc_avoid_period` | 5 | `core/scheduler.py:87` |
| Vị trí cố định | `chao_co_weekday` | 2 (Thứ 2) | `core/scheduler.py:432` |
| Vị trí cố định | `chao_co_period` | 1 | `core/scheduler.py:432` |
| Ngưỡng số lượng | `max_heavy_consecutive` | 3 | `core/scheduler.py:103-113` |
| Ngưỡng số lượng | `max_periods_per_session` | 4 | `MAX_GV_BUOI`, `core/scheduler.py:18` |
| Ngưỡng số lượng | `teacher_off_sessions_per_week` | 1 | tham số `off_slot_count` có sẵn ở `_assign_off_slots`, `run()` chưa truyền |
| Buổi/ngày khoá cứng | `forbidden_off_cells` | {(2,S),(5,S),(6,S),(5,C),(6,C)} | `FORBIDDEN_OFF_CELLS`, `core/scheduler.py:36` |
| Buổi/ngày khoá cứng | `reserved_off_weekdays_chieu` | (5, 6) | `RESERVED_OFF_WEEKDAYS_CHIEU`, `core/frame.py:26` |

**Ngoài phạm vi** (quyết định trong lúc brainstorm, lý do đi kèm):

- **Ngày sinh hoạt lớp (SHL)** — không phải hằng số độc lập, mà *suy ra*
  từ `class_has_chieu` (khung tiết của lớp, đã cấu hình được ở trang Khung
  tiết) trong `run()` dòng 345-360. Đổi nó nghĩa là ghi đè công thức suy
  luận, không phải đổi 1 con số — rủi ro cao hơn lợi ích hiện tại.
- **Tham số tuning thuật toán** (`SO_LAN_THU`, `SO_PA_TOT`, `NGUONG_KHOA`,
  `IDLE_DAY_BONUS`) — ảnh hưởng tốc độ/chất lượng lời giải, không phải quy
  tắc sư phạm. Người dùng phổ thông chỉnh sai dễ làm thuật toán chạy lâu
  hoặc ra kết quả tệ mà không hiểu vì sao.
- **Ràng buộc lõi bất biến** (không trùng GV cùng tiết, tiết kép phải liền
  buổi, môn HDTN bắt buộc tồn tại) — định nghĩa gốc của bài toán, đổi được
  sẽ kéo theo tái cấu trúc thuật toán lớn.
- **Buổi/session của chào cờ** — luôn cố định là buổi Sáng (`session="S"`),
  chỉ Thứ và Tiết trong buổi sáng đó là chỉnh được. Chào cờ buổi chiều gần
  như không xảy ra trong thực tế trường học Việt Nam nên không cần thêm
  lựa chọn này.

## Kiến trúc

### 1. `SchedulingConfig` — dataclass mới

Thêm vào `core/models.py`, cạnh `RoleIndex`/`SchedulingInput` (giữ nguyên
quy ước: mọi cấu trúc dữ liệu dùng chung cho scheduler/importer/UI đặt
trong file này):

```python
@dataclass
class SchedulingConfig:
    gdtc_avoid_period: int = 5
    chao_co_weekday: int = 2
    chao_co_period: int = 1
    max_heavy_consecutive: int = 3
    max_periods_per_session: int = 4
    teacher_off_sessions_per_week: int = 1
    forbidden_off_cells: frozenset = field(
        default_factory=lambda: frozenset({(2, "S"), (5, "S"), (6, "S"), (5, "C"), (6, "C")})
    )
    reserved_off_weekdays_chieu: tuple = (5, 6)
```

`SchedulingInput` (cùng file) thêm 1 field mới, đúng khuôn `extra_kep_ids`
đã có:

```python
    config: SchedulingConfig = field(default_factory=SchedulingConfig)
```

Nhờ default factory, **mọi call site hiện tại của `SchedulingInput(...)` và
`sched.run(inp)` không cần sửa gì** — hành vi mặc định giữ nguyên 100% cho
tới khi một trường chủ động lưu cấu hình khác.

### 2. Lưu trữ — `data/repository.py`

Theo đúng khuôn `get_base_cap`/`set_base_cap` (mỗi field 1 dòng trong
`app_meta`, đọc qua `get_meta`/`set_meta` sẵn có — không thêm bảng mới):

```python
def get_scheduling_config(conn) -> SchedulingConfig:
    ...  # đọc từng key sched_*, parse int/tuple, fallback về default field-by-field

def set_scheduling_config(conn, config: SchedulingConfig) -> None:
    ...  # ghi từng field thành 1 key sched_* dạng string
```

Meta keys: `sched_gdtc_avoid_period`, `sched_chao_co_weekday`,
`sched_chao_co_period`, `sched_max_heavy_consecutive`,
`sched_max_periods_per_session`, `sched_teacher_off_sessions_per_week`,
`sched_forbidden_off_cells` (chuỗi `"2S,5S,6S,5C,6C"`, parse bằng 1 helper
nhỏ dùng chung cho get/set), `sched_reserved_off_weekdays_chieu` (chuỗi
`"5,6"`).

`build_scheduling_input()` (đã tồn tại trong `data/repository.py`, dùng
bởi `06_Xep_TKB.py`) gọi thêm `get_scheduling_config(conn)` và gán vào
`SchedulingInput.config` — 1 dòng, không đổi chữ ký hàm.

### 3. `core/scheduler.py` — đọc từ `inp.config` thay vì hằng số module

Các thay đổi tại đúng vị trí đã khảo sát:

- Dòng 87 (`ts.period == 5`) → `ts.period == config.gdtc_avoid_period`
- Dòng 432 (chào cờ) → so `ts.weekday == config.chao_co_weekday and
  ts.session == "S" and ts.period == config.chao_co_period`
- Dòng 18 `MAX_GV_BUOI` dùng ở dòng 83 → `config.max_periods_per_session`
- Dòng 36 `FORBIDDEN_OFF_CELLS` dùng ở `_assign_off_slots` dòng 312 → nhận
  qua tham số thay vì đọc hằng số module
- Dòng 418 (gọi `_assign_off_slots` không truyền `off_slot_count`) → truyền
  `off_slot_count=config.teacher_off_sessions_per_week`
- Dòng 103-113 (window trượt "3 tiết liên tiếp"): **viết lại tổng quát**
  theo `N = config.max_heavy_consecutive`. Logic hiện tại kiểm tra 2 cửa sổ
  cố định độ dài 4 bắt đầu tại tiết 1 và 2 (đủ cho buổi 5 tiết, chặn chuỗi
  4 tiết nặng liên tiếp = cho phép tối đa 3). Tổng quát hoá: cửa sổ độ dài
  `N + 1`, duyệt mọi điểm bắt đầu hợp lệ trong buổi (`range(1, max_periods_
  trong_buoi - N + 1)`) thay vì 2 điểm cố định `(1, 2)`. Đây là điểm rủi ro
  kỹ thuật cao nhất trong spec này — cần test riêng cho N = 2, 3, 4.

`_feasible()` và `_assign_off_slots()` nhận `config: SchedulingConfig` qua
tham số (lấy từ `inp.config` ở nơi gọi trong `run()`), không import hằng số
module nữa. `FORBIDDEN_OFF_CELLS`/`MAX_GV_BUOI` module-level giữ lại làm
**default value** cho tham số hàm (backward-compat cho test gọi hàm nội bộ
trực tiếp), nhưng nguồn sự thật khi chạy qua `run()` luôn là `inp.config`.

### 4. `core/frame.py` — tham số hoá `reserved_off_weekdays_chieu`

`RESERVED_OFF_WEEKDAYS_CHIEU` giữ làm default value cho tham số mới trên
các hàm liên quan (`active_cells`, `total_cells_per_class`, và hàm nào
khác đang đọc hằng số này) — module này độc lập với `scheduler.py`/
`SchedulingConfig` theo đúng ranh giới đã có ("frame = ô nào tồn tại,
scheduler = xếp gì vào ô"), nên không import `SchedulingConfig` từ đây.
Nơi gọi (các trang `pages/05_Khung_tiet.py`, `data/repository.py`) tự lấy
`config.reserved_off_weekdays_chieu` từ `get_scheduling_config(conn)` và
truyền vào.

### 5. UI — trang cấu hình mới

`pages/10_Cau_hinh_Xep_lich.py`:

- Đọc `repo.get_scheduling_config(conn)`, hiển thị form 7 ô nhập, nhóm theo
  3 bảng ở phần Phạm vi (dùng `st.subheader` phân nhóm, giống phong cách
  các trang setup khác).
- Validate range dựa trên hằng số có sẵn, không tự chế số magic mới:
  `chao_co_period`/`gdtc_avoid_period` ∈ [1, `frame.MAX_PERIODS_PER_SESSION`],
  `chao_co_weekday` ∈ `core.models.WEEKDAYS`, `max_heavy_consecutive` ∈
  [1, `frame.MAX_PERIODS_PER_SESSION`], `max_periods_per_session` ∈ [1,
  `frame.MAX_PERIODS_PER_SESSION`], `teacher_off_sessions_per_week` ∈
  [0, 3].
- `forbidden_off_cells`/`reserved_off_weekdays_chieu`: multiselect theo
  Thứ × Buổi, giống UI đã có ở `04_GV_Ban.py` (không phát minh pattern
  mới).
- Nút "Lưu cấu hình" → `repo.set_scheduling_config(conn, new_config)`.
- Đặt trong nhóm "Thiết lập dữ liệu" ở `app.py` (vị trí trong menu do dict
  `pages` quyết định, không cần đổi số file các trang cũ).

`ui_common.py` — `FIXED_SCHEDULING_RULES`/`sidebar_fixed_rules()`: đổi
sang hàm nhận `config: SchedulingConfig`, chèn giá trị thật vào câu chữ
cho 7 dòng đã tham số hoá (vd *"Thể dục né Tiết {config.gdtc_avoid_period}"*),
giữ nguyên dạng tĩnh cho các dòng thuộc nhóm "ràng buộc lõi bất biến" (không
trùng GV, tiết kép liền buổi, không buổi lẻ 1 tiết). Mọi trang gọi
`sidebar_fixed_rules()` cần truyền thêm `conn` (đã có sẵn ở mọi trang) để
hàm tự lấy config.

## Testing

Bộ test hiện có (`tests/test_scheduler.py`, `tests/test_frame.py`) đã phủ
đúng các bất biến mặc định cần giữ nguyên — dùng làm lưới an toàn:
`test_gdtc_never_period5`, `test_heavy_subject_run_of_3_cap`,
`test_max_gv_buoi_session_cap`, `test_off_slot_count_defaults_to_1_buoi_per_week`,
`test_off_slots_respect_forbidden_cells_gvcn_and_must_monday`,
`test_active_cells_never_includes_chieu_thu5_thu6`. Các test này phải pass
**không sửa nội dung** khi gọi với `SchedulingConfig()` mặc định — xác
nhận hành vi cũ không đổi.

Thêm test mới cho từng field khi đổi giá trị khỏi mặc định, tối thiểu:

- `test_gdtc_avoid_period_configurable` — đổi né tiết 3, xác nhận không
  bao giờ xếp GDTC vào tiết 3 (và CÓ xếp được vào tiết 5).
- `test_chao_co_position_configurable` — đổi Thứ 3 Tiết 2, xác nhận HDTN
  ghim đúng ô mới, không còn ghim T2 Tiết 1.
- `test_max_heavy_consecutive_configurable` — chạy lần lượt N=2 và N=4,
  xác nhận chuỗi tiết nặng liên tiếp tối đa đúng bằng N (đây là test quan
  trọng nhất — bảo vệ phần viết lại vòng lặp cửa sổ trượt).
- `test_max_periods_per_session_configurable` — đổi trần 3, xác nhận
  không GV nào có ≥ 4 tiết cùng buổi.
- `test_teacher_off_sessions_per_week_configurable` — đổi 2, xác nhận mỗi
  GV có đúng 2 buổi nghỉ (khi đủ chỗ).
- `test_forbidden_off_cells_configurable` — đổi tập cấm, xác nhận buổi
  nghỉ không rơi vào ô mới cấm, CÓ THỂ rơi vào ô cũ (không còn cấm).
- `test_reserved_off_weekdays_chieu_configurable` (ở `test_frame.py`) —
  đổi thành (4, 5), xác nhận `active_cells()` loại đúng buổi chiều mới,
  không còn loại chiều Thứ 6 mặc định.

## Di trú dữ liệu

Không cần script migrate: `get_scheduling_config()` fallback về giá trị
mặc định cho mọi key `sched_*` chưa tồn tại trong `app_meta` — trường đang
chạy (kể cả DB cũ hơn tính năng này) tự động giữ nguyên hành vi hiện tại
cho tới khi ai đó chủ động vào trang cấu hình mới và lưu.
