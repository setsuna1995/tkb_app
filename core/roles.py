"""Port of ResolveRoles (XepTKB.bas): resolve each subject's pedagogical role
from its role_code, looked up BY NAME/id rather than a hardcoded row number.
"""
from __future__ import annotations

from core.models import ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG, ROLE_NANG_KEP, RoleIndex


class MissingHDTNError(Exception):
    """Raised when no subject has role_code 5 (HDTN) -- mirrors the VBA hard-stop."""


def resolve_roles(subjects: list, extra_kep_ids: frozenset = frozenset()) -> RoleIndex:
    """extra_kep_ids: subject_id cần xếp "kép" (2 tiết liền kề cùng buổi) CHỈ cho lần chạy này,
    không phải thuộc tính cố định của môn (role_code) -- dùng khi 1 tuần cụ thể cần thêm môn
    khác ngoài các môn đã cố định KEP/NANG_KEP cũng xếp liền kề (vd Toán/KHTN tuần kiểm tra).
    """
    idx = RoleIndex()
    for s in subjects:
        if s.role_code == ROLE_NANG:
            idx.heavy_ids.add(s.subject_id)
        elif s.role_code == ROLE_KEP:
            idx.kep_ids.add(s.subject_id)
        elif s.role_code == ROLE_NANG_KEP:
            idx.heavy_ids.add(s.subject_id)
            idx.kep_ids.add(s.subject_id)
        elif s.role_code == ROLE_GDTC:
            idx.gdtc_id = s.subject_id
        elif s.role_code == ROLE_HDTN:
            idx.hdtn_id = s.subject_id
    idx.kep_ids |= set(extra_kep_ids)
    if idx.hdtn_id is None:
        raise MissingHDTNError(
            "Không tìm thấy môn có MÃ = 5 (HDTN). Hãy điền số 5 vào cột MÃ VAI TRÒ "
            "tại dòng 'Hoạt động trải nghiệm, hướng nghiệp'."
        )
    return idx
