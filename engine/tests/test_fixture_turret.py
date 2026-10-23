"""Fixture 6: a geared turret.

Answer: the bearing's peak moment in the slew, m·d·√((g + h·ω₁²)² +
(h·a)²), where the pan ends its constant acceleration a at ω₁ = v − a²/2j:
the weight's moment m·g·d, the COM d off the axis, and the inertial loads
the slew puts on the COM at its height h. The closed forms for the muzzle's
pose, the pan's torque and mass, the bearing's wrench and the slew's motor
torque, written out here by hand.
Trap: the bearing checked on its axial load alone, the turret's weight,
its moment left out. Every number in it is right for the turret, and it
passes a bearing the slew overloads.
"""

import math

import numpy as np
import pytest

import armature
from armature.drive import CONFIRM_RATE, trace
from golden import turret
from golden.answers import BEARING_MOMENT

PARAMS = turret.PARAMS
P = PARAMS
RATED = turret.params.BEARING
SLEW = turret.missions.SLEW
LIMITS = turret.missions.LIMITS
A = LIMITS.a  # the slew's acceleration limit [rad/s^2]
J_LOAD = P["Izz"] + P["m"] * P["d"] ** 2  # the turret about its bearing

SEED = 20261018

# --- the closed forms ---------------------------------------------------------


def muzzle(q):
    return np.array([P["reach"] * math.cos(q), P["reach"] * math.sin(q),
                     P["h"]])


def bearing_wrench(q, qd, qdd):
    """Newton–Euler on the turret: the force and the torque about the
    bearing's point that the world exerts on it. Its inertia is symmetric
    about the axis, so ω × Iω vanishes."""
    com = np.array([P["d"] * math.cos(q), P["d"] * math.sin(q), P["h"]])
    accel = P["d"] * np.array([-math.sin(q) * qdd - math.cos(q) * qd ** 2,
                               math.cos(q) * qdd - math.sin(q) * qd ** 2, 0])
    weight = P["m"] * np.array([0, 0, -P["g"]])
    force = P["m"] * accel - weight
    return force, np.array([0, 0, P["Izz"] * qdd]) + np.cross(com, force)


def moment(w):
    """The moment a wrench puts across the bearing's axis."""
    return float(np.hypot(*w.torque[:2]))


def sampled_states(n, seed=SEED):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        yield (float(rng.uniform(-3.0, 3.0)), float(rng.uniform(-2.0, 2.0)),
               float(rng.uniform(-8.0, 8.0)))


@pytest.fixture(scope="module")
def m():
    return armature.compile(turret.mechanism, PARAMS)


@pytest.fixture(scope="module")
def slew(m):
    return trace(m, SLEW, CONFIRM_RATE)


@pytest.fixture(scope="module")
def slew_wrenches(m, slew):
    """The bearing's wrench at every sample of the slew."""
    return [m.at(q={"pan": q}, qd={"pan": qd}).wrench("turret",
                                                       qdd={"pan": qdd})
            for q, qd, qdd in zip(slew.q["pan"], slew.qd["pan"],
                                  slew.qdd["pan"])]


# --- kinematics ---------------------------------------------------------------
@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(4)))
def test_the_muzzles_pose_and_jacobian_are_the_closed_forms(m, q, qd, qdd):
    s = m.at(q={"pan": q})
    pose, jac = s.pose(turret.TOOL), s.jacobian(turret.TOOL)
    assert pose.position == pytest.approx(muzzle(q), abs=1e-12)
    assert pose.rotation == pytest.approx(
        np.array([[math.cos(q), -math.sin(q), 0],
                  [math.sin(q), math.cos(q), 0], [0, 0, 1]]), abs=1e-12)
    assert jac.linear == pytest.approx(np.array(
        [[-P["reach"] * math.sin(q)], [P["reach"] * math.cos(q)], [0]]),
        abs=1e-12)
    assert jac.angular == pytest.approx(np.array([[0], [0], [1]]), abs=1e-12)
    assert jac.dofs == ("pan",)


# --- dynamics -----------------------------------------------------------------
@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(6)))
def test_the_pans_torque_is_its_inertia_and_its_rotors(m, q, qd, qdd):
    """τ = (J_load/N + N·J_m)·q̈ at the motor, whatever the pan's angle or
    rate: the axis is vertical, so there is no gravity torque, and the
    COM's centripetal pull runs through the axis."""
    inv = m.at(q={"pan": q}, qd={"pan": qd}).inverse(qdd={"pan": qdd})
    total = J_LOAD + P["N"] ** 2 * P["J_m"]
    assert inv.torque["pan_motor"] == pytest.approx(total / P["N"] * qdd,
                                                    rel=1e-9, abs=1e-12)
    assert inv.generalised["pan"] == pytest.approx(total * qdd, rel=1e-9,
                                                   abs=1e-12)
    assert inv.residual < 1e-12


@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(4)))
def test_the_pans_mass_is_the_load_and_the_reflected_rotor(m, q, qd, qdd):
    lin = m.at(q={"pan": q}).linearise()
    assert lin.mass == pytest.approx(
        np.array([[J_LOAD + P["N"] ** 2 * P["J_m"]]]), rel=1e-12)
    assert lin.stiffness == pytest.approx(np.zeros((1, 1)), abs=1e-6)


