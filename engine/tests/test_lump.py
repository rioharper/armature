"""`lump(body, into)` moves a body's mass into a neighbour, onto a point, or
away altogether, and the release sizes it by how much a quantity changes.

Answer: fixture 1's planar arm, closed forms written here by hand. Lumped
into the upper link, the forearm's mass rides with it as if the elbow were
held at home, so the shoulder's static torque is the straight arm's at every
elbow angle. Massless, the forearm adds nothing. Trap: MuJoCo refuses a
moving body without mass, so a massless body compiles with a floor; a test
pins the refusal, so the floor is not removed by mistake.
"""

import math

import mujoco
import numpy as np
import pytest
import sympy as sp

import armature
import armature.compiler
from armature import actuator, body, gravity, joint, lump, massless, site

P = {"l1": 0.30, "l2": 0.25, "lc1": 0.15, "lc2": 0.125, "m1": 1.20,
     "m2": 0.80, "I1": 0.012, "I2": 0.006, "Ix": 0.0002, "g": 9.81,
     "N1": 50.0, "N2": 30.0, "J1": 2e-5, "J2": 1e-5}
FLOOR = 1e-5  # relative: the floor adds 1e-6 of the forearm's own mass


def arm(p):
    """Fixture 1's arm: planar, gravity along −y, both links along +x."""
    return [
        body("upper", mass=p["m1"], com=(p["lc1"], 0, 0),
             inertia=np.diag([p["Ix"], p["I1"], p["I1"]])),
        body("fore", mass=p["m2"], com=(p["l1"] + p["lc2"], 0, 0),
             inertia=np.diag([p["Ix"], p["I2"], p["I2"]])),
        joint("shoulder", "hinge", parent="world", child="upper",
              axis=(0, 0, 1), point=(0, 0, 0), range=(-math.pi, math.pi)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 0, 1),
              point=(p["l1"], 0, 0), range=(-2.6, 2.6)),
        site("tip", body="fore", pos=(p["l1"] + p["l2"], 0, 0)),
        site("pin", body="upper", pos=(p["l1"], 0, 0)),
        actuator("shoulder_motor", joint="shoulder", gear=p["N1"],
                 rotor_inertia=p["J1"]),
        actuator("elbow_motor", joint="elbow", gear=p["N2"],
                 rotor_inertia=p["J2"]),
        gravity((0, -p["g"], 0)),
    ]


INTO_UPPER = lump("fore", into="upper", assumption="A4")
LUMPED = armature.reduce(arm, INTO_UPPER, name="forearm lumped")
MASSLESS = armature.reduce(arm, lump("fore", into=massless, assumption="A5"))


def gravity_torque(q1, q2):
    """The full arm's shoulder gravity torque, joint side."""
    return P["g"] * ((P["m1"] * P["lc1"] + P["m2"] * P["l1"]) * math.cos(q1)
                     + P["m2"] * P["lc2"] * math.cos(q1 + q2))


def shoulder(s):
    return s.inverse().torque["shoulder_motor"]


# --- into a neighbour ---------------------------------------------------------
def test_lump_preserves_total_mass_and_com():
    """In the description, exactly: the variant's masses and COMs, at home,
    against the full description's, symbolically."""
    def totals(view):
        mass = sum(view.mass.values())
        moment = sum((view.mass[b] * view.com[b].pos_from(view.origin)
                      .to_matrix(view.world) for b in view.mass), sp.zeros(3, 1))
        home = {q: 0 for q in view.q.values()}
        return mass, (moment / mass).subs(home)

    mass, com = totals(armature.symbolic(LUMPED, P))
    full_mass, full_com = totals(armature.symbolic(arm, P))
    assert sp.simplify(mass - full_mass) == 0
    assert sp.simplify(com - full_com) == sp.zeros(3, 1)

    view = armature.symbolic(LUMPED, P)
    p = view.params
    assert view.mass == {"upper": p["m1"] + p["m2"], "fore": 0}


def test_the_compiled_lump_preserves_them_to_the_floor():
    v, full = armature.compile(LUMPED, P), armature.compile(arm, P)
    assert v.model.body_subtreemass[0] == pytest.approx(
        full.model.body_subtreemass[0], rel=FLOOR)
    com = []
    for m in (v, full):
        data = mujoco.MjData(m.model)
        mujoco.mj_forward(m.model, data)
        com.append(data.subtree_com[0].copy())
    assert com[0] == pytest.approx(com[1], abs=FLOOR * 0.3)


