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

- [x] **Task 1**: Khung mô hình — thêm `ortools`, tạo `core/scheduler/cpsat_model.py`, lưới biến `x[slot, subject]`, ràng buộc "mỗi ô đúng 1 môn" + "đúng định mức mỗi (môn, lớp)". Test: lời giải qua được `compute_quota_diff`. Brief: `task-1-brief.md`
- [x] **Task 2**: Ràng buộc GIÁO VIÊN — không trùng giờ, GV bận, trần tiết/buổi, trần tiết/ngày, buổi nghỉ. Test: qua `find_teacher_conflicts`, `find_teacher_day_cap_violations`, `find_teacher_unavailability_violations`. Brief: `task-2-brief.md`
- [x] **Task 3**: Ràng buộc MÔN — môn sáng bắt buộc, GDTC khung tiết + cách nhật, môn không liền ngày, môn nặng (/buổi, liên tiếp, tiết 3 chiều), luật môn–lớp–buổi. Test: qua `find_invalid_gdtc_periods`, `find_morning_only_violations`, `find_max_heavy_violations`, `find_consecutive_subject_days`, `find_subject_class_rule_violations`. Brief: `task-3-brief.md`
- [x] **Task 4**: Khung LỚP + ghim — ≤1 tiết/môn/ngày (HĐTN 2), chào cờ, SHL, tuần chuyên đề, không hở tiết giữa buổi, trần tiết/ngày của lớp, lớp không có buổi 1 tiết. Brief: `task-4-brief.md`
- [x] **Task 5**: Môn KÉP và 1-CẶP — khối 2 tiết liền kề, `single_pair_ids`. Task rủi ro cao nhất, tách riêng. Brief: `task-5-brief.md`
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

- **Setup (2026-09-04)**: Đã commit riêng tính năng dở dang `strict_morning_weekdays`
  trên `main` trước khi bắt đầu (commit `2aae4bb`, không liên quan tới plan này).
  Tạo worktree cô lập `.worktrees/cpsat-scheduler` (branch `cpsat-scheduler`) bằng
  `git worktree add` thủ công thay vì tool worktree gốc, vì tool đó mặc định
  branch từ `origin/main` (thiếu commit `2aae4bb` mà Task 6 cần tới qua `is_bgh`/
  `strict_morning_weekdays`) — branch đúng từ local HEAD. Baseline: `243 passed,
  1 skipped, 1 xpassed` (13 phút). Tạo file con trỏ
  `.superpowers/sdd/2026-09-04-cpsat-scheduler.md` theo đúng convention đã có ở
  `2026-09-02-hard-gate-hdsp-rules.md` để `sdd-workspace`/`review-package` resolve
  đúng thư mục workspace sẵn có (không tạo thư mục mới).
- **Ruling**: Người dùng chọn dừng lại sau Task 5 để báo cáo trước khi làm Task 6
  (hàm mục tiêu) và Task 8 (nối vào `run()`), vì Task 5 là task rủi ro cao nhất.
- **Ruling (cập nhật, superseded trên)**: do giới hạn token của phiên làm việc,
  người dùng quyết định dừng lại NGAY SAU TASK 4 (không làm Task 5 trong phiên
  này). Task 5 (môn kép/1-cặp, rủi ro cao nhất) và Task 6-8 để lại cho phiên sau.
  Sau khi Task 4 review sạch, sẽ dọn workspace theo đúng quy trình dừng giữa
  chừng (không xoá ledger — Task 5-8 vẫn "chưa bắt đầu", ledger giữ nguyên để
  phiên sau resume đúng chỗ).
- **Ruling (Task 2, rule 5 — buổi nghỉ GV)**: implementer đổi ràng buộc từ "đúng
  `effective_count` buổi nghỉ" (`==`, đúng chữ trong brief) thành chặn trên
  (`<=`), vì `==` cứng làm chính fixture của Task 1 vô nghiệm (`SchedulingConfig`
  mặc định `teacher_off_sessions_per_week=1`, fixture nhỏ không đủ ô không-cấm để
  chạm đúng số). Ruling: CHẤP NHẬN thay đổi này — brief tự mâu thuẫn: đoạn ngay
  sau bảng ràng buộc nói rõ ý định thật là "buổi nghỉ chỉ là ưu tiên nếu đã thoả
  các điều kiện trên" (yêu cầu trường 2026-09-04, xem `design.md` §4.2 dòng
  10/11 + `task-2-brief.md` "Ghi chú về buổi nghỉ"), tức không nên là ràng buộc
  cứng bắt buộc đạt đúng số. Chữ "đúng" trong bảng ràng buộc của brief mâu thuẫn
  với chính đoạn giải thích ý định ngay sau nó — thiết kế thắng chữ trong bảng.
  Chi phí nếu sai: nếu thực ra trường muốn ép cứng đúng số buổi nghỉ, hành vi
  mới sẽ dưới-nghỉ (GV nghỉ ít hơn mong muốn) chứ không vượt — an toàn hơn theo
  hướng sai, dễ sửa lại thành `==` sau nếu Task 8 đo thấy sai khác so với engine
  cũ. Đã yêu cầu reviewer xác nhận độc lập cách hiểu này thay vì tự tôi phán.
