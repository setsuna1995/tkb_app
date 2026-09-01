"""Test modular architecture of core.scheduler package."""
import pytest


def test_modular_subpackage_imports():
    # Direct submodule imports
    from core.scheduler import constants
    from core.scheduler import state
    from core.scheduler import placement
    from core.scheduler import feasibility
    from core.scheduler import heuristics
    from core.scheduler import teacher_off
    from core.scheduler import blocks
    from core.scheduler import swaps
    from core.scheduler import quality
    from core.scheduler import engine

    assert constants.MAX_GV_BUOI == 4
    assert hasattr(state, "_State")
    assert hasattr(placement, "_put_at")
    assert hasattr(feasibility, "_feasible")
    assert hasattr(heuristics, "_pick_best_scored")
    assert hasattr(teacher_off, "_assign_off_slots")
    assert hasattr(blocks, "_try_place_block_atomically")
    assert hasattr(swaps, "_try_swap_repair")
    assert hasattr(quality, "_teacher_quality_penalty")
    assert hasattr(engine, "run")


def test_facade_backward_compatibility():
    import core.scheduler as sched
    from core.scheduler import _State, _feasible, _put_at, _remove_at, run

    assert callable(sched.run)
    assert callable(run)
    assert sched._State is _State
    assert callable(_feasible)
    assert callable(_put_at)
    assert callable(_remove_at)
    assert sched.MAX_GV_BUOI == 4
    assert isinstance(sched.FORBIDDEN_OFF_CELLS, (set, frozenset))
