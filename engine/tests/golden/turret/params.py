"""
params.py — the geared turret's parameter block.

The turret's mass, its COM off the bearing's axis and its inertia about the
COM, the muzzle's reach, the pan motor's gear ratio and rotor inertia, and
the pan bearing's ratings. Every number is a `ledger.toml` entry's (ADR
0010), the ledger nearest this file's folder.
"""

from pathlib import Path

from armature.ledger import load

LEDGER = load(path=Path(__file__).resolve().parent)

# Exactly what mechanism(p) reads, in SI.
PARAMS = LEDGER.section("mechanism")

# --- the pan bearing, PB-1 ---
# Kept apart from PARAMS because the engine compiles PARAMS into the truth
# model and refuses a parameter it never reads. Its static ratings, from the
# bearing's datasheet, each with the safety factor already applied: `axial`
# along the axis [N], `moment` across it, about the bearing's centre [N m].
BEARING = LEDGER.section("part.PB-1")
