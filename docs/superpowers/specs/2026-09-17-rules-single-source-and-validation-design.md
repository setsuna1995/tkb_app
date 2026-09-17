# Hợp nhất nguồn sự thật cho bộ luật xếp TKB & sửa tầng validate

**Ngày:** 2026-09-17
**Trạng thái:** Chờ duyệt
**Phạm vi:** Sửa lỗi đúng đắn + hợp nhất tầng validate. Không bao gồm tối ưu hiệu năng, phân tầng trọng số, hay dọn engine greedy đã chết.

---

## 1. Vấn đề

Bộ luật HĐSP hiện được định nghĩa ở **ba nơi độc lập**, không có cơ chế nào đảm bảo chúng đồng ý với nhau:

| Tầng | File | Vai trò thực tế |
|---|---|---|
| 1. Mô hình | `core/scheduler/cpsat/objectives.py`, `constraints.py` | Thứ solver thực sự tối ưu và ép cứng |
| 2. Chấm điểm | `core/scheduler/quality.py` | Không còn caller nào trong luồng chạy |
| 3. Hậu kiểm | `core/validation.py` | **Thứ chặn nút lưu của người dùng** |

Đường sống là 1 → 3: solver tối ưu theo tầng 1, giao diện chặn lưu theo tầng 3. Hai tầng này chưa từng được kiểm chứng tương đương. Hệ quả đã đo được:

- **Báo lỗi giả.** Bật "Môn Nặng bắt buộc xếp buổi sáng" → CP-SAT cố ý nới trần môn nặng liên tiếp để bài toán khả thi (`constraints.py:292`), nhưng validator đọc trần gốc từ config (`pages/06_Xep_TKB.py:583`) → hiện lỗi đỏ trên lịch hợp lệ.
- **Mù với ràng buộc cứng.** Bảy ràng buộc CP-SAT ép cứng không có hậu kiểm nào. Ba lỗi mô hình phát hiện trong đợt audit đều nằm trong vùng mù này.
- **Luật kiểm sai bản chất.** `find_single_pair_violations` đếm số tiết/ngày nhưng luật quy định **hai tiết liền kề** — validator không xét tính liền kề, cũng không bắt trường hợp không có cặp nào.
- **Ngưỡng trôi lệch.** Cùng một ngưỡng có ba giá trị mặc định khác nhau: `15` (`validation.py:358`), `0` (`quality.py:32`), `8` (`models.py:155`).

Nguyên nhân gốc không phải từng lỗi riêng lẻ mà là **không có nguồn sự thật chung**: mỗi tầng tự đọc `config` bằng `getattr` rải rác, tự dựng bản đồ giáo viên, tự quyết định lọc `teacher_id` và ô trống.

---

## 2. Mục tiêu

1. Mọi ngưỡng luật — kể cả ngưỡng **thích ứng** do solver tự nới — có đúng một nơi được tính, và được mang theo trong kết quả để hậu kiểm dùng lại.
2. Mọi bộ đếm vi phạm nhận cùng một cách nhìn về lịch: cùng bản đồ giáo viên, cùng quy ước ô trống.
3. Mỗi ràng buộc cứng CP-SAT ép đều có một bộ đếm hậu kiểm tương ứng.
4. Nới lỏng một luật cứng phải là **một lượng có bằng chứng**, không phải một công tắc. Mọi nới lỏng vẫn được đếm và báo cáo như vi phạm.
5. Có một bài kiểm tra tự động khẳng định tầng 1 và tầng 3 đồng ý, chạy trên mọi luật.
6. Sửa các lỗi đúng đắn đã xác định trong đợt audit.

### Ngoài phạm vi

| Hạng mục | Lý do hoãn |
|---|---|
| Tiền tính `slots_by_session` (giảm ~40× thời gian dựng mô hình) | Hiệu năng, không ảnh hưởng tính đúng đắn |
| Phân tầng trọng số theo thứ tự từ điển | Thay đổi lớn hành vi tối ưu, cần đo riêng |
| Siết `time_limit` thành trần cứng | Độc lập, làm sau |
| Hệ số 10⁹ ở nhánh `minimize_changes` | Chung gốc với phân tầng trọng số |
| Xóa ~1.500 dòng engine greedy đã chết | Cần dọn test kèm theo, làm riêng |
| Encoding tiết trống nhẹ hơn | Hiệu năng |

---

## 3. Quyết định nghiệp vụ đã chốt

**Q1 — Luật II.8 (ngày chia lẻ) giữ nghĩa hẹp.** Điều kiện đúng là `S == 1 và C == 1`. Code cả ba tầng đã đúng; **docstring** tại `validation.py:414-425` mô tả sai và phải sửa. Ca bất đối xứng (1 tiết sáng + 3 tiết chiều) **không** tính vi phạm.

**Q2 — Luật buổi nghỉ GV trở thành tùy chọn có mức độ.** Khi bật: ưu tiên mềm, cố đạt tối đa có thể, không bao giờ gây vô nghiệm. Khi tắt: không can thiệp, để tải giáo viên và thuật toán tự quyết. Thiết kế chi tiết ở §5.2.

**Q3 — Phạm vi:** sửa lỗi + hợp nhất validate (đã nêu ở §2).

---

## 4. Kiến trúc

### 4.1 Ba khối mới

```
core/rules/
  __init__.py      RULES registry mở rộng (id, title, tier, config_flag, weight)
  params.py        Threshold, EffectiveParams, resolve_effective_params(inp)
  violations.py    Violation, Relaxation, classify(...)
  view.py          ScheduleView + build_schedule_view(inp, assignment)
  detectors.py     detect_*(view, params) -> list[Violation]
```

`core/rules_registry.py` hiện tại (85 dòng, 6 luật) được chuyển vào `core/rules/__init__.py` và mở rộng, giữ nguyên `RULES` và `HARD_POST_GENERATION_IDS` để không phá caller.

### 4.2 Ngữ nghĩa vi phạm — chuẩn duy nhất là config

Đây là nguyên tắc nền, mọi thứ còn lại suy ra từ nó.

> **Vi phạm luôn được đếm theo giá trị khai báo trong config. Không có ngoại lệ.**
> Việc mô hình nới trần hay bỏ qua một luật **không làm vi phạm biến mất** — nó chỉ giải thích *vì sao* vi phạm xảy ra. Nới lỏng về bản chất là một loại vi phạm, và phải được báo cáo như vậy.

Bản nháp trước của spec này vi phạm chính nguyên tắc đó: nó cho hậu kiểm đọc ngưỡng đã nới rồi so với số đếm của mô hình, tức để mô hình tự chấm bài mình. Hai tầng sẽ luôn đồng ý — về một chuẩn đã bị hạ.

Hệ quả cho V1: một lịch có 4 tiết nặng liên tiếp trong khi `max_heavy_consecutive = 3` **thật sự là vi phạm**, kể cả khi mô hình đã cố ý nới trần để bài toán khả thi. Cái sai không phải ở việc báo, mà ở việc báo nó như lỗi hệ thống thay vì như hệ quả bắt buộc có kèm bằng chứng.

#### Ba mức vi phạm

| Mức | Nghĩa | Chặn lưu? |
|---|---|---|
| `BREACH` | Vi phạm luật cứng mà **không** có bằng chứng bất khả kháng. Đây là bug mô hình hoặc lỗi cấu hình. | Có |
| `FORCED` | Vi phạm luật cứng nhưng mô hình **đã chứng minh** không thể ít hơn. Kèm bằng chứng và số vi phạm tối thiểu. | Không — cảnh báo + xác nhận |
| `SHORTFALL` | Chưa đạt một tiêu chí mềm. | Không |

```python
@dataclass(frozen=True)
class Violation:
    rule_id: str
    level: Literal["BREACH", "FORCED", "SHORTFALL"]
    teacher_id: Optional[int] = None
    class_id: Optional[int] = None
    weekday: Optional[int] = None
    session: Optional[str] = None
    period: Optional[int] = None
    detail: str = ""            # mô tả tiếng Việt hiển thị thẳng lên UI
    evidence: str = ""          # BẮT BUỘC khi level == "FORCED" -- vì sao không thể ít hơn
```

Trường `evidence` không được để rỗng ở mức `FORCED`. Không chứng minh được thì đó là `BREACH`, không phải `FORCED`. Đây là ràng buộc kiểm được bằng test (§6.2).

### 4.3 `EffectiveParams` — giữ cả hai giá trị, không thay thế

Vì chuẩn là config, `EffectiveParams` **không** được che mất giá trị khai báo. Nó mang **cả hai**, cộng lý do chênh lệch:

