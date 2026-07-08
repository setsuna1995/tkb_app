"""Port of ModSeed.bas: weekly reproducibility (new seed / replay / parity flip).

Note: Python's random.Random(seed) is not bit-compatible with VBA's Rnd/
Randomize PRNG. Seeds are reproducible WITHIN this Python tool (same seed +
same data -> same schedule, forever), but will not replay historical
VBA-generated timetables bit-for-bit. This is expected and documented for
the user in the UI.
"""
from __future__ import annotations

import random

MAX_SEED = 999_999
MAX_GEN_TRIES = 100_000


def generate_unused_seed(used_seeds: set, rng: random.Random) -> int:
    for _ in range(MAX_GEN_TRIES):
        candidate = rng.randint(1, MAX_SEED)
        if candidate not in used_seeds:
            return candidate
    raise RuntimeError("Không thể sinh seed mới chưa từng dùng sau nhiều lần thử.")


def flip_parity(current: str) -> str:
    return "L" if current == "C" else "C"


def next_week_no(existing_week_nos: list) -> int:
    return (max(existing_week_nos) + 1) if existing_week_nos else 1
