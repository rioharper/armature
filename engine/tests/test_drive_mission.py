"""Missions: moves, holds and a followed q(t), through inverse dynamics to
each actuator's motor torque and speed.

Answer: a move's end is the start plus its distance along its direction,
written out here; its limits are the numbers it was given, checked on the
trace's own samples by difference; a geared pendulum's prescribed swing has
a closed-form torque, N²J_m included, whose peak and RMS are worked here and
by quadrature; a hold, the actuation seam and the five-bar are checked
against `inverse` called directly at the same states.
"""

import math

import numpy as np
import pytest
from scipy.integrate import quad

import armature
from armature import actuator, body, gravity, joint
from armature import Coordinates, Direction, Interval
from armature.drive import (CONFIRM_RATE, SEARCH_RATE, Duty, Limits, Mission,
                            follow, hold, move, trace)
from test_fixture_2r_arm import PARAMS as ARM
from test_fixture_2r_arm import arm, joint_torque
from test_fixture_five_bar import PARAMS as FIVE_BAR
from test_fixture_five_bar import five_bar

LIMITS = Limits(v=1.5, a=4.0, j=40.0,  # rad/s, rad/s², rad/s³
                along="coordinate")


@pytest.fixture(scope="module")
def m():
    return armature.compile(arm, ARM)


# --- moves -------------------------------------------------------------------
def test_a_move_by_direction_and_distance_reaches_the_end_it_names(m):
    start = {"shoulder": -0.4, "elbow": 0.9}
    direction = np.array([3.0, -4.0, 0.0])  # unit (0.6, -0.8); the third
    distance = 0.75                          # component is beyond the arm's
    end = {"shoulder": -0.4 + 0.6 * distance, "elbow": 0.9 - 0.8 * distance}

    by_end = trace(m, Mission("by end", [move(start, end=end,
                                              limits=LIMITS)]), CONFIRM_RATE)
    by_direction = trace(m, Mission("by direction", [move(
        m.at(q=start), direction=direction, distance=distance,
        limits=LIMITS)]), CONFIRM_RATE)

    for name, value in end.items():
        assert by_end.q[name][-1] == pytest.approx(value, abs=1e-9)
        assert by_direction.q[name][-1] == pytest.approx(value, abs=1e-9)
        assert by_end.q[name][0] == start[name]
    assert by_direction.t[-1] == pytest.approx(by_end.t[-1], abs=1e-12)
    # a straight line in the coordinates: the elbow's travel is −4/3 the
    # shoulder's at every sample
    travelled = {n: by_direction.q[n] - start[n] for n in start}
    np.testing.assert_allclose(travelled["elbow"],
                               -4 / 3 * travelled["shoulder"], atol=1e-12)


def _on(limit, name):
    """A limit's value on coordinate `name`."""
    return limit[name] if hasattr(limit, "keys") else limit


def test_a_move_reads_its_start_direction_and_distance_from_search_axes(m):
    """A `Coordinates` axis's state, a `Direction` axis's base-frame vector
    and an `Interval` axis's value, as `fn` would read them at a point."""
    state = Coordinates(arm, ARM).value((0.4, 0.7))
    turn = math.atan2(-0.8, 0.6)  # the direction (0.6, −0.8, 0)
    direction = Direction("xy").value(((turn / math.pi + 1) / 2,))
    distance = Interval(0.0, 1.0).value((0.75,))
    t = trace(m, Mission("searched", [move(state, direction=direction,
                                           distance=distance,
                                           limits=LIMITS)]), SEARCH_RATE)
    assert t.q["shoulder"][-1] == pytest.approx(
        state.q["shoulder"] + 0.6 * 0.75, abs=1e-9)
    assert t.q["elbow"][-1] == pytest.approx(state.q["elbow"] - 0.8 * 0.75,
                                             abs=1e-9)