```python
@dataclass(frozen=True)
class Threshold:
    declared: int          # từ config -- chuẩn để ĐẾM vi phạm
    effective: int         # trị mô hình THỰC SỰ dùng -- chỉ để PHÂN LOẠI mức
    reason: str = ""       # bắt buộc khi effective != declared

    def __post_init__(self):
        if self.effective != self.declared and not self.reason:
            raise ValueError("chênh lệch ngưỡng phải có lý do")
```

**`effective` được điền hai thì.** Lúc `resolve_effective_params` chạy, chưa giải nên `effective = declared` với mọi ngưỡng — không có gì bị nới trước. Sau khi giải, `build_result` đọc giá trị `cap_var` mà solver đã chọn (§4.6) và điền lại `effective` kèm `reason` sinh tự động. Ngưỡng nào không phải nới thì hai trị bằng nhau và `reason` rỗng.

Thứ tự này quan trọng: nó đảm bảo **không ngưỡng nào bị nới trước khi chứng minh là cần**. Logic `_get_eff_max_heavy` hiện tại làm ngược — nới sẵn lúc dựng mô hình dựa trên một phép chia ước lượng, nên không ai biết liệu có thật sự cần hay không.

```python
@dataclass(frozen=True)
class EffectiveParams:
    # Ngưỡng tải (gộp ba default đang lệch nhau về một)
    min_weekly_periods_for_lone_penalty: int
    min_weekly_periods_for_mandatory_morning: int
    max_load_for_4consec_penalty: int

    # Tập miễn trừ đã giải quyết sẵn -- caller không tự tính lại
    lone_exempt_ids: frozenset[int]
    bgh_ids: frozenset[int]
    pinned_day_offs: dict[int, int]          # teacher_id -> weekday

    # Tải theo GV, tính MỘT lần từ _build_effective_assigned_teacher
    teacher_load: dict[int, int]

    # Ngưỡng THÍCH ỨNG -- mang cả declared lẫn effective
    max_heavy_per_session: dict[tuple[int, str], Threshold]
    max_heavy_consecutive: dict[tuple[int, str], Threshold]
    max_academic_per_morning: dict[int, Threshold]
    academic_floor_cells: frozenset[tuple[int, int]]   # {(class_id, weekday)} nơi sàn cứng >=1 có hiệu lực

    # Ngưỡng cố định (declared == effective, không cần Threshold)
    max_teacher_periods_per_day: int
    max_periods_per_session: int
    max_teacher_gaps_per_session: int
    mandatory_morning_weekdays: tuple
    strict_morning_weekdays: tuple

    # Cờ bật/tắt, giải quyết sẵn để detector không phải getattr
    flags: dict[str, bool]
```

**Quy tắc sử dụng, không được đảo:**

| Việc | Dùng trường nào |
|---|---|
| Đếm vi phạm | `declared` — luôn luôn |
| Ép ràng buộc trong CP-SAT | `effective` |
| Phân loại `BREACH` hay `FORCED` | so `declared` với `effective`; chênh lệch có `reason` → `FORCED`, `reason` trở thành `evidence` |

Ví dụ V1: lớp 9A có 14 tiết nặng, chỉ 4 buổi sáng, bật `heavy_subjects_morning_only`. `Threshold(declared=3, effective=4, reason="lớp 9A cần 14 tiết nặng trên 4 buổi sáng, tối thiểu 4 tiết/buổi")`. Detector đếm theo `declared=3` → tìm thấy các chuỗi 4 tiết. Bộ phân loại thấy `effective=4 >= 4` và có `reason` → gắn `FORCED`, `evidence = reason`. Người dùng thấy: *"⚠️ Lớp 9A: 4 tiết nặng liên tiếp sáng Thứ 3 — vượt trần 3 của cấu hình. Bắt buộc: lớp cần 14 tiết nặng trên 4 buổi sáng."* Không chặn lưu, không giả vờ là không có gì.

**Luồng:**

1. `resolve_effective_params(inp)` gọi đúng một lần đầu `build_model()` (`cpsat_model.py:52`), gắn vào `built.params`.
2. `constraints.py` và `objectives.py` đọc `.effective` từ `built.params`, thay toàn bộ `getattr(config, ..., default)` rải rác. Logic tính trần thích ứng hiện nằm trong `_get_eff_max_heavy` (`constraints.py:277-284`) và khối academic (`constraints.py:434-455`) chuyển sang `resolve_effective_params`, **kèm theo việc sinh `reason`** — hiện logic này nới trần mà không ghi lại vì sao.
3. `build_result()` (`solver.py:16`) sao `built.params` vào `ScheduleResult.effective_params`.
4. Hậu kiểm ở `pages/06_Xep_TKB.py` và `compute_tkb_health_score` đọc `result.effective_params`, không đọc `inp.config`.

### 4.4 `ScheduleView` — một cách nhìn duy nhất về lịch

Gốc của V5, V6, V8: mỗi hàm `find_*` tự lọc `teacher_id` theo một quy tắc riêng (`< 0` ở ba hàm, `<= 0` ở ba hàm khác, `> 0` ở `quality.py`), tự chọn bản đồ giáo viên (thô hay effective), và chỉ `quality.py` lọc sentinel `-1`.

```python
@dataclass(frozen=True)
class ScheduleView:
    slots: list[Slot]
    assignment: dict[int, Optional[int]]      # -1 đã quy về None
    slot_teacher: dict[int, Optional[int]]    # từ _build_effective_assigned_teacher; id <= 0 quy về None
    need: dict[tuple[int, int], int]
    classes: list
    subjects: list
    teachers: list
```

`build_schedule_view(inp, assignment)` là **nơi duy nhất** áp dụng hai quy ước lọc. Mọi detector nhận `ScheduleView`, không nhận `(slots, assignment, assigned_teacher)` rời rạc.

### 4.5 Detectors và bộ phân loại — hai việc tách rời

Không thể dùng chung *code* giữa CP-SAT (biến ký hiệu) và hậu kiểm (giá trị cụ thể) — hai miền khác nhau. Thứ có thể dùng chung, và spec này bắt buộc dùng chung:

1. **Tham số** — qua `EffectiveParams`, luôn đọc `.declared` khi đếm.
2. **Cách nhìn dữ liệu** — qua `ScheduleView`.
3. **Vị trí** — bộ dựng term CP-SAT và detector của cùng một luật phải nằm cạnh nhau, có comment trỏ chéo, để việc trôi lệch nhìn thấy được khi đọc.
4. **Kiểm chứng tương đương** — test tự động ở §6.

Việc phát hiện và việc phân loại phải tách rời, vì đó chính là chỗ bản nháp trước bị lẫn:

```python
# Phát hiện: CHỈ biết config, không biết gì về nới lỏng.
# Mọi Violation trả về đều mang level="BREACH".
def detect_<rule>(view: ScheduleView, params: EffectiveParams) -> list[Violation]

# Phân loại: hạ BREACH -> FORCED khi có bằng chứng bất khả kháng.
# Hai nguồn bằng chứng: Threshold.reason (ngưỡng thích ứng),
# và result.relaxations (nới lỏng do chẩn đoán, §4.6).
def classify(
    violations: list[Violation],
    params: EffectiveParams,
    relaxations: dict[str, Relaxation],
) -> list[Violation]
```

Detector không được nhận `relaxations`. Nếu nó biết luật nào đã được nới, nó sẽ lại tự bỏ qua vi phạm — đúng vòng luẩn quẩn cần tránh.

Trường `detail` thay cho `_format_rule_item` ở `pages/06_Xep_TKB.py:22` — định dạng thuộc về nơi phát hiện vi phạm, nơi còn đủ ngữ cảnh.

### 4.6 Nới lỏng luật cứng: nới **bao nhiêu**, không phải nới **hay không**

Cơ chế hiện tại nới theo kiểu công tắc: `_diagnose_and_solve` (`solver.py:299-408`) gặp INFEASIBLE thì bỏ **toàn bộ** luật đó cho **toàn trường**. Bốn vấn đề:

| Vấn đề | Vị trí | Hệ quả |
|---|---|---|
| Nới cả luật thay vì nới tối thiểu | `solver.py:400` `relaxed \|= offending` | Chỉ 1 GV bất khả kháng cũng làm cả trường mất luật đó |
| Timeout bị coi là bằng chứng | `solver.py:405-407` | UNKNOWN nghĩa là *chưa kết luận được*, không phải *không thể*. Hiện báo "đã nới lỏng" dù có thể tồn tại lịch tuân thủ đầy đủ |
| Thứ tự ưu tiên nới nằm cứng trong code | `solver.py:274` `("II.4", "II.8", "II.3")` | Trường không đổi được, không có căn cứ ghi lại |
| Sàng lọc tiền giải nới toàn cục | `solver.py:266-267` | Một sáng vi phạm pigeonhole → nới II.3 cho mọi sáng |

