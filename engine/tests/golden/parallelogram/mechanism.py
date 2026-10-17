"""
mechanism.py — golden mechanism 4: a balanced parallelogram arm,
CineWave-shaped.

The upper arm turns about O on J1. The forearm hangs from its far end P, and
its direction is set by a crank on J2, also at O, through a coupler that stays
parallel to the upper arm: O, P, Q and C are a parallelogram, and the forearm
turns with the crank. Every hinge is about z, and gravity is −y. Self-tests
in mechanism_checks.py.
"""

import functools

import numpy as np

import armature
from armature import actuator, body, gravity, joint, loop, site

from params import BANDS as ALL_BANDS, PARAMS

# The mechanism's tolerance bands: those of PARAMS' parameters.
BANDS = {k: band for k, band in ALL_BANDS.items() if k in PARAMS}
MILESTONE = (0, "Milestone 0: the mechanism description")
TOOL = "tip"


def mechanism(p):
    """At home the upper arm lies along +x (θ1 = 0) and the crank along +y
    (φ = π/2), so O = (0, 0), P = (a, 0), C = (0, c) and Q = (a, c). The
    forearm hangs from P, its tip at (a, −b), and its lever runs up to Q."""
    i = np.diag([p["I"]] * 3)
    span = (-2.6, 2.6)
    return [
        body("upper", mass=p["m1"], com=(p["r1"], 0, 0), inertia=i),
        body("fore", mass=p["m2"], com=(p["a"], p["r2"], 0), inertia=i),
        body("crank", mass=p["m3"], com=(0, p["r3"], 0), inertia=i),
        body("coupler", mass=p["m4"], com=(p["r4"], p["c"], 0), inertia=i),
        joint("J1", "hinge", parent="world", child="upper", axis=(0, 0, 1),
              point=(0, 0, 0), range=(-1.2, 1.2)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 0, 1),
              point=(p["a"], 0, 0), range=span),
        joint("J2", "hinge", parent="world", child="crank", axis=(0, 0, 1),
              point=(0, 0, 0), range=span),
        joint("pin", "hinge", parent="crank", child="coupler",
              axis=(0, 0, 1), point=(0, p["c"], 0), range=span),
        site("Q_fore", body="fore", pos=(p["a"], p["c"], 0)),
        site("Q_coupler", body="coupler", pos=(p["a"], p["c"], 0)),
        site(TOOL, body="fore", pos=(p["a"], -p["b"], 0)),
        loop("parallelogram", "Q_coupler", "Q_fore"),
        actuator("J1_motor", joint="J1", gear=p["N1"],
                 rotor_inertia=p["J_m"]),
        actuator("J2_motor", joint="J2", gear=p["N2"],
                 rotor_inertia=p["J_m"]),
        gravity((0, -p["g"], 0)),
    ]


@functools.cache
def truth():
    """The truth model: the description, compiled."""
    return armature.compile(mechanism, PARAMS)
