"""Tính trạng thái hoàn thành từng bước thiết lập dữ liệu trước khi xếp TKB.

Mỗi hàm check_* nhận dữ liệu đã tổng hợp sẵn (không tự truy vấn DB) để giữ
core/ độc lập với Streamlit và data/repository.py, theo đúng cấu trúc hiện có
của thư mục này.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StepStatus:
    ok: bool
    detail: str


def check_khai_bao(num_classes: int, num_subjects: int, num_teachers: int) -> StepStatus:
    missing = []
    if num_classes == 0:
        missing.append("lớp")
    if num_subjects == 0:
        missing.append("môn")
    if num_teachers == 0:
        missing.append("giáo viên")
    if missing:
        return StepStatus(False, "Chưa có " + ", ".join(missing) + ".")
    return StepStatus(True, f"{num_classes} lớp, {num_subjects} môn, {num_teachers} giáo viên.")


def check_phan_cong(periods_per_week: dict, assignments: dict) -> StepStatus:
    """periods_per_week: (subject_id, class_id, parity) -> tiết/tuần.
    assignments: (subject_id, class_id) -> teacher_id (thiếu key hoặc None = chưa phân công).
    Một cặp (môn, lớp) cần GV nếu có tiết/tuần > 0 ở BẤT KỲ tuần Chẵn hoặc Lẻ nào.
    """
    needed_pairs = {(subject_id, class_id) for (subject_id, class_id, _parity), value in periods_per_week.items()
                     if value > 0}
    missing = [pair for pair in needed_pairs if not assignments.get(pair)]
    if missing:
        return StepStatus(False, f"{len(missing)} cặp môn-lớp có tiết nhưng chưa có GV.")
    return StepStatus(True, f"Đã phân công đủ {len(needed_pairs)} cặp môn-lớp.")


def check_dinh_muc(quota_view: list) -> StepStatus:
    """quota_view: kết quả data.repository.get_teacher_quota_view -- mỗi dict đã có
    'over'/'under' tính theo TRUNG BÌNH tải 2 tuần Chẵn/Lẻ (xem repository.py)."""
    over = [q for q in quota_view if q["cap"] > 0 and q["over"] > 0]
    under = [q for q in quota_view if q["under"] > 0]
    if over or under:
        parts = []
        if over:
            parts.append(f"{len(over)} GV vượt trần")
        if under:
            parts.append(f"{len(under)} GV dưới sàn")
        return StepStatus(False, ", ".join(parts) + ".")
    return StepStatus(True, "Không GV nào vượt trần / dưới sàn.")


def check_khung_tiet(class_totals: dict, class_quota_by_parity: dict) -> StepStatus:
    """class_totals: class_id -> tổng ô/tuần theo khung đã chọn (core.frame.total_cells_per_class).
    class_quota_by_parity: class_id -> {"C": tổng tiết tuần Chẵn, "L": tổng tiết tuần Lẻ}.
    Khung dùng chung cho cả 2 tuần nên phải đủ chỗ cho tuần NẶNG HƠN (max Chẵn/Lẻ)."""
    short = [
        class_id for class_id, quotas in class_quota_by_parity.items()
        if max(quotas.get("C", 0), quotas.get("L", 0)) > class_totals.get(class_id, 0)
    ]
    if short:
        return StepStatus(False, f"{len(short)} lớp thiếu chỗ trong khung tiết so với định mức.")
    return StepStatus(True, "Mọi lớp đã đủ chỗ trong khung tiết.")


def check_gv_ban(num_teachers: int, num_teachers_with_busy: int) -> StepStatus:
    """Không chặn -- 0 tiết bận là trạng thái hợp lệ (GV rảnh cả tuần), chỉ để tham khảo."""
    return StepStatus(True, f"{num_teachers_with_busy}/{num_teachers} GV đã khai báo tiết bận.")