**Thay bằng: nới dần theo hai trục — từng luật một, và trong mỗi luật thì từng nấc phạm vi.**

Nguyên tắc: *một lần nới chỉ được lấy đi đúng phần tự do tối thiểu để bài toán có nghiệm, không hơn.*

#### Trục 1 — mỗi luật có một cách nới riêng, không phải công tắc

Mỗi luật cứng khai báo **trục nới** của nó trong `RuleSpec`. Có hai kiểu:

| Kiểu | Nghĩa | Biến mô hình |
|---|---|---|
| `widen` | Nới ngưỡng số, từng nấc 1 đơn vị, có trần | `cap_var = IntVar(declared, relax_ceiling)` thay cho hằng số; chi phí nới `= cap_var - declared` |
| `exempt` | Miễn trừ từng đơn vị phạm vi khỏi luật | `exempt_u = BoolVar()` cho mỗi đơn vị `u`; chi phí nới `= sum(exempt_u)` |

Bảng trục nới cho từng luật — **đơn vị phạm vi chọn nhỏ nhất còn có nghĩa**, để mỗi lần nới ảnh hưởng ít nhất:

| Luật | Kiểu | Đơn vị phạm vi | Trần nới |
|---|---|---|---|
| II.3 thiếu sáng bắt buộc | `exempt` | (GV, sáng) | — |
| II.4 buổi lẻ / ngày lẻ | `exempt` | (GV, buổi) | — |
| II.8 ngày chia lẻ | `exempt` | (GV, ngày) | — |
| Trần môn nặng liên tiếp | `widen` | (lớp, buổi) | `MAX_PERIODS_PER_SESSION` |
| Trần môn nặng / buổi | `widen` | (lớp, buổi) | `MAX_PERIODS_PER_SESSION` |
| Trần học thuật / sáng | `widen` | lớp | `MAX_PERIODS_PER_SESSION` |
| Trần tiết/ngày của GV | `widen` | GV | `declared + 2` |
| `FILL` lấp ô lớp quá tải | `exempt` | lớp | — |
| Lớp không hở tiết giữa buổi | **không nới** | — | — |
| Lớp không có buổi 1 tiết | **không nới** | — | — |
| Khối môn Kép liền kề | **không nới** | — | — |

Ba luật cuối không có trục nới: chúng là ràng buộc cấu trúc của một thời khóa biểu hợp lệ, vi phạm nghĩa là lịch hỏng chứ không phải trường phải đánh đổi. Vô nghiệm vì chúng là lỗi dữ liệu đầu vào, phải báo như vậy.

Điểm mấu chốt của kiểu `widen`: khi CP-SAT tự chọn `cap_var`, nó tìm ra **mức nới nhỏ nhất** mà không cần ta liệt kê sẵn các nấc. Và vì `cap_var` riêng cho từng (lớp, buổi), việc lớp 9A cần trần 4 **không** kéo theo lớp 8B cũng được trần 4 — đúng yêu cầu "hạn chế ảnh hưởng nhất có thể". Đây là khác biệt lớn so với `_get_eff_max_heavy` hiện tại, vốn nới theo lớp cho mọi buổi sáng của lớp đó.

Với kiểu `exempt` ở đơn vị nhỏ nhất, `sum(exempt_u)` đúng bằng số vi phạm — nhưng khác số đếm thuần ở chỗ ta **biết chính xác đơn vị nào** được miễn, nên vi phạm ngoài tập đó vẫn là `BREACH`.

#### Trục 2 — mở dần tập luật được phép nới

```
Pass 1 — mọi cap_var = declared, mọi exempt_u = 0.
  OPTIMAL/FEASIBLE  -> xong, không vi phạm nào.
  INFEASIBLE        -> trích UNSAT core, sang Pass 2 với tập khởi đầu = core
                       (core rỗng -> tập khởi đầu = luật có breach_priority thấp nhất).
  UNKNOWN           -> sang Pass cuối (KHÔNG coi là bằng chứng).

Pass k (k = 2..N) — tập S gồm các luật được phép nới:
  - Luật trong S: thả cap_var / exempt_u tự do.
  - Luật ngoài S: vẫn khóa ở mức config.
  - Mục tiêu: minimize  RELAX_WEIGHT * sum(chi phí nới của S)  +  (điểm phạt chất lượng)
  Khả thi -> DỪNG. Ghi lại chính xác đã nới gì, bao nhiêu, ở đâu.
  Vô nghiệm -> S := S + luật kế tiếp theo breach_priority tăng dần. Sang Pass k+1.

Pass cuối — chỉ khi Pass 1 trả UNKNOWN:
  Thả toàn bộ luật có trục nới, gắn nhãn minimality = "UNPROVEN".
```

Dừng ở **pass khả thi đầu tiên** đảm bảo tập luật bị nới là nhỏ nhất theo thứ tự ưu tiên; `minimize` bên trong pass đó đảm bảo lượng nới trong tập cũng nhỏ nhất. Hai trục kết hợp cho đúng thứ bạn yêu cầu: nới ít luật nhất, mỗi luật nới ít nhất.

`RELAX_WEIGHT` tính tại thời điểm dựng, không đặt cứng:

```python
RELAX_WEIGHT = 1 + sum(weight * len(terms) for weight, terms in quality_objective_terms)
```

Đây là cận trên chặt của tổng mọi điểm phạt chất lượng, nên mô hình không bao giờ chấp nhận nới thêm một nấc để đổi lấy điểm chất lượng. Tính từ dữ liệu nên không phình vô cớ ở trường nhỏ.

**Số lần giải không tăng so với hiện tại.** Vòng `while True` hiện có cũng nới dần từng luật, tối đa `len(active_rids) + 1` pass. Thiết kế mới giữ đúng cận đó, nhưng mỗi pass nới *một lượng tối thiểu* thay vì *cả luật*.

#### Kết quả nới lỏng ghi lại có cấu trúc

Thay cho `relaxed_rules: list[dict]`:

```python
@dataclass(frozen=True)
class Relaxation:
    rule_id: str
    kind: Literal["widen", "exempt"]

    # kind == "widen": ngưỡng bị nới, theo từng phạm vi cụ thể
    widened: dict[str, tuple[int, int]]   # "9A / Sáng" -> (declared=3, effective=4)

    # kind == "exempt": các đơn vị được miễn khỏi luật
    exempted: list[str]                   # ["Nguyễn Văn A / Thứ 3 Sáng", ...]

    minimality: Literal["PROVEN", "UNPROVEN"]
    source: Literal["unsat_core", "presolve_capacity", "timeout"]
    evidence: str                         # câu giải thích tiếng Việt
```

`ScheduleResult.relaxations: dict[str, Relaxation]`.

#### Bất biến nối nới lỏng với vi phạm

> Tập vi phạm được phép mang mức `FORCED` **đúng bằng** tập đơn vị nêu trong `relaxations`. Không hơn một phần tử.

Một vi phạm nằm ngoài phạm vi đã nới là `BREACH`, kể cả khi cùng `rule_id` với một luật đã được nới ở chỗ khác. Đây là điều mà cơ chế công tắc hiện tại không thể diễn đạt: nới II.4 cho một GV hiện đồng nghĩa mọi GV khác cũng hết bị kiểm.

Bất biến này kiểm được trực tiếp — xem `test_forced_within_relaxed_scope` ở §6.2.

#### Hệ quả: logic nới trần đoán trước bị bỏ

`_get_eff_max_heavy` (`constraints.py:277-284`) hiện **đoán trước** trần cần nới bằng phép chia pigeonhole rồi nới sẵn ngay khi dựng mô hình, cho cả lớp. Với `cap_var` thì không cần đoán nữa: Pass 1 khóa ở trần config, nếu vô nghiệm thì Pass 2 để solver tự tìm mức nới nhỏ nhất, riêng cho từng (lớp, buổi). Ba cái lợi:

- Mức nới là **tối thiểu chứng minh được**, không phải ước lượng của một công thức chia.
- Phạm vi nới hẹp hơn: hiện nới theo lớp cho mọi buổi sáng, sau sửa chỉ nới đúng buổi cần.
- Lý do nới không còn phải viết tay — nó là chênh lệch giữa `cap_var` giải ra và `declared`, sinh tự động.

Đổi lại tốn thêm một pass khi có nới. Chấp nhận được vì trước đó cũng đã có vòng lặp nới dần.

Khối tính sàn học thuật (`constraints.py:434-455`) xử lý tương tự.

