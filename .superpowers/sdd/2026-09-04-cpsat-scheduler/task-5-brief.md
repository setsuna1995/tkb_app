# Task 5: Môn KÉP và môn 1 CẶP LIỀN TIẾT

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` syntax.

**Goal:** Model adjacency for block subjects (`kep_ids`, `block_size >= 2`) and
the "exactly one adjacent pair per week" rule (`single_pair_ids`).

**Why (Vietnamese):** Đây là task rủi ro cao nhất của cả kế hoạch, nên tách
riêng để review kỹ. Lý do: mọi ràng buộc trước đều là "đếm" (≤ n, = n), còn cái
này là ràng buộc **vị trí tương đối** — hai tiết phải nằm cạnh nhau trong cùng
buổi. Viết sai kiểu ràng buộc này thường không gây lỗi mà chỉ âm thầm cho ra
TKB tách rời khối, rất khó phát hiện nếu không có test đúng hình dạng.

Thêm một cái bẫy: engine cũ **không đảm bảo ghép khối tuyệt đối** — nó có cơ chế
`_repair_unpaired_blocks` và chấp nhận "dư đúng 1 tiết lẻ/tuần nếu số tiết là số
lẻ" (xem `FAILURE_MESSAGE` mục 6 trong `constants.py`). Mô hình mới phải giữ
đúng mức nới đó, đừng siết chặt hơn rồi làm bài toán vô nghiệm.

**Files:**
- Modify: `core/scheduler/cpsat_model.py` (`_add_block_constraints`)
- Modify: `tests/test_cpsat_model.py`

**Interfaces:**
- Consumes: `CpSatModel.x`, `.slots_by_class`, `.role_index`
- Produces: không có interface mới.

## Cách mô hình hoá

**Môn kép (`block_size[sid] = 2`)**: với mỗi (lớp, môn kép, ngày, buổi), gọi
`p1..pn` là các tiết trong buổi đó. Tạo biến `pair[cid, sid, wd, sess, p]` = 1
nghĩa là "có một khối bắt đầu ở tiết p", với ràng buộc:

- `pair[p] <= x[slot(p), sid]` và `pair[p] <= x[slot(p+1), sid]`
- `x[slot(p), sid] + x[slot(p+1), sid] - 1 <= pair[p]` (ép pair=1 khi cả hai bật)
- Số tiết của môn đó trong ngày = `2 * (số pair)` — tức không có tiết lẻ đứng
  một mình trong ngày.

**Số tiết lẻ toàn tuần**: nếu `need[(sid, cid)]` là số lẻ thì cho phép đúng 1
tiết đơn trong tuần. Mô hình: `sum(tất cả pair trong tuần) * 2 + single = need`,
với `single` là biến nhị phân, và `single = need % 2`.

**`single_pair_ids`**: đúng 1 cặp liền kề trong tuần, các tiết còn lại đều đơn
lẻ và phải ở ngày khác nhau. Mô hình: `sum(pair toàn tuần) == 1`, cộng ràng buộc
≤1 tiết/ngày đã có từ Task 4 cho các tiết còn lại (lưu ý: ngày chứa cặp sẽ có 2
tiết nên ràng buộc ≤1 phải được nới riêng cho ngày đó).

## Test — bắt buộc có đủ 4 hình dạng

1. **Môn kép số tiết chẵn** (4 tiết) → phải ra đúng 2 khối liền kề, 0 tiết đơn.
2. **Môn kép số tiết lẻ** (3 tiết) → 1 khối + đúng 1 tiết đơn (đúng mức nới của
   engine cũ; nếu ép chặt sẽ vô nghiệm).
3. **`single_pair` (Ngữ văn 4 tiết)** → đúng 1 cặp liền + 2 tiết đơn ở 2 ngày khác.
4. **Không có môn kép nào** → mô hình không sinh ràng buộc thừa, vẫn giải được.

Với hình dạng 1 và 3, assert trực tiếp trên vị trí: lấy các `(wd, sess, period)`
của môn đó rồi kiểm tính liền kề, đừng chỉ đếm số tiết.

- [ ] Step 1: viết 4 test → FAIL
- [ ] Step 2: cài `_add_block_constraints`
- [ ] Step 3: chạy lại → PASS
- [ ] Step 4: `python -m pytest tests/ -q` → 244 passed, 1 xpassed
- [ ] Step 5: commit `feat(cpsat): block and single-pair adjacency constraints`
