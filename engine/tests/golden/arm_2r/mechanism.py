"""
mechanism.py — golden mechanism 1: the 2R arm.

A planar 2R arm in the xy plane, gravity along -y, both links along +x at
home, each joint geared with its rotor. Self-tests in mechanism_checks.py.
"""

import functools
import math

import numpy as np

import armature
from armature import actuator, body, gravity, joint, site

from params import LEDGER, PARAMS

# The mechanism's tolerance bands: its ledger section's.
BANDS = LEDGER.bands("mechanism")
MILESTONE = (0, "Milestone 0: the mechanism description")
TOOL = "tip"


def mechanism(p):
    """The 2R arm. Each link's inertia is a slender rod's, on every axis."""
    return [
        body("upper", mass=p["m1"], com=(p["lc1"], 0, 0),
             inertia=np.diag([p["Ix1"], p["I1"], p["I1"]])),
        body("fore", mass=p["m2"], com=(p["l1"] + p["lc2"], 0, 0),
             inertia=np.diag([p["Ix2"], p["I2"], p["I2"]])),
        joint("shoulder", "hinge", parent="world", child="upper",
              axis=(0, 0, 1), point=(0, 0, 0), range=(-math.pi, math.pi)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 0, 1),
              point=(p["l1"], 0, 0), range=(-2.6, 2.6)),
        site(TOOL, body="fore", pos=(p["l1"] + p["l2"], 0, 0)),
        actuator("shoulder_motor", joint="shoulder", gear=p["N1"],
                 rotor_inertia=p["J1"], torque_limit=p["limit"]),
        actuator("elbow_motor", joint="elbow", gear=p["N2"],
                 rotor_inertia=p["J2"], torque_limit=p["limit"]),
        gravity((0, -p["g"], 0)),
    ]


@functools.cache
def truth():
    """The truth model: the description, compiled."""
    return armature.compile(mechanism, PARAMS)