#### Sàng lọc tiền giải không còn tự nới

`_presolve_capacity_screening` (`solver.py:220-269`) hiện trả `{"II.3"}` rồi nới thẳng cho toàn trường. Đổi thành: trả về **bằng chứng có địa chỉ** — sáng nào, sức chứa bao nhiêu, cần bao nhiêu — dùng để chọn tập khởi đầu của Pass 2 mà không phải tốn một vòng INFEASIBLE. Nới bao nhiêu, ở GV nào vẫn do Pass 2 giải ra, không do sàng lọc đoán. Bằng chứng trở thành `Relaxation.evidence`, ví dụ *"sáng Thứ 5 có 30 ô, 18 GV bắt buộc có mặt cần tối thiểu 36 ô"*.

#### Thứ tự ưu tiên thành dữ liệu

Thêm `breach_priority: int` vào `RuleSpec` — quyết định thứ tự **mở dần tập S** ở Trục 2, luật ưu tiên thấp được nới trước. Giá trị khởi đầu giữ đúng thứ tự cứng hiện có (II.4 nới trước, rồi II.8, rồi II.3). `_select_fallback_relaxations` (`solver.py:272-277`) bị xóa.

Đây cũng là chỗ trường có thể đổi chính sách mà không sửa mã: nếu trường coi "không GV nào vắng sáng Thứ 2" quan trọng hơn "không buổi lẻ", chỉ cần đảo `breach_priority`.

#### Ảnh hưởng tới giao diện

`pages/06_Xep_TKB.py:329-331` và `:966-968` hiện chỉ in số luật bị nới. Đổi thành liệt kê cụ thể:

> ⚠️ **Đã phải nới 1 ràng buộc để có lịch**
> **II.4 — buổi lẻ:** miễn trừ 2 trường hợp: *Nguyễn Văn A / Thứ 3 Sáng*, *Trần Thị B / Thứ 6 Chiều*.
> Lý do: mô hình chứng minh không thể ít hơn. Các GV và buổi khác vẫn được kiểm đầy đủ.

Khi `minimality == "UNPROVEN"` thêm dòng *"chưa chứng minh được đây là mức tối thiểu — thử tăng giới hạn thời gian giải"*. Đây là thông tin hành động được, khác hẳn "đã nới lỏng 2 ràng buộc".

### 4.7 `ScheduleResult.rule_counts` — số của mô hình, dùng để đối chứng chứ không để phán xét

`build_result` (`solver.py:37-48`) hiện chỉ đọc `penalty_terms` cho các luật hard-gate. Mở rộng: đọc **mọi** khóa trong `penalty_terms` và ghi vào

```python
rule_counts: dict[str, int]    # rule_id -> số vi phạm theo chính mô hình
```

Giới hạn sử dụng, quan trọng: `rule_counts` **không** phải nguồn chân lý về vi phạm. Nó là số mô hình tự đếm trên ngưỡng mô hình tự dùng. Vai trò duy nhất của nó là làm vế đối chứng trong test §6.1 — để phát hiện khi mô hình và hậu kiểm bất đồng. Con số hiển thị cho người dùng luôn đến từ `detect_*` + `classify`, đếm theo config.

### 4.8 Tóm tắt luồng

```
config ──> resolve_effective_params ──> params {declared, effective, reason}
                                          │
                                          ├──> CP-SAT ép theo .effective
                                          │       │
                                          │       └──> nới dần 2 trục (§4.6) ──> relaxations {widened/exempted, evidence}
                                          │
                                          └──> detect_* đếm theo .declared ──> [Violation(level=BREACH)]
                                                                                      │
                                     relaxations + params.reason ──> classify ────────┘
                                                                                      │
                                                                                      v
                                                          [BREACH]    -> ❌ chặn lưu
                                                          [FORCED]    -> ⚠️ cảnh báo + bằng chứng + cho lưu
                                                          [SHORTFALL] -> ℹ️ khuyến nghị
```

Vi phạm chảy theo một chiều: đếm theo config trước, giải thích sau. Không có nhánh nào cho phép bằng chứng quay ngược lại làm biến mất một vi phạm.

---

## 5. Thay đổi chi tiết

### 5.1 Nhóm A — Lỗi solver

**A1 + A2 — Lấp ô cho lớp quá tải: chuyển từ thưởng mềm sang ràng buộc cứng có thể nới**

Hai lỗi này cùng một gốc và phải sửa cùng nhau.

*Hiện trạng.* Lớp có `need > sức chứa` được nới thành `sum(vs) <= n` (`cpsat_model.py:147-148`), bù lại bằng số hạng thưởng lấp ô `-1000 * sum(x)` (`objectives.py:533-534`). Sinh ra hai hỏng hóc:

- **Dừng sớm.** Khoảng 1.000 ô được xếp cho ~-1.000.000 điểm, át toàn bộ phạt. Nghiệm khả thi **đầu tiên** đã có `obj < 0`, mà `solver.py:214-215` có `if obj <= 0: self.StopSearch()` → dừng tức khắc, trả lịch gần như chưa tối ưu, giao diện vẫn báo thành công.
- **Nhánh `minimize_changes` không có thưởng.** Số hạng đó chỉ tồn tại ở nhánh `else`. Bật `cpsat_minimize_changes=True` cùng lớp quá tải thì không gì thúc solver lấp ô — "dạy ít nhất có thể" cho điểm phạt thấp nhất.

*Cách sửa.* **Xóa hẳn số hạng `-1000 * sum(x)`.** Với lớp quá tải, số ô lấp được tối đa đã biết trước và bằng đúng sức chứa của lớp — đây là một sự kiện, không phải một sở thích cần cân đo trong hàm mục tiêu. Diễn đạt nó bằng ràng buộc:

```python
# cpsat_model.py, sau vòng ràng buộc need
for class_id, cap in class_cap.items():
    if class_total_need[class_id] > cap:
        vs = [x[s.slot_id, sid] for s in slots_by_class[class_id]
              for sid in subject_ids if (s.slot_id, sid) in x]
        term = m.NewBoolVar(f"underfill_c{class_id}")
        m.Add(sum(vs) == cap).OnlyEnforceIf(term.Not())
        built.penalty_terms["FILL"].append(term)
```

Đăng ký `"FILL"` vào `HARD_POST_GENERATION_IDS` với `breach_priority` cao nhất. Pass 1 ép `sum(terms) == 0` (lấp kín mọi ô của lớp quá tải); nếu vô nghiệm, Pass 2 (§4.6) tối thiểu hóa số lớp không lấp kín được và trả về con số đó kèm bằng chứng. Đây chính là thứ số hạng `-1000 * sum(x)` cố làm bằng cách nhân hệ số — nay làm đúng bằng cơ chế nới lỏng có kiểm chứng, không thêm máy móc mới.

*Ba lợi ích:*
1. Hàm mục tiêu không còn số hạng âm → điều kiện `obj <= 0` ở `solver.py:214` trở lại đúng (obj = 0 nghĩa là không còn phạt nào, dừng là hợp lý). **Giữ nguyên dòng đó**, thêm comment nêu rõ bất biến "hàm mục tiêu không được chứa hệ số âm".
2. Hai nhánh `minimize_changes` hành xử giống nhau, không cần nhân đôi logic.
3. Không thêm hệ số khổng lồ nào — ngược lại còn gỡ bỏ một hệ số 1.000 khỏi hàm mục tiêu, giúp nhẹ bớt vấn đề số học đã hoãn ở §2 thay vì làm nặng thêm.

*Bất biến cần bảo vệ:* thêm `tests/test_objective_no_negative_terms.py` — duyệt `model.Proto().objective.coefficients`, khẳng định không có hệ số âm nào. Bất biến này là thứ khiến A1 đúng; mất nó thì lỗi dừng sớm quay lại.

**A3. GV miễn trừ không còn bị hard-gate II.8** — `objectives.py:145-153`

Vòng tính split day thiếu nhánh `is_soft_exempt`, khác với vòng lone session ngay trên và vòng lone day ngay dưới. `sp` luôn rơi vào `penalty_terms["II.8"]`, mà `solver.py:346-347` ép `sum(terms) == 0` → GV trường đã chủ động miễn vẫn bị ép cứng, có thể gây vô nghiệm và khiến II.8 bị báo "đã nới lỏng" cho toàn trường.

Sửa: thêm nhánh đối xứng, đẩy `sp` của GV miễn trừ vào `soft_exempt_split_terms` (danh sách khai báo tại `objectives.py:127` nhưng chưa bao giờ được append) → kích hoạt `TEACHER_EXEMPT_SPLIT_DAY_SOFT_PENALTY = 700` đang là code chết.

