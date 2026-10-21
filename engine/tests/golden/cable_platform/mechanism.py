"""
mechanism.py — golden mechanism 2: a platform on four cables, Plumb-shaped.

The anchor square is a scaled copy of the attachment square, so the six rows
of the structure matrix span only three dimensions (Pott 2018, ch. 3): all
three rotations are free at first order, and gravity alone sets the
orientation. Self-tests in mechanism_checks.py.
"""

import functools

import armature
from armature import body, cable, joint, site

from params import ANCHORS, ATTACH, COM, EA, HOME, LEDGER, PARAMS

# The mechanism's tolerance bands: its ledger section's.
BANDS = LEDGER.bands("mechanism")
MILESTONE = (0, "Milestone 0: the mechanism description")
TOOL = "centre"


def mechanism(p):
    """The platform hung at the room centre, level, on four cables; its free
    joint's point is the centre of the attachment square. Its inertia is one
    tensor about its COM, in base axes, as the ledger states it."""
    return [
        body("platform", mass=p["m"], com=HOME + COM, inertia=p["I_P"]),
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
