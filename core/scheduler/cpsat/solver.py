"""Execution, diagnosis, and result extraction for CP-SAT model."""
from __future__ import annotations

from collections import defaultdict
import os
import threading
import time
from typing import Callable, Optional, Sequence

from core.models import ScheduleResult, is_bgh, ROLE_HDTN
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
                 plateau_window_s: float = 4.0,
                 min_improvement_rate: float = 0.03,
                 min_improvement_abs: float = 600.0,
                 min_search_s: float = 3.5,
                 progress_cb: Optional[Callable[[dict], None]] = None,
                 pass_no: int = 1, max_passes: int = 1):
        if cp_model is not None:
            super().__init__()
        self.stagnation_s = stagnation_s
        self.plateau_window_s = plateau_window_s
        self.min_improvement_rate = min_improvement_rate
        self.min_improvement_abs = min_improvement_abs
        self.min_search_s = min_search_s
        self.progress_cb = progress_cb
        self.pass_no = pass_no
        self.max_passes = max_passes
        self.start_time = time.time()
        self.last_sol_time = None
        self.sol_count = 0
        self.best_obj = None
        self.history: list[tuple[float, float]] = []
        self.stop_event = threading.Event()
        self.watcher = threading.Thread(target=self._watch, daemon=True)

    def _check_plateau(self) -> bool:
        """Kiểm tra xem tốc độ cải thiện điểm phạt có bị bão hòa (plateau) hay không."""
        now = time.time()
        if now - self.start_time < self.min_search_s:
            return False
        if len(self.history) < 2 or self.best_obj is None:
            return False

        cutoff = now - self.plateau_window_s
        recent_candidates = [obj for (t, obj) in self.history if t <= cutoff]
        if not recent_candidates:
            base_obj = self.history[0][1]
        else:
            base_obj = recent_candidates[-1]

        improvement_abs = base_obj - self.best_obj
        if base_obj > 0:
            improvement_rate = improvement_abs / base_obj
        else:
            improvement_rate = 0.0

        if improvement_abs < self.min_improvement_abs or improvement_rate < self.min_improvement_rate:
            return True
        return False

    def _watch(self):
        while not self.stop_event.is_set():
            time.sleep(0.3)
            now = time.time()
            if self.last_sol_time is not None:
                if now - self.last_sol_time > self.stagnation_s:
                    self.StopSearch()
                    break
                if self._check_plateau():
                    self.StopSearch()
                    break

    def on_solution_callback(self):
        self.sol_count += 1
        now = time.time()
        self.last_sol_time = now
        obj = self.ObjectiveValue()
        self.best_obj = obj
        self.history.append((now, obj))
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
        elif self._check_plateau():
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

    res: set[str] = set()
    all_mand = set(mand_morns) | set(strict_morns)
    for wd in all_mand:
        morn_slots = [s for s in built.inp.slots if s.ts.weekday == wd and s.ts.session == "S"]
        cap = len(morn_slots)
        mand_teacher_ids = set()
        for t in built.inp.teachers:
            if t.teacher_id in bgh_ids:
                continue
            if _is_teacher_busy_morning(built.inp, t.teacher_id, wd):
                continue
            is_strict = (wd in strict_morns)
            is_mand = (wd in mand_morns and wd not in strict_morns and load[t.teacher_id] >= min_mand_load)
            if is_strict or is_mand:
                mand_teacher_ids.add(t.teacher_id)

        if wd == getattr(config, "chao_co_weekday", 2) and not built.inp.hdtn_thematic_week:
            hdtn_id = getattr(built.inp, "hdtn_id", None) or next((s.subject_id for s in built.inp.subjects if s.role_code == ROLE_HDTN), None)
            cc_period = getattr(config, "chao_co_period", 1)
            cc_slots = [s for s in morn_slots if s.ts.period == cc_period]
            # Tiết chào cờ chỉ bị trừ khỏi dung lượng khả dụng nếu không được phân cho GV bắt buộc có mặt
            cc_taken_by_others = 0
            for s in cc_slots:
                assigned_t = built.inp.assigned_teacher.get((hdtn_id, s.class_id))
                if not assigned_t or assigned_t not in mand_teacher_ids:
                    cc_taken_by_others += 1
            cap -= cc_taken_by_others

        min_needed = len(mand_teacher_ids) * 2
        if cap > 0 and min_needed > cap:
            return {"II.3"}

    return set()