@pytest.mark.parametrize("limits", [
    LIMITS,
    Limits(v={"shoulder": 1.0, "elbow": 0.5},
           a={"shoulder": 3.0, "elbow": 6.0},
           j={"shoulder": 30.0, "elbow": 10.0}, along="coordinate")])
def test_a_move_keeps_within_its_limits_at_every_sample(m, limits):
    """The rates and accelerations are the trace's own; the jerk is the
    acceleration's slope between samples, a mean of the jerk, so it is held
    to the limit too. The long shoulder travel makes each limit bind."""
    start, end = {"shoulder": -1.5, "elbow": 0.4}, {"shoulder": 1.5,
                                                    "elbow": 1.6}
    t = trace(m, Mission("long", [move(start, end=end, limits=limits)]),
              CONFIRM_RATE)
    for name in start:
        v, a, j = (_on(lim, name) for lim in (limits.v, limits.a, limits.j))
        jerk = np.diff(t.qdd[name]) / np.diff(t.t)
        assert np.max(np.abs(t.qd[name])) <= v * (1 + 1e-9)
        assert np.max(np.abs(t.qdd[name])) <= a * (1 + 1e-9)
        assert np.max(np.abs(jerk)) <= j * (1 + 1e-9)
    leading = "shoulder"  # the longest travel against its limits
    v, a = (_on(lim, leading) for lim in (limits.v, limits.a))
    assert np.max(np.abs(t.qd[leading])) == pytest.approx(v, rel=1e-6)
    assert np.max(np.abs(t.qdd[leading])) == pytest.approx(a, rel=1e-6)


def test_a_move_limited_along_its_path_holds_its_speed_there(m):
    """Limits along the path bound the magnitude of the rate and its
    derivatives, as Plumb's 2.0 m/s does: a diagonal move under v reaches v
    along it, where the same limits on each coordinate reach √2·v."""
    start = {"shoulder": -1.0, "elbow": -1.0}
    end = {"shoulder": 1.0, "elbow": 1.0}
    v, a, j = 0.5, 2.0, 20.0

    def run(along):
        return trace(m, Mission(along, [move(start, end=end, limits=Limits(
            v=v, a=a, j=j, along=along))]), CONFIRM_RATE)

    def magnitude(rates):
        return np.hypot(rates["shoulder"], rates["elbow"])

    path, each = run("path"), run("coordinate")
    speed, accel = magnitude(path.qd), magnitude(path.qdd)
    jerk = np.hypot(*(np.diff(path.qdd[n]) / np.diff(path.t)
                      for n in start))
    assert np.max(speed) <= v * (1 + 1e-9)
    assert np.max(speed) == pytest.approx(v, rel=1e-6)
    assert np.max(accel) == pytest.approx(a, rel=1e-6)
    assert np.max(jerk) <= j * (1 + 1e-9)
    assert np.max(magnitude(each.qd)) == pytest.approx(math.sqrt(2) * v,
                                                       rel=1e-6)
    for name, value in end.items():
        assert path.q[name][-1] == pytest.approx(value, abs=1e-9)
    np.testing.assert_allclose(path.q["elbow"], path.q["shoulder"],
                               atol=1e-12)  # the diagonal, a straight line


def test_limits_name_what_they_bound():
    with pytest.raises(TypeError, match="along"):
        Limits(v=1.0, a=1.0, j=1.0)
    with pytest.raises(ValueError, match="'coordinate', 'path'"):
        Limits(v=1.0, a=1.0, j=1.0, along="axis")
    with pytest.raises(ValueError, match="path"):
        Limits(v={"shoulder": 1.0}, a=1.0, j=1.0, along="path")


# --- the geared pendulum swing -----------------------------------------------
SWING = {"m": 1.0, "lc": 0.2, "Ic": 0.003, "N": 50.0, "Jm": 2e-5, "g": 9.81}
AMPLITUDE, PERIOD = 1.0, 1.0  # rad, s: q(t) = A sin(2π t / T)


