"""
mechanism.py — golden mechanism 5: a mass on a cable.

A bob on a vertical slide, hung on an elastic cable under the engine's
default gravity, −z. The cable's stiffness lives only in MuJoCo's passive
force. Self-tests in mechanism_checks.py.
"""

import functools

import numpy as np

import armature
from armature import body, cable, joint

from params import LEDGER, PARAMS

# The mechanism's tolerance bands: its ledger section's.
BANDS = LEDGER.bands("mechanism")
MILESTONE = (0, "Milestone 0: the mechanism description")


def bob(p):
    """The bob: a 10 mm sphere's inertia, so the body is a rigid body."""
    r = 0.01
    i = 0.4 * p["m"] * r ** 2
    return body("bob", mass=p["m"], com=(0, 0, 0), inertia=np.diag([i, i, i]))


def slide(**spring):
    """The bob's vertical slide; `spring` is its joint stiffness, if any."""
    return joint("z", "slide", parent="world", child="bob", axis=(0, 0, 1),
                 point=(0, 0, 0), range=(-0.1, 0.1), **spring)


def mechanism(p):
    """The bob, anchored `drop` above on a cable whose EA / rest is k."""
    return [bob(p), slide(),
            cable("hang", start=("world", (0, 0, p["drop"])),
                  end=("bob", (0, 0, 0)), ea=p["k"] * p["rest"],
                  rest_length=p["rest"])]


@functools.cache
def truth():
    """The truth model: the description, compiled."""
    return armature.compile(mechanism, PARAMS)
