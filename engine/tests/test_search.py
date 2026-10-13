"""The worst-case search, on plain callables and on three mechanism margins.

Answer: each margin's worst is known without the search, from a closed form,
by construction, or from a dense run of the same margin. Golden 1 is the 2R
arm's holding margin, whose worst posture is interior while its worst mass
is a corner of its band; golden 2 is the cable platform's tension floor,
whose slope jumps where the active cable switches and whose worst sits on
two mirror corners. The five-bar's pin clearance is searched over ±π, where
three of the four corners and a third of the space cannot close.
"""

import math
from collections import Counter

import numpy as np
import pytest
from scipy.optimize import minimize

import armature
from armature import (Band, Budget, Choice, Coordinates, Direction, Infeasible,
                      Interval, Margin, Rejected, Space, body, joint, search)
from armature.sampler import unit_cube
from test_fixture_2r_arm import PARAMS as ARM
from test_fixture_2r_arm import arm
from test_fixture_cable_platform import HOME, LEVEL, params, platform, settled
from test_fixture_five_bar import PARAMS as FIVE_BAR
from test_fixture_five_bar import POINTS, five_bar


def margin(fn, budget=None, **axes):
    return Margin("slack", fn, "N", over=Space(**axes), budget=budget)


# --- golden 1: the 2R arm's holding margin ------------------------------------
TIP_LOAD = 20.0  # N
BANDS = {"m2": (0.9 * ARM["m2"], 1.1 * ARM["m2"])}  # kg: the forearm ± 10 %


def holding(p):
    """The worse motor's torque left under its limit (N·m), holding the arm
    at its state against gravity and a 20 N tip load along `load`."""
    inv = p.state.inverse(loads={"tip": TIP_LOAD * p.load})
    return min(ARM["limit"] - abs(t) for t in inv.torque.values())


def test_golden_arm_holding_margin():
    m1, l1, l2, lc1, lc2, g = (ARM[k] for k in
                               ("m1", "l1", "l2", "lc1", "lc2", "g"))
    heavy = BANDS["m2"][1]
    answer = ARM["limit"] - (g * (m1 * lc1 + heavy * l1 + heavy * lc2)
                             + TIP_LOAD * (l1 + l2)) / ARM["N1"]
    assert answer == pytest.approx(0.1713052, abs=5e-8)
    worst = search(Margin(
        "shoulder holding", holding, "N·m",
        over=Space(m2=Band("m2", BANDS), state=Coordinates(arm, ARM),
                   load=Direction("xy"))))
    print(worst)
    assert worst.value == pytest.approx(answer, abs=1e-9)
    assert worst.passes
    assert worst.at["m2"] == heavy
    assert np.allclose(worst.at["load"], (0, -1, 0), atol=1e-4)
    q = worst.at["state"]
    assert set(q) == {"shoulder", "elbow"}
    assert abs(math.remainder(q["shoulder"], math.pi)) < 1e-3
    assert abs(q["elbow"]) < 1e-3


# --- golden 2: the cable platform's tension floor -----------------------------
ROOM = armature.pose_envelope(box=((1.5, 2.5), (1.6, 2.2), (0.9, 1.4)),
                              tilt=0.0, yaw=(0.0, 0.0))


def floor(p):
    """The slackest cable's tension once the 2 kg platform, commanded level
    to its state's point, has settled (N), each pose's rest lengths from
    fixture 2's tension law. A settle that does not come to rest is outside
    the space."""
    out = settled(p.state.pose("centre").position, 2.0)
    if not out.stable:
        raise Infeasible("the settle did not come to rest")
    return min(out.tension.values())


def test_golden_platform_tension_floor():
    # The commanded pose is level, so the space is the level variant's three
    # slides across the envelope's box. The free platform would add a tilt,
    # an azimuth and a yaw the envelope holds at zero: three more axes to
    # spend Sobol points and corners on, and nothing to find there.
    worst = search(Margin(
        "tension floor", floor, "N",
        over=Space(state=Coordinates(LEVEL, params(HOME, 2.0),
                                     poses={"hang": ROOM}))))
    print(worst)
    assert worst.value == pytest.approx(4.987626, abs=1e-5)
    at = worst.at["state"]
    assert at["hang:x"] in (1.5, 2.5)
    assert (at["hang:y"], at["hang:z"]) == (1.6, 0.9)


# --- the five-bar's pin over ±π -----------------------------------------------
FLOOR = -0.30  # m: a floor 0.30 m below the hips


def pin_clearance(p):
    """How far the five-bar's pin C is above the floor (m)."""
    return above_floor(p.state)


