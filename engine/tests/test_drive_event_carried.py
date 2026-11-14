"""What an event's mechanism carried: each loop's force and each joint's
wrench, at every sample, from MuJoCo's solution of that step.

Answer: the explicit solve at the same sample, `State.inverse` for a loop's
force and `State.wrench` for a joint's, from the sample's state and the
accelerations the event recorded, never from the event module. The two
read the same motion two ways: the event's loop is MuJoCo's soft
constraint, held to its path by the step, the explicit solve's an exact
closure, so they agree to first order in the step, and halving it halves
the gap. Along a hinge's axis nothing is soft, and they agree exactly. On
an open chain under a load the explicit wrench is the event's own, to
rounding.
"""

import math
from types import MappingProxyType

import numpy as np
import pytest

import armature
from armature import State, actuator, body, gravity, joint, site
from armature.drive import Carried, Limits, Mission, after, event, move, trace

from test_drive_event import BAR_MOTORS, drive
from test_fixture_five_bar import PARAMS as FIVE_BAR, five_bar


def _state(m, tr, k):
    q = {n: float(tr.q[n][k]) for n in m.coordinates}
    qd = {d: float(tr.qd[d][k]) for d in m.dofs}
    return State(m, MappingProxyType(q), MappingProxyType(qd))


@pytest.fixture(scope="module")
def stopped():
    """The five-bar's e-stop: both motors shorted halfway through a
    reach."""
    m = armature.compile(five_bar, FIVE_BAR)
    reach = move({"A": 0.0, "E": 0.0}, end={"A": 0.25, "E": -0.15},
                 limits=Limits(v=2.0, a=20.0, j=400.0, along="coordinate"))
    stop = event(after(reach, 0.5), {a: "short" for a in BAR_MOTORS}, 0.3)
    t = trace(m, Mission("e-stop", [reach, stop]), 1000.0,
              drive=drive(tuple(BAR_MOTORS), 20.0))
    return m, t.events[0]


def _gaps(m, run, every=40):
    """The largest gap, over every `every`-th sample, between what the
    event recorded and what the explicit solve reads there: the loop's
    force, the knees' forces and their torques along the axis; and the
    largest force."""
    tr = run.trace
    loop = force = axial = largest = 0.0
    for k in range(0, len(tr.t), max(1, len(tr.t) // every)):
        s = _state(m, tr, k)
        qdd = {d: float(tr.qdd[d][k]) for d in tr.qdd}
        pin = np.asarray(s.inverse(qdd=qdd).constraint["pin"])
        loop = max(loop, float(np.max(np.abs(pin - run.loops["pin"][k]))))
        largest = max(largest, float(np.max(np.abs(pin))))
        for joint, child in (("B", "l2"), ("D", "l4")):
            w, c = s.wrench(child, qdd=qdd), run.joints[joint]
            force = max(force, float(np.max(np.abs(w.force - c.force[k]))))
            axial = max(axial, abs(float(w.torque[2] - c.torque[k][2])))
            largest = max(largest, float(np.max(np.abs(w.force))))
            np.testing.assert_allclose(c.point[k], w.point, atol=1e-12)
    return loop, force, axial, largest


def test_an_event_records_the_loops_force_and_the_knees_wrench(stopped):
    m, simulated = stopped
    run = simulated.run
    assert set(run.loops) == {"pin"}
    assert set(run.joints) == {"A", "B", "E", "D"}
    assert isinstance(run.joints["B"], Carried)
    n = len(run.trace.t)
    assert run.loops["pin"].shape == (n, 3)
    assert run.joints["B"].force.shape == (n, 3)
    loop, force, axial, largest = _gaps(m, run)
    assert loop < 1e-3 * largest and force < 1e-3 * largest
    assert axial < 1e-9  # the spring at B and nothing soft


def test_halving_the_step_halves_the_gap(stopped):
    m, simulated = stopped
    coarse = _gaps(m, simulated.run)
    fine = _gaps(m, simulated.half)
    for a, b in zip(coarse[:2], fine[:2]):
        assert 1.6 < a / b < 2.4


def hung(p):
    """A bob on a pivot about z under gravity −y, a load at its tip."""
    return [body("bob", mass=1.0, com=(0, -0.4, 0),
                 inertia=np.diag([1e-3] * 3)),
            joint("pivot", "hinge", parent="world", child="bob",
                  axis=(0, 0, 1), point=(0, 0, 0), range=(-math.pi, math.pi)),
            site("tip", body="bob", pos=(0, -0.5, 0)),
            actuator("motor", joint="pivot"),
            gravity((0, -9.81, 0))]


def test_a_load_is_carried_where_it_acts():
    """An open chain: the explicit wrench, with the load applied at its
    site as the event applies it, is the event's own to rounding."""
    m = armature.compile(hung, {})
    load = {"tip": (3.0, 1.0, 0.5)}
    start = m.at(q={"pivot": 0.3}, qd={"pivot": -1.0})
    run = trace(m, Mission("pushed", [event(start, {"motor": "coast"}, 0.05,
                                            loads=load, timestep=1e-4)]),
                1000.0, drive=drive(("motor",), 1.0)).events[0].run
    tr = run.trace
    for k in (0, 100, len(tr.t) - 1):
        s = _state(m, tr, k)
        w = s.wrench("bob", qdd={"pivot": float(tr.qdd["pivot"][k])},
                     loads=load)
        np.testing.assert_allclose(run.joints["pivot"].force[k], w.force,
                                   atol=1e-9)
        np.testing.assert_allclose(run.joints["pivot"].torque[k], w.torque,
                                   atol=1e-9)


def test_an_event_without_loops_records_none():
    m = armature.compile(hung, {})
    run = trace(m, Mission("swing", [event(m.at(q={"pivot": 0.3}),
                                           {"motor": "coast"}, 0.01)]),
                1000.0, drive=drive(("motor",), 1.0)).events[0].run
    assert dict(run.loops) == {}
    assert set(run.joints) == {"pivot"}
