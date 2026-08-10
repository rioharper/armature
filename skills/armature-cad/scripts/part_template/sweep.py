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

Run it:  uv run --with build123d python sweep.py

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

L1 = mm(0.30)  # params.PARAMS["l1"]
L2 = mm(0.25)  # params.PARAMS["l2"]
LINK_W = 40.0  # envelope guess, generous on purpose
LINK_H = 30.0
POST_R = 60.0  # base housing the arm must not fold into
POST_H = 250.0

# Adjacent links share a joint and overlap there by design; flagging that
# on every posture would bury the collisions that matter.
ADJACENT = {("link1", "link2"), ("base", "link1")}


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


def joint_limits_and_interior(n: int = 9):
    """Postures to check. Sample the interior, but ALWAYS include the
    limits — interference lives at the extremes, and a grid that stops
    one step short of them reports a clean sweep for a mechanism that
    collides on its first move to a hard stop."""
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
    return 0


def demo():
    """Self-check: the sweep finds a collision that is there, and reports
    none for a mechanism that clears."""
    # Folded hard back on itself, the forearm reaches the base post.
    folded = pose((0.0, math.pi))
    assert interference(folded["link2"], folded["base"]) > 0, "folded arm must hit the post"

    # Straight out, nothing but the design-adjacent pairs touch.
    straight = pose((0.0, 0.0))
    assert interference(straight["link2"], straight["base"]) == 0.0

    hits = sweep_clearance(pose, [(0.0, 0.0)], ignore=ADJACENT)
    assert hits == [], hits

    hits = sweep_clearance(pose, [(0.0, math.pi)], ignore=ADJACENT)
    assert [(h[1], h[2]) for h in hits] == [("base", "link2")], hits

    # A pair listed in `ignore` must stay quiet even when it overlaps.
    assert sweep_clearance(pose, [(0.0, math.pi)], ignore=ADJACENT | {("base", "link2")}) == []

    print("sweep.py self-tests passed (collision found, clearance clean, ignore honored)")


if __name__ == "__main__":
    demo()
    sys.exit(main())
