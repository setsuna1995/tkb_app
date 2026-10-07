"""Execution, diagnosis, and result extraction for CP-SAT model."""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional, Sequence

from core.models import ScheduleResult, ROLE_HDTN
from core.rules import HARD_POST_GENERATION_IDS
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

    cells_changed = sum(
        1 for slot in inp.slots
        if assignment.get(slot.slot_id) != slot.old_subject_id
    )
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

    rule_counts = {
        rule_id: int(sum(solver.Value(term) for term in terms))
        for rule_id, terms in built.penalty_terms.items() if terms and not rule_id.startswith("_")
    }

    successes_found = 1 if not relaxed_rules else 0

    diag = dict(diagnostics or {})
    status_int = diag.get("status")
    if status_int is None and hasattr(solver, "response_proto"):
        status_int = getattr(solver.response_proto, "status", None)
    final_status = _STATUS_NAMES.get(status_int, "FEASIBLE" if status_int is None else str(status_int))

    diag.update(
        final_status=final_status,
        objective=float(solver.ObjectiveValue()),
        best_bound=float(solver.BestObjectiveBound()),
        wall_time_s=float(solver.WallTime()),
    )

    return ScheduleResult(
        success=True,
        assignment=assignment,
        cells_changed=cells_changed,
        cells_total=cells_total,
        attempts_tried=1,
        successes_found=successes_found,
        relaxed_rules=relaxed_rules,
        solver_name="cpsat",
        diagnostics=diag,
        effective_params=built.params,
        rule_counts=rule_counts,
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
        base_obj = recent_candidates[-1] if recent_candidates else self.history[0][1]

        improvement_abs = base_obj - self.best_obj
        improvement_rate = (improvement_abs / base_obj) if base_obj > 0 else 0.0

        return improvement_abs < self.min_improvement_abs or improvement_rate < self.min_improvement_rate

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


def _morning_capacity_rows(built: CpSatModel) -> list[dict]:
    """Phân tích giải tích dung lượng các buổi sáng bắt buộc theo từng thứ."""
    config = built.inp.config
    params = built.params
    mand_morns = params.mandatory_morning_weekdays
    strict_morns = params.strict_morning_weekdays
    min_mand_load = params.min_weekly_periods_for_mandatory_morning
    bgh_ids = params.bgh_ids
    load = params.teacher_load  # same effective teacher map the objective uses (spec A5)

    rows = []
    all_mand = set(mand_morns) | set(strict_morns)
    for wd in sorted(all_mand):
        morn_slots = [s for s in built.inp.slots if s.ts.weekday == wd and s.ts.session == "S"]
        cap = len(morn_slots)
        mand_teacher_ids = set()
        must_mon_ids = getattr(params, "must_monday_ids", frozenset())
        for t in built.inp.teachers:
            if load.get(t.teacher_id, 0) <= 0:
                continue
            if t.teacher_id in bgh_ids:
                continue
            if t.pinned_full_day_off == wd:
                continue
            if wd == 2 and must_mon_ids and t.teacher_id not in must_mon_ids and load.get(t.teacher_id, 0) < min_mand_load:
                continue
            if _is_teacher_busy_morning(built.inp, t.teacher_id, wd):
                continue
            is_strict = (wd in strict_morns)
            is_mand = (wd in mand_morns and wd not in strict_morns and load.get(t.teacher_id, 0) >= min_mand_load)
            if is_strict or is_mand:
                mand_teacher_ids.add(t.teacher_id)

        cc_wd = getattr(config, "hdtn_p1_weekday", None) or getattr(config, "chao_co_weekday", 2)
        if wd == cc_wd and not built.inp.hdtn_thematic_week:
            hdtn_id = getattr(built.inp, "hdtn_id", None) or next((s.subject_id for s in built.inp.subjects if s.role_code == ROLE_HDTN), None)
            cc_period = getattr(config, "hdtn_p1_period", None) or getattr(config, "chao_co_period", 1)
            cc_session = getattr(config, "hdtn_p1_session", "S")
            cc_slots = [s for s in morn_slots if s.ts.period == cc_period and s.ts.session == cc_session]
            # Tiết chào cờ chỉ bị trừ khỏi dung lượng khả dụng nếu không được phân cho GV bắt buộc có mặt
            cc_taken_by_others = 0
            for s in cc_slots:
                assigned_t = built.inp.assigned_teacher.get((hdtn_id, s.class_id))
                if not assigned_t or assigned_t not in mand_teacher_ids:
                    cc_taken_by_others += 1
            cap -= cc_taken_by_others

        allow_lone_mand = getattr(config, "allow_lone_period_on_mandatory_mornings", True)
        min_per_t = 1 if allow_lone_mand else 2
        min_needed = len(mand_teacher_ids) * min_per_t
        rows.append({"weekday": wd, "teachers": len(mand_teacher_ids), "need": min_needed, "cap": cap})

    return rows


def _presolve_capacity_screening(built: CpSatModel) -> set[str]:
    """Phân tích giải tích tiền giải (0.001s) để phát hiện mâu thuẫn dung lượng toán học (Pigeonhole)."""
    if any(r["cap"] > 0 and r["need"] > r["cap"] for r in _morning_capacity_rows(built)):
        return {"II.3"}
    return set()


def _select_fallback_relaxations(hard_rids: Sequence[str], strategy: str = "default") -> set[str]:
    """Lựa chọn quy tắc nới lỏng dự phòng theo chiến lược cấu hình:
    - 'anti_lone': Ưu tiên cao nhất cho II.4 (không buổi lẻ), nới lỏng II.3 -> II.8 trước.
    - 'presence':  Ưu tiên cao nhất cho II.3 (sáng có mặt), nới lỏng II.4 -> II.8 trước.
    - 'pareto'/'default': Cân bằng đa mục tiêu, nới lỏng II.8 -> II.4 -> II.3.
    """
    if strategy == "anti_lone":
        order = ("II.3", "II.8", "II.4")
    elif strategy == "presence":
        order = ("II.4", "II.8", "II.3")
    else:
        order = ("II.8", "II.4", "II.3")

    for candidate in order:
        if candidate in hard_rids:
            return {candidate}
    return set(hard_rids)


def _create_solver(built: CpSatModel, workers: Optional[int] = None) -> cp_model.CpSolver:
    """Khởi tạo và cấu hình solver CP-SAT với số worker và tham số chuẩn."""
    if workers is not None and int(workers) > 0:
        eff_workers = max(1, int(workers))
    elif os.environ.get("PYTEST_XDIST_WORKER"):
        eff_workers = 2
    else:
        user_workers = getattr(built.inp.config, "cpsat_workers", 0)
        eff_workers = detect_optimal_workers(override=user_workers)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = int(eff_workers)
    solver.parameters.linearization_level = 1
    solver.parameters.cp_model_probing_level = 1
    if getattr(built.inp, "seed", None):
        solver.parameters.random_seed = int(built.inp.seed)
    return solver


def _diagnose_and_solve(built: CpSatModel, solver: cp_model.CpSolver, time_limit_s: float,
                        progress_cb: Optional[Callable[[dict], None]] = None,
                        strategy: str = "default",
                        deep: bool = False) -> dict:
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
        "deep": deep,
        "morning_capacity": [],
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
            diag["morning_capacity"] = _morning_capacity_rows(built)
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

        # Phân bổ thời gian giữa các pass:
        # Pass 1 là pass quan trọng nhất và nhiều điều kiện nhất (chặn cứng toàn bộ tiêu chí SP).
        # Cần ưu tiên tối đa thời gian cho Pass 1 để tìm nghiệm chuẩn, tránh bị timeout oan.
        # Các pass nới lỏng sau này rất lỏng lẻo nên giải rất nhanh (chỉ cần 1-3s), chỉ cần vài giây dự phòng.
        if len(hard_rids) > 1 and remaining > 8.0:
            pass_limit = max(1.0, float(remaining - 4.0))
        else:
            pass_limit = max(1.0, float(remaining))

        solver.parameters.max_time_in_seconds = float(pass_limit)
        solver.parameters.relative_gap_limit = 0.0 if deep else 0.03
        # deep: chỉ dừng khi hết giờ hoặc chứng minh tối ưu -- người dùng đã chủ động trả thêm thời gian
        stop_kw = ({"stagnation_s": float(pass_limit), "min_improvement_abs": 0.0, "min_improvement_rate": 0.0}
                   if deep else {"stagnation_s": stagnation})
        cb = EarlyStoppingCallback(
            progress_cb=progress_cb, pass_no=diag["passes_run"], max_passes=max_passes, **stop_kw
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

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) or not hard_rids:
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
                offending = _select_fallback_relaxations(hard_rids, strategy=strategy)
            elif len(offending) > 1:
                offending = _select_fallback_relaxations(list(offending), strategy=strategy)

            relaxed |= offending
            diag["relaxed_by_diagnosis"] = sorted(relaxed)
            continue

        # Nếu UNKNOWN (timeout): Nới lỏng quy tắc dự phòng theo thứ tự ưu tiên
        if status == cp_model.UNKNOWN:
            relaxed |= _select_fallback_relaxations(hard_rids, strategy=strategy)
            diag["relaxed_by_diagnosis"] = sorted(relaxed)
            continue


def solve_to_result(built: CpSatModel, time_limit_s: float = 30.0,
                    workers: Optional[int] = None,
                    progress_cb: Optional[Callable[[dict], None]] = None,
                    strategy: str = "default",
                    *, deep: bool = False) -> Optional[ScheduleResult]:
    """Giải mô hình và trả về ScheduleResult hoàn chỉnh, hoặc None nếu không giải được."""
    if not _HAS_ORTOOLS or cp_model is None:
        raise CpSatUnavailable("ortools chưa được cài")

    solver = _create_solver(built, workers=workers)
    diag = _diagnose_and_solve(built, solver, float(time_limit_s), progress_cb=progress_cb, strategy=strategy, deep=deep)
    if diag["status"] not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    return build_result(built, solver, diagnostics=diag)


def solve_three_strategies(built: CpSatModel, time_limit_s: float = 30.0,
                           workers: Optional[int] = None,
                           progress_cb: Optional[Callable[[dict], None]] = None) -> dict[str, Optional[ScheduleResult]]:
    """Giải đồng thời 3 chiến lược nới lỏng để người dùng chọn:
    - 'anti_lone': Ưu tiên triệt tiêu buổi lẻ (phạt nặng II.4, sẵn sàng nới lỏng II.3/II.8 nếu kẹt)
    - 'presence':  Ưu tiên kỷ luật hiện diện (giữ vững II.3 sáng Thứ 2 bắt buộc, nới lỏng II.4 nếu kẹt)
    - 'pareto':    Cân bằng đa mục tiêu Pareto (hài hòa giữa số buổi lẻ và phân bố các ngày)
    """
    strategies = [
        ("anti_lone", "PA1: Triệt tiêu buổi lẻ"),
        ("presence", "PA2: Kỷ luật hiện diện"),
        ("pareto", "PA3: Cân bằng tối ưu"),
    ]
    results = {}
    per_strat_tl = max(10.0, min(float(time_limit_s) * 0.7, 30.0))
    for strat_key, strat_label in strategies:
        if progress_cb:
            progress_cb({
                "event": "strategy_start",
                "strategy": strat_key,
                "strategy_label": strat_label,
            })
        res = solve_to_result(built, time_limit_s=per_strat_tl, workers=workers,
                              progress_cb=progress_cb, strategy=strat_key)
        results[strat_key] = res
    return results


def solve(built: CpSatModel, time_limit_s: float = 10.0,
          workers: Optional[int] = None) -> Optional[dict]:
    """Trả {slot_id: subject_id} cho các ô CÓ môn, hoặc None nếu không giải được."""
    if not _HAS_ORTOOLS or cp_model is None:
        raise CpSatUnavailable("ortools chưa được cài")

    solver = _create_solver(built, workers=workers)
    diag = _diagnose_and_solve(built, solver, float(time_limit_s))
    if diag["status"] not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    return {
        slot_id: subject_id
        for (slot_id, subject_id), var in built.x.items()
        if solver.Value(var)
    }
