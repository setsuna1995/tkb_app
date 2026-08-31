from core import scheduler as sched
from core.models import (ClassRoom, SchedulingConfig,
                         SchedulingInput, Slot, Subject, Teacher, TimeSlot)

def test_non_consecutive_day_constraint():
    slots = []
    ts1 = TimeSlot(1, 2, "S", 1)  # Mon
    ts2 = TimeSlot(2, 3, "S", 1)  # Tue
    ts3 = TimeSlot(3, 4, "S", 1)  # Wed
    
    slots.extend([Slot(1, 101, ts1), Slot(2, 101, ts2), Slot(3, 101, ts3)])
    
    subjects = [
        Subject(10, "Math", 1, 1),
        Subject(20, "GDTC", 1, 1),
        Subject(30, "HDTN", 5, 1)
    ]
    
    teachers = [Teacher(1, "T1"), Teacher(2, "T2")]
    
    assigned_teacher = {(10, 101): 1, (20, 101): 2}
    
    # Block Wed for GDTC teacher -> GDTC MUST be Mon and Tue
    # Wait, in the test I can just set ban_busy={(2, 3)} where 2 is T2 and 3 is ts3.ts_id
    ban_busy = {(2, 3)} 
    
    config_no = SchedulingConfig(
        max_heavy_consecutive=2,
        teacher_off_sessions_per_week=0,
        max_periods_per_session=5,
        non_consecutive_subject_ids=frozenset()
    )
    
    inp_no = SchedulingInput(
        classes=[ClassRoom(101, "6A5")],
        slots=slots, subjects=subjects, teachers=teachers, assigned_teacher=assigned_teacher,
        ban_busy=ban_busy,
        need={(10, 101): 1, (20, 101): 2},
        timeslots=[ts1, ts2, ts3],
        config=config_no, seed=1
    )
    
    res1 = sched.run(inp_no)
    assert res1.success
    
    config_yes = SchedulingConfig(
        max_heavy_consecutive=2,
        teacher_off_sessions_per_week=0,
        max_periods_per_session=5,
        non_consecutive_subject_ids=frozenset({20})
    )
    
    inp_yes = SchedulingInput(
        classes=[ClassRoom(101, "6A5")],
        slots=slots, subjects=subjects, teachers=teachers, assigned_teacher=assigned_teacher,
        ban_busy=ban_busy,
        need={(10, 101): 1, (20, 101): 2},
        timeslots=[ts1, ts2, ts3],
        config=config_yes, seed=1
    )
    
    res2 = sched.run(inp_yes)
    assert not res2.success
