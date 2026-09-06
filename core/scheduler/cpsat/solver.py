"""Execution, diagnosis, and result extraction for CP-SAT model."""
from __future__ import annotations

from collections import defaultdict
import os
import threading
import time
from typing import Callable, Optional, Sequence

from core.models import ScheduleResult, is_bgh
from core.rules_registry import HARD_POST_GENERATION_IDS
from core.scheduler.cpsat.types import CpSatModel, CpSatUnavailable, _HAS_ORTOOLS, cp_model
from core.scheduler.cpsat.constraints import _is_teacher_busy_morning


def build_result(built: CpSatModel, solver: cp_model.CpSolver, diagnostics: Optional[dict] = None) -> ScheduleResult:
    """Dựng đối tượng ScheduleResult hoàn chỉnh từ một lời giải CP-SAT."""
    inp = built.inp
    x = built.x

    assignment = {}
    for slot in inp.slots:
        chosen_subj = None
        for subj in inp.subjects:
            key = (slot.slot_id, subj.subject_id)
            if key in x and solver.Value(x[key]):
                chosen_subj = subj.subject_id
                break
        assignment[slot.slot_id] = chosen_subj

    cells_changed = 0
    for slot in inp.slots:
        if assignment.get(slot.slot_id) != slot.old_subject_id:
            cells_changed += 1
    cells_total = len(inp.slots)

    relaxed_rules = []
    unsat_core = set((diagnostics or {}).get("unsat_core", []))
    for rid in HARD_POST_GENERATION_IDS:
        terms = built.penalty_terms.get(rid, [])
        v_count = sum(solver.Value(t) for t in terms) if terms else 0
        if v_count > 0:
            entry = {"rule_id": rid, "count": int(v_count)}
            if rid in unsat_core:
                entry["proven_infeasible"] = True
            relaxed_rules.append(entry)

    successes_found = 1 if not relaxed_rules else 0

    return ScheduleResult(
        success=True,
        assignment=assignment,
        cells_changed=cells_changed,
        cells_total=cells_total,
        attempts_tried=1,
        successes_found=successes_found,
        relaxed_rules=relaxed_rules,
        solver_name="cpsat",
        diagnostics=diagnostics or {},
    )


def _build_gated_model(built: CpSatModel, rids: Sequence[str]) -> tuple:
    """Clone built.model và thêm một reified gate BoolVar cho mỗi rid."""
    model = built.model.Clone()
    gates = {}
    for rid in rids:
        terms = built.penalty_terms.get(rid)
        if not terms:
            continue
        gate = model.NewBoolVar(f"gate_{rid}")
        model.Add(sum(terms) == 0).OnlyEnforceIf(gate)
        gates[rid] = gate
    return model, gates


_STATUS_NAMES = {
    0: "UNKNOWN",
    1: "MODEL_INVALID",
    2: "FEASIBLE",
    3: "INFEASIBLE",
    4: "OPTIMAL",
}
if cp_model is not None:
    _STATUS_NAMES.update({
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "UNKNOWN",
    })


def detect_optimal_workers(override: int = 0) -> int:
    """Tự động phát hiện môi trường thực thi để chọn số workers tối ưu cho CP-SAT."""
    if override and int(override) > 0:
        return int(override)

    # 1. Biến môi trường Streamlit Community Cloud
    if os.environ.get("STREAMLIT_SHARING_HOST") or os.environ.get("IS_STREAMLIT_CLOUD"):
        return 2

    # 2. Linux cgroups CPU Quota
    try:
        if os.path.exists("/sys/fs/cgroup/cpu.max"):
            with open("/sys/fs/cgroup/cpu.max") as f:
                quota, period = f.read().split()
                if quota != "max":
                    cgroup_cpus = int(int(quota) / int(period))
                    return max(1, min(2, cgroup_cpus))
        elif os.path.exists("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"):
            with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as f_q, open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as f_p:
                q = int(f_q.read().strip())
                p = int(f_p.read().strip())
                if q > 0 and p > 0:
                    cgroup_cpus = int(q / p)
                    return max(1, min(2, cgroup_cpus))
    except Exception:
        pass

    # 3. Tiến trình bị giới hạn core
    try:
        if hasattr(os, "sched_getaffinity"):
            eff = len(os.sched_getaffinity(0))
            if eff <= 2:
                return max(1, eff)
        if hasattr(os, "process_cpu_count"):
            p_cpu = os.process_cpu_count()
            if p_cpu and p_cpu <= 2:
                return max(1, p_cpu)
    except Exception:
        pass

    # 4. Môi trường PC/Laptop cục bộ
    cpu_cores = os.cpu_count() or 4
    return 4 if cpu_cores >= 4 else max(1, cpu_cores)


