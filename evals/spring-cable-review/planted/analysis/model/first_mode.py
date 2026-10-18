"""
first_mode.py — DR-01: the bob's first mode, against R-4.

Mirrors docs/testing/DR-01-first-mode.md, *The decision* and *Method*.
DERIVED is the variant the task reads: the description with the cable rigid,
A3 in analysis/derivation/00_setup.md. Self-tests in first_mode_checks.py;
report_dr01.py prints the report's tables.
"""

import functools
import math

import armature
from armature import rigid

from mechanism import mechanism
from params import PARAMS

MILESTONE = (5, "DR-01: the bob's first mode")

R4_FLOOR = 10.0  # R-4: every mode of the rig at or above this [Hz]

A3 = rigid("hang", assumption="A3")
DERIVED = armature.reduce(mechanism, A3, name="inextensible cable")


@functools.cache
def derived():
    """The derived variant, compiled."""
    return armature.compile(DERIVED, PARAMS)


def modes():
    """The derived variant's modes at its rest (Hz), lowest first, by
    `linearise()` on the constraint manifold."""
    return sorted(float(f) for f in derived().at().linearise().frequencies)


def first_mode():
    """The lowest of `modes()` (Hz), or inf where the variant has none."""
    found = modes()
    return found[0] if found else math.inf


def sag():
    """A3's release (m): how far the bob settles once the cable may stretch,
    the full description against the derived variant, from its rest."""
    out = derived().at().release(quantity=lambda s: s.settle().q["z"])
    return out.sized[A3], out