**A4. Đưa hai ràng buộc cứng ra khỏi hàm mục tiêu**

| Vị trí | Hiện tại | Sửa |
|---|---|---|
| `objectives.py:260` | `m.Add(sum(sess_gaps) <= 1)` — ràng buộc cứng nằm trong objective, trong khi II.7 khai báo `SOFT`. Vì II.7 không thuộc `HARD_POST_GENERATION_IDS`, vòng chẩn đoán không bao giờ nới nó → vô nghiệm không giải thích được. | Chuyển sang `constraints.py`, đọc trần từ `params.max_teacher_gaps_per_session`. Thêm trường `max_teacher_gaps_per_session: int = 1` vào `SchedulingConfig` — giá trị mặc định giữ đúng hành vi hiện tại. |
| `objectives.py:171` | `m.Add(sum(t_lones) <= 2)` — chặn cứng GV "miễn trừ" ở 2 buổi lẻ, mâu thuẫn với chính khái niệm miễn trừ. | Xóa. Thay bằng phạt mềm có hiệu lực: nâng `TEACHER_EXEMPT_LONE_SESSION_SOFT_PENALTY` từ **20 → 600**. |

Về con số 600: đợt audit đo được sàn nhiễu thực tế của solver là 600 điểm — `EarlyStoppingCallback` dừng khi `improvement_abs < 600` **hoặc** `rate < 3%` (`solver.py:180`, phép **hoặc**). Mọi trọng số dưới 600 không bao giờ ảnh hưởng được kết quả. Giá trị 20 hiện tại là trang trí. Nâng lên 600 giữ đúng ý định ban đầu — "GV miễn trừ không thành bãi rác mặc định" — mà vẫn không phải ràng buộc cứng.

**A5. `_presolve_capacity_screening` dùng sai bản đồ giáo viên** — `solver.py:230`

Dùng `built.inp.assigned_teacher` (thô) trong khi `objectives.py:66,71` dùng `_build_effective_assigned_teacher`. Tải `load[t]` tính ra khác nhau → một GV có thể vượt `min_mand_load` ở tầng screening nhưng không ở tầng mục tiêu → II.3 bị nới oan hoặc không được nới khi cần.

Sửa: đọc `params.teacher_load`. Trở thành hệ quả tự nhiên của §4.2, không cần sửa riêng.

**A6. Docstring II.8** — `validation.py:414-425`

Theo quyết định Q1, viết lại docstring cho khớp code (`S == 1 và C == 1`), bỏ đoạn cảnh báo về nghĩa rộng vì nó mô tả một luật không còn áp dụng. Ghi rõ quyết định 2026-09-17 và lý do, để lần sau không ai "sửa lại cho đúng docstring".

**A7. Thay cơ chế nới lỏng theo công tắc bằng nới lỏng theo lượng** — `solver.py:220-408`

Triển khai §4.6. Đây là hạng mục lớn nhất của Nhóm A, và là thứ biến "nới lỏng" từ một lời thú nhận mơ hồ thành một con số có bằng chứng.

| Xóa / Đổi | Thành |
|---|---|
| `_select_fallback_relaxations` (`solver.py:272-277`) — thứ tự nới nằm cứng trong code | `RuleSpec.breach_priority`, quyết định thứ tự mở dần tập S (Trục 2) |
| `relaxed \|= offending` rồi bỏ hẳn luật (`solver.py:400`) | `cap_var` / `exempt_u` được thả tự do, mục tiêu tối thiểu hóa chi phí nới với `RELAX_WEIGHT` (Trục 1) |
| `_get_eff_max_heavy` đoán trước trần rồi nới sẵn cả lớp (`constraints.py:277-284`) | `cap_var = IntVar(declared, relax_ceiling)` theo từng (lớp, buổi); solver tự tìm mức nới nhỏ nhất |
| Nhánh UNKNOWN nới luật như thể đã chứng minh (`solver.py:405-407`) | Pass cuối riêng, gắn `minimality="UNPROVEN"` |
| `_presolve_capacity_screening` trả `{"II.3"}` rồi nới thẳng (`solver.py:266-267`) | Trả bằng chứng (sáng nào, sức chứa bao nhiêu, cần bao nhiêu); chỉ dùng để đưa II.3 vào tập nghi vấn Pass 2 sớm |
| `ScheduleResult.relaxed_rules: list[dict]` | `ScheduleResult.relaxations: dict[str, Relaxation]` |

**Ngân sách thời gian.** Pass 2 thêm một lần giải. Phân bổ: Pass 1 lấy 50% `time_limit`, trích UNSAT core giữ nguyên 3,5s, Pass 2 lấy phần còn lại. Nếu Pass 2 hết giờ mà đã có nghiệm, giữ nghiệm đó với `minimality="UNPROVEN"`. Việc `time_limit` chưa phải trần cứng vẫn nằm ngoài phạm vi (§2) — nhưng A7 **không được** làm nó tệ hơn, nên tổng số lần giải phải giữ nguyên hoặc giảm: bỏ vòng lặp `while True` nới dần từng luật một (hiện có thể chạy tới 4 pass) đổi lấy tối đa 3 pass cố định.

---

### 5.2 Nhóm B — Luật buổi nghỉ giáo viên (thiết kế mới)

**Hiện trạng.** `constraints.py:178` chỉ có `m.Add(sum(off_vars) <= required_total)` — trần, không có sàn. Biến `off_var = 1` chỉ *thêm* ràng buộc (`sum(teach_vars) == 0`) mà không mang lợi ích nào trong hàm mục tiêu, nên solver luôn đặt về 0. Luật vô hiệu hoàn toàn, trừ các ô được ghim.

> Đây là lỗi kinh điển khi chuyển từ greedy sang solver: trong greedy, *đánh dấu* một buổi nghỉ trực tiếp ngăn thuật toán xếp vào đó — đánh dấu là hành động. Trong CP-SAT, một biến chỉ báo mà không nơi nào đọc tới sẽ luôn nhận giá trị rẻ nhất.

**Thiết kế mới theo Q2.**

Không thêm cờ cấu hình. `teacher_off_sessions_per_week` đã là `number_input(0, 3, ...)` tại `pages/10_Cau_hinh_Xep_lich.py:229` — giá trị `0` chính là trạng thái "tắt".

| Giá trị | Hành vi |
|---|---|
| `0` (tắt) | `required_total = len(pinned)`. Chỉ các buổi BGH đã ghim được ép cứng. Không sinh `off_var` tự do, không phạt. Số buổi nghỉ do tải giáo viên và thuật toán tự quyết. |
| `N ≥ 1` (bật) | Ưu tiên mềm, cố đạt tối đa `N` buổi/GV. Không bao giờ gây vô nghiệm. |

Thay đổi ở `_add_off_day_constraints` (`constraints.py:133-178`):

- Giữ nguyên cách dựng `off_vars` và bộ lọc `forbidden` (sáng bắt buộc + ô đã khóa khỏi TKB).
- Giữ nguyên ép cứng `off_var == 1` cho ô đã ghim — BGH duyệt là quyết định hành chính, không thương lượng.
- Giữ nguyên trần `sum(off_vars) <= required_total` — không thưởng cho việc nghỉ quá mức.
- **Thêm** biến thiếu hụt và đưa vào hàm mục tiêu:

```python
shortfall = m.NewIntVar(0, required_total, f"off_short_t{teacher_id}")
m.Add(shortfall >= required_total - sum(off_vars))
built.penalty_terms["OFF"].append(shortfall)
```

- Trọng số mới trong `constants.py`:

```python
TEACHER_OFF_SHORTFALL_PENALTY = 600   # thiếu mỗi buổi nghỉ so với cấu hình.
# Phải >= 600 mới vượt sàn nhiễu của EarlyStoppingCallback (solver.py:180);
# dưới ngưỡng đó trọng số không ảnh hưởng được kết quả.
# Hiệu chỉnh lại sau lần chạy đầu trên dữ liệu thật của trường.
```

Vì `off_var = 1` giờ có lợi, solver sẽ đánh dấu nghỉ ở mọi buổi giáo viên vốn đã trống, và chủ động sắp xếp lại để giải phóng thêm buổi khi đáng giá. Đúng nghĩa "ưu tiên áp dụng tối đa có thể". Nơi không thể, `shortfall` hấp thụ mà không gây vô nghiệm.

**Đăng ký luật.** Thêm vào `RULES`:

```python
"OFF": RuleSpec(
    id="OFF",
    title_vi="Mỗi GV được nghỉ đủ số buổi theo cấu hình",
    tier=RuleTier.SOFT,          # không bao giờ chặn lưu
    config_flag=None,            # bật/tắt qua teacher_off_sessions_per_week > 0
)
```