def above_floor(state):
    return float(state.pose("C2").position[1]) - FLOOR


def lowest_pin():
    """The lowest the pin reaches (m): where the circles each leg reaches
    at full stretch meet below the hips, which are level, with both legs
    straight."""
    a, b, c = (np.array(POINTS[k]) for k in "ABC")
    e, d = (np.array(POINTS[k]) for k in "ED")
    ra = np.linalg.norm(b - a) + np.linalg.norm(c - b)
    re = np.linalg.norm(d - e) + np.linalg.norm(c - d)
    half = np.linalg.norm(e - a) / 2
    x = (ra ** 2 - re ** 2) / (4 * half)  # from the hips' midpoint
    return -math.sqrt(ra ** 2 - (half + x) ** 2)


def dense(cube, fn, lo, hi, n):
    """`fn` at each state of an n × n grid over [lo, hi]² of the unit cube,
    with the grid point; a point that cannot close is skipped."""
    axis = [np.linspace(l, h, n) for l, h in zip(lo, hi)]
    points = np.array([(a, e) for a in axis[0] for e in axis[1]])
    states = cube.map(points)
    return [(fn(s), u) for s, u in zip(states, points)
            if not isinstance(s, Rejected)]


def test_five_bar_pin_clearance_is_the_feasible_worst_over_pi():
    m = armature.compile(five_bar, FIVE_BAR)
    cube = unit_cube(m)
    corners = cube.map([(a, e) for a in (0.0, 1.0) for e in (0.0, 1.0)])
    refused = Counter(s.reason for s in corners if isinstance(s, Rejected))
    # only (−π, −π) closes: (π, π) is the same posture, but the branch from
    # home cannot reach it
    assert refused == {"loop 'pin'": 3}

    worst = search(Margin("pin clearance", pin_clearance, "m", over=Space(
        state=Coordinates(five_bar, FIVE_BAR))))
    print(worst)
    # the three corners, and draws that cannot close or would put a
    # dependent joint out of range: about 30 % of ±π², and a fifth of the
    # Sobol set at least
    assert worst.rejected["loop 'pin'"] >= 3
    assert set(worst.rejected) <= {"loop 'pin'", "joint 'B'", "joint 'D'"}
    assert sum(worst.rejected.values()) > 0.2 * 128

    # the dense reference: the same margin over a 21 × 21 grid, then a
    # 21 × 21 grid across the cells round its best
    coarse = min(dense(cube, above_floor, (0, 0), (1, 1), 21),
                 key=lambda r: r[0])
    cell = 1 / 20
    fine = min(dense(cube, above_floor, np.clip(coarse[1] - cell, 0, 1),
                     np.clip(coarse[1] + cell, 0, 1), 21), key=lambda r: r[0])
    print(f"dense reference: {coarse[0]:.7g} m on the coarse grid, "
          f"{fine[0]:.7g} m on the fine; closed form "
          f"{lowest_pin() - FLOOR:.7g} m")
    assert worst.value <= fine[0] <= coarse[0]
    assert worst.value == pytest.approx(fine[0], abs=2e-5)
    assert worst.value == pytest.approx(lowest_pin() - FLOOR, abs=1e-9)
    assert worst.passes

    # the worst is a state that closes, and reads the same again
    assert above_floor(m.at(q=worst.at["state"])) == pytest.approx(
        worst.value, abs=1e-12)


# --- Band and Coordinates -----------------------------------------------------
def counted(calls):
    """The 2R arm, counting each time it is described: once per compile."""
    def mechanism(p):
        calls.append(p["m2"])
        return arm(p)
    return mechanism


def test_a_band_is_applied_before_the_state_is_compiled():
    calls, seen = [], []

    def fn(p):
        seen.append((p.m2, p.state.compiled.model.body("fore").mass[0]))
        return p.state.q["shoulder"]

    search(margin(fn, budget=Budget(global_points=8, polish_starts=0),
                  m2=Band("m2", BANDS),
                  state=Coordinates(counted(calls), ARM)))
    assert all(given == pytest.approx(compiled) for given, compiled in seen)
    assert {m2 for m2, _ in seen} >= set(BANDS["m2"])
    assert calls[0] == ARM["m2"]  # the nominal compile, which reads the axes
    assert len(calls) <= 1 + len(seen)


def test_a_space_without_a_band_compiles_once():
    calls = []
    worst = search(margin(lambda p: p.state.q["elbow"],
                          state=Coordinates(counted(calls), ARM)))
    assert calls == [ARM["m2"]]
    assert worst.value == -2.6 and worst.at["state"]["elbow"] == -2.6


