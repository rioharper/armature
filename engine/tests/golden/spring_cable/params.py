"""
params.py — the mass on a cable's parameter block.

The cable is anchored `drop` above the bob, its EA chosen so that EA / rest
is k: an elastic cable, a spring that only pulls. Every number is a
`ledger.toml` entry's (ADR 0010), the ledger nearest this file's folder.
"""

from pathlib import Path

from armature.ledger import load

LEDGER = load(path=Path(__file__).resolve().parent)

# Exactly what mechanism(p) reads, in SI: the bob, the cable's stiffness,
# the anchor's drop and the cable's rest length.
PARAMS = LEDGER.section("mechanism")
