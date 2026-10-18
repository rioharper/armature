"""
skid.py — DR-01: the skid pad's clearance above the floor, against R-5.

Mirrors docs/testing/DR-01-skid-clearance.md, *The decision* and *Method*.
SKIDDED is the description with the knee's skid pad added: a sphere of
radius R_SKID round B on l1, against the floor. SKID_AT_ALPHA_ZERO is the
clearance margin over the postures A3 names, the leg straight under the
hips, which run_all.py searches. Self-tests in skid_checks.py;
report_dr01.py prints the report's tables.
"""

import functools
import math

import numpy as np
from scipy.optimize import newton

import armature
from armature import Choice, Margin, Space, contact, shape

from mechanism import mechanism
from params import PARAMS, POINTS, R_SKID, WORKSPACE

MILESTONE = (5, "DR-01: the skid pad's clearance")

STRAIGHT_STEPS = 40  # hip-A steps each way from home along α = 0
SKID_PARAMS = PARAMS | {"r_skid": R_SKID}
HIPS_X = (POINTS["A"][0] + POINTS["E"][0]) / 2  # the hips' midpoint [m]


def skidded(p):
    """The description with the knee's skid pad: a sphere round B, fixed to
    l1, against the floor the tyre stands on."""
    floor = (0, p["Cy"] - p["r"], 0)
    return mechanism(p) + [
        contact("skid", body="l1",
                shape=shape("sphere", pos=(p["Bx"], p["By"], 0),
                            radius=p["r_skid"]),
                against=shape("plane", pos=floor, axis=(0, 1, 0)),
                mu=p["mu"])]


@functools.cache
def model():
    """The skidded description, compiled."""
    return armature.compile(skidded, SKID_PARAMS)


def standing(ya, ye):
    """The leg at hips (ya, ye) with the tyre on the floor: the torso's
    height lowered by the tyre's gap, the whole leg riding on it."""
    hips = {"A": float(ya), "E": float(ye)}
    gap = armature.clearance(model().at(q=hips), "tyre")
    return model().at(q=hips | {"y": -gap})


def alpha(ya, ye):
    """The leg's angle α (rad): the pin C seen from the hips' midpoint, from
    straight down."""
    c = model().at(q={"A": float(ya), "E": float(ye)}).pose("C2").position
    return math.atan2(c[0] - HIPS_X, POINTS["A"][1] - c[1])


@functools.cache
def straight():
    """A3's postures: hip pairs inside WORKSPACE with α = 0, from the
    shortest leg to the longest. For each A, the E that puts the pin under
    the hips' midpoint, walked out from home so each root seeds the next."""
    (a0, a1), (e0, e1) = WORKSPACE["A"], WORKSPACE["E"]
    found = [(0.0, 0.0)]
    for end in (a0, a1):
        ye = 0.0
        for ya in np.linspace(0.0, end, STRAIGHT_STEPS + 1)[1:]:
            ye = float(newton(lambda e, a=ya: model().at(
                q={"A": a, "E": e}).pose("C2").position[0] - HIPS_X, ye))
            if e0 <= ye <= e1:
                found.append((float(ya), ye))
    return tuple(found)


def skid_mm(ya, ye):
    """The skid pad's clearance above the floor (mm), the tyre on it: a
    margin against first contact, which touching fails."""
    return armature.clearance(standing(ya, ye), "skid") * 1e3


def closed_form_mm(ya, ye):
    """The same clearance from the truth model's geometry (mm): the knee B,
    turned with l1 about A, above the pin C, plus the wheel's radius, less
    the pad's. 00_setup.md (1)."""
    ax, ay = POINTS["A"]
    bx, by = POINTS["B"][0] - ax, POINTS["B"][1] - ay
    knee = ay + math.sin(ya) * bx + math.cos(ya) * by
    pin = model().at(q={"A": float(ya), "E": float(ye)}).pose("C2").position
    return (knee - pin[1] + PARAMS["r"] - R_SKID) * 1e3


SKID_AT_ALPHA_ZERO = Margin(
    "skid clearance at α = 0", lambda p: skid_mm(*p.hips), "mm",
    over=Space(hips=Choice(list(straight()))),
    truth=lambda p: closed_form_mm(*p.hips), agree=1e-3)
