# SDD Ledger: Mandatory School Rules & MOET Standards Compliance

**Feature Slug**: `2026-09-01-mandatory-school-rules-and-moet-standards`
**Context**: Implement, verify, and enforce 100% of MOET standards and School Council (HĐSP) 15-point criteria in the TKB scheduling engine.

---

## 1. Requirements & Compliance Matrix

| Rule ID | Category | Requirement Description | Implementation Strategy | Status |
|---|---|---|---|---|
| **I.1.1** | MOET System | 1 GV không dạy 2 lớp cùng tiết | Hard constraint (`state.busy`) | Verified |
| **I.1.2** | MOET System | 1 Lớp không học 2 môn cùng tiết | Structural model (`Slot`) | Verified |
| **I.1.3** | MOET System | Khớp định lượng số tiết môn (GDPT 2018) | Exact quota satisfaction (`need == 0`) | Verified |
| **I.1.4** | MOET System | Khớp định mức phân công giáo viên | Exact teacher quota assignment | Verified |
| **I.2.1** | MOET Pedagogy | Số tiết max/ngày (THCS 1 buổi <=5, 2 buổi <=7) | Class frame grid + day_capacity enforcement | Verified |
| **I.2.2** | MOET Pedagogy | Tránh môn nặng liên tiếp (>3 tiết) | `max_heavy_consecutive = 3` window check | Verified |
| **I.2.3** | MOET Pedagogy | Phân bố môn học (môn >=2 tiết không cùng ngày trừ kép) | `len(positions) >= cap_d` | Verified |
| **I.2.4** | MOET Pedagogy | Tiết cách đều trong tuần | Non-consecutive day heuristic penalties | Verified |
| **I.2.5** | MOET Pedagogy | Thể dục tránh tiết 5 | `gdtc_avoid_period = 5`, morning (1-4), afternoon (2-3) | Verified |
| **I.2.6** | MOET Pedagogy | Chào cờ cố định sáng Thứ 2 tiết 1 | `chao_co_weekday=2, period=1` | Verified |
| **I.2.7** | MOET Pedagogy | Sinh hoạt lớp cố định tiết cuối Thứ 6 / Thứ 7 | `shl_target_slot` reservation | Verified |
| **II.1** | HĐSP | Đảm bảo đúng định lượng tiết/tuần | 100% need completion | Verified |
| **II.2** | HĐSP | GV không quá tải vượt 5 tiết/ngày | `max_teacher_periods_per_day = 5` constraint | To Implement |
| **II.3** | HĐSP | GV có 1 buổi nghỉ chủ nhật xanh (trừ sáng T2, T5, T6) | `_assign_off_slots` + `FORBIDDEN_OFF_CELLS` | Verified |
| **II.4** | HĐSP | Hạn chế GV dạy 1 tiết/buổi hoặc 1 tiết/ngày (trừ GV <15 tiết) | Lone session scoring & exemption for load <15 | To Refine |
| **II.5** | HĐSP | GDTC + Toán + Văn ưu tiên buổi sáng | Morning priority bonuses & morning-only rules | Verified |
| **II.6** | HĐSP | HĐTN 3 tiết: T1 sáng T2, T3 cuối T6, T2 mặc định buổi chiều | Designated afternoon placement for HĐTN period 2 | To Implement |
| **II.7** | HĐSP | Hạn chế thủng tiết GV (dạy T1 nghỉ T2-T3 dạy T4) | `_calculate_teacher_gap_penalty` + gap scoring | Verified |
| **II.8** | HĐSP | Không xếp GV dạy sáng 1 tiết + chiều 1 tiết | `_count_teacher_split_sessions` & `TEACHER_SPLIT_DAY_PENALTY` | Verified |
| **II.9** | HĐSP | Không để GV nghỉ toàn bộ các buổi chiều | `_count_teacher_missing_afternoon_duty` penalty | Verified |
| **II.10** | HĐSP | Không trùng tiết GV | 100% conflict-free validation | Verified |
| **II.11** | HĐSP | Toán-Văn-Anh-KHTN-LS&ĐL kiểm tra 2 tiết liền kề | Block atomic placement & repair | Verified |
| **II.12** | HĐSP | GDTC cách ít nhất 1 ngày giữa các buổi | `avoid_gdtc_consecutive_days = True` | Verified |
| **II.13** | HĐSP | Không xếp dồn đồng thời các môn nặng cho 1 lớp vào 1 buổi | `max_heavy_per_session = 3` & session heavy limit | To Implement |
| **II.14** | HĐSP | Hạn chế xếp GV dạy 4 tiết liên tục sáng (trừ GV >20 tiết/tuần) | Morning consecutive load heuristic penalty | To Implement |
| **II.15** | HĐSP | Hạn chế xếp môn nặng vào tiết 3 chiều | Heavy afternoon period 3 penalty/constraint | To Implement |

---

## 2. Pre-flight Conflict Scan Table

| Tasks | File | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | `core/models.py`, `core/scheduler/feasibility.py` | Defines new config fields (`max_teacher_periods_per_day`, `avoid_heavy_afternoon_period3`, `max_heavy_per_session`, etc.) | Feasibility checks use config fields for pruning | Clean — Strict order 1 -> 2 |
| 2, 3 | `core/scheduler/feasibility.py`, `core/scheduler/heuristics.py` | Feasibility enforces hard caps (max 5/day, heavy limits) | Heuristics scores soft penalties (4-period morning, lone session exemptions) | Clean — Complementary modules |
| 3, 4 | `core/scheduler/quality.py`, `pages/06_Xep_TKB.py` | Quality penalty reflects 15 HĐSP rules | UI renders checkboxes & explanations for the rules | Clean — Disjoint layers |

---

## 3. Task Checklist

- [x] **Task 1**: Domain Models & Config Extensions for HĐSP & MOET Standards (`core/models.py`)
- [x] **Task 2**: Hard Constraints & Feasibility Rules (GV max 5 tiết/ngày, Heavy session cap, Heavy period 3 afternoon constraint) (`core/scheduler/feasibility.py`, `core/scheduler/state.py`)
- [x] **Task 3**: Scoring Heuristics & Quality Penalties (HĐTN period 2 afternoon preference, GV 4-period morning limit for load <= 20, <15 period lone exemption) (`core/scheduler/heuristics.py`, `core/scheduler/quality.py`, `core/scheduler/engine.py`)
- [x] **Task 4**: UI Streamlit Settings & Visual Rule Cards (`pages/06_Xep_TKB.py`)
- [x] **Task 5**: Full Integration & Red-Green Verification Suite (`tests/test_mandatory_rules_compliance.py`)
