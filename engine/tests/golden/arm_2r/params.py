"""
params.py — the 2R arm's parameter block.

Each link's length, COM and inertia (a slender rod's, on every axis), the
gears and rotor inertias, and the motors' torque limit. Every number is a
`ledger.toml` entry's (ADR 0010), the ledger nearest this file's folder.
"""

from pathlib import Path

from armature.ledger import load

LEDGER = load(path=Path(__file__).resolve().parent)

# Exactly what mechanism(p) reads, in SI.
PARAMS = LEDGER.section("mechanism")
