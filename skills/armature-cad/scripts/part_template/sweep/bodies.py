"""
sweep/bodies.py — the envelopes the sweep moves, where they sit at a
posture, and how each adjacent pair's design overlap is excused. Replace
the bodies and CARRIERS with your mechanism. Self-tests in bodies_checks.py.

Every envelope is written where it sits at the home posture, in the base
frame, as the mechanism description writes everything (ADR 0003), and rides
on a site of the description: at a posture, the engine says where that site
is and how its body has turned, and the envelope moves with it. There is no
forward kinematics here to drift from the derivation's.
"""

from __future__ import annotations

import sys
from pathlib import Path

from build123d import Box, Cylinder, Location, Plane

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check import interference, mm  # noqa: E402

# --- where the mechanism comes from ------------------------------------
# SI in, mm out. See check/__init__.py's unit contract.
#
# The lengths are READ, never typed: a number restated here drifts the
# moment the derivation re-runs. They are the ledger's `mechanism` section
# (ADR 0010), from the ledger the model reads: the nearest `ledger.toml` at
# or above analysis/model/, which in a project is its root. Same
# honest-provenance guard as part.py (see _resolve_lengths below), with no
# fallback at all. A part's mass target can fall back to a budget line and
# stay useful; a link length can't - a guessed L1/L2 could hide a real
# self-collision or invent one that isn't there, so a missing or renamed
# source is fatal here, not advisory. The postures are the same: they come
# from the engine's truth model of analysis/model/mechanism.py, or the
# sweep does not run.
MODEL_DIR = Path(__file__).resolve().parents[3] / "analysis" / "model"
sys.path.insert(0, str(MODEL_DIR))


def _mechanism(model_dir):
    """The ledger's `mechanism` section nearest `model_dir`, SI: exactly
    what the model's `mechanism(p)` reads. No ledger is fatal; a ledger
    with no `mechanism` section raises as itself, a broken link."""
    from armature.ledger import LedgerError, find, load
    try:
        path = find(model_dir)
    except LedgerError as exc:
        raise RuntimeError(
            f"sweep: no ledger.toml at or above {model_dir} - nothing to "
            "build the link envelopes from. Run the armature-derive "
            "milestone that writes the mechanism's entries first; there is "
            "no safe placeholder for a link length."
        ) from exc
    return load("mechanism", path=path)


def _resolve_lengths(model_dir=MODEL_DIR):
    """(L1, L2) in mm, from the ledger's mechanism.l1 and .l2 (SI, metres).

    No ledger is fatal. A `KeyError` (l1/l2 renamed) and a `LedgerError`
    (no mechanism section) both mean the derivation is there and the link
    to it is broken - not a reason to sweep against a different length -
    so they propagate uncaught, same as part.py.
    """
    p = _mechanism(model_dir)
    return mm(p["l1"]), mm(p["l2"])


def _resolve_truth(model_dir=MODEL_DIR):
    """The truth model, compiled by the engine from analysis/model's
    `mechanism(p)` and the ledger's mechanism section.

    Only a missing `mechanism` MODULE is turned into a message, and it
    carries no fallback: a pose computed any other way is a second forward
    kinematics, which is the copy this file exists not to keep. Anything
    else - the engine not installed, a description the engine refuses -
    propagates as itself.
    """
    try:
        import mechanism  # analysis/model/mechanism.py
    except ModuleNotFoundError as exc:
        if exc.name != "mechanism":
            raise  # the engine, or something mechanism.py imports, is missing
        raise RuntimeError(
            f"sweep: no analysis/model/mechanism.py on sys.path ({model_dir})"
            " - nothing to pose the envelopes with. Write the description at "
            "armature-derive's Milestone 0 first; the sweep keeps no forward "
            "kinematics of its own."
        ) from exc
    import armature
    return armature.compile(mechanism.mechanism, _mechanism(model_dir))


