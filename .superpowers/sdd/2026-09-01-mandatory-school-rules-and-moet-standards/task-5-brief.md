# Task 5 Brief: Full Integration & Compliance Verification Suite

## 1. Objective & Scope
Construct an end-to-end integration test suite in `tests/test_mandatory_rules_compliance.py` asserting all 15 school council criteria and MOET standards against scheduler execution with full scheduling inputs.

## 2. Interface Specifications
- Full test functions covering all 15 criteria and MOET standards.
- Real scheduling run scenarios verifying:
  - Exact quota satisfaction
  - 0 teacher conflicts
  - 0 day-cap violations (teacher day <= 5)
  - 0 heavy-in-afternoon-p3 violations
  - 0 gdtc-consecutive-days violations
  - 0 gap violations when solvable
  - Correct HĐTN 3-period distribution (Mon p1, Fri last, p2 afternoon)

## 3. TDD Strategy
- Add tests to `tests/test_mandatory_rules_compliance.py`.
- Run `python -m pytest tests/test_mandatory_rules_compliance.py`.
- Run full test suite across the repository to verify 0 regressions.
- Verify GREEN status.