Không đưa vào `HARD_POST_GENERATION_IDS`. Đây là tùy chọn của trường, không phải tiêu chí HĐSP đánh số.

**Hậu kiểm.** `detect_teacher_off_shortfall(view, params)` trả về danh sách GV chưa đủ số buổi nghỉ, hiển thị ở mục khuyến nghị của bảng sức khỏe với `type: "info"`. Không chặn lưu.

**Dọn kèm.** Hằng số `BAT_NGHI_1_BUOI` (`constants.py:17`) không còn nghĩa — luật giờ điều khiển bằng `teacher_off_sessions_per_week`. Xóa hằng số và mục tương ứng trong `core/scheduler/__init__.py`. Cập nhật ghi chú tại `rules_registry.py:37-43` cho khớp thiết kế mới.

---

### 5.3 Nhóm C — Lỗi tầng validate

**V1. Trần môn nặng thích ứng — không phải báo lỗi giả, mà là báo sai mức.**

`pages/06_Xep_TKB.py:583` truyền `config.max_heavy_consecutive` vào validator, trong khi `constraints.py:292` nới trần này khi bật `heavy_subjects_morning_only`. Lịch kết quả hiện lỗi đỏ.

Cách hiểu đúng theo §4.2: lịch đó **thật sự vi phạm** trần khai báo. Không được cho validator đọc trần đã nới để vi phạm biến mất. Sửa đúng là giữ nguyên việc phát hiện, đổi cách phân loại và trình bày:

- `detect_heavy_consecutive(view, params)` đếm theo `params.max_heavy_consecutive[(class_id, session)].declared` → vẫn tìm ra chuỗi 4 tiết, `level="BREACH"`.
- `classify` thấy `effective=4 != declared=3` **tại đúng (lớp, buổi) đó** và có `reason` → hạ xuống `level="FORCED"`, `evidence = reason`.
- Chuỗi 4 tiết ở một (lớp, buổi) mà `effective` vẫn bằng 3 → giữ `BREACH`. Nới ở chỗ này không xá tội cho chỗ khác.
- Giao diện hiện ⚠️ kèm lý do thay vì ❌, không chặn lưu.

Điều này phụ thuộc vào việc `_get_eff_max_heavy` (`constraints.py:277-284`) được thay bằng `cap_var` theo §4.6 — chỉ khi đó `effective` mới là mức nới tối thiểu có thật, riêng cho từng buổi, và `reason` mới sinh được tự động. Nếu vẫn dùng công thức đoán trước, ta lại rơi vào cảnh nới cả lớp vì một buổi.

**V2. Môn 1 cặp — kiểm đúng bản chất.** `validation.py:251` đếm số tiết/ngày, bỏ qua hai điều kiện định nghĩa luật.

`detect_block_integrity(view, params)` mới, bắt cả ba trường hợp, dùng chung cho môn Kép và môn 1-cặp:

| Trường hợp | Hiện tại bắt được? |
|---|---|
| Hai tiết cùng ngày nhưng **không liền kề** (tiết 1 và tiết 4) | ❌ ghi nhận nhầm là cặp hợp lệ |
| **Không có cặp nào** (4 tiết rải 4 ngày) | ❌ lọt |
| Quá 2 tiết/ngày | ✅ |
| Môn Kép thiếu khối / khối bị cắt rời | ❌ chưa có validator |

Đối chiếu với `constraints.py:529-544` (`sum(all_block_starts) == 1`, block là các tiết liên tiếp) và `constraints.py:548-569` (môn Kép: `full_blocks` + tối đa một ngày dư).

**V3. Bảy ràng buộc cứng thiếu hậu kiểm.** Bổ sung detector, mỗi cái đối chiếu trực tiếp với ràng buộc CP-SAT tương ứng:

| Detector mới | Đối chiếu |
|---|---|
| `detect_teacher_session_cap` | `constraints.py:122` |
| `detect_class_heavy_per_session` | `constraints.py:288` |
| `detect_class_session_gaps` | `constraints.py:384` |
| `detect_class_lone_session` | `constraints.py:414` |
| `detect_block_integrity` | `constraints.py:550` (gộp với V2) |
| `detect_hdtn_pinned` | `constraints.py:357` |
| `detect_teacher_off_shortfall` | §5.2 |

Vi phạm của nhóm này luôn ra mức `BREACH` — chúng kiểm tra ràng buộc mô hình đã ép cứng, nên nếu tìm thấy thì đó là **bug của mô hình**, không phải lựa chọn của trường, và không có `Relaxation` nào hợp lệ để hạ xuống `FORCED`.

Ngoại lệ ở phần trình bày: `BREACH` thông thường chặn lưu vì người dùng sửa được (đổi cấu hình, đổi phân công). Nhóm này người dùng không sửa được, nên hiển thị ở mục riêng — *"Cảnh báo kỹ thuật: kết quả không khớp ràng buộc mô hình"* — kèm gợi ý báo lại cho người phát triển, và **không** chặn lưu. Phân biệt bằng cờ `blocks_save: bool` trong `RuleSpec`, không bằng cách hạ mức vi phạm.

**V4. Ngưỡng học thuật buổi sáng.** Ba tầng đang dùng ba điều kiện khác nhau:

| Tầng | Điều kiện |
|---|---|
| Sàn cứng CP-SAT | `>= 1`, chỉ khi `c_academic_need >= c_mornings` (`constraints.py:454`) |
| Sàn mềm CP-SAT | `>= min_academic` (=2), phạt 120đ (`objectives.py:415`) |
| Validator | `< min_academic` là vi phạm, **không** xét điều kiện khả thi (`validation.py:213-216`) |

Lớp không đủ môn học thuật để rải 2 tiết mỗi sáng — bất khả kháng — vẫn bị liệt kê và trừ điểm (`validation.py:613`).

Sửa, theo cùng nguyên tắc §4.2 — tách thành hai luật riêng biệt vì chúng có tier khác nhau:

| Luật | Ngưỡng | Tier | Mức khi vi phạm |
|---|---|---|---|
| `ACAD.FLOOR` | sàn cứng `>= 1`, chỉ trên `params.academic_floor_cells` | HARD | `BREACH` — mô hình đã ép, vi phạm nghĩa là bug |
| `ACAD.MIN` | sàn mềm `>= config.min_academic_per_morning` | SOFT | `SHORTFALL` — khuyến nghị |
| `ACAD.MAX` | trần `params.max_academic_per_morning.declared` | HARD | `BREACH`, hạ `FORCED` nếu trần đã nới có `reason` |

Việc validator hiện liệt kê lớp không đủ môn học thuật để rải 2 tiết/sáng không còn là lỗi: nó rơi vào `ACAD.MIN` mức `SHORTFALL`, hiển thị ở mục khuyến nghị. Điều kiện `c_academic_need >= c_mornings` không cần sao chép sang detector — nó chỉ quyết định `academic_floor_cells` gồm những ô nào, và việc đó thuộc `resolve_effective_params`.

**V5–V8.** Giải quyết trọn bằng §4.4:

| Mã | Vấn đề | Cách xử lý |
|---|---|---|
| V5 | `teacher_id` lọc bằng `< 0` ở ba hàm, `<= 0` ở ba hàm khác, `> 0` ở `quality.py` | `build_schedule_view` quy `id <= 0` về `None` một lần |
| V6 | Sentinel `-1` không được lọc trong `validation.py` | `build_schedule_view` quy `-1` về `None` một lần |
| V7 | Luật môn/lớp đọc từ `repo.list_subject_class_rules` trong khi CP-SAT đọc `inp.subject_class_allowed_cells` | Detector đọc từ `view`, tức cùng `inp` mà solver đã dùng. Bỏ đường nạp thứ hai. |
| V8 | `compute_tkb_health_score` dựng `slot_teacher` từ bản đồ effective nhưng gọi `find_*` với bản đồ thô | Nhận `ScheduleView`, một bản đồ duy nhất |

**V9.** `detect_teacher_gaps` tôn trọng `params.flags["avoid_teacher_gaps"]`, không chạy khi trường tắt tiêu chí.

**V10 — không sửa trong đợt này.** Thang điểm sức khỏe (ngày chia lẻ 15đ, `validation.py:736`) không liên quan tới thang trọng số solver (ngày chia lẻ 700đ, hạng ba). Việc đồng bộ hai thang thuộc hạng mục phân tầng trọng số đã hoãn. Trước mắt bổ sung một dòng ghi chú trong bảng sức khỏe: *"Điểm này đánh giá theo thang sư phạm, khác thang tối ưu của bộ giải."*