@pytest.mark.parametrize("q2", [-1.2, 0.0, 0.9])
def test_the_lumped_forearm_rides_as_if_the_elbow_were_straight(q2):
    """The shoulder's torque and its inertia are the straight arm's, at every
    elbow angle: the forearm's mass moved into the upper link at home."""
    s = armature.compile(LUMPED, P).at(q={"shoulder": 0.4, "elbow": q2})
    straight = P["g"] * (P["m1"] * P["lc1"] + P["m2"] * (P["l1"] + P["lc2"]))
    assert shoulder(s) * P["N1"] == pytest.approx(straight * math.cos(0.4),
                                                  rel=FLOOR)
    m11 = (P["I1"] + P["I2"] + P["m1"] * P["lc1"] ** 2
           + P["m2"] * (P["l1"] + P["lc2"]) ** 2 + P["N1"] ** 2 * P["J1"])
    assert s.linearise().mass[0, 0] == pytest.approx(m11, rel=FLOOR)


def test_a_lump_is_released_by_the_change_in_a_quantity():
    q1, q2 = 0.4, 0.9
    out = armature.compile(LUMPED, P).at(
        q={"shoulder": q1, "elbow": q2}).release(quantity=shoulder)
    change = (P["g"] * P["m2"] * P["lc2"]
              * (math.cos(q1 + q2) - math.cos(q1)) / P["N1"])
    assert set(out.sized) == {INTO_UPPER}
    assert out.sized[INTO_UPPER] == pytest.approx(change, rel=FLOOR)
    assert out.settled is None and out.moved == {}
    assert "lump 'fore' into 'upper' (assumption A4) changed it by" in str(out)


def test_a_lump_is_released_at_the_states_rates():
    """Moving, the full arm's shoulder also carries the forearm's Coriolis
    torque, −h (2 q̇1 q̇2 + q̇2²); rigidly lumped, it carries none. The
    variant without the lump must be asked at the same rates."""
    q1, q2, qd1, qd2 = 0.4, 0.9, 1.5, -2.0
    out = armature.compile(LUMPED, P).at(
        q={"shoulder": q1, "elbow": q2},
        qd={"shoulder": qd1, "elbow": qd2}).release(quantity=shoulder)
    h = P["m2"] * P["l1"] * P["lc2"] * math.sin(q2)
    straight = P["g"] * (P["m1"] * P["lc1"] + P["m2"] * (P["l1"] + P["lc2"]))
    change = (gravity_torque(q1, q2) - h * (2 * qd1 * qd2 + qd2 ** 2)
              - straight * math.cos(q1)) / P["N1"]
    assert out.sized[INTO_UPPER] == pytest.approx(change, rel=FLOOR)


def test_a_lump_with_no_quantity_named_is_refused():
    s = armature.compile(LUMPED, P).at()
    with pytest.raises(ValueError, match="quantity"):
        s.release()


# --- massless -----------------------------------------------------------------
def test_massless_compiles_and_flags_the_variant_approximate():
    v = armature.compile(MASSLESS, P)
    assert v.approximate and "'fore'" in v.approximate[0]
    assert "mass" in v.approximate[0]
    assert armature.compile(arm, P).approximate == ()
    assert armature.compile(LUMPED, P).approximate  # its forearm is left massless
    assert v.model.body("fore").mass[0] == pytest.approx(
        armature.compiler.MASS_FLOOR * P["m2"], rel=1e-12)
    for q1 in (-1.0, 0.4):
        s = v.at(q={"shoulder": q1, "elbow": 0.7})
        assert shoulder(s) * P["N1"] == pytest.approx(
            P["g"] * P["m1"] * P["lc1"] * math.cos(q1), rel=FLOOR)
    assert armature.symbolic(MASSLESS, P).mass["fore"] == 0


def test_mujoco_refuses_a_moving_body_without_mass():
    """Why the floor exists: pinned against MuJoCo itself, so it is not
    removed by mistake."""
    spec = mujoco.MjSpec()
    spec.compiler.inertiafromgeom = (
        mujoco.mjtInertiaFromGeom.mjINERTIAFROMGEOM_FALSE)
    b = spec.worldbody.add_body(name="b")
    b.mass, b.inertia, b.explicitinertial = 0.0, [1e-3] * 3, True
    b.add_joint(name="j", type=mujoco.mjtJoint.mjJNT_HINGE, axis=[0, 0, 1])
    with pytest.raises(ValueError, match="mass and inertia of moving bodies "
                                         "must be larger than mjMINVAL"):
        spec.compile()


def test_without_the_floor_massless_does_not_compile(monkeypatch):
    monkeypatch.setattr(armature.compiler, "MASS_FLOOR", 0.0)
    with pytest.raises(ValueError, match="mjMINVAL|positive eigenvalues"):
        armature.compile(MASSLESS, P)


