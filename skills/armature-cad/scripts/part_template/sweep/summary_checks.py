"""
sweep/summary_checks.py — self-tests for summary.py and, through main(),
for what report.py prints: one row per pair, rows labelled as samples, and
an exit code that fails on a collision.
"""

import contextlib
import io
import math

from check import sweep_clearance
from sweep import bodies
from sweep.grid import joint_limits_and_interior
from sweep.summary import main, summarize

def coarse():
    """A coarse grid (n=13, ~170 postures rather than ~1400): the same
    q1-redundancy shape as the default at a fraction of the cost. Built per
    check rather than at import, because the grid reads its limits from the
    mechanism description, which importing the package never needs."""
    return joint_limits_and_interior(13)


def test_one_row_per_pair_bounded_by_pairs_not_grid():
    COARSE = coarse()
    # link1<->link2's overlap doesn't depend on q1, so its raw hit count
    # scales with however finely q1 is sampled; the summary is one row per
    # pair however many raw postures collided.
    hits = sweep_clearance(bodies.pose, COARSE, ignore=bodies.ADJACENT)
    assert len(hits) > 20, "fixture assumption: the coarse grid needs real redundancy"
    rows = summarize(hits, COARSE)
    assert len(rows) <= 2, rows  # link1<->link2, base<->link2; base<->link1 excused
    elbow = next(r for r in rows if r[:2] == ("link1", "link2"))
    assert elbow[2] > 10, "fixture assumption: many raw hits collapsed to this one row"
    # n=13 steps every 30 deg; the first SAMPLE past the true 91 deg onset
    # is 120 deg. The 29 deg between them is why the report must not call
    # 120 the onset: a limit set there sits 29 deg inside the collision.
    first_q2 = abs(math.degrees(elbow[3][1]))
    assert math.isclose(first_q2, 120, abs_tol=1e-6) and first_q2 > 91, first_q2
    # q1 is not part of this finding - the pair interferes at EVERY sampled
    # q1 - so the row says so rather than presenting one arbitrary sample.
    assert elbow[7] == (True, False), elbow[7]

    # ...but only when that axis was actually SWEPT: q1 held at one value
    # must not read `any`.
    pinned = [(0.0, q2) for _, q2 in COARSE]
    pinned_row = next(r for r in summarize(sweep_clearance(bodies.pose, pinned, ignore=bodies.ADJACENT), pinned)
                      if r[:2] == ("link1", "link2"))
    assert pinned_row[7] == (False, False), pinned_row[7]
    print("  [PASS] one row per pair; `any` only for an axis actually swept")


def test_exit_code_fails_on_a_collision():
    # The real function, one-posture fixtures, quiet.
    assert main([(0.0, math.pi)], verbose=False) == 1, "a colliding posture must return nonzero"
    assert main([(0.0, 0.0)], verbose=False) == 0, "a clear posture must return 0"
    # An empty grid must not read as a clean bill of health.
    try:
        main([])
    except ValueError:
        pass
    else:
        raise AssertionError("an empty grid must raise, not exit 0")
    print("  [PASS] exit 1 on a collision, 0 on a clear sweep, raise on nothing")


def test_printed_report_is_safe_to_act_on():
    # What a reader SEES has to be safe to act on, not just the tuple
    # summarize() returns - reading a joint limit off it is the entire
    # reason armature-derive routes here.
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        main(coarse())
    printed = captured.getvalue()
    # Labelled as a SAMPLE: "onset (nearest clear)" named a posture that
    # interferes by 1.3 cm^3 and sits 29 deg inside the collision.
    assert "first interfering sample" in printed, printed
    assert "nearest clear" not in printed, printed
    # The step is printed, and so is what it means for the boundary.
    assert "grid step" in printed and "one step" in printed, printed
    assert "30.0" in printed, "the grid step (30 deg at n=13) must be printed"
    assert "120.0" in printed, "the elbow pair's first interfering sample must be printed"
    assert "any" in printed, "an axis the pair interferes at EVERY sample of must read `any`"
    assert "-50.0" not in printed, "a non-varying axis must not print one arbitrary sample"
    assert "... and" not in printed, "must not fall back to a truncated per-posture list"
    print("  [PASS] printed rows labelled as samples, with the grid step")
