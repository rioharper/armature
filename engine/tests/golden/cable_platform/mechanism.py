"""
mechanism.py — golden mechanism 2: a platform on four cables, Plumb-shaped.

The anchor square is a scaled copy of the attachment square, so the six rows
of the structure matrix span only three dimensions (Pott 2018, ch. 3): all
three rotations are free at first order, and gravity alone sets the
orientation. Self-tests in mechanism_checks.py.
"""

import functools

import numpy as np

import armature
from armature import body, cable, joint, site

from params import (ANCHORS, ATTACH, BANDS as ALL_BANDS, COM, EA, HOME, I_P,
                    PARAMS)

# The mechanism's tolerance bands: those of PARAMS' parameters.
BANDS = {k: band for k, band in ALL_BANDS.items() if k in PARAMS}
MILESTONE = (0, "Milestone 0: the mechanism description")
TOOL = "centre"


def mechanism(p):
    """The platform hung at the room centre, level, on four cables; its free
    joint's point is the centre of the attachment square."""
    return [
        body("platform", mass=p["m"], com=HOME + COM,
             inertia=np.diag([I_P] * 3)),
        joint("hang", "free", parent="world", child="platform", point=HOME),
        site(TOOL, body="platform", pos=HOME),
        *(cable(f"c{i + 1}", start=("world", ANCHORS[i]),
                end=("platform", HOME + ATTACH[i]), ea=EA,
                rest_length=p[f"l0_{i + 1}"]) for i in range(4)),
    ]


@functools.cache
def truth():
    """The truth model: the description, compiled."""
    return armature.compile(mechanism, PARAMS)