# NOT resolved here. `L1, L2 = _resolve_lengths()` at module scope makes
# importing the package raise whenever analysis/model/ isn't already on
# sys.path, so its checks couldn't even be discovered without a real project
# layout. Set by `ensure_geometry()`, called first thing by main() and by
# every check - nothing touches L1/L2, TRUTH or RANGES before they do. Read
# them, and ADJACENT, as `bodies.L1`: a `from bodies import L1` binds the
# None below, not the resolved length.
L1 = L2 = None
TRUTH = HOME = None   # the compiled description, and its home state
RANGES = None         # each swept coordinate's joint range, in TRUTH's order
LINK_W = 40.0  # envelope guess, generous on purpose
LINK_H = 30.0
POST_R = 60.0  # base housing the arm must not fold into
POST_H = 250.0

# Which site of the description each moving envelope rides on: any site on
# the envelope's body will do, since the whole body turns with it. A body
# not listed here (the base post) is fixed to the world.
CARRIERS = {"link1": "elbow_pin", "link2": "tip"}

# JOINT_TRIM is how much link2's box is set back from the elbow, instead
# of starting flush at it. See pose() for where it's used and ADJACENT
# below for why link1<->link2 needs no volume threshold at all once this
# is in place.
#
# Measured (isolated two-box rig, not this worked example, so the widths
# could be varied independently):
#
#   w1(untrimmed) w2(trimmed) trim   onset (deg, 1 deg res)
#     40           40          0      1   (flush at the joint: no gap)
#     40           40         10     31
#     40           40         20     91   <- LINK_W / 2 both links, chosen
#     40           40         40    127
#     60           40         20     46   (trim = w2/2, the WRONG rule)
#     60           40         30     91   (trim = w1/2, the RIGHT rule)
#     40           60         30    107
#
# The onset is governed by the UNTRIMMED NEIGHBOUR's half-width (link1's,
# since link2 is the one being trimmed), NOT the trimmed box's own -
# compare the w1=60/w2=40 rows: trim sized from link2's own half-width
# (20) gives onset 46 deg, trim sized from link1's half-width (30) gives
# 91 deg, the same as the all-40mm case. `JOINT_TRIM = LINK_W / 2` is
# correct here ONLY because both links share `LINK_W`; a mechanism whose
# links have different widths must size the trim from the NEIGHBOUR
# link's half-width, not its own. bodies_checks.py re-measures both rows.
#
# Rule of thumb (not a certified bound - this is a crude planning tool):
# onset ~= 180 - 2*atan((w_neighbour/2) / trim), valid once
# trim >= w_neighbour/2 (below that, the untrimmed neighbour's own corner
# sticks out past the trim and dominates instead - see the w1=60/w2=40/
# trim=20 row, which trim=w1/2=30 would put in the valid regime instead).
# Measured accurate to ~1 deg near trim = w_neighbour/2 (3 of 4 tested
# configurations); measured up to 6 deg OPTIMISTIC (predicts a later,
# safer-looking onset than actually occurs) when the TRIMMED link's own
# width is much larger than the untrimmed one and trim sits well above
# w_neighbour/2 (w1=40/w2=60/trim=30: formula predicts 112.6, measured
# 107). If your two links have visibly different widths, measure your own
# onset the way bodies_checks.py does rather than trusting the formula.
#
# 20 mm leaves link1<->link2 EXACTLY 0.0 mm^3 for the entire q2 in
# [-90, 90] deg range (not just below some volume floor - the boxes have a
# real, measured gap there) and reports it from 91 deg outward, growing to
# 276000 mm^3 at 180 deg. That RANGE is what makes a threshold measured at
# any single posture wrong for this pair: the excuse has to track the
# whole range, and a box set back from the joint is what buys that instead
# of a volume number guessed to cover it.
JOINT_TRIM = LINK_W / 2


def at_home():
    """Every envelope where it sits at the home posture, in the base frame.

    The arm lies along +X at home, as the description writes it: link1 from
    the shoulder at the origin out to the elbow, link2 from the elbow out to
    the tool. link2's BOX is set back JOINT_TRIM from the elbow rather than
    flush against it - see JOINT_TRIM's own comment for the measured basis.
    """
    l2_len = L2 - JOINT_TRIM
    return {
        "base": Cylinder(POST_R, POST_H).locate(Location((0, 0, POST_H / 2))),
        "link1": Box(L1, LINK_W, LINK_H).locate(Location((L1 / 2, 0, 0))),
        "link2": Box(l2_len, LINK_W, LINK_H).locate(
            Location((L1 + JOINT_TRIM + l2_len / 2, 0, 0))),
    }


