"""Test modular architecture of data.repositories package."""
import pytest


def test_modular_repositories_imports():
    from data.repositories import entities
    from data.repositories import curriculum
    from data.repositories import constraints
    from data.repositories import config
    from data.repositories import runs
    from data.repositories import builder

    assert hasattr(entities, "list_classes")
    assert hasattr(curriculum, "get_periods_per_week")
    assert hasattr(constraints, "get_teacher_busy_cells")
    assert hasattr(config, "get_scheduling_config")
    assert hasattr(runs, "save_run")
    assert hasattr(builder, "build_scheduling_input")


def test_repository_facade_backward_compatibility():
    from data import repository as repo

    assert hasattr(repo, "list_classes")
    assert hasattr(repo, "list_subjects")
    assert hasattr(repo, "list_teachers")
    assert hasattr(repo, "get_periods_per_week")
    assert hasattr(repo, "get_assignments")
    assert hasattr(repo, "get_teacher_busy_cells")
    assert hasattr(repo, "get_scheduling_config")
    assert hasattr(repo, "set_scheduling_config")
    assert hasattr(repo, "build_scheduling_input")
    assert hasattr(repo, "save_run")
