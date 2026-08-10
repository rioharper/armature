"""
sweep.py — interference checking across a motion range, for the
kinematics and planning stages.

This runs BEFORE any part exists. The point is that a self-collision is a
kinematics finding, not a CAD finding: if the forearm hits the base post at
q2 = -2.4 rad, the fix is a joint limit or a link length in `params.py`,
and the cheapest moment to learn that is while those are still just numbers
in a derivation. Learning it from a rebuilt assembly two weeks later costs
the rebuild.

So the bodies here are deliberately crude — boxes and cylinders sized from
the link lengths already in `analysis/model/params.py`. An envelope that is
20% too fat is the right fidelity: it finds the collisions that matter and
costs nothing to write. Do not model features here.

Run it:  uv run --with 'build123d~=0.11' --with sympy python sweep.py

Needs analysis/model/params.py on sys.path for the link lengths (hence
--with sympy, which params.py imports) - there is no placeholder fallback
for a link length (see _resolve_lengths below): a guessed one could hide a
real self-collision or invent one that isn't there.

The example below is the planar 2R arm from the armature-math template,
with a base post it can fold back into. Replace the bodies and pose() with
your mechanism; keep the shape of the file.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from build123d import Box, Cylinder, Location, Rotation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import interference, mm, sweep_clearance  # noqa: E402

# --- link geometry, from the parameter table ---------------------------
# SI in, mm out. See check.py's unit contract.
#
# The lengths are IMPORTED, never typed: a number restated here drifts the
# moment the derivation re-runs. Same honest-provenance guard as part.py
# (see _resolve_lengths below): only a missing `params` MODULE is caught,
# and even that has no fallback. A part's mass target can fall back to a
# budget row and stay useful; a link length can't - a guessed L1/L2 could
# hide a real self-collision or invent one that isn't there, so a missing
# or renamed source is fatal here, not advisory.
PARAMS_DIR = Path(__file__).resolve().parents[2] / "analysis" / "model"
sys.path.insert(0, str(PARAMS_DIR))


def _resolve_lengths():
    """(L1, L2) in mm, from analysis/model/params.py's l1/l2 (SI, metres).

    Only a missing `params` MODULE is caught. A `KeyError` (l1/l2 renamed)
    and an `AttributeError` (no PARAMS table) both mean the derivation is
    there and the link to it is broken - not a reason to sweep against a
    different length - so they propagate uncaught, same as part.py.
    """
    try:
        import params  # analysis/model/params.py -- SI: metres, kilograms
    except ModuleNotFoundError as exc:
        if exc.name != "params":
            raise  # params.py imports something that isn't installed
        raise RuntimeError(
            f"sweep.py: no analysis/model/params.py on sys.path ({PARAMS_DIR}) "
            "- nothing to build the link envelopes from. Run the "
            "armature-math milestone that produces params.py first; there "
            "is no safe placeholder for a link length."
        ) from exc
    return mm(params.PARAMS["l1"]), mm(params.PARAMS["l2"])


# NOT resolved here. `L1, L2 = _resolve_lengths()` at module scope makes
# `import sweep` itself raise whenever analysis/model/params.py isn't
# already on sys.path, so the file can't be imported for its own demo()
# without a real project layout. Set by `_ensure_geometry()`, called first
# thing by main() and demo() - nothing else in this file touches L1/L2
# before they do.
L1 = L2 = None
LINK_W = 40.0  # envelope guess, generous on purpose
LINK_H = 30.0
POST_R = 60.0  # base housing the arm must not fold into
POST_H = 250.0

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
# link's half-width, not its own. demo() re-measures both rows.
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
# onset the way this file's demo() does rather than trusting the formula.
#
# 20 mm leaves link1<->link2 EXACTLY 0.0 mm^3 for the entire q2 in
# [-90, 90] deg range (not just below some volume floor - the boxes have a
# real, measured gap there) and reports it from 91 deg outward, growing to
# 276000 mm^3 at 180 deg. That RANGE is what makes a threshold measured at
# any single posture wrong for this pair: the excuse has to track the
# whole range, and a box set back from the joint is what buys that instead
# of a volume number guessed to cover it.
JOINT_TRIM = LINK_W / 2


def pose(q) -> dict:
    """Position every body at posture q = (q1, q2) in radians.

    Each link is drawn along +X from its own joint, then rotated into
    place — the same convention as the DH table in params.py, so the
    postures this reports are postures the derivation can act on.
    """
    q1, q2 = q

    base = Cylinder(POST_R, POST_H).locate(Location((0, 0, POST_H / 2)))

    # link1: from joint 1 at the origin, out along +X, rotated by q1.
    link1 = Box(L1, LINK_W, LINK_H).locate(Location((L1 / 2, 0, 0)))
    link1 = Rotation(0, 0, math.degrees(q1)) * link1

    # link2: from the elbow, out along +X, rotated by q1 + q2. The elbow is
    # a pure translation — link2's own rotation already carries q1, and
    # composing a rotated Location here would apply q1 to it twice.
    #
    # link2's BOX is set back JOINT_TRIM from the elbow (starts at local
    # x=JOINT_TRIM instead of x=0) rather than flush against it - see
    # JOINT_TRIM's own comment for the measured basis. This changes what
    # shape sits in link2's frame, not the frame itself: `elbow` and the
    # rotation angle below are the plain FK and must stay that way.
    elbow = Location((L1 * math.cos(q1), L1 * math.sin(q1), 0))
    l2_len = L2 - JOINT_TRIM
    link2 = Box(l2_len, LINK_W, LINK_H).locate(Location((JOINT_TRIM + l2_len / 2, 0, 0)))
    link2 = elbow * (Rotation(0, 0, math.degrees(q1 + q2)) * link2)

    return {"base": base, "link1": link1, "link2": link2}


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
#                  pose(), which gives link2 a real gap to bend through.
#
# The distinction is "constant overlap gets a threshold", NOT "adjacent
# pairs get a threshold".
#
# RESIDUAL BLIND SPOT of a threshold (see sweep_clearance's docstring in
# check.py): it hides a genuine collision below its volume at EVERY
# posture it applies to, not only near the joint. For base<->link1 that is
# provably harmless - constant overlap, so there is no posture where a real
# problem hides under a smaller reading. A GROWING-overlap pair gets no
# such guarantee from a threshold at any single sample, which is why
# link1<->link2 is fixed in geometry instead.
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
def _ensure_geometry():
    """Resolve L1/L2 from params.py and derive ADJACENT's threshold.

    Deferred from module scope: resolving params.py at import time makes
    `import sweep` itself raise whenever analysis/model/params.py isn't on
    sys.path, which breaks running this file's own demo(). main() and
    demo() both call this first; nothing else in this file uses
    L1/L2/ADJACENT before they do.
    """
    global L1, L2, ADJACENT
    L1, L2 = _resolve_lengths()
    home = pose((0.0, 0.0))
    ADJACENT = {
        frozenset(("base", "link1")): interference(home["base"], home["link1"]),
    }


ADJACENT = {}  # populated by _ensure_geometry()


def joint_limits_and_interior(n: int = 37):
    """Postures to check. Sample the interior, but ALWAYS include the
    limits — interference lives at the extremes, and a grid that stops
    one step short of them reports a clean sweep for a mechanism that
    collides on its first move to a hard stop.

    n=37 (a 10 deg step over the full +-180 deg range) is sized to the
    worked example's own narrowest known collision band, not a round
    number picked by feel. base<->link2's collision band near the folded
    limit is 11 deg wide at 1 deg resolution (last clear at q2=168 deg,
    first interfering at q2=169 deg - re-measured in this file's demo()).
    A finer, 0.1 deg scan finds the true continuous edge at q2=168.3 deg,
    so 11 deg is itself a slight overstatement of how much margin there
    really is. A grid can only be GUARANTEED to land a sample inside a
    band if its step is smaller than the band - otherwise the band sits
    entirely between two grid points and vanishes, unless it happens to
    abut a sampled endpoint. 10 deg is below the measured 11 deg, so THIS
    worked example's band cannot be stepped over. It promises nothing
    about a band narrower than 10 deg in a mechanism with different
    geometry - remeasure and tighten n if you change LINK_W, LINK_H,
    POST_R, or POST_H.

    The step also bounds how precisely a reported collision LOCATES its
    own boundary: the first interfering sample can be up to one step past
    the true onset, so a joint limit read off it must be set at least one
    step inside. See main()'s printed report, which says so.

    Same class of limit as `rebuild_sweep`'s (see part_template/README.md):
    this finds a collision that is there over a real grid; it does not
    prove one is absent between grid points narrower than the step.

    Cost is O(n^2) postures x n_pairs booleans: n=37 is ~1400 postures and
    took ~16 s for this 3-body example - fine for a planning-stage script
    run a handful of times, not something to put in a hot loop.
    """
    if n < 2:
        raise ValueError(
            f"joint_limits_and_interior: n={n}, need at least 2 samples so "
            "both joint limits are included - a single sample can't hold both."
        )
    q1_range = (-math.pi, math.pi)
    # Elbow stops aren't set yet — sweeping the unrestricted range is how
    # you find out where they belong. Once they're chosen, narrow this to
    # the chosen limits so the sweep keeps checking the real envelope.
    q2_range = (-math.pi, math.pi)

    def grid(lo, hi):
        return [lo + (hi - lo) * i / (n - 1) for i in range(n)]

    return [(a, b) for a in grid(*q1_range) for b in grid(*q2_range)]


def _summarize(hits, qs):
    """Collapse sweep_clearance's per-posture hits to one row per pair -
    its FIRST INTERFERING SAMPLE (smallest overlap among the hits: nearest
    to clear where overlap grows monotonically away from the clear region,
    which a mechanism need not do) and its WORST (largest overlap).

    Per PAIR, not per posture: printing every posture buries the two facts
    a reader needs behind noise that isn't even independent information -
    the worked example's link1<->link2 overlap does not depend on q1 at
    all, so its 666 raw hits are 18 distinct q2 values times 37 REDUNDANT
    q1 copies of the same finding. Reporting reported-postures as a
    FRACTION of swept ones never fixes that, because the redundancy scales
    with however fine the other, irrelevant axis is sampled. The row count
    here is bounded by the number of pairs, never by grid resolution.

    An axis a pair interferes at EVERY sampled value of contributes
    nothing to the finding, and is reported as `any` rather than as one
    arbitrary sample of it - that is what `free` carries. `qs` is passed
    in for exactly that comparison.

    Returns [(name_a, name_b, count, first_q, first_vol, worst_q,
    worst_vol, free), ...], worst-first by `worst_vol`.
    """
    swept = [{q[k] for q in qs} for k in range(len(qs[0]))]
    by_pair = {}
    for q, a, b, vol in hits:
        by_pair.setdefault((a, b), []).append((q, vol))
    rows = []
    for (a, b), entries in by_pair.items():
        entries.sort(key=lambda e: e[1])
        first_q, first_vol = entries[0]
        worst_q, worst_vol = entries[-1]
        free = tuple(
            {q[k] for q, _ in entries} == swept[k] for k in range(len(swept))
        )
        rows.append((a, b, len(entries), first_q, first_vol, worst_q, worst_vol, free))
    return sorted(rows, key=lambda r: -r[6])


def _grid_steps(qs):
    """Smallest gap between distinct sampled values on each axis, in
    degrees, or None for an axis sampled at a single value. This is the
    resolution the report's boundary caveat is stated in."""
    steps = []
    for k in range(len(qs[0])):
        values = sorted({q[k] for q in qs})
        gaps = [b - a for a, b in zip(values, values[1:])]
        steps.append(math.degrees(min(gaps)) if gaps else None)
    return steps


def _fmt_q(q, free=None):
    """A posture in degrees. An axis flagged in `free` - one the pair
    interferes at EVERY sampled value of - prints as `any` instead of one
    arbitrary sample, because that axis is not part of the finding. The
    worst-overlap row passes no flags: it is one real measured posture,
    labelled as such, not a claim about a boundary."""
    free = (False,) * len(q) if free is None else free
    return "(" + ", ".join(
        "    any" if f else f"{math.degrees(v):7.1f}" for v, f in zip(q, free)
    ) + ") deg"


def main(qs=None, verbose=True) -> int:
    """Sweep `qs` (default: `joint_limits_and_interior()`) and report hits.

    `qs` is a parameter so demo() can exercise this function's real
    print/return-code behaviour against a couple of cheap hand-picked
    postures instead of paying for the full ~1400-posture default grid a
    second time on every run; `verbose=False` silences the printing for
    exactly that use, so a one-posture fixture's report block can't be
    mistaken for the real one.
    """
    _ensure_geometry()
    if qs is None:
        qs = joint_limits_and_interior()
    if not qs:
        raise ValueError(
            "main(): no postures to sweep. An empty grid reports 'swept 0 "
            "postures, 0 interfering' and exits 0 - a clean bill of health "
            "for a mechanism nothing looked at."
        )
    hits = sweep_clearance(pose, qs, ignore=ADJACENT)
    summary = _summarize(hits, qs)

    if verbose:
        steps = _grid_steps(qs)
        print(f"swept {len(qs)} postures, {len(hits)} interfering ({len(summary)} distinct pair(s))")
        print(
            "  grid step: "
            + ", ".join("n/a" if s is None else f"{s:.1f}" for s in steps)
            + " deg. The rows below are SAMPLES, not boundaries: the true"
        )
        print(
            "  onset lies up to one step before the first interfering sample, so set a"
        )
        print(
            "  joint limit at least one step inside it, or re-run a fine scan around it."
        )
        for a, b, count, first_q, first_vol, worst_q, worst_vol, free in summary:
            print(f"  {a} <-> {b}: {count} of {len(qs)} postures interfere")
            print(
                f"    first interfering sample  q = {_fmt_q(first_q, free)}"
                f"  overlap {first_vol / 1000:8.1f} cm^3"
            )
            print(
                f"    worst                     q = {_fmt_q(worst_q)}"
                f"  overlap {worst_vol / 1000:8.1f} cm^3"
            )

    if hits and verbose:
        print(
            "\nThis is an armature-math finding, not a CAD one: tighten a joint\n"
            "limit or change a link length in params.py, re-derive, re-run."
        )

    # A colliding mechanism must not exit 0. The README groups all four
    # template files under one runnable block and states the set's
    # exit-code contract (nonzero means a check failed), so returning 0
    # unconditionally here is a green CI gate on a mechanism that folds
    # into itself. Advisory-only was considered and rejected: a self-
    # collision is exactly the kind of finding "fail loud" exists for.
    return 1 if hits else 0


def demo():
    """Self-check: the sweep finds a collision that is there, reports none
    for a mechanism that clears, plus an assertion behind every guard in
    this file, each written to FAIL if the guard is removed."""
    import importlib
    import tempfile

    _ensure_geometry()

    def raised(exc_type, fn, *args, **kwargs):
        """The exception `fn` raised, or None. A check that cannot fail is
        not a check, so every use of this is asserted truthy."""
        try:
            fn(*args, **kwargs)
        except exc_type as exc:
            return exc
        return None

    # Folded hard back on itself, the forearm reaches the base post.
    folded = pose((0.0, math.pi))
    assert interference(folded["link2"], folded["base"]) > 0, "folded arm must hit the post"

    # Straight out, nothing but the design-adjacent pairs touch.
    straight = pose((0.0, 0.0))
    assert interference(straight["link2"], straight["base"]) == 0.0

    hits = sweep_clearance(pose, [(0.0, 0.0)], ignore=ADJACENT)
    assert hits == [], hits

    # --- The elbow pair is excused by JOINT_TRIM (geometry), not by a
    # threshold - a threshold measured at home is provably wrong for this
    # pair (see the comment above ADJACENT) and flags 98.2% of the swept
    # grid. A blanket pair-ignore reports ONLY base<->link2 (5321.8 mm^3)
    # at q2=180 and hides link1<->link2 completely; both must be visible,
    # worst first. base<->link1 stays quiet - its constant 35321.8 mm^3 is
    # exactly its own threshold, never above it (see the epsilon note).
    hits = sweep_clearance(pose, [(0.0, math.pi)], ignore=ADJACENT)
    assert [(h[1], h[2]) for h in hits] == [("link1", "link2"), ("base", "link2")], hits
    # The fully-folded overlap is 276000 mm^3, not the 300000 an untrimmed
    # link2 gives (the trim removes a 20x40x30 mm slab that would otherwise
    # be in there). Asserted so JOINT_TRIM's comment can't drift from it.
    assert math.isclose(hits[0][3], 276000.0), hits[0][3]

    # A mechanism whose joint limits keep the elbow inside JOINT_TRIM's
    # clean zone must sweep clear. q2 confined to +-45 deg (well inside the
    # measured 91 deg onset below) at every q1 reports nothing.
    limited_qs = [
        (q1, q2)
        for q1 in (-math.pi, 0.0, math.pi / 2, math.pi)
        for q2 in (-math.radians(45), 0.0, math.radians(45))
    ]
    assert sweep_clearance(pose, limited_qs, ignore=ADJACENT) == [], "limited q2 must clear"

    # The elbow collision's TRUE onset, measured at 1 deg resolution rather
    # than trusted from JOINT_TRIM's comment, so a geometry change fails
    # this assertion first. Symmetric both directions.
    def elbow_onset():
        """First |q2|, walking out from 0 in each direction, where
        link1<->link2 interferes, at 1 deg steps. Both directions in one
        pass - it is a symmetric measurement, so don't scan twice."""
        onset = {}
        for sign in (1, -1):
            for deg in range(1, 180):
                p = pose((0.0, math.radians(sign * deg)))
                if interference(p["link1"], p["link2"]) > 0.0:
                    onset[sign] = deg
                    break
            else:
                raise AssertionError("no onset found in the scanned range")
        return onset[1], onset[-1]

    onset_pos, onset_neg = elbow_onset()
    assert onset_pos == onset_neg, "expected the onset to be symmetric"
    assert onset_pos == 91, onset_pos  # measured: JOINT_TRIM = LINK_W/2 = 20 mm -> 91 deg

    # Re-derive rows of JOINT_TRIM's trim-vs-onset table directly against
    # an isolated two-box rig (not this file's pose(), so LINK_W can't leak
    # in and make the test trivially agree with itself), so an edit that
    # regresses the table fails here rather than misleading a reader.
    def isolated_onset(w1, w2, trim):
        """Same box-pivot geometry as pose()'s link1/link2, in isolation:
        link1 (width w1, untrimmed) meets link2 (width w2, set back
        `trim` from the shared pivot) at q1=0."""
        link1 = Box(L1, w1, LINK_H).locate(Location((L1 / 2, 0, 0)))
        elbow = Location((L1, 0, 0))
        l2len = L2 - trim
        link2 = Box(l2len, w2, LINK_H).locate(Location((trim + l2len / 2, 0, 0)))
        for deg in range(1, 180):
            rotated = elbow * (Rotation(0, 0, deg) * link2)
            if interference(link1, rotated) > 0.0:
                return deg
        raise AssertionError("no onset found in the scanned range")

    assert isolated_onset(LINK_W, LINK_W, 10.0) == 31, "trim-vs-onset table row (trim=10mm) went stale"
    # The rule ("size from the NEIGHBOUR's half-width, not the trimmed
    # box's own") only matters when the two links differ - the worked
    # example can't catch a regression to "trim from link2's own width"
    # because LINK_W is shared. This can: trim sized from link2's own
    # half-width (20, wrong rule) gives a much earlier, more dangerous
    # onset than trim sized from link1's (30, right rule) on a mechanism
    # with a wider proximal link.
    assert isolated_onset(60.0, 40.0, 20.0) == 46, "w2/2-sized trim (wrong rule)"
    assert isolated_onset(60.0, 40.0, 30.0) == 91, "w1/2-sized trim (right rule)"

    # A per-posture report floods: link1<->link2's overlap doesn't depend
    # on q1 at all, so its raw hit count is however many distinct q2 values
    # collide, multiplied by however finely q1 happens to be sampled -
    # which is why "reported postures as a fraction of swept ones" is not a
    # metric that can be fixed. A coarse grid (n=13, ~170 postures rather
    # than the full ~1400) has the same q1-redundancy shape and is enough:
    # `_summarize()` collapses to ONE row per pair however many raw
    # postures collided, because the row count is bounded by the number of
    # PAIRS, not by grid resolution.
    coarse_qs = joint_limits_and_interior(13)
    coarse_hits = sweep_clearance(pose, coarse_qs, ignore=ADJACENT)
    assert len(coarse_hits) > 20, "fixture assumption: the coarse grid needs real redundancy to prove anything"
    summary = _summarize(coarse_hits, coarse_qs)
    # At most 2 pairs interfere in this worked example (link1<->link2,
    # base<->link2); base<->link1 is excused. However many raw hits, the
    # summary is one row per pair - verified against real (if coarse) data
    # rather than assumed from the design.
    assert len(summary) <= 2, summary
    elbow_row = next(r for r in summary if r[:2] == ("link1", "link2"))
    assert elbow_row[2] > 10, "fixture assumption: many raw hits collapsed to this one row"
    first_q2_deg = abs(math.degrees(elbow_row[3][1]))
    # n=13 over +-180 steps every 30 deg (-180,-150,...,150,180); the first
    # SAMPLE past the true 91 deg onset is 120 deg (isclose: the grid is
    # built from float division, not exact multiples of 30). The 29 deg gap
    # between the two is the whole reason the report must not call 120 the
    # onset: a joint limit set there puts the arm 29 deg inside a
    # self-collision on its first move to the stop.
    assert math.isclose(first_q2_deg, 120, abs_tol=1e-6), first_q2_deg
    assert first_q2_deg > onset_pos, (first_q2_deg, onset_pos)
    # q1 is not part of this finding - the pair interferes at EVERY sampled
    # q1 - so the row must say so rather than presenting one arbitrary
    # sample of it as if it mattered.
    assert elbow_row[7] == (True, False), elbow_row[7]

    # Without a slop guard the threshold is an exact-equality knife edge
    # against OCC's own float noise. base<->link1's threshold IS the
    # volume measured at q1=0; recomputing "the same" boolean at a
    # DIFFERENT q1 differs in the last bits (measured: +2.18e-11 mm^3 max
    # deviation across 37 q1 samples), and a bare `v > threshold` reports
    # 444 of those as collisions. `sweep_clearance` guards with
    # `threshold + min_volume` (check.py) - assert it holds across several
    # q1, not only the q1=0 sample, which is bit-exact by construction and
    # so proves nothing.
    for q1deg in (0, 45, 90, 135, 180, -90):
        p = pose((math.radians(q1deg), 0.0))
        assert sweep_clearance(pose, [(math.radians(q1deg), 0.0)], ignore=ADJACENT) == [], (
            q1deg,
            interference(p["base"], p["link1"]),
        )

    # A pair can still be fully excused - at a threshold explicitly wider
    # than any overlap it will see - which is the blanket behaviour, still
    # available, just no longer the only option and now a visible, tunable
    # number instead of an invisible rule.
    wide = dict(ADJACENT)
    wide[frozenset(("base", "link2"))] = math.inf
    hits = sweep_clearance(pose, [(0.0, math.pi)], ignore=wide)
    assert len(hits) == 1 and hits[0][1:3] == ("link1", "link2"), hits

    # main() must not exit 0 on a posture that collides, and must exit 0 on
    # one that clears - exercising the real function, not a stand-in.
    # One-posture fixtures, and quiet: printing their report blocks opens
    # `python sweep.py`'s output with a "swept 1 postures, ..." line ahead
    # of the real one, indistinguishable from it at a glance.
    assert main([(0.0, math.pi)], verbose=False) == 1, "a colliding posture must return nonzero"
    assert main([(0.0, 0.0)], verbose=False) == 0, "a clear posture must return 0"
    # An empty grid must not read as a clean bill of health: "swept 0
    # postures, 0 interfering" and exit 0 is the green-on-nothing this
    # whole file exists to avoid, same class as
    # joint_limits_and_interior's n<2 guard.
    assert raised(ValueError, main, [])

    # What a reader of `python sweep.py` actually SEES has to be safe to
    # act on, not just the tuple `_summarize()` returns - reading a joint
    # limit off it is the entire reason armature-math routes here.
    import contextlib
    import io

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        main(coarse_qs)
    printed = captured.getvalue()
    # The row is labelled as a SAMPLE. "onset (nearest clear)" named a
    # posture that interferes by 1.3 cm^3 and sits 29 deg inside the
    # collision - a limit set from it drives the arm into the stop.
    assert "first interfering sample" in printed, printed
    assert "nearest clear" not in printed, printed
    # The step is printed, and so is what it means for the boundary: the
    # true onset is up to one step earlier, so a limit goes one step inside.
    assert "grid step" in printed, printed
    assert "30.0" in printed, "the grid step (30 deg at n=13) must be printed"
    assert "one step" in printed, printed
    # The elbow row's own numbers, and no arbitrary q1 sample beside them.
    assert "120.0" in printed, "the elbow pair's first interfering sample must be printed"
    assert "any" in printed, "an axis the pair interferes at EVERY sample of must read `any`"
    assert "-50.0" not in printed, "a non-varying axis must not print one arbitrary sample"
    assert "... and" not in printed, "must not fall back to a truncated per-posture list"

    # n<2 is a bare ZeroDivisionError (n=1: division by n-1=0) unless
    # guarded; it must raise a clear error instead.
    assert raised(ValueError, joint_limits_and_interior, 1)
    assert raised(ValueError, joint_limits_and_interior, 0)

    # The default (n=37, 10 deg step) must be fine enough to land a
    # sample inside the worked example's narrowest known band. Re-measure
    # that band here (1 deg resolution) instead of trusting the
    # docstring's number, so a geometry change that moves the band fails
    # THIS assertion first, rather than going stale in a comment.
    def band_reach():
        """Degrees inward from each sampled +-180 deg endpoint that
        base<->link2 stays interfering, at 1 deg steps. Both directions in
        one pass - it is a symmetric measurement, so don't scan twice."""
        reach = {}
        for sign in (1, -1):
            for deg in range(1, 30):
                p = pose((0.0, math.radians(sign * (180 - deg))))
                if interference(p["link2"], p["base"]) <= 0.0:
                    reach[sign] = deg - 1
                    break
            else:
                raise AssertionError("band wider than the scanned range")
        return reach[1], reach[-1]

    band_pos, band_neg = band_reach()
    assert band_pos == band_neg, "expected the band to be symmetric"
    band_width = band_pos
    assert band_width == 11, band_width
    step = 360.0 / (37 - 1)
    assert step < band_width, (
        f"resolution step {step} deg is not smaller than the measured "
        f"{band_width} deg band - it can be stepped over again"
    )

    # --- No restated params.py numbers, and no silent fallback.
    def resolve_with(params_src):
        """Resolve link lengths against a params.py written to a temp dir.

        Every directory already holding a params.py is dropped from
        sys.path for the duration, not just PARAMS_DIR: `import params`
        searches the whole path, including this file's own directory, so
        a real params.py sitting there would otherwise answer the case
        meant to test having none. Same hermetic setup as part.py's
        equivalent test, same reason.
        """
        saved = sys.path[:]
        with tempfile.TemporaryDirectory() as tmp:
            if params_src is not None:
                Path(tmp, "params.py").write_text(params_src)
            sys.path[:] = [tmp] + [
                p for p in saved if not Path(p or ".", "params.py").exists()
            ]
            sys.modules.pop("params", None)
            importlib.invalidate_caches()
            try:
                return _resolve_lengths()
            finally:
                sys.path[:] = saved
                sys.modules.pop("params", None)

    l1, l2 = resolve_with("PARAMS = {'l1': 0.30, 'l2': 0.25}\n")
    assert (l1, l2) == (300.0, 250.0), (l1, l2)

    # No params.py anywhere: fatal, not a fallback to a typed 300.0 /
    # 250.0 - there is no safe placeholder for a link length.
    assert raised(RuntimeError, resolve_with, None)
    # A renamed key propagates instead of substituting a hand-typed number.
    assert raised(KeyError, resolve_with, "PARAMS = {'l1': 0.30}\n")
    # No PARAMS table at all is the same class of broken link, not a
    # missing-module event.
    assert raised(AttributeError, resolve_with, "NOT_PARAMS = {}\n")
    # params.py itself failing to import (a missing dependency of the
    # derivation, e.g. sympy) is NOT the same as no params.py at all -
    # `exc.name != "params"` must re-raise it, not swallow it as a fallback.
    assert raised(ModuleNotFoundError, resolve_with, "import definitely_not_a_real_module_xyz\n")

    print(
        "sweep.py self-tests passed (collision found, clearance clean, elbow "
        "overlap reported, exit code, resolution guard, params provenance)"
    )


if __name__ == "__main__":
    demo()
    sys.exit(main())
