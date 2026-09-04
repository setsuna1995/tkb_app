# Task 8: Nối vào `run()`, fallback, UI, và test song song

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` syntax.

**Goal:** Wire the solver into `run()` behind an off-by-default flag with a safe
fallback to the existing engine, and prove on real fixtures that it never does
worse than what we have today.

**Why (Vietnamese):** Task này là chỗ quyết định "có dám dùng thật không". Hai
nguyên tắc: (1) **mặc định TẮT** — bật lên là quyết định của trường, không phải
của bản cập nhật; (2) **không bao giờ để người dùng thấy màn hình lỗi** vì bộ
giải — thiếu thư viện, quá giờ, hay vô nghiệm đều phải êm ái rơi về engine cũ.

**Files:**
- Modify: `core/models.py` (2 field config)
- Modify: `core/scheduler/engine.py` (`run()`)
- Modify: `data/repositories/config.py` (lưu/đọc 2 field)
- Modify: `pages/10_Cau_hinh_Xep_lich.py` (2 ô cấu hình)
- Create: `tests/test_cpsat_engine_integration.py`

**Interfaces:**
- Consumes: `build_model`, `solve`, `build_result`, `CpSatUnavailable` (Task 1-7)
- Produces: `SchedulingConfig.use_cpsat: bool = False`,
  `SchedulingConfig.cpsat_time_limit_seconds: int = 30`

## Nội dung

Đầu `run()`, trước vòng lặp 6000 lượt hiện tại:

```python
if getattr(config, "use_cpsat", False):
    try:
        from core.scheduler import cpsat_model
        built = cpsat_model.build_model(inp)
        result = cpsat_model.solve_to_result(
            built, time_limit_s=getattr(config, "cpsat_time_limit_seconds", 30))
        if result is not None:
            return result
    except cpsat_model.CpSatUnavailable:
        pass          # thiếu ortools -> engine cũ
    except Exception:
        pass          # bất kỳ lỗi mô hình nào -> engine cũ, không làm hỏng UI
    # rơi xuống engine cũ bên dưới
```

**Bắt `Exception` trần là có chủ ý ở đây** (khác với thói quen chung): mục đích
là *không bao giờ* để lỗi của lõi mới làm hỏng chức năng đang chạy tốt. Nhưng
phải `logging.exception(...)` để lỗi không biến mất im lặng.

UI: ô checkbox *"Dùng bộ giải tối ưu (thử nghiệm)"* + ô số *"Giới hạn thời gian
giải (giây)"*, kèm help nói rõ: bật lên thì TKB được tối ưu toàn cục thay vì
dò tìm ngẫu nhiên; nếu bộ giải không xong trong giới hạn thì tự quay về cách cũ.

## Test song song — phần quan trọng nhất của cả kế hoạch

Tạo `tests/test_cpsat_engine_integration.py`. Với **cả hai** fixture:
`io_excel/sample_school.xlsm` (qua `import_xlsm` vào DB tạm, theo đúng cách
`tests/test_real_data_schedule.py` đang làm) và `schools/truong-thcs.db` nếu có:

1. **`use_cpsat=False` không đổi gì**: chạy `run()` và khẳng định kết quả giống
   hệt trước khi có task này (dùng seed cố định, so `assignment`).
2. **Lời giải CP-SAT hợp lệ**: chạy với `use_cpsat=True`, cho kết quả đi qua
   **toàn bộ** hàm `find_*` trong `core/validation.py` → tất cả phải rỗng.
   Đây là kiểm chứng độc lập: KHÔNG dùng lại ràng buộc trong mô hình để tự chấm.
3. **Không thua engine cũ**: chạy cả hai lõi trên cùng dữ liệu, khẳng định
   CP-SAT có số vi phạm **≤** engine cũ ở TỪNG tiêu chí (II.3, II.4, II.8, II.7,
   II.14). Không được "tốt tổng thể nhưng tệ hơn ở một tiêu chí".
4. **Fallback hoạt động**: giả lập `ortools` không import được (monkeypatch
   `cpsat_model._HAS_ORTOOLS = False`) → `run()` vẫn trả TKB hợp lệ từ engine cũ.
5. **Quá giờ vẫn an toàn**: đặt `cpsat_time_limit_seconds=0` → fallback êm.

## Định nghĩa xong

- Toàn bộ 244 test cũ pass với mặc định (`use_cpsat=False`).
- Trên Tuần 2 thật với `use_cpsat=True`: II.3 = 0, II.4 = 0 (không kể GV được
  miễn), II.8 = 0 — khớp con số POC đã đạt.
- Thời gian giải < 10s/tuần.

- [ ] Step 1: thêm 2 field config + lưu/đọc DB + 2 ô UI
- [ ] Step 2: viết 5 test tích hợp → FAIL
- [ ] Step 3: nối vào `run()` với fallback
- [ ] Step 4: chạy `python -m pytest tests/ -q` → 244 cũ + test mới đều pass
- [ ] Step 5: đo thật trên `truong-thcs.db` Tuần 2, ghi số vào `progress.md`
- [ ] Step 6: commit `feat(cpsat): wire solver into run() behind an off-by-default flag`