- **Carry-forward cho Task 6** (chưa dispatch trong phiên này — dừng sau Task 5
  theo yêu cầu người dùng): implementer Task 2 thu hẹp tập ô-cấm của buổi nghỉ
  chỉ còn 3 loại brief nêu tên, bỏ `must_monday`/GVCN-SHL/TPT-BGH mà engine cũ
  có. Vô hại với dữ liệu thật hiện tại (`teacher_off_sessions_per_week=0` nên
  luật này chưa kích hoạt) nhưng cần soát lại khi Task 6 (hàm mục tiêu) hoặc bất
  kỳ session nào sau này bật tính năng buổi nghỉ thật.
- Task 2: complete (commits 07d0fe1..7b88611, review clean; ruling trên confirmed
  độc lập bởi reviewer — tự tái tạo INFEASIBLE với `==` trên chính fixture Task 1).
  - Minor (deferred): rule 2 không tái dùng `vars_by_teacher_ts` đã dựng ở rule 1
    (`cpsat_model.py:133-139`) — chỉ là bỏ lỡ rút gọn, không phải lỗi.
  - Minor (deferred): báo cáo implementer nói quá — claim "AddAtMostOne luôn là
    nhóm đơn lẻ" không đúng cho rule 3/4 với cặp môn/lớp chưa gán GV có need>=2.
    Không phải lỗi chức năng, chỉ là self-review ghi sai.
  - Minor (deferred): chưa có test trực tiếp cho `built.teacher_of` với id âm
    tổng hợp (đường dẫn GV chưa gán) — Task 6 cần interface này đúng. Reviewer
    đã tự tay kiểm chứng thủ công là đúng, nhưng chưa có test hồi quy tự động.
    Cần Task 6 hoặc phiên sau chú ý.
  - Minor (deferred): rule 3 dùng `config.max_periods_per_session` trực tiếp còn
    rule 4 dùng `getattr(..., 5)` dù cả hai đều có default thật — không nhất
    quán, vô hại.
- **Tooling (commit `8b85421`, không thuộc task nào)**: người dùng phản hồi full
  suite chạy quá lâu (13 phút, lặp lại mỗi task). Thêm `pytest-xdist` vào
  `requirements-dev.txt`, benchmark `-n auto` trên 16 core: `257 passed, 1
  skipped, 1 xpassed in 202s` — giống hệt kết quả tuần tự, nhanh hơn ~3.9 lần.
  Từ đây dùng `python -m pytest tests/ -q -n auto` cho mọi lần chạy full suite
  (dispatch implementer/reviewer đều được nhắc dùng lệnh mới).
- **Note (Task 3)**: implementer tự phát hiện + tự sửa 2 lỗi trong chính ví dụ
  mẫu của brief (test rule 3 GDTC): (1) fixture gốc vô nghiệm vì đụng trần
  tiết/buổi đã merge ở Task 2 (5 tiết/1 buổi > default cap 4) — sửa bằng cách
  thêm `max_periods_per_session=5` vào config của riêng test đó; (2) brief gọi
  `find_invalid_gdtc_periods` sai chữ ký so với hàm thật trong `core/validation.py`
  — sửa lại lời gọi cho khớp hàm thật. Cả hai đã ghi trong report, yêu cầu
  reviewer xác nhận độc lập đây là sửa test cho khớp thực tế (không phải làm yếu
  giá trị chứng minh của test).
- Task 3: fix round 1/5 (1 addressed, 0 open; commits b52bbbe..724047f).
  Root cause: `max_heavy_sess = max(max_heavy_per_session, max_heavy_consecutive)`
  khiến rule 5 chỉ có thể "cắn" ở dàn trải không liên tục (vd. tiết {1,3,4}), mà
  `find_max_heavy_violations` chỉ phát hiện chuỗi liên tục nên không thấy được.
  Re-reviewer tự suy lại toán học độc lập (không chỉ tin lời implementer),
  xác nhận đúng.
  - Minor (deferred): docstring test còn ghi "max_heavy_consecutive=2 (<
    max_heavy_per_session=2, ...)" trong khi hai số bằng nhau — sai chữ, không
    ảnh hưởng hành vi.
  - Minor (deferred): lệnh gọi `find_max_heavy_violations(...)` bổ trợ còn thiếu
    tham số `max_consecutive` nên dùng default 3 thay vì 2 của fixture — làm
    yếu thêm phần kiểm bổ trợ (vốn đã không phải phần chính chứng minh).
  Task 3: complete (commits 7b88611..724047f, 1 fix round, review clean).
