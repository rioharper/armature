"""A contact between two moving bodies: `against=(other, shape)`.

Answer, worked here from the geometry and Newton's laws:
- Two spheres of radius r on vertical slides, the upper's centre dx to the
  side of the lower's, the lower on a frictionless floor. At rest the upper
  presses along the line of centres, n = (dx, 0, h)/2r with
  h = √(4r² − dx²), with N = m_u g 2r/h, so that N n_z = m_u g. Its slide
  carries N n_x back, the lower's slide the opposite, and the floor holds
  (m_l + m_u) g.
- Two blocks on one frictionless line, the first sliding into the second
  at rest: the contact is internal, so their momentum m₁v₁ + m₂v₂ stays
  m₁v₀, and the impulse the second takes, ∫N dt, is m₂v₂ after.
"""

import math

import numpy as np
import pytest

import armature
from armature import (DescriptionError, actuator, body, contact, gravity,
                      joint, shape)
from armature.drive import Mission, event, trace

from test_drive_event import drive

R, DX, G = 0.1, 0.03, 9.81
M_LOW, M_UP = 1.0, 0.5
H = math.sqrt(4 * R ** 2 - DX ** 2)
FLOOR = shape("plane", pos=(0, 0, 0), axis=(0, 0, 1))


def stacked(p, **change):
    """The lower sphere's centre at z = r, on the floor; the upper's at
    z = r + h + gap, dx to its side."""
    low, up = (0.0, 0.0, R), (DX, 0.0, R + H + p["gap"])
    elements = {
        "lower": body("lower", mass=M_LOW, com=low, inertia=np.diag([1e-3] * 3)),
        "upper": body("upper", mass=M_UP, com=up, inertia=np.diag([1e-3] * 3)),
        "zl": joint("zl", "slide", parent="world", child="lower",
                    axis=(0, 0, 1), point=low, range=(-1, 1)),
        "zu": joint("zu", "slide", parent="world", child="upper",
                    axis=(0, 0, 1), point=up, range=(-1, 1)),
        "floor": contact("floor", body="lower",
                         shape=shape("sphere", pos=low, radius=R),
                         against=FLOOR, mu=0),
        "touch": contact("touch", body="upper",
                         shape=shape("sphere", pos=up, radius=R),
                         against=("lower", shape("sphere", pos=low, radius=R)),
                         mu=0),
        "gravity": gravity((0, 0, -G)),
    }
    elements.update(change)
    return list(elements.values())


N_TOUCH = M_UP * G * 2 * R / H  # along the line of centres
SIDEWAYS = N_TOUCH * DX / (2 * R)  # its horizontal share


def test_the_pair_joins_the_two_bodies():
    m = armature.compile(stacked, {"gap": 0.0})
    model, pair = m.model, m.model.pair("touch").id
    held = {model.geom_bodyid[model.pair_geom1[pair]],
            model.geom_bodyid[model.pair_geom2[pair]]}
    assert held == {model.body("lower").id, model.body("upper").id}


def test_the_clearance_is_the_gap_between_the_spheres():
    gap = 0.004
    m = armature.compile(stacked, {"gap": gap})
    expected = math.hypot(DX, H + gap) - 2 * R
    assert armature.clearance(m.at(), "touch") == pytest.approx(expected,
                                                                abs=1e-12)


@pytest.fixture(scope="module")
def settled():
    m = armature.compile(stacked, {"gap": 0.002})
    out = m.at().settle()
    assert out.stable
    return m, out


def test_settle_reads_the_upper_body_resting_on_the_lower(settled):
    _, rest = settled
    assert rest.contacts["touch"].normal == pytest.approx(N_TOUCH, rel=1e-6)
    assert rest.contacts["floor"].normal == pytest.approx(
        (M_LOW + M_UP) * G, rel=1e-6)


def test_inverse_carries_both_contacts_at_the_rest(settled):
    m, rest = settled
    inv = m.at(q=dict(rest.q)).inverse()
    assert inv.contacts["touch"].normal == pytest.approx(N_TOUCH, rel=1e-9)
    assert inv.contacts["floor"].normal == pytest.approx(
        (M_LOW + M_UP) * G, rel=1e-9)
    assert inv.residual < 1e-9


