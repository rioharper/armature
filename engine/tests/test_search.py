"""The worst-case search, on plain callables and on two golden margins.

Answer: each margin's worst is known without the search, from a closed form
or by construction. Golden 1 is the 2R arm's holding margin, whose worst
posture is interior while its worst mass is a corner; golden 2 is the cable
platform's tension floor, whose slope jumps where the active cable switches
and whose worst sits on two mirror corners.
"""

import math

import numpy as np
import pytest
from scipy.optimize import minimize

import armature
from armature import (Budget, Choice, Direction, Infeasible, Interval, Margin,
                      Space, search)
from test_fixture_2r_arm import PARAMS as ARM
from test_fixture_2r_arm import arm
from test_fixture_cable_platform import settled


def margin(fn, budget=None, **axes):
    return Margin("slack", fn, "N", over=Space(**axes), budget=budget)


# --- golden 1: the 2R arm's holding margin ------------------------------------
TIP_LOAD = 20.0  # N


def holding(p):
    """The worse motor's torque left under its limit (N·m), holding the arm
    at (q1, q2) against gravity and a 20 N tip load along `load`."""
    m = armature.compile(arm, {**ARM, "m2": p.m2})
    inv = m.at(q={"shoulder": p.q1, "elbow": p.q2}).inverse(
        loads={"tip": TIP_LOAD * p.load})
    return min(ARM["limit"] - abs(t) for t in inv.torque.values())


def test_golden_arm_holding_margin():
    m1, m2, l1, l2, lc1, lc2, g = (ARM[k] for k in
                                   ("m1", "m2", "l1", "l2", "lc1", "lc2", "g"))
    heavy = 1.1 * m2
    answer = ARM["limit"] - (g * (m1 * lc1 + heavy * l1 + heavy * lc2)
                             + TIP_LOAD * (l1 + l2)) / ARM["N1"]
    assert answer == pytest.approx(0.1713052, abs=5e-8)
    worst = search(Margin(
        "shoulder holding", holding, "N·m",
        over=Space(q1=Interval(-math.pi, math.pi), q2=Interval(-2.6, 2.6),
                   load=Direction("xy"), m2=Interval(0.9 * m2, 1.1 * m2))))
    print(worst)
    assert worst.value == pytest.approx(answer, abs=1e-9)
    assert worst.passes
    assert worst.at["m2"] == pytest.approx(heavy)
    assert np.allclose(worst.at["load"], (0, -1, 0), atol=1e-4)
    assert abs(math.remainder(worst.at["q1"], math.pi)) < 1e-3
    assert abs(worst.at["q2"]) < 1e-3


# --- golden 2: the cable platform's tension floor -----------------------------
def floor(p):
    """The slackest cable's tension once the 2 kg platform has settled (N),
    each pose's rest lengths from fixture 2's tension law. A settle that does
    not come to rest is outside the space."""
    out = settled((p.x, p.y, p.z), 2.0)
    if not out.stable:
        raise Infeasible("the settle did not come to rest")
    return min(out.tension.values())


def test_golden_platform_tension_floor():
    worst = search(Margin(
        "tension floor", floor, "N",
        over=Space(x=Interval(1.5, 2.5), y=Interval(1.6, 2.2),
                   z=Interval(0.9, 1.4))))
    print(worst)
    assert worst.value == pytest.approx(4.987626, abs=1e-5)
    assert worst.at["x"] in (1.5, 2.5)
    assert (worst.at["y"], worst.at["z"]) == (1.6, 0.9)


# --- the point ----------------------------------------------------------------
def test_fn_reads_each_axis_by_name():
    seen = []

    def fn(p):
        seen.append(p)
        return p.x + p["y"]

    worst = search(margin(fn, x=Interval(0, 1), y=Interval(-1, 0)))
    assert all(0 <= p.x <= 1 and -1 <= p.y <= 0 for p in seen)
    assert worst.at == {"x": 0.0, "y": -1.0}
    with pytest.raises(AttributeError, match=r"no axis named 'z'.*'x', 'y'"):
        seen[0].z


def test_a_plane_direction_has_its_four_axis_directions_as_corners():
    seen = []

    def fn(p):
        seen.append(p.load)
        return 1.0 + p.load[1]

    worst = search(margin(fn, load=Direction("xy")))
    assert all(np.linalg.norm(d) == pytest.approx(1) and d[2] == 0
               for d in seen)
    for corner in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)):
        assert any(np.array_equal(d, corner) for d in seen), corner
    assert worst.value == 0.0
    assert worst.at["load"] == (0.0, -1.0, 0.0)


