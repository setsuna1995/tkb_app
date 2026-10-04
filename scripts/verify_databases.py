import sqlite3
from core.scheduler import cpsat_model
from data.repositories.builder import build_scheduling_input
from core.scheduler.refinement import compute_candidate_metrics

for path in ['schools/truong-thcs.db', 'schools/truong-thcs-2-buoi.db']:
    print(f"=== Testing {path} ===")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    inp = build_scheduling_input(conn, parity="C", seed=0)
    print(f"Slots: {len(inp.slots)}, Need: {sum(inp.need.values())}")
    built = cpsat_model.build_model(inp)
    res = cpsat_model.solve_to_result(built, time_limit_s=15.0)
    if res and res.success:
        print(f"SUCCESS! Relaxed: {res.relaxed_rules}")
        metrics = compute_candidate_metrics(inp, res)
        print("Metrics:", {k: v for k, v in metrics.items() if k != "afternoon_off_status"})
        print("Afternoon off status:", metrics.get("afternoon_off_status"))
        
        # Check GV Hà
        ha = next((t for t in inp.teachers if "Hà" in t.name), None)
        if ha:
            slots_ha = []
            slot_by_id = {s.slot_id: s for s in inp.slots}
            for sid, sub_id in res.assignment.items():
                s = slot_by_id[sid]
                tid = inp.assigned_teacher.get((sub_id, s.class_id))
                if tid == ha.teacher_id:
                    cname = next(c.name for c in inp.classes if c.class_id == s.class_id)
                    slots_ha.append((s.ts.weekday, s.ts.session, s.ts.period, cname))
            print("GV Hà slots:", sorted(slots_ha))
    else:
        print("FAILED:", res.failure_reason if res else "None")
    conn.close()
    print()