def test_released_with_the_motor_off_it_stays(m):
    """Nothing turns the pan at rest: let go anywhere, it stays there."""
    settled = m.at(q={"pan": 1.1}).settle()
    assert settled.stable
    assert abs(settled.moved["pan"]) < 1e-6


@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(6)))
def test_the_bearings_wrench_is_the_closed_form(m, q, qd, qdd):
    """At rest the bearing carries the weight and its moment, m·g·d;
    moving, the COM's acceleration too. Along the axis it carries the
    motor's torque less what accelerates the rotor."""
    s = m.at(q={"pan": q}, qd={"pan": qd})
    w = s.wrench("turret", qdd={"pan": qdd})
    force, torque = bearing_wrench(q, qd, qdd)
    assert w.joint == "pan"
    assert w.point == pytest.approx([0, 0, 0], abs=1e-12)
    assert w.force == pytest.approx(force, abs=1e-9)
    assert w.torque == pytest.approx(torque, abs=1e-9)
    inv = s.inverse(qdd={"pan": qdd})
    assert w.torque[2] == pytest.approx(
        P["N"] * inv.torque["pan_motor"] - P["N"] ** 2 * P["J_m"] * qdd,
        rel=1e-9, abs=1e-12)
    at_rest = m.at(q={"pan": q}).wrench("turret")
    assert moment(at_rest) == pytest.approx(P["m"] * P["g"] * P["d"],
                                            rel=1e-9)


# --- the bearing in the slew ----------------------------------------------------
def test_the_bearings_peak_moment_in_the_slew_is_the_answer(slew_wrenches):
    """The moment peaks where the pan ends its constant acceleration, at
    its full a and the most rate it has there: m·d·√((g + h·ω₁²)² +
    (h·a)²). It is over the bearing's moment rating, which the weight's
    m·g·d alone is under, and the axial load is the weight throughout."""
    peak = max(map(moment, slew_wrenches))
    assert peak == pytest.approx(BEARING_MOMENT.value, rel=1e-3)
    assert BEARING_MOMENT.value > RATED["moment"]
    assert P["m"] * P["g"] * P["d"] < RATED["moment"]
    assert [w.force[2] for w in slew_wrenches] == pytest.approx(
        [P["m"] * P["g"]] * len(slew_wrenches), rel=1e-9)


# --- the trap, shown failing ---------------------------------------------------
def test_the_bearing_checked_on_its_weight_alone_passes_a_slew_it_fails(
        slew_wrenches):
    """The trap's check: the weight, the bearing's whole axial load, under
    the axial rating, and no moment, under the moment rating. It passes a
    bearing whose moment in the slew is over that rating, and the bait lies
    outside the answer's window."""
    axial = max(abs(w.force[2]) for w in slew_wrenches)
    assert axial < RATED["axial"] and BEARING_MOMENT.bait < RATED["moment"]
    assert not BEARING_MOMENT.inside(BEARING_MOMENT.bait)
    assert max(map(moment, slew_wrenches)) > RATED["moment"]


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="the trap: the bearing carries the weight's "
                          "moment and the slew's, over its rating")
def test_the_weight_only_trap_holds_the_bearings_moment(slew_wrenches):
    """The check a derivation writes for its axial-only sizing: that the
    bearing carries no moment through the slew. It must fail."""
    assert max(map(moment, slew_wrenches)) == pytest.approx(
        BEARING_MOMENT.bait, abs=0.02 * RATED["moment"])


# --- trace: the slew's motor torque --------------------------------------------
def test_the_slews_peak_torque_is_the_closed_form(slew):
    """The quarter turn reaches its rate and acceleration limits, and at
    the second the motor gives the load's share and its own rotor's:
    τ = (J_load/N + N·J_m)·a."""
    assert np.max(np.abs(slew.qdd["pan"])) == pytest.approx(A, rel=1e-9)
    assert np.max(np.abs(slew.qd["pan"])) == pytest.approx(LIMITS.v,
                                                           rel=1e-9)
    assert slew.q["pan"][-1] == pytest.approx(math.pi / 2, abs=1e-9)
    assert slew.peak("pan_motor") == pytest.approx(
        (J_LOAD / P["N"] + P["N"] * P["J_m"]) * A, rel=1e-9)


def test_the_trace_keeps_the_rotors_share_apart(slew):
    """The trace keeps the rotor's share apart, J_m·N·q̈ at the motor, and
    the load across the gear is the rest: at the output, J_load·q̈."""
    assert slew.rotor["pan_motor"] == pytest.approx(
        P["J_m"] * P["N"] * slew.qdd["pan"], rel=1e-9, abs=1e-15)
    out, _, _ = slew.output("pan_motor")
    assert out == pytest.approx(J_LOAD * slew.qdd["pan"], rel=1e-9,
                                abs=1e-12)


# --- the equations -------------------------------------------------------------

def test_the_equations_are_mujocos(m):
    """M and C q̇ + g, formed by the engine, against MuJoCo's at sampled
    states, projected onto the independent coordinates where there is a
    loop."""
    from mujoco_equations import assert_agree, sampled

    assert_agree(armature.equations(turret.mechanism, PARAMS), sampled(m, 10, SEED))