def pendulum(p):
    """A bob hanging below a hinge about z, gravity −y, driven through a
    gear N by a motor whose rotor has inertia Jm."""
    return [
        body("bob", mass=p["m"], com=(0, -p["lc"], 0),
             inertia=np.diag([p["Ic"]] * 3)),
        joint("pivot", "hinge", parent="world", child="bob", axis=(0, 0, 1),
              point=(0, 0, 0), range=(-math.pi, math.pi)),
        actuator("motor", joint="pivot", gear=p["N"], rotor_inertia=p["Jm"]),
        gravity((0, -p["g"], 0)),
    ]


W = 2 * math.pi / PERIOD
J_JOINT = SWING["Ic"] + SWING["m"] * SWING["lc"] ** 2  # about the pivot
J_TOTAL = J_JOINT + SWING["N"] ** 2 * SWING["Jm"]      # with the rotor, N²J_m
MGL = SWING["m"] * SWING["g"] * SWING["lc"]


def swing_q(t):
    return {"pivot": AMPLITUDE * math.sin(W * t)}


def swing_qd(t):
    return {"pivot": AMPLITUDE * W * math.cos(W * t)}


def swing_qdd(t):
    return {"pivot": -AMPLITUDE * W ** 2 * math.sin(W * t)}


def motor_torque(t, rotor=True):
    """τ_m = (J q̈ + m g l_c sin q) / N, with J about the pivot plus N²J_m."""
    q = AMPLITUDE * math.sin(W * t)
    qdd = -AMPLITUDE * W ** 2 * math.sin(W * t)
    inertia = J_TOTAL if rotor else J_JOINT
    return (inertia * qdd + MGL * math.sin(q)) / SWING["N"]


def test_a_geared_swing_peaks_and_rms_as_its_closed_form():
    """J ω² > m g l_c, so |τ| grows with |sin ωt| and peaks where the swing
    turns, at t = T/4 and 3T/4, both samples at 1 kHz. The RMS is the
    closed form's integral over the period, by quadrature."""
    assert J_TOTAL * W ** 2 > MGL
    peak = ((J_TOTAL * AMPLITUDE * W ** 2 - MGL * math.sin(AMPLITUDE))
            / SWING["N"])
    square, _ = quad(lambda t: motor_torque(t) ** 2, 0, PERIOD, limit=200,
                     epsabs=0, epsrel=1e-13)
    rms = math.sqrt(square / PERIOD)
    without = math.sqrt(quad(lambda t: motor_torque(t, rotor=False) ** 2, 0,
                             PERIOD, limit=200)[0] / PERIOD)
    assert rms / without > 1.5  # the rotor's N²J_m is no small term here

    m = armature.compile(pendulum, SWING)
    t = trace(m, Mission("swing", [follow(swing_q, PERIOD, qd=swing_qd,
                                          qdd=swing_qdd)]), CONFIRM_RATE)
    assert len(t.t) == 1001 and t.t[-1] == PERIOD
    assert t.peak("motor") == pytest.approx(peak, rel=1e-6)
    assert t.rms("motor") == pytest.approx(rms, rel=1e-6)
    np.testing.assert_allclose(  # motor side: N times the joint's rate
        t.speed["motor"], SWING["N"] * AMPLITUDE * W * np.cos(W * t.t),
        rtol=0, atol=1e-9)
    assert t.gear["motor"] == SWING["N"]


