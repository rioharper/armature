"""
missions.py — what the turret is asked to do, as the engine's missions
(ADR 0006): a slew. The pan turns a quarter turn, rest to rest, under its
velocity, acceleration and jerk limits.
"""

import math

from armature.drive import Limits, Mission, move

LIMITS = Limits(v=2.0, a=8.0, j=200.0, along="coordinate")  # the pan's
HOME = {"pan": 0.0}            # the payload along +x [rad]
AIMED = {"pan": math.pi / 2}   # a quarter turn on, along +y [rad]

SLEW = Mission("slew", [move(HOME, end=AIMED, limits=LIMITS)])
MISSIONS = [SLEW]
