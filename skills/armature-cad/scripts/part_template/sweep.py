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
# F11: this used to type 0.30 / 0.25 with the params.py key as a comment -
# a number restated instead of imported drifts the moment the derivation
# re-runs. Same honest-provenance guard as part.py's F1 fix (see
# _resolve_lengths below): only a missing `params` MODULE is caught, and
# even that has no fallback. A part's mass target can fall back to a
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
    different length - so they propagate uncaught, same as part.py's F1.
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


L1, L2 = _resolve_lengths()
LINK_W = 40.0  # envelope guess, generous on purpose
LINK_H = 30.0
POST_R = 60.0  # base housing the arm must not fold into
POST_H = 250.0


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
    elbow = Location((L1 * math.cos(q1), L1 * math.sin(q1), 0))
    link2 = Box(L2, LINK_W, LINK_H).locate(Location((L2 / 2, 0, 0)))
    link2 = elbow * (Rotation(0, 0, math.degrees(q1 + q2)) * link2)

    return {"base": base, "link1": link1, "link2": link2}


# F7: adjacent bodies share a joint, and the envelope can overlap there
# even when nothing is wrong - e.g. the base post's radius reaches past
# the joint into link1 by construction. That is not a defect, it is baked
# into POST_R, and it needs excusing wherever it happens.
#
# The old blanket `ignore` excused each PAIR at every posture, which also
# hid link1<->link2's overlap - the pair that actually varies with q2, and
# where the elbow limit lives. Measured: at q2=114.6 deg the hidden
# link1<->link2 overlap is 18689 mm^3, 3.5x the base<->link2 overlap the
# old sweep DID report at q2=180 deg (5321.8 mm^3) - the tool reported the
# smaller collision and silently ate the bigger one.
#
# Fix: excuse each pair only up to ITS OWN design overlap, measured at the
# neutral/home posture (0, 0) - not a guessed margin. Above that threshold
# is real interference, reported wherever it occurs, same as any other
# pair.
#
#   base<->link1: 35321.8 mm^3 at EVERY q1 (measured - rotationally
#     symmetric about the post), so the threshold excuses it everywhere,
#     matching the old blanket behaviour for this pair exactly.
#   link1<->link2: 0.0 mm^3 at q2=0 (the boxes are built flush at the
#     joint). Its threshold is therefore ~0 - this pair needed no special
#     exclusion at all, which is exactly the bug: any real bend now gets
#     reported, sized by how far past 0 it is.
#
# RESIDUAL BLIND SPOT (see sweep_clearance's docstring in check.py): a
# pair is excused up to its threshold volume at EVERY posture, not only
# near the joint. That is harmless here only because base<->link1's
# overlap is constant across q1 - there is no posture where it reads
# smaller than its own threshold while something else is also wrong. A
# pair whose design overlap VARIES with posture would not get that
# guarantee for free.
_home = pose((0.0, 0.0))
ADJACENT = {
    frozenset(pair): interference(_home[pair[0]], _home[pair[1]])
    for pair in (("link1", "link2"), ("base", "link1"))
}


