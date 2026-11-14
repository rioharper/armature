"""A stop that gives past its face: a joint's linear spring, one-sided.

Answer: a pendulum turning about z, gravity along −z, so nothing but the
stops and the motor torques it, its inertia about the pivot
I = m l² + I_c. Past a low face q_f a stop of stiffness k pushes with
k (q_f − q), past a high face with −k (q − q_f), and inside both with
nothing. Met at ω₀, a lone linear stop brings the joint to rest
ω₀ √(I/k) past its face, carrying k ω₀ √(I/k) there, and gives the swing
back at −ω₀, a linear oscillator's half cycle. Held by a constant torque τ
into a stop, the joint rests τ/k past its face.
"""

import math

import numpy as np
import pytest

import armature
from armature import (DescriptionError, actuator, body, gravity, joint, lock,
                      stop)
from armature.drive import Mission, event, trace

from test_drive_event import drive

P = {"m": 1.0, "l": 0.5, "Ic": 1e-4, "k": 50.0, "lo": -0.2, "hi": 0.3,
     "kh": 100.0}
I = P["m"] * P["l"] ** 2 + P["Ic"]  # about the pivot


def pendulum(p, **change):
    elements = {
        "bob": body("bob", mass=p["m"], com=(p["l"], 0, 0),
                    inertia=np.diag([p["Ic"]] * 3)),
        "pivot": joint("pivot", "hinge", parent="world", child="bob",
                       axis=(0, 0, 1), point=(0, 0, 0), range=(-1.0, 1.0)),
        "low": stop("low", joint="pivot", face=p["lo"], stiffness=p["k"],
                    side="low"),
        "high": stop("high", joint="pivot", face=p["hi"], stiffness=p["kh"],
                     side="high"),
        "motor": actuator("motor", joint="pivot"),
        "gravity": gravity((0, 0, -9.81)),
    }
    elements.update(change)
    return [e for e in elements.values() if e is not None]


@pytest.fixture(scope="module")
def m():
    return armature.compile(pendulum, P)


def pushed(q):
    """The stops' torque at q, worked from the faces."""
    if q < P["lo"]:
        return P["k"] * (P["lo"] - q)
    if q > P["hi"]:
        return -P["kh"] * (q - P["hi"])
    return 0.0


@pytest.mark.parametrize("q", [-0.6, -0.2, -0.1, 0.0, 0.3, 0.31, 0.7])
def test_a_stop_pushes_only_past_its_face(m, q):
    """`inverse` holds the joint against what the stops push with, and
    nothing inside the faces."""
    torque = m.at(q={"pivot": q}).inverse().torque["motor"]
    assert torque == pytest.approx(-pushed(q), abs=1e-12)


def test_settle_rests_where_the_held_torque_meets_the_stop(m):
    tau = 6.0
    settled = m.at().settle(hold={"motor": -tau})
    assert settled.stable
    assert settled.q["pivot"] == pytest.approx(P["lo"] - tau / P["k"],
                                               abs=1e-6)


def coasting():
    return drive(("motor",), r=1.0)


@pytest.mark.parametrize("w0", [-3.0, -6.0])
def test_a_lone_stop_arrests_the_joint_through_its_closed_form(m, w0):
    """Met at ω₀ from inside the faces, the joint goes ω₀ √(I/k) past the
    face, carrying k ω₀ √(I/k) there as the wrench along its axis, and
    swings back at −ω₀. The coasting motor's back-EMF stays far under its
    diodes' onset, so nothing brakes it."""
    give = abs(w0) * math.sqrt(I / P["k"])
    arrest = math.pi * math.sqrt(I / P["k"])  # the half cycle in the stop
    start = m.at(q={"pivot": P["lo"]}, qd={"pivot": w0})
    run = trace(m, Mission("arrest", [event(start, {"motor": "coast"},
                                            1.2 * arrest, timestep=1e-5)]),
                1000.0, drive=coasting()).events[0].run
    q, qd = run.trace.q["pivot"], run.trace.qd["pivot"]
    deepest = int(np.argmin(q))
    assert P["lo"] - q[deepest] == pytest.approx(give, rel=1e-4)
    axial = run.joints["pivot"].torque[deepest, 2]
    assert axial == pytest.approx(P["k"] * give, rel=1e-4)
    back = np.flatnonzero(q > P["lo"])
    assert qd[back[back > deepest][0]] == pytest.approx(-w0, rel=1e-3)


def test_a_stop_on_a_locked_joint_goes_with_it():
    held = armature.reduce(pendulum, lock("pivot", 0.0, assumption="A1"))
    assert armature.compile(held, P).model.ntendon == 0


def test_the_equations_leave_the_stops_out():
    """The symbolic view, like the equations, holds on the faces' free
    side: with and without the stops it is the same."""
    bare = armature.equations(lambda p: pendulum(p, low=None, high=None),
                              {k: v for k, v in P.items()
                               if k not in ("k", "lo", "hi", "kh")})
    stopped = armature.equations(pendulum, P)
    assert (stopped.M - bare.M).applyfunc(lambda e: e.simplify()).is_zero_matrix
    assert (stopped.g - bare.g).applyfunc(lambda e: e.simplify()).is_zero_matrix


def test_the_frames_table_lists_each_stop():
    row = armature.frames(pendulum, P).row("Stops", "low")
    assert (row["joint"], row["face"], row["side"], row["stiffness"]) == (
        "pivot", P["lo"], "low", P["k"])


@pytest.mark.parametrize("change, message", [
    ({"low": stop("low", joint="elbow", face=0.0, stiffness=1.0,
                  side="low")}, "joint 'elbow' is not declared"),
    ({"low": stop("low", joint="pivot", face=0.0, stiffness=1.0,
                  side="below")}, "side 'below'"),
    ({"low": stop("low", joint="pivot", face=0.0, stiffness=0.0,
                  side="low")}, "stiffness 0.0 must be positive"),
    ({"low": stop("low", joint="pivot", face=1.5, stiffness=1.0,
                  side="low")}, "face 1.5 is outside joint 'pivot'"),
])
def test_a_wrong_stop_is_named(change, message):
    with pytest.raises(DescriptionError) as err:
        armature.compile(lambda p: pendulum(p, **change), P)
    assert "stop 'low'" in str(err.value) and message in str(err.value)


def test_a_stop_on_a_free_joint_is_refused():
    def floating(p):
        return [body("block", mass=1.0, com=(0, 0, 0),
                     inertia=np.diag([1e-3] * 3)),
                joint("body", "free", parent="world", child="block",
                      point=(0, 0, 0)),
                stop("s", joint="body", face=0.0, stiffness=1.0, side="low")]
    with pytest.raises(DescriptionError, match="stop 's': joint 'body' is a "
                                               "free joint"):
        armature.compile(floating, {})