def test_a_sphere_direction_is_searched_as_two_angles():
    seen = []
    against = np.array([1.0, 1.0, 1.0]) / math.sqrt(3)

    def fn(p):
        seen.append(p.load)
        return 1.0 + p.load @ against

    worst = search(margin(fn, load=Direction("sphere")))
    assert all(np.linalg.norm(d) == pytest.approx(1) for d in seen)
    for corner in np.vstack([np.eye(3), -np.eye(3)]):
        assert any(np.array_equal(d, corner) for d in seen), corner
    assert worst.value == pytest.approx(0.0, abs=1e-9)
    assert np.allclose(worst.at["load"], -against, atol=1e-4)


# --- the method ---------------------------------------------------------------
def test_each_choice_combination_keeps_its_own_worst():
    def fn(p):
        if p.case == "up":
            return (p.x - 0.37) ** 2 + 0.1
        return 0.5 - p.x

    worst = search(margin(fn, case=Choice(("up", "down")),
                          x=Interval(0, 1)))
    up, down = worst.cases
    assert up.choices == {"case": "up"}
    assert up.value == pytest.approx(0.1, abs=1e-9)
    assert up.at["x"] == pytest.approx(0.37, abs=1e-4)
    assert down.choices == {"case": "down"}
    assert (down.value, down.at) == (-0.5, {"case": "down", "x": 1.0})
    assert (worst.value, worst.at) == (down.value, down.at)
    assert not worst.passes


def test_every_choice_combination_is_enumerated():
    seen = set()

    def fn(p):
        seen.add((p.sign, p.case))
        return p.sign * p.x

    worst = search(margin(fn, sign=Choice((1, -1)),
                          case=Choice(("a", "b", "c")), x=Interval(-1, 2)))
    assert seen == {(s, c) for s in (1, -1) for c in "abc"}
    assert [c.choices for c in worst.cases] == [
        {"sign": s, "case": c} for s in (1, -1) for c in "abc"]
    assert (worst.value, worst.at) == (-2.0, {"sign": -1, "case": "a",
                                              "x": 2.0})


def test_an_infeasible_region_is_rejected_and_never_the_worst():
    def fn(p):
        if p.x + p.y < 0.5:
            raise Infeasible("below the line")
        return p.x + p.y

    worst = search(margin(fn, x=Interval(0, 1), y=Interval(0, 1)))
    assert worst.at["x"] + worst.at["y"] >= 0.5
    assert worst.value == pytest.approx(0.5, abs=1e-3)
    assert set(worst.rejected) == {"below the line"}
    assert worst.rejected["below the line"] > 0
    assert "below the line" in str(worst)


def test_a_space_with_no_feasible_point_raises_with_the_reasons():
    def fn(p):
        raise Infeasible("the loop cannot close")

    with pytest.raises(ValueError, match="the loop cannot close"):
        search(margin(fn, x=Interval(0, 1)))


def test_minus_infinity_wins_and_ends_the_polish():
    def fn(p):
        return -math.inf if p.x > 0.9 else 1.0 - p.x

    worst = search(margin(fn, x=Interval(0, 1)))
    assert worst.value == -math.inf
    assert worst.at["x"] > 0.9
    assert not worst.passes
    assert worst.n == 64 + 2  # the global set and the corners: no polish


def test_nan_raises_and_names_the_point():
    def fn(p):
        return math.nan if p.x > 0.5 else p.x

    with pytest.raises(ValueError, match=r"'slack' is nan at x = 0\.[5-9]"):
        search(margin(fn, x=Interval(0, 1)))


def test_coverage_is_the_fraction_of_the_global_set_that_passes():
    worst = search(margin(lambda p: p.x - 0.3, x=Interval(0, 1)))
    assert worst.coverage == pytest.approx(0.7, abs=0.02)
    assert worst.value == -0.3 and worst.at == {"x": 0.0}


def test_the_same_seed_gives_the_same_worst():
    def fn(p):
        return math.sin(5 * p.x) * math.cos(3 * p.y) + 0.1 * p.y

    m = margin(fn, x=Interval(0, 2), y=Interval(-1, 1))
    assert search(m, seed=7) == search(m, seed=7)
    assert search(m, seed=7).coverage != search(m, seed=8).coverage


