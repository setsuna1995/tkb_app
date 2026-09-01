# Task 4 Brief: UI Updates for `03_DinhMuc.py`

## 1. Objective & Scope
- **Objective**: Modernize and extend `pages/03_DinhMuc.py` to allow users to view, manage, and edit full-year (35 weeks) period quotas across all classes and subjects, as well as one-click auto-import from the uploaded Excel file or the default `Định lượng số tiết theo tuần năm học 2026_2027.xlsx` file. Also provide semester and weekly teacher workload views.
- **Scope**:
  - In Tab "📊 Số tiết/tuần":
    - Mode selector: "📅 Định lượng 35 tuần cả năm" vs "⚖️ Số tiết Chẵn / Lẻ".
    - In 35-week view:
      - Week selector (Tuần 1 -> Tuần 35) with semester group filter (Học kỳ I: 1-18, Học kỳ II: 19-35).
      - Editable table of periods for the selected week with column totals and validation.
      - Save button for the selected week or batch copy to other weeks.
      - Quick one-click action: "📥 Nạp dữ liệu từ file Excel định lượng cả năm" with file uploader or default file button.
      - Overview summary heatmap/matrix of total periods per class across all 35 weeks.
  - In Tab "👩‍🏫 Định mức giáo viên (DinhMuc_GV)":
    - Support viewing teacher workloads for a specific week $1..35$ alongside the 2-week average view.
- **Out of Scope**: Scheduling page (handled in Task 5).

## 2. Interface Specifications
- Streamlit interactive UI in `pages/03_DinhMuc.py`.

## 3. TDD Strategy
- Check that `03_DinhMuc.py` imports without errors.
- Test script verifying data saving and teacher quota views.

## 4. Safety & Invariants
- Preserves all existing teacher quota adjustments, reductions, and role reductions.
- Handles empty week inputs gracefully with fallback.