def test_a_trace_splits_out_the_rotors_own_torque():
    """The rotor's share of the motor torque is J_m·ω̇_m = J_m·N·q̈, and the
    rest is the load across the gear: at the output, N(τ − rotor) is the
    swing's joint torque without the rotor, J q̈ + m g l_c sin q, at ω/N."""
    m = armature.compile(pendulum, SWING)
    t = trace(m, Mission("swing", [follow(swing_q, PERIOD, qd=swing_qd,
                                          qdd=swing_qdd)]), CONFIRM_RATE)
    qdd = -AMPLITUDE * W ** 2 * np.sin(W * t.t)
    np.testing.assert_allclose(t.rotor["motor"],
                               SWING["Jm"] * SWING["N"] * qdd, rtol=0,
                               atol=1e-12)
    tau, omega, rotor = t.output("motor")
    load = SWING["N"] * np.array([motor_torque(x, rotor=False)
                                  for x in t.t])
    np.testing.assert_allclose(tau, load, rtol=0,
                               atol=1e-9 * np.max(np.abs(load)))
    np.testing.assert_allclose(omega, AMPLITUDE * W * np.cos(W * t.t),
                               rtol=0, atol=1e-12)
    assert rotor is t.rotor["motor"]


def test_a_followed_q_without_its_rates_is_differenced():
    """The same swing, its rates differenced from q(t) alone, centrally
    inside and one-sided at the ends."""
    m = armature.compile(pendulum, SWING)
    t = trace(m, Mission("swing", [follow(swing_q, PERIOD)]), CONFIRM_RATE)
    exact = np.array([motor_torque(x) for x in t.t])
    np.testing.assert_allclose(t.torque["motor"], exact, rtol=0,
                               atol=1e-6 * np.max(np.abs(exact)))


# --- holds -------------------------------------------------------------------
TIP = (6.0, -15.0, 0.0)  # N, at the tip


def test_a_hold_under_a_tip_load_is_inverse_at_rest(m):
    """Every sample of a 2 s hold reads `inverse` at rest under the load, and
    the 2R arm's closed form, τ = (g(q) − Jᵀ f) / N."""
    posture = {"shoulder": 0.7, "elbow": -1.1}
    t = trace(m, Mission("hold", [hold(posture, 2.0, loads={"tip": TIP})]),
              CONFIRM_RATE)
    direct = m.at(q=posture).inverse(loads={"tip": TIP})
    closed = joint_torque([0.7, -1.1], [0, 0], [0, 0], np.array(TIP))
    assert len(t.t) == 2001 and t.t[-1] == 2.0
    for k, name in enumerate(("shoulder_motor", "elbow_motor")):
        assert np.all(t.torque[name] == direct.torque[name])
        assert direct.torque[name] == pytest.approx(
            closed[k] / ARM[("N1", "N2")[k]], rel=1e-9)
        assert np.all(t.speed[name] == 0.0)
    assert np.all(t.residual <= 1e-9)


def test_a_hold_with_no_posture_holds_where_the_move_ended(m):
    start, end = {"shoulder": 0.0, "elbow": 0.5}, {"shoulder": 0.6,
                                                   "elbow": 1.0}
    t = trace(m, Mission("move then hold", [
        move(start, end=end, limits=LIMITS),
        hold(None, 0.5, loads={"tip": TIP})]), CONFIRM_RATE)
    held = t.segment == 1
    direct = m.at(q=end).inverse(loads={"tip": TIP})
    assert t.spans[1][1] - t.spans[1][0] == pytest.approx(0.5)
    assert np.all(t.torque["shoulder_motor"][held]
                  == direct.torque["shoulder_motor"])
    assert np.all(t.q["elbow"][held] == 1.0)


def test_a_segment_that_jumps_from_where_the_last_ended_raises(m):
    mission = Mission("jump", [hold({"shoulder": 0.2}, 1.0),
                               hold({"shoulder": 0.3}, 1.0)])
    with pytest.raises(ValueError, match="segment 1 .*'shoulder'"):
        trace(m, mission, CONFIRM_RATE)


def test_a_mission_longer_than_its_duty_period_raises(m):
    mission = Mission("long take", [hold({"shoulder": 0.2}, 3.0)],
                      duty=Duty(period=2.0, session=3600.0))
    with pytest.raises(ValueError, match="longer than its duty's period"):
        trace(m, mission, SEARCH_RATE)


