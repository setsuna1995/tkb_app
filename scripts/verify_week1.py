import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')
from data import db, repository as repo

conn = db.get_connection('schools/thcs-do-can-phan-hieu.db')
rows = repo.get_teacher_quota_view(conn, week_no=1)

print(f"{'STT':<4} | {'Họ và tên':<26} | {'Chức danh':<14} | {'Giảm':<5} | {'ĐM (Cap)':<8} | {'Tuần 1':<7} | {'Thừa/Thiếu':<10}")
print("-" * 88)
for i, r in enumerate(rows, 1):
    diff = r['load'] - r['cap']
    diff_str = f"+{diff}" if diff > 0 else (f"{diff}" if diff < 0 else "0")
    print(f"{i:<4} | {r['name']:<26} | {r['role']:<14} | {r['reduction']:<5} | {r['cap']:<8} | {r['load']:<7} | {diff_str:<10}")

tot_load = sum(r['load'] for r in rows)
print("-" * 88)
print(f"Tổng số tiết Tuần 1 của 41 giáo viên: {tot_load}")