def _diagnose_and_solve(built: CpSatModel, solver: cp_model.CpSolver, time_limit_s: float,
                        progress_cb: Optional[Callable[[dict], None]] = None) -> dict:
    """Chẩn đoán và giải tối ưu hóa toàn cục:
    Ưu tiên tuyệt đối các tiêu chí cốt lõi của nhà trường (II.4: không buổi lẻ, II.8: không chia lẻ).
    Sử dụng ràng buộc trực tiếp ở pass chính để CP-SAT presolver suy biến miền giá trị term == 0 ngay từ đầu,
    giúp giải nhanh gấp 5-10 lần so với assumption gates.
    """
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
    stagnation = 5.0 if num_workers <= 2 else 7.0

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

        # Pass giải chính với ràng buộc trực tiếp:
        model = built.model.Clone()
        for rid in hard_rids:
            terms = built.penalty_terms.get(rid)
            if terms:
                model.Add(sum(terms) == 0)

        # Phân bổ thời gian giữa các pass: nếu còn nhiều pass và còn đủ thời gian,
        # giới hạn pass 1 & 2 để luôn có ngân sách dự phòng cho pass tiếp theo.
        if len(hard_rids) > 1 and remaining > 15.0:
            pass_limit = min(max(remaining * 0.6, 15.0), 25.0)
        else:
            pass_limit = max(1.0, float(remaining))

        solver.parameters.max_time_in_seconds = float(pass_limit)
        solver.parameters.relative_gap_limit = 0.03
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

        if not hard_rids:
            return diag

        # Nếu INFEASIBLE: dùng gated model để trích xuất UNSAT core
        if status == cp_model.INFEASIBLE:
            diag_model, diag_gates = _build_gated_model(built, hard_rids)
            diag_model.Proto().clear_objective()
            diag_model.AddAssumptions(list(diag_gates.values()))
            diag_solver = cp_model.CpSolver()
            diag_solver.parameters.num_search_workers = num_workers
            diag_budget = min(max(remaining, 1.0), 3.5)
            diag_solver.parameters.max_time_in_seconds = float(diag_budget)
            if diag_solver.Solve(diag_model) == cp_model.INFEASIBLE:
                core = set(diag_solver.SufficientAssumptionsForInfeasibility())
                index_to_rid = {g.Index(): rid for rid, g in diag_gates.items()}
                offending = {index_to_rid[i] for i in core if i in index_to_rid}
            else:
                offending = set()

            if diag["passes_run"] == 1:
                diag["unsat_core"] = sorted(offending)
            if not offending:
                # Ưu tiên nới lỏng II.4 trước nếu không trích xuất được core, bảo vệ tuyệt đối II.3
                if "II.4" in hard_rids:
                    offending = {"II.4"}
                elif "II.8" in hard_rids:
                    offending = {"II.8"}
                else:
                    offending = {"II.3"}

            relaxed |= offending
            diag["relaxed_by_diagnosis"] = sorted(relaxed)
            continue

        # Nếu UNKNOWN (timeout): Nới lỏng ràng buộc tổ hợp nặng trước (II.4 rồi đến II.8),
        # bảo vệ tuyệt đối II.3 (có mặt buổi sáng T2/T6 - yêu cầu bắt buộc của nhà trường).
        if status == cp_model.UNKNOWN:
            if "II.4" in hard_rids:
                offending = {"II.4"}
            elif "II.8" in hard_rids:
                offending = {"II.8"}
            elif "II.3" in hard_rids:
                offending = {"II.3"}
            else:
                offending = set(hard_rids)
            relaxed |= offending
            diag["relaxed_by_diagnosis"] = sorted(relaxed)
            continue


def solve_to_result(built: CpSatModel, time_limit_s: float = 30.0,
                    workers: Optional[int] = None,
                    progress_cb: Optional[Callable[[dict], None]] = None) -> Optional[ScheduleResult]:
    """Giải mô hình và trả về ScheduleResult hoàn chỉnh, hoặc None nếu không giải được."""
    if not _HAS_ORTOOLS or cp_model is None:
        raise CpSatUnavailable("ortools chưa được cài")

    if os.environ.get("PYTEST_XDIST_WORKER"):
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

    if os.environ.get("PYTEST_XDIST_WORKER"):
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