def test_the_result_is_never_above_the_pre_polish_best():
    slack = []

    def fn(p):
        slack.append(abs(p.load[0]) + p.load[1] + 1.0)
        return slack[-1]

    # The trap: the worst is a corner, straight down, at a kink. The
    # polish's line searches close in on it without landing on it, so every
    # point the polish evaluates is worse than the corner it started from.
    worst = search(margin(fn, load=Direction("xy")))
    polish = slack[64 + 4:]
    assert polish and min(polish) > 0.0
    assert worst.value == worst.pre_polish == 0.0
    assert worst.at == worst.pre_polish_at == {"load": (0.0, -1.0, 0.0)}


def test_bounded_powell_alone_ends_worse_than_a_corner_it_starts_on():
    polished = minimize(lambda u: u[0] + u[1], [0.0, 0.0], method="Powell",
                        bounds=[(0, 1)] * 2)
    assert polished.fun > 0.0
    worst = search(margin(lambda p: p.x + p.y, x=Interval(0, 1),
                          y=Interval(0, 1)))
    assert worst.value == worst.pre_polish == 0.0
    assert worst.at == worst.pre_polish_at == {"x": 0.0, "y": 0.0}


def test_the_polish_finds_an_interior_worst_between_the_samples():
    def fn(p):
        return (p.x - 0.123456) ** 2 + (p.y + 0.4321) ** 2 - 1.0

    worst = search(margin(fn, x=Interval(-1, 1), y=Interval(-1, 1)))
    assert worst.pre_polish > -1.0 + 1e-6
    assert worst.value == pytest.approx(-1.0, abs=1e-12)
    assert worst.value <= worst.pre_polish


def test_the_global_set_is_a_power_of_two_and_the_corners_are_all_there():
    calls = []

    def fn(p):
        calls.append((p.x, p.y, p.z))
        return p.x

    worst = search(margin(fn, budget=Budget(global_points=100, polish_starts=0),
                          x=Interval(0, 1), y=Interval(0, 1),
                          z=Interval(0, 1)))
    assert worst.n == len(calls) == 128 + 8
    assert {c for c in calls if set(c) <= {0.0, 1.0}} == {
        (x, y, z) for x in (0.0, 1.0) for y in (0.0, 1.0) for z in (0.0, 1.0)}
    assert worst.value == worst.pre_polish


def test_the_polish_is_capped_per_start():
    worst = search(margin(lambda p: math.sin(40 * p.x) + p.y,
                          budget=Budget(global_points=16, polish_starts=2,
                                        polish_evals=10),
                          x=Interval(0, 1), y=Interval(0, 1)))
    assert worst.n <= 16 + 4 + 2 * 10


# --- the record ---------------------------------------------------------------
def test_the_row_is_one_line_with_everything_a_note_cites():
    worst = search(Margin("tip clearance", lambda p: p.x - 0.3, "mm",
                          over=Space(x=Interval(0, 1))), seed=11)
    row = str(worst)
    assert "\n" not in row
    for part in ("tip clearance", "-0.3 mm", "x = 0", "FAILS", "seed = 11",
                 f"n = {worst.n}", "coverage", "pre-polish", "Sobol",
                 "corners", "Powell"):
        assert part in row, part
    assert (worst.margin, worst.unit, worst.seed) == ("tip clearance", "mm",
                                                       11)


def test_a_margin_is_checked_when_it_is_declared():
    space = Space(x=Interval(0, 1))
    with pytest.raises(ValueError, match="agree"):
        Margin("m", lambda p: p.x, "N", over=space, truth=lambda p: p.x)
    with pytest.raises(TypeError, match="Space"):
        Margin("m", lambda p: p.x, "N", over={"x": Interval(0, 1)})
    with pytest.raises(TypeError, match="callable"):
        Margin("m", 3.0, "N", over=space)
    assert Margin("m", lambda p: p.x, "N", over=space).budget == Budget()


@pytest.mark.parametrize("make, match", [
    (lambda: Interval(1, 0), "low below its high"),
    (lambda: Interval(0, math.inf), "finite"),
    (lambda: Choice(()), "at least one"),
    (lambda: Choice("ab"), "sequence of values"),
    (lambda: Direction("xw"), "'xy', 'xz', 'yz' or 'sphere'"),
    (lambda: Space(x=(0, 1)), "an axis"),
    (lambda: Budget(polish_starts=-1), "polish_starts"),
])
def test_axes_and_budgets_are_checked(make, match):
    with pytest.raises((TypeError, ValueError), match=match):
        make()
