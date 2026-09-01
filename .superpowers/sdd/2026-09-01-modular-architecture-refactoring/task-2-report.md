# Task 2 Report: Modularize `data/repository.py`

## 1. What was Implemented
- Successfully refactored the 873-line `data/repository.py` into a domain-driven subpackage `data/repositories/` with 6 dedicated modules:
  - `entities.py`: Class, Subject, Teacher CRUD operations and helpers.
  - `curriculum.py`: Assignments (`PhanCong`), Periods per week (`SoTiet`), Role reductions, and Teacher quota views.
  - `constraints.py`: Teacher unavailability (`GV_Ban`), Class frames & allowed cells, Subject-class-slot rules.
  - `config.py`: App meta, Tuan config (chẵn/lẻ), Seed history, Scheduling configuration serialization.
  - `runs.py`: Baseline schedule (`tkb_nhap`), Run log execution records, and TKB result matrix.
  - `builder.py`: Composite builder `build_scheduling_input()` and timeslot canonical generator.
  - `data/repository.py`: Re-export facade ensuring 100% backward compatibility for all pages and tests.

## 2. Files Changed
- **New Directory & Files**:
  - `data/repositories/__init__.py`
  - `data/repositories/entities.py`
  - `data/repositories/curriculum.py`
  - `data/repositories/constraints.py`
  - `data/repositories/config.py`
  - `data/repositories/runs.py`
  - `data/repositories/builder.py`
  - `tests/test_repository_modular_imports.py`
- **Modified**:
  - `data/repository.py` (facade re-exporting all functions)

## 3. TDD Evidence

### RED Phase
Command: `python -m pytest tests/test_repository_modular_imports.py`
Output:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Kien\tkb_app
plugins: anyio-4.14.2
collected 2 items

tests\test_repository_modular_imports.py F.                              [100%]

================================== FAILURES ===================================
______________________ test_modular_repositories_imports ______________________

    def test_modular_repositories_imports():
>       from data.repositories import entities
E       ModuleNotFoundError: No module named 'data.repositories'

tests\test_repository_modular_imports.py:6: ModuleNotFoundError
=========================== short test summary info ===========================
FAILED tests/test_repository_modular_imports.py::test_modular_repositories_imports
========================= 1 failed, 1 passed in 0.13s =========================
```

### GREEN Phase
Command: `python -m pytest tests/test_repository_modular_imports.py tests/test_repository.py`
Output:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Kien\tkb_app
plugins: anyio-4.14.2
collected 21 items

tests\test_repository_modular_imports.py ..                              [  9%]
tests\test_repository.py ...................                             [100%]

============================= 21 passed in 3.38s ==============================
```

## 4. Self-Review Findings
- All functions previously in `data.repository` remain fully exposed with matching signatures.
- Clean separation of database concerns with zero circular dependencies.