def joint_limits_and_interior(n: int = 37):
    """Postures to check. Sample the interior, but ALWAYS include the
    limits — interference lives at the extremes, and a grid that stops
    one step short of them reports a clean sweep for a mechanism that
    collides on its first move to a hard stop.

    F10: n=37 (a 10 deg step over the full +-180 deg range) is sized to
    the worked example's own narrowest known collision band, not a round
    number picked by feel. base<->link2's collision band near the folded
    limit is 11 deg wide at 1 deg resolution (last clear at q2=168 deg,
    first interfering at q2=169 deg - re-measured in this file's demo(),
    matching the red-team review's own independent scan exactly). A finer,
    0.1 deg scan finds the true continuous edge at q2=168.3 deg, so 11 deg
    is itself a slight overstatement of how much margin there really is.
    A grid can only be GUARANTEED to land a sample inside a band if its
    step is smaller than the band - otherwise the band can sit entirely
    between two grid points and vanish, which is what the old n=9 default
    (45 deg step) did to every band narrower than 45 deg that doesn't
    happen to abut a sampled endpoint. 10 deg is below the measured 11 deg,
    so THIS worked example's band cannot be stepped over. It promises
    nothing about a band narrower than 10 deg in a mechanism with
    different geometry - remeasure and tighten n if you change LINK_W,
    LINK_H, POST_R, or POST_H.

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


def main() -> int:
    qs = joint_limits_and_interior()
    hits = sweep_clearance(pose, qs, ignore=ADJACENT)

    print(f"swept {len(qs)} postures, {len(hits)} interfering")
    for q, a, b, vol in hits[:10]:
        print(
            f"  q = ({math.degrees(q[0]):7.1f} deg, {math.degrees(q[1]):7.1f} deg)"
            f"  {a} <-> {b}  overlap {vol / 1000:8.1f} cm^3"
        )
    if len(hits) > 10:
        print(f"  ... and {len(hits) - 10} more")

    if hits:
        print(
            "\nThis is an armature-math finding, not a CAD one: tighten a joint\n"
            "limit or change a link length in params.py, re-derive, re-run."
        )

    # F9: a colliding worked example must not exit 0. The README groups all
    # four template files under one runnable block and states the set's
    # exit-code contract (nonzero means a check failed), so returning 0
    # unconditionally here was a green CI gate on a mechanism that folds
    # into itself. Advisory-only was considered and rejected: a self-
    # collision is exactly the kind of finding "fail loud" exists for.
    return 1 if hits else 0


def demo():
    """Self-check: the sweep finds a collision that is there, reports none
    for a mechanism that clears, plus one assertion per red-team finding
    this file was fixed for, each written to FAIL if its fix is reverted."""
    import importlib
    import tempfile

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

    # --- F7: the elbow pair is no longer blanket-ignored. At q2=180 the
    # old code reported ONLY base<->link2 (5321.8 mm^3) and hid
    # link1<->link2 (300000 mm^3) completely, because both pairs shared
    # ADJACENT's blanket exclusion. Both must be visible now, worst first;
    # base<->link1 stays quiet - its constant 35321.8 mm^3 is exactly its
    # own threshold, never above it.
    hits = sweep_clearance(pose, [(0.0, math.pi)], ignore=ADJACENT)
    assert [(h[1], h[2]) for h in hits] == [("link1", "link2"), ("base", "link2")], hits

    # THE finding: at q2=114.6 deg the review measured an 18689 mm^3
    # link1<->link2 overlap - 3.5x the base<->link2 overlap the old sweep
    # DID report at q2=180 - that the blanket ignore hid completely
    # ("reported: NOTHING"). It must be reported now, at its measured size.
    hits = sweep_clearance(pose, [(0.0, math.radians(114.6))], ignore=ADJACENT)
    assert len(hits) == 1 and hits[0][1:3] == ("link1", "link2"), hits
    assert 18600 < hits[0][3] < 18800, hits[0][3]  # measured 18691.9 mm^3

    # A pair can still be fully excused - at a threshold explicitly wider
    # than any overlap it will see - which is the old blanket behaviour,
    # still available, just no longer the only option and now a visible,
    # tunable number instead of an invisible blanket rule.
    wide = dict(ADJACENT)
    wide[frozenset(("base", "link2"))] = math.inf
    hits = sweep_clearance(pose, [(0.0, math.pi)], ignore=wide)
    assert len(hits) == 1 and hits[0][1:3] == ("link1", "link2"), hits

    # --- F9: main() must not exit 0 on a colliding worked example. This
    # runs the real swept grid (n=37, ~15-20 s) - the regression test for
    # the return-code bug has to exercise main() itself, not a stand-in.
    assert main() == 1, "worked example collides (see the sweep above); main() must return nonzero"

    # --- F10: n<2 used to be a bare ZeroDivisionError (n=1: division by
    # n-1=0); it must raise a clear error instead.
    assert raised(ValueError, joint_limits_and_interior, 1)
    assert raised(ValueError, joint_limits_and_interior, 0)

    # The new default (n=37, 10 deg step) must be fine enough to land a
    # sample inside the worked example's narrowest known band. Re-measure
    # that band here (1 deg resolution) instead of trusting the
    # docstring's number, so a geometry change that moves the band fails
    # THIS assertion first, rather than going stale in a comment.
    def band_reach(sign):
        """Degrees inward from the sampled +-180 deg endpoint (in `sign`'s
        direction) that base<->link2 stays interfering, at 1 deg steps."""
        for deg in range(1, 30):
            q2 = sign * (180 - deg)
            p = pose((0.0, math.radians(q2)))
            if interference(p["link2"], p["base"]) <= 0.0:
                return deg - 1
        raise AssertionError("band wider than the scanned range")

    band_width = band_reach(1)
    assert band_width == band_reach(-1), "expected the band to be symmetric"
    # Matches the red-team review's own independently measured 11.0 deg.
    assert band_width == 11, band_width
    step = 360.0 / (37 - 1)
    assert step < band_width, (
        f"resolution step {step} deg is not smaller than the measured "
        f"{band_width} deg band - it can be stepped over again"
    )

    # --- F11: no restated params.py numbers, and no silent fallback.
    def resolve_with(params_src):
        """Resolve link lengths against a params.py written to a temp dir.

        Every directory already holding a params.py is dropped from
        sys.path for the duration, not just PARAMS_DIR: `import params`
        searches the whole path, including this file's own directory, so
        a real params.py sitting there would otherwise answer the case
        meant to test having none. Same hermetic setup as part.py's F1
        test, same reason.
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

    # No params.py anywhere: fatal, not a fallback to the old hardcoded
    # 300.0 / 250.0 - there is no safe placeholder for a link length.
    assert raised(RuntimeError, resolve_with, None)
    # A renamed key propagates instead of substituting a hand-typed number.
    assert raised(KeyError, resolve_with, "PARAMS = {'l1': 0.30}\n")
    # No PARAMS table at all is the same class of broken link, not a
    # missing-module event.
    assert raised(AttributeError, resolve_with, "NOT_PARAMS = {}\n")

    print(
        "sweep.py self-tests passed (collision found, clearance clean, elbow "
        "overlap reported, exit code, resolution guard, params provenance)"
    )


if __name__ == "__main__":
    demo()
    sys.exit(main())