class EarlyStoppingCallback(cp_model.CpSolverSolutionCallback if cp_model is not None else object):
    """Callback theo dõi tiến trình tìm kiếm của CP-SAT và kích hoạt dừng sớm (Early Stopping)."""
    def __init__(self, stagnation_s: float = 6.0,
                 progress_cb: Optional[Callable[[dict], None]] = None,
                 pass_no: int = 1, max_passes: int = 1):
        if cp_model is not None:
            super().__init__()
        self.stagnation_s = stagnation_s
        self.progress_cb = progress_cb
        self.pass_no = pass_no
        self.max_passes = max_passes
        self.start_time = time.time()
        self.last_sol_time = None
        self.sol_count = 0
        self.best_obj = None
        self.stop_event = threading.Event()
        self.watcher = threading.Thread(target=self._watch, daemon=True)

    def _watch(self):
        while not self.stop_event.is_set():
            time.sleep(0.3)
            if self.last_sol_time is not None and (time.time() - self.last_sol_time > self.stagnation_s):
                self.StopSearch()
                break

    def on_solution_callback(self):
        self.sol_count += 1
        now = time.time()
        self.last_sol_time = now
        obj = self.ObjectiveValue()
        self.best_obj = obj
        if self.progress_cb:
            try:
                self.progress_cb({
                    "event": "solution",
                    "pass": self.pass_no,
                    "max_passes": self.max_passes,
                    "sol_count": self.sol_count,
                    "objective": obj,
                    "status": "FEASIBLE",
                    "wall_time_s": now - self.start_time,
                })
            except Exception:
                pass
        if obj <= 0:
            self.StopSearch()


def _presolve_capacity_screening(built: CpSatModel) -> set[str]:
    """Phân tích giải tích tiền giải (0.001s) để phát hiện mâu thuẫn dung lượng toán học (Pigeonhole)."""
    config = built.inp.config
    mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
    strict_morns = getattr(config, "strict_morning_weekdays", ())
    min_mand_load = getattr(config, "min_weekly_periods_for_mandatory_morning", 10)
    bgh_ids = {t.teacher_id for t in built.inp.teachers if is_bgh(t)}

    load = defaultdict(int)
    for (s_id, c_id), n in built.inp.need.items():
        t_id = built.inp.assigned_teacher.get((s_id, c_id))
        if t_id is not None and t_id > 0:
            load[t_id] += n

    all_mand = set(mand_morns) | set(strict_morns)
    for wd in all_mand:
        morn_slots = [s for s in built.inp.slots if s.ts.weekday == wd and s.ts.session == "S"]
        cap = len(morn_slots)
        req_teachers = 0
        for t in built.inp.teachers:
            if t.teacher_id in bgh_ids:
                continue
            if _is_teacher_busy_morning(built.inp, t.teacher_id, wd):
                continue
            is_strict = (wd in strict_morns)
            is_mand = (wd in mand_morns and wd not in strict_morns and load[t.teacher_id] >= min_mand_load)
            if is_strict or is_mand:
                req_teachers += 1

        min_needed = req_teachers * 2
        if min_needed > cap:
            return {"II.4"}

    return set()