# --- the actuation seam ------------------------------------------------------
def test_the_actuation_seam_replaces_inverse(monkeypatch):
    """A seam that returns known traces, on actuators the engine does not
    have: the winch's torque is the swing angle and its speed the swing's
    acceleration, then, through a hold, the load it is handed. `inverse` is
    never called."""
    def refused(*args, **kwargs):
        raise AssertionError("inverse called under an actuation seam")
    monkeypatch.setattr(armature.State, "inverse", refused)

    def winch(state, qdd, loads):
        if loads:
            return {"winch": (loads["tip"][1], 0.0)}
        return {"winch": (state.q["pivot"], qdd["pivot"])}

    def tip(p):
        return pendulum(p) + [armature.site("tip", body="bob",
                                            pos=(0, -0.3, 0))]

    m = armature.compile(tip, SWING)
    t = trace(m, Mission("seam", [
        follow(swing_q, PERIOD, qd=swing_qd, qdd=swing_qdd),
        hold(None, 0.5, loads={"tip": TIP})], actuation=winch), CONFIRM_RATE)
    swung = t.segment == 0
    assert set(t.torque) == {"winch"} and "winch" not in t.gear
    np.testing.assert_allclose(t.torque["winch"][swung],
                               AMPLITUDE * np.sin(W * t.t[swung]), atol=1e-12)
    np.testing.assert_allclose(t.speed["winch"][swung],
                               -AMPLITUDE * W ** 2 * np.sin(W * t.t[swung]),
                               atol=1e-9)
    assert np.all(t.torque["winch"][~swung] == TIP[1])
    assert t.residual is None
    assert np.all(t.rotor["winch"] == 0.0)  # none given, none assumed
    with pytest.raises(KeyError, match="winch"):
        t.output("winch")  # its gear is the project's, not the engine's


def test_an_actuation_seam_may_name_its_rotors_share():
    """A seam that returns (torque, speed, rotor) gives the rotor's share
    of its torque, which `output` takes out before the gear of ratio n."""
    def winch(state, qdd, loads):
        return {"winch": (3.0, 20.0, 0.5)}

    m = armature.compile(pendulum, SWING)
    t = trace(m, Mission("seam", [hold({"pivot": 0.0}, 0.1)],
                         actuation=winch), CONFIRM_RATE)
    assert np.all(t.rotor["winch"] == 0.5)
    tau, omega, _ = t.output("winch", n=4.0)
    assert np.all(tau == 4.0 * (3.0 - 0.5)) and np.all(omega == 5.0)


# --- a closed chain ----------------------------------------------------------
def test_a_five_bar_move_reads_inverse_called_directly():
    """Each sample's torques are `inverse`'s at the same independent q, q̇
    and q̈, the pin closed by `at()`; each speed is N times its joint's
    rate."""
    m = armature.compile(five_bar, FIVE_BAR)
    assert m.independent == ("A", "E")
    t = trace(m, Mission("reach", [
        move({"A": 0.0, "E": 0.0}, end={"A": 0.25, "E": -0.15},
             limits=Limits(v=1.0, a=5.0, j=50.0, along="coordinate")),
        hold(None, 0.2)]), SEARCH_RATE)
    assert len(t.t) > 40
    for k in range(len(t.t)):
        q = {n: t.q[n][k] for n in m.independent}
        qd = {n: t.qd[n][k] for n in m.independent}
        qdd = {n: t.qdd[n][k] for n in m.independent}
        direct = m.at(q=q, qd=qd).inverse(qdd=qdd)
        for name in ("motor_A", "motor_E"):
            assert t.torque[name][k] == pytest.approx(direct.torque[name],
                                                      rel=1e-12, abs=1e-15)
    np.testing.assert_allclose(t.speed["motor_A"], FIVE_BAR["N"] * t.qd["A"],
                               rtol=1e-15)
    assert set(t.qdd) == {"A", "E"} and "B" in t.qd and "B" in t.q
