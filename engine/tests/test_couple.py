"""A couple ties one coordinate to another, as a belt or a gear pair does,
and the queries carry it as a constraint row.

Answer: the 2R arm with the elbow tied to the shoulder, q2 = r q1, and only
the shoulder driven. Virtual work gives the couple's force as the elbow's
gravity torque g2, and the shoulder motor's torque as (g1 + r g2) / N1.
"""

import math

import numpy as np
import pytest

import armature
from armature import actuator, body, couple, gravity, joint

P = {"l1": 0.30, "lc1": 0.15, "lc2": 0.125, "m1": 1.20, "m2": 0.80,
     "I": 0.006, "g": 9.81, "N1": 50.0, "N2": 30.0}
RATIO = 0.5


def arm(p, both=False):
    """Fixture 1's planar arm, gravity along −y, both links along +x."""
    i = np.diag([p["I"]] * 3)
    out = [
        body("upper", mass=p["m1"], com=(p["lc1"], 0, 0), inertia=i),
        body("fore", mass=p["m2"], com=(p["l1"] + p["lc2"], 0, 0), inertia=i),
        joint("shoulder", "hinge", parent="world", child="upper",
              axis=(0, 0, 1), point=(0, 0, 0), range=(-math.pi, math.pi)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 0, 1),
              point=(p["l1"], 0, 0), range=(-2.6, 2.6)),
        actuator("shoulder_motor", joint="shoulder", gear=p["N1"]),
        gravity((0, -p["g"], 0)),
    ]
    if both:
        out.append(actuator("elbow_motor", joint="elbow", gear=p["N2"]))
    return out


TIED = armature.reduce(arm, couple("elbow", "shoulder", RATIO,
                                   assumption="A4"), name="belted elbow")


def gravity_torque(q1):
    q12 = q1 + RATIO * q1
    g1 = P["g"] * ((P["m1"] * P["lc1"] + P["m2"] * P["l1"]) * math.cos(q1)
                   + P["m2"] * P["lc2"] * math.cos(q12))
    g2 = P["g"] * P["m2"] * P["lc2"] * math.cos(q12)
    return g1, g2


@pytest.fixture(scope="module")
def m():
    return armature.compile(TIED, P)


def test_the_follower_is_solved(m):
    assert m.constraints == ("elbow",)
    assert m.independent == ("shoulder",)
    s = m.at(q={"shoulder": 0.4}, qd={"shoulder": 2.0})
    assert s.q["elbow"] == pytest.approx(0.2, abs=1e-14)
    assert s.qd["elbow"] == pytest.approx(1.0, abs=1e-14)
    with pytest.raises(ValueError, match="solved, not given"):
        m.at(q={"elbow": 0.1})


@pytest.mark.parametrize("q1", [-1.1, 0.0, 0.4, 1.3])
def test_the_couple_is_a_constraint_row(m, q1):
    inv = m.at(q={"shoulder": q1}).inverse()
    g1, g2 = gravity_torque(q1)
    assert inv.constraint["elbow"] == pytest.approx(g2, rel=1e-12)
    assert inv.torque["shoulder_motor"] == pytest.approx(
        (g1 + RATIO * g2) / P["N1"], rel=1e-12)
    assert (inv.rank, inv.unknowns) == (2, 2)


def test_two_motors_on_a_coupled_pair_split_the_load_any_way():
    both = armature.reduce(lambda p: arm(p, both=True),
                           couple("elbow", "shoulder", RATIO, assumption="A4"))
    inv = armature.compile(both, P).at(q={"shoulder": 0.4}).inverse()
    assert (inv.rank, inv.unknowns) == (2, 3)
    assert math.isnan(inv.torque["shoulder_motor"])
    assert math.isnan(inv.torque["elbow_motor"])
    assert inv.residual < 1e-12


def test_the_full_description_has_no_couple(m):
    assert m.full.constraints == ()
    assert m.full.coordinates == ("shoulder", "elbow")


def test_symbolic_closure_of_a_couple():
    view = armature.symbolic(TIED, P)
    q1, q2 = view.q["shoulder"], view.q["elbow"]
    assert view.closures["elbow"] - (q2 - RATIO * q1) == 0


def test_a_settle_holds_the_couple(m):
    """The compiled joint equality, which only a settle leans on, ties the
    same way as the row."""
    s = m.at(q={"shoulder": 0.4})
    settled = s.settle(dict(s.inverse().torque))
    assert settled.stable
    assert abs(settled.moved["shoulder"]) < 1e-5
    assert settled.q["elbow"] == pytest.approx(
        RATIO * settled.q["shoulder"], abs=1e-6)