def test_coordinates_corners_are_the_corners_of_within():
    seen = set()

    def fn(p):
        seen.add((p.state.q["shoulder"], p.state.q["elbow"]))
        return 1.0

    within = {"shoulder": (-0.5, 0.25), "elbow": (0.0, 1.0)}
    search(margin(fn, budget=Budget(polish_starts=0),
                  state=Coordinates(arm, ARM, within=within)))
    assert {q for q in seen if q[0] in within["shoulder"]
            and q[1] in within["elbow"]} == {
        (s, e) for s in within["shoulder"] for e in within["elbow"]}
    assert all(-0.5 <= s <= 0.25 and 0.0 <= e <= 1.0 for s, e in seen)


def test_a_point_that_cannot_close_is_rejected_with_the_constraint():
    def fn(p):
        return 1.0

    worst = search(margin(fn, budget=Budget(global_points=16,
                                            polish_starts=0),
                          state=Coordinates(five_bar, FIVE_BAR)))
    assert worst.rejected["loop 'pin'"] >= 3  # three of the four corners
    assert worst.n == 16 + 4


def test_a_floating_body_is_drawn_from_its_envelope():
    seen = []

    def fn(p):
        seen.append(p.state.q["hang"].position)
        return 1.0

    space = Space(state=Coordinates(platform, params(HOME, 2.0),
                                    poses={"hang": ROOM}))
    assert space.dims == 6
    search(Margin("slack", fn, "N", over=space,
                  budget=Budget(global_points=16, polish_starts=0)))
    box = np.array(ROOM.box)
    assert all(np.all(box[:, 0] <= x) and np.all(x <= box[:, 1])
               for x in seen)


@pytest.mark.parametrize("bands, match", [
    ({"m2": (1.0, 1.2)}, r"band 'm2'.*nominal 0\.8.*\(1\.0, 1\.2\)"),
    ({"m3": (0.0, 1.0)}, r"band 'm3'.*no parameter"),
])
def test_a_band_is_checked_before_the_first_compile(bands, match):
    calls = []
    with pytest.raises(ValueError, match=match):
        Space(band=Band(next(iter(bands)), bands),
              state=Coordinates(counted(calls), ARM))
    assert calls == []


@pytest.mark.parametrize("make, match", [
    (lambda: Band("m3", BANDS), r"no band named 'm3'.*\['m2'\]"),
    (lambda: Band("m2", {"m2": (0.9, 0.8)}), "low below its high"),
    (lambda: Band("m2", {"m2": (0.9, math.inf)}), "finite"),
    (lambda: Band("m2", {"m2": 0.9}), r"\(low, high\)"),
    (lambda: Space(a=Coordinates(arm, ARM), b=Coordinates(arm, ARM)),
     "one Coordinates"),
    (lambda: Space(a=Band("m2", BANDS), b=Band("m2", BANDS)), "twice"),
])
def test_bands_and_coordinates_are_checked(make, match):
    with pytest.raises((TypeError, ValueError), match=match):
        make()


def test_a_band_of_another_is_neither_checked_nor_compiled():
    """A drive band in a space with Coordinates: its parameter is not the
    mechanism's, so it is read by name and never compiled."""
    calls, seen = [], []

    def fn(p):
        seen.append(p.eta)
        return p.eta

    worst = search(margin(fn, budget=Budget(global_points=8, polish_starts=0),
                          eta=Band("eta", {"eta": (0.8, 0.9)}, of="drive"),
                          state=Coordinates(counted(calls), ARM)))
    assert calls == [ARM["m2"]]
    assert worst.value == 0.8 and min(seen) == 0.8
    assert "of='drive'" in repr(Band("eta", {"eta": (0.8, 0.9)}, of="drive"))
    Space(a=Band("m2", BANDS), b=Band("m2", BANDS, of="drive"))  # two owners


def test_an_unchecked_margin_fails_naming_what_is_missing():
    def fn(p):
        raise AssertionError("an unchecked margin is never evaluated")

    worst = search(Margin("winding", fn, "K", over=Space(),
                          unchecked=("thermal", "i_continuous")))
    assert worst.unchecked == ("thermal", "i_continuous")
    assert not worst.passes and math.isnan(worst.value) and worst.n == 0
    assert str(worst) == ("winding: UNCHECKED, FAILS; missing thermal, "
                          "i_continuous")
    with pytest.raises(TypeError, match="tuple of strings"):
        Margin("winding", fn, "K", over=Space(), unchecked="thermal")