def test_each_slide_carries_the_contacts_sideways_share(settled):
    """The wrench across each slide: the upper's holds it back from the
    contact's push, the lower's from the push's opposite. The settle rests
    within 10 nm of touching, which turns the normal by about 1e-7 of the
    worked one."""
    m, rest = settled
    s = m.at(q=dict(rest.q))
    upper, lower = s.wrench("upper"), s.wrench("lower")
    assert upper.force[0] == pytest.approx(-SIDEWAYS, rel=1e-6)
    assert lower.force[0] == pytest.approx(SIDEWAYS, rel=1e-6)
    assert upper.force[0] == pytest.approx(-lower.force[0], rel=1e-12)
    assert upper.force[2] == pytest.approx(0.0, abs=1e-9)  # along the slide


def blocks(p):
    """Two cubes on slides along x, the first ahead of the second by a
    gap, a coasting motor on each slide so that an event can run them."""
    one, two = (0.0, 0.0, 0.0), (0.1 + p["gap"], 0.0, 0.0)
    side = (0.05, 0.05, 0.05)
    return [
        body("one", mass=p["m1"], com=one, inertia=np.diag([1e-3] * 3)),
        body("two", mass=p["m2"], com=two, inertia=np.diag([1e-3] * 3)),
        joint("x1", "slide", parent="world", child="one", axis=(1, 0, 0),
              point=one, range=(-1, 1)),
        joint("x2", "slide", parent="world", child="two", axis=(1, 0, 0),
              point=two, range=(-1, 1)),
        actuator("m1", joint="x1"), actuator("m2", joint="x2"),
        contact("hit", body="one", shape=shape("box", pos=one,
                                               half_sizes=side),
                against=("two", shape("box", pos=two, half_sizes=side)),
                mu=0),
        gravity((0, 0, -G)),
    ]


def test_a_collision_between_two_bodies_keeps_their_momentum():
    p = {"gap": 0.002, "m1": 1.0, "m2": 2.0}
    v0 = 0.5
    m = armature.compile(blocks, p)
    start = m.at(qd={"x1": v0})
    run = trace(m, Mission("hit", [event(start, {"m1": "coast",
                                                 "m2": "coast"}, 0.05,
                                         timestep=1e-5)]),
                1000.0, drive=drive(("m1", "m2"), r=1.0)).events[0].run
    tr = run.trace
    v1, v2 = tr.qd["x1"], tr.qd["x2"]
    momentum = p["m1"] * v1 + p["m2"] * v2
    np.testing.assert_allclose(momentum, p["m1"] * v0, rtol=1e-9)
    assert v2[-1] > 0.25 * v0  # it was hit
    normal = np.array([c["hit"].normal if "hit" in c else 0.0
                       for c in run.contacts])
    impulse = float(np.sum(normal[:-1] * np.diff(tr.t)))
    assert impulse == pytest.approx(p["m2"] * v2[-1], rel=2e-3)


@pytest.mark.parametrize("against, message", [
    (("ghost", shape("sphere", pos=(0, 0, R), radius=R)),
     "against's body 'ghost' is not declared"),
    (("upper", shape("sphere", pos=(0, 0, R), radius=R)),
     "the moving body itself"),
    (("lower", shape("plane", pos=(0, 0, 0), axis=(0, 0, 1))),
     "a plane is fixed to the world"),
])
def test_a_wrong_contact_between_bodies_is_named(against, message):
    wrong = contact("touch", body="upper",
                    shape=shape("sphere", pos=(DX, 0, R + H), radius=R),
                    against=against, mu=0)
    with pytest.raises(DescriptionError) as err:
        armature.compile(lambda p: stacked(p, touch=wrong), {"gap": 0.0})
    assert "contact 'touch'" in str(err.value) and message in str(err.value)


def test_a_compliance_between_two_bodies_is_refused():
    soft = contact("touch", body="upper",
                   shape=shape("sphere", pos=(DX, 0, R + H), radius=R),
                   against=("lower", shape("sphere", pos=(0, 0, R),
                                           radius=R)),
                   mu=0, stiffness=1e4)
    with pytest.raises(DescriptionError, match="a compliance is against the "
                                               "world"):
        armature.compile(lambda p: stacked(p, touch=soft), {"gap": 0.0})


def test_a_malformed_against_is_named():
    with pytest.raises(DescriptionError, match="against must be shape"):
        contact("touch", body="upper", shape=shape("sphere", pos=(0, 0, 0),
                                                   radius=R),
                against=("lower",), mu=0)


def test_the_frames_table_names_the_other_body():
    row = armature.frames(stacked, {"gap": 0.0}).row("Contacts", "touch")
    assert (row["body"], row["against body"]) == ("upper", "lower")
    assert armature.frames(stacked, {"gap": 0.0}).row(
        "Contacts", "floor")["against body"] == "world"
