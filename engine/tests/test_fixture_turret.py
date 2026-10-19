"""Fixture 6: a geared turret.

Answer: the slew's peak motor torque, (J_load/N + N·J_m)·a, J_load = Izz +
m·d² the turret about its bearing and a the move's acceleration limit, which
the quarter turn reaches; the closed forms for the muzzle's pose, the pan's
torque and mass, and the bearing's wrench, written out here by hand.
Trap: the motor sized on the load's inertia alone, J_load·a/N, its own
rotor's N²·J_m left out. Every number in it is right for the turret, and it
reads under half the torque the slew takes.
"""

import math

import numpy as np
import pytest

import armature
from armature.drive import CONFIRM_RATE, trace
from golden import turret
from golden.answers import SLEW_TORQUE

PARAMS = turret.PARAMS
P = PARAMS
SLEW = turret.missions.SLEW
A = turret.missions.LIMITS.a  # the slew's acceleration limit [rad/s^2]
J_LOAD = P["Izz"] + P["m"] * P["d"] ** 2  # the turret about its bearing


def rotorless(p):
    """The trap's description: the turret with its motor's rotor left out."""
    return [armature.actuator("pan_motor", joint="pan", gear=p["N"])
            if getattr(e, "name", None) == "pan_motor" else e
            for e in turret.mechanism(p)]


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
    """At rest the bearing carries the weight and its overturning moment,
    m·g·d; moving, the COM's acceleration too. Along the axis it carries
    the motor's torque less what accelerates the rotor."""
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
    assert np.hypot(*at_rest.torque[:2]) == pytest.approx(
        P["m"] * P["g"] * P["d"], rel=1e-9)


# --- trace: the slew ------------------------------------------------------------
def test_the_slews_peak_torque_is_the_answer(slew):
    """The quarter turn reaches its acceleration limit, and there the motor
    gives the load's share and its own rotor's: τ = (J_load/N + N·J_m)·a."""
    assert np.max(np.abs(slew.qdd["pan"])) == pytest.approx(A, rel=1e-9)
    assert slew.q["pan"][-1] == pytest.approx(math.pi / 2, abs=1e-9)
    assert SLEW_TORQUE.value == pytest.approx(0.0224, rel=1e-9)
    assert slew.peak("pan_motor") == pytest.approx(SLEW_TORQUE.value,
                                                   rel=1e-9)


def test_the_rotors_share_is_what_the_trap_leaves_out(slew):
    """The trace keeps the rotor's share apart, J_m·N·q̈ at the motor, and
    the load across the gear is the rest: at the output, J_load·q̈. The
    rotor's share is the larger."""
    assert slew.rotor["pan_motor"] == pytest.approx(
        P["J_m"] * P["N"] * slew.qdd["pan"], rel=1e-9, abs=1e-15)
    out, _, _ = slew.output("pan_motor")
    assert out == pytest.approx(J_LOAD * slew.qdd["pan"], rel=1e-9,
                                abs=1e-12)
    assert np.max(np.abs(slew.rotor["pan_motor"])) > np.max(
        np.abs(slew.torque["pan_motor"] - slew.rotor["pan_motor"]))


# --- the trap, shown failing ---------------------------------------------------
def test_the_motor_sized_on_the_load_alone_misses_the_slew():
    """The rotorless description traces the slew at J_load·a/N, the bait,
    under half the answer and outside its window."""
    wrong = trace(armature.compile(rotorless, PARAMS), SLEW,
                  CONFIRM_RATE).peak("pan_motor")
    assert wrong == pytest.approx(J_LOAD / P["N"] * A, rel=1e-9)
    assert wrong == pytest.approx(SLEW_TORQUE.bait, rel=1e-9)
    assert not SLEW_TORQUE.inside(wrong)
    assert wrong < 0.5 * SLEW_TORQUE.value


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="the trap: the load alone is under half the "
                          "slew's torque")
def test_the_load_only_trap_holds_the_slews_torque(slew):
    """The check a derivation writes for its load-only sizing: that the
    slew's peak motor torque is J_load·a/N. It must fail."""
    assert slew.peak("pan_motor") == pytest.approx(J_LOAD / P["N"] * A,
                                                   rel=0.02)
