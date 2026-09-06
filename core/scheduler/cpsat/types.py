"""Data types and environment detection for CP-SAT solver."""
from __future__ import annotations

from dataclasses import dataclass, field
from core.models import SchedulingInput

try:
    from ortools.sat.python import cp_model
    _HAS_ORTOOLS = True
except ImportError:  # pragma: no cover - phụ thuộc mềm
    cp_model = None
    _HAS_ORTOOLS = False


class CpSatUnavailable(RuntimeError):
    """ortools chưa được cài đặt trong môi trường hiện tại."""


@dataclass
class CpSatModel:
    model: object                      # cp_model.CpModel
    x: dict                            # (slot_id, subject_id) -> BoolVar
    inp: SchedulingInput
    slots_by_class: dict = field(default_factory=dict)
    slots_by_ts: dict = field(default_factory=dict)
    teacher_of: dict = field(default_factory=dict)     # (slot_id, subject_id) -> teacher_id
    role_index: object = None                          # kết quả resolve_roles()
    penalty_terms: dict = field(default_factory=dict)  # mã tiêu chí -> list biến phạt
    changed_terms: list = field(default_factory=list)  # biến đổi ô so với tiết cũ
