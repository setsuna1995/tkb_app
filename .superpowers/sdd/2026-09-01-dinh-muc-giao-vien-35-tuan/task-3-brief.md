# Task 3 Brief: UI Modernization for `pages/03_DinhMuc.py` Teacher Tab

## 1. Objective & Scope
- **Objective**: Modernize Tab "👩‍🏫 Định mức giáo viên (DinhMuc_GV)" in `pages/03_DinhMuc.py` to give administrators and teachers full visibility over teacher workloads based on the 35-week curriculum:
  - **Filter Mode**:
    1. 📅 **Theo Tuần cụ thể trong năm (1-35)**: Slider/Selectbox to pick week, showing exact teaching load for that week, deviation from cap, and highlighting teachers over cap for that week.
    2. 📈 **Toàn năm học (35 tuần)**: Showing Full-Year Average Load, HK1 Average Load, HK2 Average Load, Cap, Deviation, Peak week / Lowest week.
    3. ⚖️ **Theo Chẵn / Lẻ (Legacy)**: Existing 2-week average view.
  - **Interactive 35-Week Teacher Workload Heatmap/Matrix**:
    - Expander displaying a matrix of all teachers (rows) across all 35 weeks (columns $T_1 \dots T_{35}$).
    - Shows each teacher's exact period count per week.
    - Highlights cells exceeding cap in red/orange or below floor in yellow.
  - **Teacher Details Drill-down**:
    - Select a teacher to view detailed breakdown of classes, subjects, and periods per week for all 35 weeks.
  - **Inline Editing of Teacher Roles & Reductions**:
    - Direct editing of *Chức vụ / Kiêm nhiệm* and *Giảm trừ (tiết)* with quick save button.
- **Scope**: `pages/03_DinhMuc.py`.
- **Out of Scope**: Core repository logic (already completed in Task 1).

## 2. Interface Specifications
- Streamlit interactive UI in `pages/03_DinhMuc.py`.

## 3. TDD Strategy
- Check compilation and test UI rendering logic.

## 4. Safety & Invariants
- Preserves all role reduction configs and base cap/min floor settings.