---

### 5.4 Nhóm D — Hợp nhất

1. Chuyển toàn bộ hàm `find_*_violations` từ `core/validation.py` sang `core/rules/detectors.py`, đổi chữ ký sang `detect_*(view, params)`.
2. `core/validation.py` giữ lại phần không thuộc bộ luật: `compute_quota_diff`, `compute_actual_counts`, `compute_tkb_health_score`. `compute_tkb_health_score` gọi detector thay vì tự cài đặt lại.
3. Xóa `core/scheduler/quality.py`. Ba hàm còn caller thực — `_count_teacher_excess_gaps` (`validation.py:624`), `_count_teacher_back_to_back_shifts`, `_count_subject_consecutive_days` (`validation.py:17-19`) — được thay bằng detector tương ứng ở GĐ 6 trước khi xóa file. `_teacher_quality_penalty` không còn caller nào, xóa thẳng.
4. Gộp ba bản sao helper "GV có bận buổi sáng đó không" — `constraints.py:611`, `quality.py:137`, `validation.py:288` — về một hàm trong `core/rules/detectors.py`, nhận `ScheduleView`.
5. Cập nhật ~15 điểm gọi trong `pages/06_Xep_TKB.py`. Không tạo lớp bọc tương thích ngược — sửa thẳng điểm gọi.

---

## 6. Kiểm thử

### 6.1 Test tương đương — trụ cột của spec này

`tests/test_rule_equivalence.py`. Đây là bài kiểm tra mà nếu tồn tại từ trước, cả bốn lỗi A3, V1, V2, V4 đã không lọt.

Một phép khẳng định là không đủ, và bản nháp trước của spec sai đúng ở chỗ này: so `detect` với `rule_counts` trên cùng ngưỡng đã nới thì hai tầng luôn đồng ý — về một chuẩn đã bị hạ. Cần **ba** phép khẳng định tách bạch.

```python
@pytest.mark.parametrize("fixture", ALL_FIXTURES)
@pytest.mark.parametrize("rule_id", ALL_RULE_IDS)
def test_rule_integrity(fixture, rule_id):
    inp = load_fixture(fixture)
    result = sched.run(inp)
    assert result.success

    view = build_schedule_view(inp, result.assignment)
    params = result.effective_params

    # A. Mô hình giữ lời hứa của CHÍNH NÓ.
    #    Đếm lại trên ngưỡng mô hình đã ép -- phải khớp số mô hình tự đếm.
    at_effective = len(DETECTORS[rule_id](view, params.as_effective()))
    assert at_effective == result.rule_counts.get(rule_id, 0), (
        f"{rule_id}: mô hình ép ngưỡng của nó nhưng hậu kiểm đếm ra số khác "
        f"({at_effective} vs {result.rule_counts.get(rule_id, 0)}) — hai tầng trôi lệch"
    )

    # B. Đếm theo CONFIG. Mọi vi phạm vượt quá A đều phải giải thích được.
    raw = DETECTORS[rule_id](view, params)          # params đọc .declared
    classified = classify(raw, params, result.relaxations)

    for v in classified:
        if v.level == "FORCED":
            assert v.evidence, f"{rule_id}: FORCED mà không có bằng chứng — phải là BREACH"

    # C. BREACH chỉ được phép tồn tại nếu fixture cố ý dựng ra nó.
    breaches = [v for v in classified if v.level == "BREACH"]
    assert not breaches or fixture in EXPECTED_BREACH_FIXTURES, (
        f"{rule_id}: {len(breaches)} vi phạm không giải thích được — "
        f"bug mô hình hoặc thiếu bằng chứng nới lỏng"
    )
```

`params.as_effective()` trả một `EffectiveParams` mà mọi `Threshold` đọc `.effective` thay vì `.declared` — chỉ dùng trong test, không có nơi nào trong mã sản xuất được gọi nó.

Ba phép khẳng định bắt ba loại lỗi khác nhau:

| | Bắt được gì | Lỗi đã tìm thấy thuộc loại này |
|---|---|---|
| **A** | Mô hình và hậu kiểm hiểu khác nhau về cùng một luật trên cùng một ngưỡng | V2 (môn 1-cặp không xét liền kề), A3 (GV miễn trừ) |
| **B** | Nới lỏng không có bằng chứng, hoặc ngưỡng bị nới mà không ghi lý do | V1 (trần nặng nới không ghi lý do) |
| **C** | Ràng buộc cứng bị vi phạm mà không ai giải thích được | V3 (7 ràng buộc không có hậu kiểm) |

`ALL_RULE_IDS` gồm mọi luật có detector. Luật là ràng buộc cứng thuần (trần tiết/buổi, lớp không hở tiết, khối môn Kép…) không có `penalty_terms`, nên vế phải của A bằng 0 — đúng ý đồ: hậu kiểm không được tìm thấy vi phạm nào của thứ mô hình đã ép cứng.

Bộ fixture phải bao các cấu hình làm lộ ngưỡng thích ứng:

| Fixture | Mục đích |
|---|---|
| `baseline` | Cấu hình mặc định |
| `heavy_morning_only` | `heavy_subjects_morning_only=True` — kích hoạt trần nặng thích ứng (V1) |
| `oversubscribed` | Lớp có `need > sức chứa` — kích hoạt nhánh lấp ô (A1, A2) |
| `lone_exempt` | Có GV trong `lone_session_exempt_teacher_ids` — kích hoạt A3 |
| `off_enabled` / `off_disabled` | `teacher_off_sessions_per_week` = 2 và 0 (§5.2) |
| `single_pair` | Có môn 1-cặp — kích hoạt V2 |
| `infeasible_ii4` | Dựng cố ý để II.4 không thể thỏa mãn (một GV tải 9 tiết, mọi ô khác bị chặn) — kích hoạt Pass 2 của §4.6. Thuộc `EXPECTED_BREACH_FIXTURES`. |

### 6.2 Test hồi quy theo lỗi

| Test | Khẳng định |
|---|---|
| `test_objective_no_negative_terms` | Không hệ số âm nào trong `model.Proto().objective` (A1 — bất biến làm điều kiện `obj <= 0` đúng) |
| `test_oversubscribed_fills_every_slot` | Fixture `oversubscribed` → mọi ô của lớp quá tải đều có môn, hoặc `relaxations` chứa `"FILL"` kèm bằng chứng (A2) |
| `test_fill_identical_across_branches` | `minimize_changes=True` và `False` cho cùng số ô được lấp trên fixture `oversubscribed` (A2) |
| `test_exempt_teacher_not_hard_gated_ii8` | GV miễn trừ có ngày chia lẻ → `relaxations` **không** chứa II.8 (A3) |
| `test_gap_cap_is_declared_constraint` | `max_teacher_gaps_per_session=2` cho ra lịch khác `=1` (A4) |
| `test_off_shortfall_soft_not_infeasible` | Dữ liệu chật + `teacher_off_sessions_per_week=3` → vẫn có nghiệm, `rule_counts["OFF"] > 0` (§5.2) |
| `test_off_disabled_no_penalty` | `=0` → `rule_counts.get("OFF", 0) == 0` (§5.2) |
| `test_relaxation_amount_is_minimal` | Fixture `infeasible_ii4` → `minimality == "PROVEN"`, và ép chi phí nới `<= (đã dùng − 1)` cho ra INFEASIBLE — chứng minh không thể nới ít hơn (A7, Trục 1) |
| `test_relaxation_ruleset_is_minimal` | Fixture `infeasible_ii4` → chỉ II.4 nằm trong `relaxations`; II.3 và II.8 vẫn khóa ở mức config (A7, Trục 2) |
| `test_forced_within_relaxed_scope` | Mọi fixture: tập đơn vị của các `Violation` mức `FORCED` **là tập con** của `exempted` ∪ `widened` trong `relaxations`. Bất biến §4.6 (A7) |
| `test_widen_is_per_scope_unit` | Fixture `heavy_morning_only` → chỉ (lớp, buổi) thật sự cần mới có `effective > declared`; các buổi khác của cùng lớp giữ nguyên trần config (A7, Trục 1) |
| `test_no_preemptive_widening` | Fixture `baseline` → mọi `Threshold` có `effective == declared` và `reason` rỗng; không ngưỡng nào bị nới khi chưa cần (§4.3) |
| `test_timeout_is_not_evidence` | `cpsat_time_limit_seconds=1` trên fixture lớn → `minimality == "UNPROVEN"`, **không** có `Relaxation` nào mang `source="unsat_core"` (A7) |
| `test_forced_always_has_evidence` | Mọi fixture: không `Violation` nào có `level="FORCED"` mà `evidence` rỗng (§4.2) |
| `test_heavy_cap_reported_as_forced` | Fixture `heavy_morning_only` → vi phạm trần nặng vẫn được **đếm** theo `declared=3`, nhưng mức là `FORCED` kèm lý do, không chặn lưu (V1) |
| `test_single_pair_non_adjacent_detected` | Lịch thủ công với hai tiết cùng ngày không liền kề → detector bắt được (V2) |
| `test_single_pair_zero_pairs_detected` | 4 tiết rải 4 ngày → detector bắt được (V2) |