def carried(shape, state, site):
    """`shape`, written at home, moved as `site`'s body has moved from home
    to `state`: x -> R (x - p0) + p, with p0 and p the site's position at
    home and at the state and R its body's turn, all from the engine."""
    here, home = state.pose(site), HOME.pose(site)
    R = here.rotation
    shift = [mm(v) for v in here.position - R @ home.position]
    frame = Plane(origin=shift, x_dir=tuple(R[:, 0]), z_dir=tuple(R[:, 2]))
    return Location(frame) * shape


def pose(q) -> dict:
    """Position every body at posture q, the swept coordinates' values in
    radians in RANGES order: `TRUTH.at(q)` is the posture, and each envelope
    rides on its carrier site."""
    state = TRUTH.at(q=dict(zip(TRUTH.independent, q)))
    return {name: (carried(shape, state, CARRIERS[name]) if name in CARRIERS
                   else shape)
            for name, shape in at_home().items()}


# Adjacent bodies share a joint, and the envelope can overlap there even
# when nothing is wrong - the base post's radius reaches past the joint
# into link1 by construction. That is not a defect, it is baked into
# POST_R, and it needs excusing wherever it happens.
#
# WHICH excuse a pair gets turns on whether its design overlap moves with
# posture, and that is a measurement, not a judgement call:
#
#   base<->link1   CONSTANT across q1 (the post is rotationally symmetric),
#                  so one measurement at home is honest at every posture
#                  the pair reaches -> a threshold, in ADJACENT below.
#   link1<->link2  0.0 mm^3 at home and GROWING with |q2| - which is what
#                  a revolute joint's rigid boxes always do, real collision
#                  or not. A threshold sampled at home therefore excuses
#                  effectively nothing: measured, it flags 98.2% of the
#                  swept grid. -> a GEOMETRIC excuse instead, JOINT_TRIM in
#                  at_home(), which gives link2 a real gap to bend through.
#
# The distinction is "constant overlap gets a threshold", NOT "adjacent
# pairs get a threshold".
#
# RESIDUAL BLIND SPOT of a threshold (see sweep_clearance's docstring in
# check/interference.py): it hides a genuine collision below its volume at
# EVERY posture it applies to, not only near the joint. For base<->link1
# that is provably harmless - constant overlap, so there is no posture
# where a real problem hides under a smaller reading. A GROWING-overlap
# pair gets no such guarantee from a threshold at any single sample, which
# is why link1<->link2 is fixed in geometry instead.
#
# THE TRIM HAS ITS OWN, DIFFERENT BLIND SPOT: JOINT_TRIM does not just
# excuse link1<->link2, it deletes link2's first JOINT_TRIM mm from the
# MODEL. That missing stub cannot be reported as colliding with ANYTHING -
# not just link1, any body - because there is no geometry there to test.
# Harmless in this worked example only because nothing else passes within
# JOINT_TRIM of the elbow (the stub sits 280-320 mm out from the origin;
# POST_R=60 doesn't reach it). Add a body that could pass near the elbow (a
# cable run, a second arm) and this trim would silently miss a collision
# with the missing 20 mm the same way an `ignore` threshold misses one
# below its volume - check it explicitly if you add one.
def ensure_geometry():
    """Resolve L1/L2 from the ledger, the truth model from mechanism.py,
    and ADJACENT's threshold.

    Deferred from module scope so the package imports without analysis/model
    (see L1 above). main() and every check call this first; idempotent.
    """
    global L1, L2, TRUTH, HOME, RANGES, ADJACENT
    L1, L2 = _resolve_lengths()
    TRUTH = _resolve_truth()
    HOME = TRUTH.at()
    ranges = {j.name: j.range for j in TRUTH.description.joints}
    RANGES = [tuple(float(v) for v in ranges[name]) for name in TRUTH.independent]
    home = pose([TRUTH.home(name) for name in TRUTH.independent])
    ADJACENT = {
        frozenset(("base", "link1")): interference(home["base"], home["link1"]),
    }


ADJACENT = {}  # populated by ensure_geometry()