# --- onto a point ---------------------------------------------------------------
def test_onto_its_own_site_the_forearm_is_a_point_mass():
    v = armature.compile(armature.reduce(
        arm, lump("fore", into="tip", assumption="A6")), P)
    assert v.approximate  # a point mass has no inertia of its own
    q1, q2 = 0.4, -0.8
    s = v.at(q={"shoulder": q1, "elbow": q2})
    closed = P["g"] * (P["m1"] * P["lc1"] * math.cos(q1) + P["m2"] * (
        P["l1"] * math.cos(q1) + P["l2"] * math.cos(q1 + q2)))
    assert shoulder(s) * P["N1"] == pytest.approx(closed, rel=FLOOR)


def test_onto_a_neighbours_site_the_mass_rides_there():
    """A point mass at the pin: its weight, and m2 l1² about the shoulder
    with none of the forearm's own inertia."""
    v = armature.compile(armature.reduce(
        arm, lump("fore", into="pin", assumption="A6")), P)
    m11 = (P["I1"] + P["m1"] * P["lc1"] ** 2 + P["m2"] * P["l1"] ** 2
           + P["N1"] ** 2 * P["J1"])
    for q2 in (-1.0, 1.4):
        s = v.at(q={"shoulder": 0.4, "elbow": q2})
        assert shoulder(s) * P["N1"] == pytest.approx(
            P["g"] * (P["m1"] * P["lc1"] + P["m2"] * P["l1"]) * math.cos(0.4),
            rel=FLOOR)
        assert s.linearise().mass[0, 0] == pytest.approx(m11, rel=FLOOR)


def test_the_lumped_inertia_is_the_parallel_axis_sum():
    """Two bodies off every axis, with full tensors: the lumped one's inertia
    about the combined COM, against the parallel-axis theorem by hand."""
    ia = np.array([[0.02, 0.003, -0.001], [0.003, 0.015, 0.002],
                   [-0.001, 0.002, 0.01]])
    ib = np.array([[0.004, -0.0005, 0.0], [-0.0005, 0.006, 0.001],
                   [0.0, 0.001, 0.005]])
    ca, cb, ma, mb = np.array([0.1, 0.2, -0.05]), np.array([0.4, -0.1, 0.3]), \
        1.5, 0.7

    def pair(p):
        return [body("a", mass=ma, com=ca, inertia=ia),
                body("b", mass=mb, com=cb, inertia=ib),
                joint("ja", "hinge", parent="world", child="a", axis=(0, 0, 1),
                      point=(0, 0, 0), range=(-1, 1)),
                joint("jb", "hinge", parent="a", child="b", axis=(1, 0, 0),
                      point=(0.3, 0, 0), range=(-1, 1))]

    d = armature.describe(armature.reduce(
        pair, lump("b", into="a", assumption="A1")), {})
    a = {x.name: x for x in d.bodies}["a"]
    centre = (ma * ca + mb * cb) / (ma + mb)

    def moved(i, m, c):
        r = c - centre
        return i + m * (r @ r * np.eye(3) - np.outer(r, r))

    assert float(a.mass) == pytest.approx(ma + mb, rel=1e-15)
    assert np.array(a.com, dtype=float) == pytest.approx(centre, abs=1e-15)
    assert np.array(a.inertia, dtype=float) == pytest.approx(
        moved(ia, ma, ca) + moved(ib, mb, cb), abs=1e-15)
    assert d.floored["b"].mass == mb


# --- validation -----------------------------------------------------------------
def hand(p):
    return arm(p) + [
        body("hand", mass=0.1, com=(0.6, 0, 0), inertia=np.eye(3) * 1e-4),
        joint("wrist", "hinge", parent="fore", child="hand", axis=(0, 0, 1),
              point=(0.55, 0, 0), range=(-1, 1))]


@pytest.mark.parametrize("reductions, why", [
    ((lump("ghost", into="upper", assumption="A1"),), "no body named 'ghost'"),
    ((lump("fore", into="nowhere", assumption="A1"),),
     "no body or site named 'nowhere'"),
    ((lump("fore", into="fore", assumption="A1"),), "into itself"),
    ((lump("hand", into="upper", assumption="A1"),), "not a neighbour"),
    ((lump("fore", into="upper", assumption=None),), "carries no assumption"),
    ((lump("fore", into="upper", assumption="A1"),
      lump("fore", into=massless, assumption="A2")), "already lumped"),
    ((lump("hand", into=massless, assumption="A1"),
      lump("fore", into="hand", assumption="A2")), "already lumped away"),
])
def test_lump_faults(reductions, why):
    with pytest.raises(armature.DescriptionError, match=why):
        armature.compile(armature.reduce(hand, *reductions), P)
