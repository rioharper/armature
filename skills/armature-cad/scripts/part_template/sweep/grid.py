"""
sweep/grid.py — the postures the sweep checks, and the resolution that
bounds what a clean sweep can claim. Self-tests in grid_checks.py.
"""

from __future__ import annotations

import itertools
import math

from sweep import bodies


def joint_limits_and_interior(n: int = 37):
    """Postures to check. Sample the interior, but ALWAYS include the
    limits — interference lives at the extremes, and a grid that stops
    one step short of them reports a clean sweep for a mechanism that
    collides on its first move to a hard stop.

    n=37 (a 10 deg step over the full +-180 deg range) is sized to the
    worked example's own narrowest known collision band, not a round
    number picked by feel. base<->link2's collision band near the folded
    limit is 11 deg wide at 1 deg resolution (last clear at q2=168 deg,
    first interfering at q2=169 deg - re-measured in grid_checks.py).
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
    step inside. The printed summary (sweep/report.py) says so.

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
    # The limits are the description's joint ranges, the one envelope the
    # derivation and the truth model share. The worked example's elbow range
    # is the whole turn because its stops aren't set yet — sweeping it is how
    # you find out where they belong. Once they're chosen, narrow the range
    # in mechanism.py, and the sweep keeps checking the real envelope.
    bodies.ensure_geometry()

    def grid(lo, hi):
        return [lo + (hi - lo) * i / (n - 1) for i in range(n)]

    return list(itertools.product(*(grid(lo, hi) for lo, hi in bodies.RANGES)))


def grid_steps(qs):
    """LARGEST gap between distinct sampled values on each axis, in
    degrees, or None for an axis sampled at a single value. This is the
    resolution the report's boundary caveat is stated in.

    Largest, not smallest: the caveat tells the reader the true onset lies
    up to one step before the first interfering sample, so on a
    non-uniform grid the smallest gap would understate how far back that
    boundary can be - an error in the direction that under-warns. The
    built-in grid is uniform and the two agree there, but main() accepts
    arbitrary postures.
    """
    steps = []
    for k in range(len(qs[0])):
        values = sorted({q[k] for q in qs})
        gaps = [b - a for a, b in zip(values, values[1:])]
        steps.append(math.degrees(max(gaps)) if gaps else None)
    return steps