def _diagnose_and_solve(built: CpSatModel, solver: cp_model.CpSolver, time_limit_s: float,
                        progress_cb: Optional[Callable[[dict], None]] = None) -> dict:
    """Chẩn đoán leo thang assumption gates cho HARD_POST_GENERATION_IDS và giải tối ưu."""
    active_rids = [rid for rid in HARD_POST_GENERATION_IDS if built.penalty_terms.get(rid)]
    max_passes = len(active_rids) + 1
    relaxed: set = set()
    remaining = float(time_limit_s)
    diag = {
        "status": cp_model.UNKNOWN if cp_model is not None else 0,
        "pass1_status": None,
        "unsat_core": [],
        "relaxed_by_diagnosis": [],
        "passes_run": 0,
    }

    if remaining <= 0.0 or cp_model is None:
        return diag

    num_workers = int(getattr(solver.parameters, "num_search_workers", 2) or 2)
    stagnation = 5.0 if num_workers <= 2 else 8.0

    while True:
        diag["passes_run"] += 1
        hard_rids = [rid for rid in active_rids if rid not in relaxed]

        if progress_cb:
            progress_cb({
                "event": "pass_start", "pass": diag["passes_run"], "max_passes": max_passes,
                "hard_rids": hard_rids, "relaxed_so_far": sorted(relaxed),
                "workers": num_workers, "remaining_budget_s": remaining,
            })

        if diag["passes_run"] == 1:
            incompatible_rids = _presolve_capacity_screening(built)
            if incompatible_rids:
                relaxed |= incompatible_rids
                diag["relaxed_by_diagnosis"] = sorted(relaxed)
                hard_rids = [rid for rid in active_rids if rid not in relaxed]

        if not hard_rids:
            model, _gates = _build_gated_model(built, [])
            solver.parameters.max_time_in_seconds = float(remaining)
            cb = EarlyStoppingCallback(
                stagnation_s=stagnation, progress_cb=progress_cb,
                pass_no=diag["passes_run"], max_passes=max_passes
            )
            cb.watcher.start()
            status = solver.Solve(model, cb)
            cb.stop_event.set()
            diag["status"] = status
            if diag["pass1_status"] is None:
                diag["pass1_status"] = _STATUS_NAMES.get(status, str(status))
            if progress_cb:
                progress_cb({
                    "event": "pass_end", "pass": diag["passes_run"], "max_passes": max_passes,
                    "status": _STATUS_NAMES.get(status, str(status)), "wall_time_s": solver.WallTime(),
                })
            return diag

        # Chẩn đoán tính khả thi thuần túy (Pass 1)
        diag_model, diag_gates = _build_gated_model(built, hard_rids)
        diag_model.Proto().clear_objective()
        diag_model.AddAssumptions(list(diag_gates.values()))
        diag_solver = cp_model.CpSolver()
        diag_solver.parameters.num_search_workers = num_workers
        diag_solver.parameters.linearization_level = 1
        diag_solver.parameters.cp_model_probing_level = 1
        if getattr(built.inp, "seed", None):
            diag_solver.parameters.random_seed = int(built.inp.seed)
        diag_budget = min(2.5, max(remaining * 0.15, 1.0))
        diag_solver.parameters.max_time_in_seconds = float(diag_budget)

        feas_status = diag_solver.Solve(diag_model)
        remaining -= diag_solver.WallTime()

        if feas_status == cp_model.INFEASIBLE:
            core = set(diag_solver.SufficientAssumptionsForInfeasibility())
            index_to_rid = {g.Index(): rid for rid, g in diag_gates.items()}
            offending = {index_to_rid[i] for i in core if i in index_to_rid}
            if diag["pass1_status"] is None:
                diag["pass1_status"] = "INFEASIBLE"
                diag["unsat_core"] = sorted(offending)
            if not offending:
                offending = set(hard_rids)
            relaxed |= offending
            diag["relaxed_by_diagnosis"] = sorted(relaxed)
            if progress_cb:
                progress_cb({
                    "event": "pass_end", "pass": diag["passes_run"], "max_passes": max_passes,
                    "status": "INFEASIBLE", "wall_time_s": diag_solver.WallTime(),
                })
            continue

        if feas_status == cp_model.UNKNOWN:
            if diag["pass1_status"] is None:
                diag["pass1_status"] = "UNKNOWN"
            relaxed |= set(hard_rids)
            diag["relaxed_by_diagnosis"] = sorted(relaxed)
            if progress_cb:
                progress_cb({
                    "event": "pass_end", "pass": diag["passes_run"], "max_passes": max_passes,
                    "status": "UNKNOWN", "wall_time_s": diag_solver.WallTime(),
                })
            continue

        # Pass 2: Giải tối ưu hóa
        model, gates = _build_gated_model(built, hard_rids)
        model.AddAssumptions(list(gates.values()))
        solver.parameters.max_time_in_seconds = float(remaining)
        cb = EarlyStoppingCallback(
            stagnation_s=stagnation, progress_cb=progress_cb,
            pass_no=diag["passes_run"], max_passes=max_passes
        )
        cb.watcher.start()
        status = solver.Solve(model, cb)
        cb.stop_event.set()
        remaining -= solver.WallTime()
        diag["status"] = status
        if diag["pass1_status"] is None:
            diag["pass1_status"] = _STATUS_NAMES.get(status, str(status))

        if progress_cb:
            progress_cb({
                "event": "pass_end", "pass": diag["passes_run"], "max_passes": max_passes,
                "status": _STATUS_NAMES.get(status, str(status)), "wall_time_s": solver.WallTime(),
            })

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return diag

        relaxed |= set(hard_rids)
        diag["relaxed_by_diagnosis"] = sorted(relaxed)
        continue