### 6.3 Test hiện có

Toàn bộ suite phải xanh. Các test chạm trực tiếp vào chữ ký `find_*` cũ cần cập nhật theo chữ ký mới — đây là thay đổi cơ học, không phải nới lỏng khẳng định. **Không được** sửa giá trị kỳ vọng của test để làm nó xanh; nếu một test đổi kết quả, phải giải thích được vì sao trước khi cập nhật.

---

## 7. Thứ tự triển khai

Mỗi giai đoạn để lại cây mã chạy được và test xanh.

| GĐ | Nội dung | Phụ thuộc |
|---|---|---|
| 1 | `core/rules/view.py` + `build_schedule_view`. Chuyển detector hiện có sang chữ ký mới, chưa đổi logic. Cập nhật điểm gọi. | — |
| 2 | `core/rules/params.py` + `Threshold` + `resolve_effective_params`. Mọi ngưỡng khởi tạo `effective == declared` — **chưa** đụng `_get_eff_max_heavy`, việc đó thuộc GĐ 5. Gắn `built.params`, `result.effective_params`. | GĐ 1 |
| 3 | `Violation.level` + `classify` + `RuleSpec.breach_priority`/`blocks_save`. Chưa đổi cơ chế giải — `relaxations` tạm dựng từ `relaxed_rules` cũ. | GĐ 2 |
| 4 | `result.rule_counts` + `tests/test_rule_equivalence.py` (cả ba phép khẳng định). **Dự kiến có test đỏ** — chính là V1, V2, V4 và các nới lỏng thiếu bằng chứng đang chờ sửa. | GĐ 3 |
| 5 | **A7 — nới lỏng theo hai trục** (§4.6): `cap_var`/`exempt_u` thay hằng số, vòng mở dần tập luật, bỏ `_get_eff_max_heavy` và `_select_fallback_relaxations`. Hạng mục lớn nhất; làm sau GĐ 4 để có test bắt hồi quy. | GĐ 4 |
| 6 | Nhóm A còn lại (A1–A6). Test hồi quy tương ứng. | GĐ 4 |
| 7 | Nhóm B — luật buổi nghỉ. | GĐ 2 |
| 8 | Nhóm C — V1, V2, V3, V4, V9. Test ở GĐ 4 chuyển sang xanh. | GĐ 4 |
| 9 | Nhóm D — dọn `quality.py`, gộp helper trùng, xóa `BAT_NGHI_1_BUOI`. | GĐ 8 |

GĐ 4 đặt trước mọi giai đoạn sửa lỗi là có chủ ý: test đỏ trước, sửa sau, để mỗi cái sửa có bằng chứng nó thực sự sửa được cái gì. GĐ 3 tách khỏi GĐ 5 để `classify` và giao diện ba mức lên trước, độc lập với việc thay động cơ nới lỏng — nếu GĐ 5 phải hoãn, phần còn lại vẫn dùng được.

---

## 8. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| **Bỏ nới trần đoán trước làm Pass 1 vô nghiệm ở những bộ dữ liệu trước đây chạy thẳng** | Cao | Đây là đánh đổi có chủ ý: mức nới đúng đắn và tối thiểu, trả giá bằng một pass. Số pass tối đa vẫn bằng cận cũ (`len(active_rids) + 1`). Đo thời gian giải trên dữ liệu thật trước/sau GĐ 5; nếu tổng tăng, kéo hạng mục "trần thời gian cứng" (mục 9 báo cáo audit, ngoài phạm vi §2) vào làm ngay sau. |
| **`cap_var` làm mô hình to hơn** — mỗi (lớp, buổi) thêm một IntVar và biến ràng buộc từ hằng số thành biến | Vừa | Số `cap_var` bằng số đơn vị phạm vi (~20 lớp × 12 buổi = 240), nhỏ so với ~10k biến phụ hiện có. Ràng buộc `sum(vs) <= cap_var` vẫn tuyến tính. Nếu presolve chậm đi rõ rệt, khóa `cap_var == declared` ở Pass 1 để presolve suy biến được như cũ. |
| **`RELAX_WEIGHT` tính từ tổng trọng số** có thể lớn ở trường nhiều lớp, làm xấu LP relaxation | Vừa | Chỉ dùng từ Pass 2 trở đi, không có ở Pass 1 (đường chạy thông thường). Nếu Pass 2 chậm bất thường, tách làm hai lần giải (giải 1 tối thiểu chi phí nới, cố định chi phí đó, giải 2 tối ưu chất lượng) — chậm hơn nhưng số học sạch. |
| Ràng buộc lấp kín (A2) gây vô nghiệm trên lớp quá tải khi các ràng buộc cứng khác không cho lấp hết ô | Vừa | `"FILL"` là luật cứng có `breach_priority` cao nhất, nên Pass 2 tự tối thiểu hóa số lớp không lấp kín và trả về con số kèm bằng chứng. Kiểm bằng `test_oversubscribed_fills_every_slot` (chấp nhận cả hai kết cục). |
| Bật luật buổi nghỉ làm bài toán chật thêm, chất lượng các tiêu chí khác giảm | Vừa | Trọng số `600` đặt thấp hơn ngày chia lẻ `700` nên không lấn át tiêu chí nặng hơn. Chạy đối chứng `off_enabled` vs `off_disabled` trên dữ liệu thật, so `rule_counts` từng luật. |
| Bỏ chặn cứng `sum(t_lones) <= 2` khiến solver dồn tiết khó vào GV miễn trừ | Vừa | Phạt mềm nâng 20 → 600 chính là để chặn điều này. Fixture `lone_exempt` khẳng định số buổi lẻ của GV miễn trừ không tăng so với trước. |
| Chuyển detector làm sót điểm gọi trong `pages/06_Xep_TKB.py` | Thấp | Xóa hẳn hàm cũ thay vì để lại lớp bọc — sót chỗ nào sẽ lỗi import ngay, không âm thầm. |
| Test tương đương đỏ vì lý do ngoài dự kiến ở GĐ 3 | Thấp | Đó là kết quả hợp lệ — mỗi bất đồng là một trôi lệch thật cần phân loại trước khi sửa, không phải test hỏng. |

---

## 9. Tiêu chí hoàn thành

- [ ] `tests/test_rule_equivalence.py` xanh trên toàn bộ 6 fixture × toàn bộ luật
- [ ] Mọi test hồi quy ở §6.2 xanh
- [ ] Suite hiện có xanh, không có giá trị kỳ vọng nào bị nới lỏng mà không giải thích
- [ ] `grep -rn "getattr(config" core/scheduler/cpsat/` không còn kết quả nào cho các ngưỡng đã đưa vào `EffectiveParams`
- [ ] Hàm mục tiêu không còn hệ số âm nào; `core/scheduler/quality.py` đã bị xóa
- [ ] Không `Violation` nào ở mức `FORCED` mà `evidence` rỗng, trên toàn bộ fixture
- [ ] Mọi vi phạm hiển thị cho người dùng đều đếm theo `config`, không theo ngưỡng đã nới — kiểm bằng `grep` không còn chỗ nào gọi `.effective` ngoài `constraints.py`, `objectives.py` và `params.as_effective()` trong test
- [ ] Timeout không còn sinh ra `Relaxation` nào có `source="unsat_core"`
- [ ] Tập vi phạm mức `FORCED` là tập con của phạm vi nêu trong `relaxations`, trên toàn bộ fixture
- [ ] `_get_eff_max_heavy` và `_select_fallback_relaxations` đã bị xóa; không còn chỗ nào nới ngưỡng trước khi chứng minh là cần
- [ ] Trên fixture `infeasible_ii4`: chỉ đúng một luật bị nới, và giảm chi phí nới đi 1 làm bài toán vô nghiệm
- [ ] Chỉ còn một hàm "GV có bận buổi sáng đó không" trong toàn repo
- [ ] Bật `heavy_subjects_morning_only` trên dữ liệu thật của trường: không còn cảnh báo trần môn nặng giả
- [ ] `teacher_off_sessions_per_week` đặt 0 / 1 / 2 cho ra ba kết quả khác nhau rõ rệt về số buổi nghỉ
