import random
from core.models import Teacher
from core.scheduler.teacher_off import _assign_off_slots


def test_assign_off_slots_returns_tuple_with_empty_shortfall_when_feasible():
    """A teacher with no unusual exclusions gets their 1 off-slot; shortfall empty."""
    teachers_by_id = {1: Teacher(teacher_id=1, name="GV A")}
    rng = random.Random(42)
    gv_off_slots, shortfall = _assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
    assert 1 in gv_off_slots
    assert len(gv_off_slots[1]) == 1
    assert shortfall == {}


def test_assign_off_slots_reports_shortfall_when_teacher_over_excluded():
    """A teacher who is TPT/BGH (forbidden ALL mornings, i.e. only 6 afternoon
    cells eligible: T3,T4,T7 chiều + any not already forbidden) requiring an
    off_slot_count larger than what remains must be reported as short, not
    silently truncated."""
    teachers_by_id = {
        1: Teacher(teacher_id=1, name="Hieu Truong", role="Hiệu trưởng"),
    }
    rng = random.Random(42)
    # TPT/BGH forbids ALL mornings (wd 2-7) plus the standard FORBIDDEN_OFF_CELLS
    # (which already includes T5 chiều, T6 chiều) -- eligible afternoon cells left:
    # T2, T3, T4, T7 chiều = 4 cells. Ask for more off-sessions than that.
    gv_off_slots, shortfall = _assign_off_slots({1}, teachers_by_id, rng, off_slot_count=5)
    assert 1 in shortfall
    assigned_count, required_count = shortfall[1]
    assert required_count == 5
    assert assigned_count < 5
    assert assigned_count == len(gv_off_slots[1])


def test_assign_off_slots_shortfall_is_deterministic_across_rng_seeds():
    """The SAME teacher must be reported short by the SAME (assigned, required)
    counts regardless of which rng seed is used -- shortfall depends only on
    fixed exclusions, never on randomness (only WHICH cells get picked varies)."""
    teachers_by_id = {1: Teacher(teacher_id=1, name="Hieu Truong", role="Hiệu trưởng")}
    seeds_shortfalls = []
    for seed in (1, 2, 3, 999):
        rng = random.Random(seed)
        _, shortfall = _assign_off_slots({1}, teachers_by_id, rng, off_slot_count=5)
        seeds_shortfalls.append(shortfall[1])  # (assigned_count, required_count) tuple
    assert len(set(seeds_shortfalls)) == 1