def test_a_band_may_not_change_the_axes():
    def renamed(p):
        name = "a" if p["m"] < 1.05 else "b"
        return [body("link", mass=p["m"], com=(0.1, 0, 0),
                     inertia=np.diag([1e-3] * 3)),
                joint(name, "hinge", parent="world", child="link",
                      axis=(0, 0, 1), point=(0, 0, 0), range=(-1, 1))]

    space = Space(m=Band("m", {"m": (0.9, 1.1)}),
                  state=Coordinates(renamed, {"m": 1.0}))
    with pytest.raises(ValueError, match=r"\['a'\].*\['b'\]"):
        search(Margin("slack", lambda p: 1.0, "N", over=space))


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


# --- the truth ----------------------------------------------------------------
def interior(p):
    """An interior worst, between the Sobol points: the polish moves it, so
    the worst and the pre-polish best are different points."""
    return (p.x - 0.123456) ** 2 + (p.y + 0.4321) ** 2 - 1.0


def test_truth_is_evaluated_at_the_worst_and_at_the_pre_polish_best():
    seen = []

    def truth(p):
        seen.append({"x": p.x, "y": p.y})
        return interior(p) + 1e-9

    worst = search(Margin("slack", interior, "N", over=Space(
        x=Interval(-1, 1), y=Interval(-1, 1)), truth=truth, agree=1e-6))
    assert worst.at != worst.pre_polish_at
    assert seen == [worst.at, worst.pre_polish_at]
    confirmed = worst.truth
    assert confirmed.value == pytest.approx(worst.value + 1e-9, abs=1e-15)
    assert confirmed.pre_polish == pytest.approx(worst.pre_polish + 1e-9,
                                                 abs=1e-15)
    assert confirmed.gap == pytest.approx(1e-9, abs=1e-15)
    assert confirmed.agree == 1e-6 and confirmed.agrees
    assert "truth" in str(worst) and "agrees" in str(worst)


def test_truth_runs_once_where_the_polish_did_not_move_the_worst():
    seen = []

    def truth(p):
        seen.append(p.x)
        return p.x - 0.3

    worst = search(Margin("slack", lambda p: p.x - 0.3, "N", over=Space(
        x=Interval(0, 1)), truth=truth, agree=1e-9))
    assert worst.at == worst.pre_polish_at == {"x": 0.0}
    assert seen == [0.0]
    assert worst.truth.value == worst.truth.pre_polish == -0.3
    assert worst.truth.gap == 0.0 and worst.truth.agrees


def test_a_truth_that_disagrees_beyond_agree_is_recorded_not_hidden():
    worst = search(Margin("slack", interior, "N", over=Space(
        x=Interval(-1, 1), y=Interval(-1, 1)),
        truth=lambda p: interior(p) - 0.1, agree=0.01))
    assert worst.truth.gap == pytest.approx(0.1, abs=1e-12)
    assert not worst.truth.agrees
    assert "DISAGREES" in str(worst)
    assert worst.value == pytest.approx(-1.0, abs=1e-12)  # fn's, not truth's


def test_a_truth_that_reads_nan_disagrees():
    worst = search(Margin("slack", lambda p: p.x, "N", over=Space(
        x=Interval(0, 1)), truth=lambda p: math.nan, agree=1.0))
    assert math.isnan(worst.truth.gap) and not worst.truth.agrees


def test_a_truth_that_cannot_evaluate_the_worst_raises_naming_it():
    def truth(p):
        raise Infeasible("the settle did not come to rest")

    with pytest.raises(ValueError, match=r"truth.*x = 0.*settle did not"):
        search(Margin("slack", lambda p: p.x, "N", over=Space(
            x=Interval(0, 1)), truth=truth, agree=1.0))


def test_without_a_truth_nothing_is_confirmed():
    worst = search(margin(lambda p: p.x, x=Interval(0, 1)))
    assert worst.truth is None and "truth" not in str(worst)


def test_truth_reads_the_state_fn_read_compiled_with_its_band():
    def truth(p):
        """The same margin on a fresh compile at the point's band value and
        its state's coordinates."""
        fresh = armature.compile(arm, {**ARM, "m2": p.m2}).at(q=p.state.q)
        inv = fresh.inverse(loads={"tip": TIP_LOAD * p.load})
        return min(ARM["limit"] - abs(t) for t in inv.torque.values())

    worst = search(Margin(
        "shoulder holding", holding, "N·m",
        over=Space(m2=Band("m2", BANDS), state=Coordinates(arm, ARM),
                   load=Direction("xy")),
        truth=truth, agree=1e-9,
        budget=Budget(global_points=16, polish_starts=1, polish_evals=20)))
    assert worst.at["m2"] in BANDS["m2"]
    assert worst.truth.agrees, worst.truth


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
