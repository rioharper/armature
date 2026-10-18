"""
deck.py — DR-01: the deck's tilt at the edge midpoint, against R-2.

Mirrors docs/testing/DR-01-deck-tilt.md, *The decision* and *Method*.
DERIVED is the variant the task reads: the description with the platform's
three turns locked level, A3 in analysis/derivation/00_setup.md. Self-tests
in deck_checks.py; report_dr01.py prints the report's tables.
"""

import functools
import math

import numpy as np

import armature
from armature import lock

from mechanism import mechanism
from params import ANCHORS, ATTACH, EA, G, HOME, PARAMS, POSE

MILESTONE = (5, "DR-01: the deck's tilt at the edge midpoint")

R2_LIMIT = 2.0  # R-2: the deck within this of level, the gimbal's range [deg]
SLIDES = ("hang:x", "hang:y", "hang:z")

A3 = tuple(lock(f"hang:{turn}", 0.0, assumption="A3")
           for turn in ("rx", "ry", "rz"))
DERIVED = armature.reduce(mechanism, *A3, name="level platform")


@functools.cache
def derived():
    """The derived variant on params.py's rest lengths, compiled."""
    return armature.compile(DERIVED, PARAMS)


def placed(point):
    """The variant's coordinates with the platform's point at `point`."""
    return dict(zip(SLIDES, (float(c) for c in point)))


def centre_law(m=PARAMS["m"]):
    """00_setup.md (1) and (2): the level-platform law at the room centre.
    By the rig's symmetry it pays out four equal tensions, each carrying a
    quarter of the weight along its cable, T = m g L / 4h, on rest lengths
    L / (1 + T / EA). Returns the parameters and the tensions (N)."""
    span = ANCHORS - (HOME + ATTACH)
    length = np.linalg.norm(span, axis=1)
    tension = m * G * length / (4 * span[:, 2])
    rest = length / (1 + tension / EA)
    return ({"m": m, **{f"l0_{i + 1}": float(rest[i]) for i in range(4)}},
            tension)


def tilt(rotation):
    """The deck's tilt from level (deg): its axis against the vertical."""
    return math.degrees(math.acos(min(1.0, float(rotation[2, 2]))))


def at_the_edge():
    """The variant settled from POSE: where the level platform rests on
    params.py's rest lengths, and what each cable carries there."""
    return derived().at(q=placed(POSE)).settle()


def deck_tilt():
    """R-2's quantity at the edge midpoint, on the variant (deg): the deck's
    tilt where the variant rests."""
    rest = derived().at(q=at_the_edge().q)
    return tilt(rest.pose("centre").rotation)


@functools.cache
def release_at_the_centre():
    """A3 released at the room centre: the full description against the
    variant, hung there on the law's own rest lengths. Returns the largest
    turn the release finds (deg) and the release."""
    params, _ = centre_law()
    out = armature.compile(DERIVED, params).at(q=placed(HOME)).release()
    return math.degrees(max(abs(v) for v in out.moved.values())), out
