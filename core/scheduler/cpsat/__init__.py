"""CP-SAT solver subpackage for timetable scheduling."""
from core.scheduler.cpsat.types import CpSatModel, CpSatUnavailable, _HAS_ORTOOLS, cp_model

__all__ = [
    "CpSatModel",
    "CpSatUnavailable",
    "_HAS_ORTOOLS",
    "cp_model",
]
