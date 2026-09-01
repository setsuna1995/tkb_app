# Task 2 Brief: Modularize `data/repository.py`

## 1. Objective & Scope
Refactor the 873-line `data/repository.py` into a modular package `data/repositories/` split by domain concern:
- `entities.py`: Classes, Subjects, Teachers CRUD.
- `curriculum.py`: Assignments, Quotas, Role reductions, Teacher quota views.
- `constraints.py`: Teacher unavailability (GV bận), Class frames & allowed cells, Subject-class-slot rules.
- `config.py`: App meta, Tuan config, Seed history, Scheduling configuration serialization/deserialization.
- `runs.py`: Baseline schedule (`tkb_nhap`), Run log history, TKB results.
- `builder.py`: Canonical timeslots generation and composite `build_scheduling_input()`.
- `data/repository.py`: Facade module re-exporting all functions for 100% backward compatibility.

## 2. Interface Specifications
All functions currently exported by `data/repository.py` must remain available with identical signatures and semantics via `from data import repository as repo`:
- Entity operations: `list_classes`, `get_class_by_name`, `upsert_class`, `delete_class`, `list_subjects`, `get_subject_by_name`, `upsert_subject`, `delete_subject`, `list_teachers`, `get_teacher_by_name`, `upsert_teacher`, `delete_teacher`.
- Curriculum & Quota: `get_base_cap`, `set_base_cap`, `get_min_floor`, `set_min_floor`, `get_role_reduction`, `set_role_reduction`, `get_teacher_quota_view`, `get_teacher_caps`, `get_assignments`, `set_assignment`, `get_periods_per_week`, `set_periods_per_week`.
- Constraints: `list_unavailability`, `add_unavailability`, `clear_unavailability`, `get_teacher_busy_cells`, `compress_busy_cells`, `set_teacher_busy_cells`, `get_frame_template`, `get_all_frame_templates`, `set_frame_template`, `get_class_allowed_cells`, `get_all_class_allowed_cells`, `set_class_allowed_cells`, `list_subject_class_rules`, `upsert_subject_class_rule`, `delete_subject_class_rule`, `get_subject_class_allowed_cells`.
- Configuration: `get_meta`, `set_meta`, `get_tuan_config`, `set_tuan_config`, `list_seed_history`, `add_seed_history`, `clear_seed_history`, `get_scheduling_config`, `set_scheduling_config`.
- Runs & TKB: `get_tkb_nhap`, `bulk_replace_tkb_nhap`, `save_run`, `save_tkb_result`, `get_latest_run`, `get_latest_run_by_parity`, `get_tkb_result`.
- Builder: `build_scheduling_input`.

## 3. TDD Strategy
- Test file: `tests/test_repository_modular_imports.py` testing individual submodule imports and complete repository suite (`tests/test_repository.py`).
- RED Phase: import fails before `data/repositories/` package is created.
- GREEN Phase: implement all submodules in `data/repositories/` and update `data/repository.py` facade; verify `pytest tests/test_repository_modular_imports.py tests/test_repository.py`.