def solve_to_result(built: CpSatModel, time_limit_s: float = 30.0,
                    workers: Optional[int] = None,
                    progress_cb: Optional[Callable[[dict], None]] = None) -> Optional[ScheduleResult]:
    """Giải mô hình và trả về ScheduleResult hoàn chỉnh, hoặc None nếu không giải được."""
    if not _HAS_ORTOOLS or cp_model is None:
        raise CpSatUnavailable("ortools chưa được cài")

    if os.environ.get("PYTEST_XDIST_WORKER") or os.environ.get("PYTEST_CURRENT_TEST"):
        eff_workers = 2
    elif workers is None or int(workers) <= 0:
        user_workers = getattr(built.inp.config, "cpsat_workers", 0)
        eff_workers = detect_optimal_workers(override=user_workers)
    else:
        eff_workers = max(1, int(workers))

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = int(eff_workers)
    solver.parameters.linearization_level = 1
    solver.parameters.cp_model_probing_level = 1
    if getattr(built.inp, "seed", None):
        solver.parameters.random_seed = int(built.inp.seed)

    diag = _diagnose_and_solve(built, solver, float(time_limit_s), progress_cb=progress_cb)
    if diag["status"] not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    return build_result(built, solver, diagnostics=diag)


def solve(built: CpSatModel, time_limit_s: float = 10.0,
          workers: Optional[int] = None) -> Optional[dict]:
    """Trả {slot_id: subject_id} cho các ô CÓ môn, hoặc None nếu không giải được."""
    if not _HAS_ORTOOLS or cp_model is None:
        raise CpSatUnavailable("ortools chưa được cài")

    if os.environ.get("PYTEST_XDIST_WORKER") or os.environ.get("PYTEST_CURRENT_TEST"):
        eff_workers = 2
    elif workers is None or int(workers) <= 0:
        user_workers = getattr(built.inp.config, "cpsat_workers", 0)
        eff_workers = detect_optimal_workers(override=user_workers)
    else:
        eff_workers = max(1, int(workers))

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = int(eff_workers)
    solver.parameters.linearization_level = 1
    solver.parameters.cp_model_probing_level = 1
    if getattr(built.inp, "seed", None):
        solver.parameters.random_seed = int(built.inp.seed)

    diag = _diagnose_and_solve(built, solver, float(time_limit_s))
    if diag["status"] not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    assignment = {}
    for (slot_id, subject_id), var in built.x.items():
        if solver.Value(var):
            assignment[slot_id] = subject_id
    return assignment
