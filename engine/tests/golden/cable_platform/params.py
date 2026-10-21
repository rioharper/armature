"""
params.py — the cable platform's parameter block: Plumb Rev 1.0's rig.

The anchor square (4 m, at 2.4 m) is a scaled copy of the attachment square
(0.15 m). The platform is described hung at HOME, the room centre; PARAMS'
rest lengths are those the level-platform tension law of Plumb's Milestone 1
Rev 1.0 (01_kinematics.md §3) gives at POSE, the edge midpoint, carrying m.
Every number is a `ledger.toml` entry's (ADR 0010), the ledger nearest this
file's folder.
"""

from pathlib import Path

import numpy as np

from armature.ledger import load

LEDGER = load(path=Path(__file__).resolve().parent)
RIG = LEDGER.section("part.rig")
PLATFORM = LEDGER.section("part.platform")

G = RIG["g"]                         # the engine's default gravity [m/s^2]
EA = LEDGER.section("part.cable")["ea"]  # each cable's axial stiffness [N]
# One row per cable, c1 first, in the ledger's order [m].
ANCHORS = np.array([v for k, v in RIG.items() if k.startswith("anchor-")])
ATTACH = np.array([v for k, v in PLATFORM.items()
                   if k.startswith("attach-")])  # about the point
COM = PLATFORM["com"]                # below the point [m]
HOME = RIG["home"]                   # the room centre [m]
POSE = RIG["pose"]                   # the edge midpoint [m]

# Exactly what mechanism(p) reads, in SI: the platform's mass, each cable's
# rest length at POSE, and its inertia, one tensor about its COM.
PARAMS = LEDGER.section("mechanism")