- Task 4: fix round 1/5 (5 addressed, 0 open; commits dd3fbc2..d2b8a83).
  Review gốc (sonnet) dùng phương pháp thực nghiệm mạnh: tắt từng luật qua cờ
  config, chạy lại `build_model`, so kết quả — không chỉ đọc code. Phát hiện
  4/9 fixture cũ (Task 2/3) bị implementer sửa lại cho hợp Rule 1 mới (≤1
  tiết/môn/ngày) đã VÔ TÌNH mất khả năng bắt lỗi hồi quy: `test_teacher_
  respects_daily_cap`, `test_gdtc_respects_allowed_periods`,
  `test_max_heavy_per_session`, `test_heavy_subject_avoids_afternoon_period3`
  — tắt luật tương ứng, kết quả solver KHÔNG đổi. Cộng 1 test mới của chính
  Task 4 (`test_class_has_no_lone_single_period_session_when_slack_available`,
  rule 7) cũng không cô lập được rule 7. Nguyên nhân chung: kiểu sửa "tách 1
  môn cần N tiết/ngày thành N môn cùng role cần 1 tiết" làm bài toán chật tới
  mức solver luôn ra cùng một lời giải dù luật đang kiểm có bật hay không.
  Implementer sửa cả 5 bằng mẫu "infeasible-vs-feasible" (bền hơn với tìm kiếm
  song song không xác định của CP-SAT). Re-review (haiku, phạm vi hẹp) tự tay
  lặp lại đúng phương pháp "tắt ràng buộc → chạy lại → phải FAIL, bật lại →
  phải PASS" cho cả 5 fixture, độc lập với lời implementer. Cả 5 đều
  ADDRESSED, `cpsat_model.py` xác nhận 0 dòng đổi (fix chỉ ở test).
  Task 4: complete (commits 724047f..d2b8a83, 1 fix round, review clean).
- **DỪNG PHIÊN TẠI ĐÂY** (2026-09-04): theo yêu cầu người dùng do giới hạn token,
  dừng ngay sau Task 4. Task 5 (môn kép/1-cặp liền tiết — rủi ro cao nhất của cả
  kế hoạch) CHƯA bắt đầu, brief đã có sẵn tại `task-5-brief.md`. Task 6-8 cũng
  chưa bắt đầu. Worktree `.worktrees/cpsat-scheduler` (branch `cpsat-scheduler`)
  giữ nguyên, KHÔNG xoá, KHÔNG merge. Phiên sau resume: đọc ledger này, brief
  Task 5, dispatch implementer Task 5 với BASE = HEAD hiện tại của branch
- Task 1: complete (commits 2aae4bb..07d0fe1, review clean). Reviewer (sonnet):
  Spec ✅, Task quality Approved, 0 Critical/Important.
  - Minor (deferred): `test_each_cell_holds_at_most_one_subject` chỉ kiểm tra
    gián tiếp ràng buộc "tối đa 1" (dựa vào bất biến kiểu dict) — kế thừa nguyên
    văn từ brief, không phải lệch của implementer.
    - Minor (deferred, đã tự giải quyết): reviewer thắc mắc con số full-suite
    `246 passed, 1 skipped, 1 xpassed` không khớp kỳ vọng của brief
    (`244 passed, 1 xpassed`). Đã đối chiếu: baseline THẬT đo được trước khi bắt
    đầu Task 1 là `243 passed, 1 skipped, 1 xpassed` — "1 skipped" đã có sẵn từ
    trước Task 1, không phải do task này gây ra; con số `244`/`1 xpassed` trong
    "Định nghĩa xong" ở ledger này là ước tính cũ, không phải baseline đo thật.
    Không có gì cần sửa trong code.
- **Task 5 (2026-09-04)**: Complete (môn kép và single-pair).
  Đã tổng quát hóa khối kích thước N >= 2 (hỗ trợ cả N=2 và N=3 tuần chuyên đề HĐTN).
  Đã kiểm chứng RED phase (thất bại do nhảy cóc / tách tiết / chia sai ngày) và
  GREEN phase (24 passed trong 1.19s).
  Full suite: 267 passed, 1 skipped, 1 xpassed (272s, zero regressions).
  Báo cáo chi tiết: `task-5-report.md`.
