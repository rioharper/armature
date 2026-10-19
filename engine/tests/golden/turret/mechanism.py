"""
mechanism.py — golden mechanism 6: a geared turret.

A pan stage on a vertical bearing, its payload's COM off the axis, turned
through a gearbox by one motor. The axis is z and gravity −z, so the pan
carries no gravity torque. Self-tests in mechanism_checks.py.
"""

import functools

import numpy as np

import armature
from armature import actuator, body, gravity, joint, site

from params import BANDS as ALL_BANDS, PARAMS

# The mechanism's tolerance bands: those of PARAMS' parameters.
BANDS = {k: band for k, band in ALL_BANDS.items() if k in PARAMS}
MILESTONE = (0, "Milestone 0: the mechanism description")
TOOL = "muzzle"


def mechanism(p):
    """At home the payload points along +x (pan = 0): its COM d out and h up
    from the bearing, the muzzle `reach` out at the COM's height."""
    return [
        body("turret", mass=p["m"], com=(p["d"], 0, p["h"]),
             inertia=np.diag([p["Ixx"], p["Ixx"], p["Izz"]])),
        joint("pan", "hinge", parent="world", child="turret", axis=(0, 0, 1),
              point=(0, 0, 0), range=(-3.0, 3.0)),
        site(TOOL, body="turret", pos=(p["reach"], 0, p["h"])),
        actuator("pan_motor", joint="pan", gear=p["N"],
                 rotor_inertia=p["J_m"]),
        gravity((0, 0, -p["g"])),
    ]


@functools.cache
def truth():
    """The truth model: the description, compiled."""
    return armature.compile(mechanism, PARAMS)
