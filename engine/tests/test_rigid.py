"""`rigid(element)` makes a cable inextensible or locks a compliant joint,
and the release sizes it by how much a quantity changes.

Answer: fixture 5's bob on a cable. Rigid, the cable holds it at its rest
length; elastic, it stretches m g / k further, which is the sag the release
must report. A bob swinging on a rigid cable is a pendulum, whose tension and
drive force are written here in closed form. A crane's sprung elbow, held
rigid, droops by the root of k (q − rest) = m g l cos q when released.
"""

import math

import numpy as np
import pytest
from scipy.optimize import brentq

import armature
from armature import (actuator, body, cable, couple, gravity, joint, lock, rigid,
                      site)
from golden import spring_cable
from golden.answers import CABLE_SAG

PARAMS = spring_cable.PARAMS
G = 9.81


def _ball(name, mass, com):
    i = 0.4 * mass * 0.01 ** 2  # a 10 mm sphere's
    return body(name, mass=mass, com=com, inertia=np.diag([i, i, i]))


# Fixture 5's bob, the golden mass on a cable: anchored `drop` above on a
# cable with EA / rest = k, 1 cm stretched at home.
on_cable = spring_cable.mechanism


STIFF = rigid("hang", assumption="A3")
INEXTENSIBLE = armature.reduce(on_cable, STIFF, name="inextensible cable")


@pytest.fixture(scope="module")
def m():
    return armature.compile(INEXTENSIBLE, PARAMS)


def test_a_rigid_cable_is_a_constraint_row(m):
    assert m.constraints == ("hang",)
    assert (m.independent, m.dependent) == ((), ("z",))
    assert m.model.tendon_stiffness[0] == 0.0  # no spring left in it
    assert m.model.neq == 1
    assert armature.compile(on_cable, PARAMS).constraints == ()


def test_at_holds_it_at_its_rest_length(m):
    s = m.at()
    assert s.q["z"] == pytest.approx(PARAMS["drop"] - PARAMS["rest"], abs=1e-12)
    inv = s.inverse()
    assert inv.constraint["hang"] == pytest.approx(PARAMS["m"] * G, rel=1e-12)
    assert (inv.rank, inv.unknowns) == (1, 1)
    assert inv.residual < 1e-12
    # A settle's tensions are the springs'; a rigid cable has none to read.
    assert "hang" not in s.settle().tension


def test_rigid_cable_releases_with_the_sag_the_elastic_one_shows(m):
    out = m.at().release(quantity=lambda s: s.settle().q["z"])
    sag = -CABLE_SAG.value / 1e3
    assert out.sized[STIFF] == pytest.approx(sag, abs=1e-7)
    # the full model's own stretch says the same
    full = m.full.at(q={"z": PARAMS["drop"] - PARAMS["rest"]}).settle()
    assert full.tension["hang"] / PARAMS["k"] == pytest.approx(-sag, rel=1e-4)
    assert "rigid 'hang' (assumption A3) changed it by -0.0049" in str(out)


def test_the_symbolic_closure_is_the_length_less_the_rest(m):
    view = armature.symbolic(INEXTENSIBLE, PARAMS)
    numbers = {view.params[k]: v for k, v in PARAMS.items()}
    for z, gap in ((0.01, 0.0), (0.0, 0.01), (-0.05, 0.06)):
        value = view.closures["hang"].subs({**numbers, view.q["z"]: z})
        assert float(value) == pytest.approx(gap, abs=1e-15)


# --- a pendulum on a rigid cable: rates and accelerations ------------------------
H, L, M_CART, M_BOB = 1.0, 0.8, 0.3, 0.5


def swing(p):
    """A bob on a carriage (slide x), on a slide z, hung from (0, 0, H) by a
    cable of rest length L: rigid, a pendulum driven along x."""
    return [_ball("cart", M_CART, (0, 0, 0)), _ball("bob", M_BOB, (0, 0, 0)),
            joint("x", "slide", parent="world", child="cart", axis=(1, 0, 0),
                  point=(0, 0, 0), range=(-0.5, 0.5)),
            joint("z", "slide", parent="cart", child="bob", axis=(0, 0, 1),
                  point=(0, 0, 0), range=(-0.5, 0.5)),
            cable("rope", start=("world", (0, 0, H)), end=("bob", (0, 0, 0)),
                  ea=1e4, rest_length=L),
            actuator("drive", joint="x"),
            gravity((0, 0, -G))]


@pytest.mark.parametrize("x, xd, xdd", [(0.0, 0.0, 0.0), (0.3, 0.0, 0.0),
                                        (0.3, 1.2, -0.7), (-0.45, -0.8, 2.0)])
def test_a_rigid_cable_pendulum_matches_its_closed_form(x, xd, xdd):
    m = armature.compile(armature.reduce(swing, rigid("rope", assumption="A1")),
                         {})
    r = math.sqrt(L ** 2 - x ** 2)            # the bob's depth below H
    z, zd = H - r, x * xd / r
    zdd = (xd ** 2 + x * xdd) / r + (x * xd) ** 2 / r ** 3
    tension = M_BOB * (zdd + G) * L / r
    drive = (M_CART + M_BOB) * xdd + tension * x / L

    s = m.at(q={"x": x}, qd={"x": xd})
    assert s.q["z"] == pytest.approx(z, abs=1e-12)
    assert s.qd["z"] == pytest.approx(zd, abs=1e-12)
    inv = s.inverse(qdd={"x": xdd})
    assert inv.constraint["rope"] == pytest.approx(tension, rel=1e-9)
    assert inv.torque["drive"] == pytest.approx(drive, rel=1e-9, abs=1e-12)


# --- a 2R arm tied by a rigid cable: a four-bar, with J̇ in its drift -------------
ARM = {"l1": 0.30, "l2": 0.25, "lc1": 0.15, "lc2": 0.125, "m1": 1.20,
       "m2": 0.80, "I1": 0.012, "I2": 0.006}
ANCHOR = (0.30, 0.40)
TIE = math.hypot(ARM["l1"] + ARM["l2"] - ANCHOR[0], ANCHOR[1])  # taut at home


def tied_arm(p):
    """Fixture 1's arm in the xy plane, gravity along −y, its tip tied to
    the world at ANCHOR by a cable taut at home: rigid, a four-bar."""
    a = ARM
    return [
        body("upper", mass=a["m1"], com=(a["lc1"], 0, 0),
             inertia=np.diag([1e-4, a["I1"], a["I1"]])),
        body("fore", mass=a["m2"], com=(a["l1"] + a["lc2"], 0, 0),
             inertia=np.diag([1e-4, a["I2"], a["I2"]])),
        joint("shoulder", "hinge", parent="world", child="upper",
              axis=(0, 0, 1), point=(0, 0, 0), range=(-3, 3)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 0, 1),
              point=(a["l1"], 0, 0), range=(-3, 3)),
        cable("tie", start=("world", (*ANCHOR, 0)),
              end=("fore", (a["l1"] + a["l2"], 0, 0)), ea=1e4,
              rest_length=TIE),
        actuator("motor", joint="shoulder"),
        gravity((0, -G, 0))]


def four_bar(q1, qd1, qdd1):
    """The tied arm's motor torque and tension, minimal coordinates in
    40-digit mpmath: q2(q1) closes |tip − anchor| = TIE from the home branch,
    and Q = M q̈ + C + g = [τ, 0] − T ∂L/∂q."""
    from mpmath import mp
    mp.dps = 40
    a = {k: mp.mpf(v) for k, v in ARM.items()}

    def tip(x1, x2):
        return (a["l1"] * mp.cos(x1) + a["l2"] * mp.cos(x1 + x2),
                a["l1"] * mp.sin(x1) + a["l2"] * mp.sin(x1 + x2))

    def length(x1, x2):
        x, y = tip(x1, x2)
        return mp.sqrt((x - ANCHOR[0]) ** 2 + (y - ANCHOR[1]) ** 2)

    def q2_of(x1):
        return mp.findroot(lambda x2: length(x1, x2) - TIE, mp.mpf(0))

    q2 = q2_of(q1)
    d1, d2 = mp.diff(q2_of, q1, 1), mp.diff(q2_of, q1, 2)
    qd2, qdd2 = d1 * qd1, d2 * qd1 ** 2 + d1 * qdd1
    h = a["m2"] * a["l1"] * a["lc2"]
    m11 = (a["I1"] + a["I2"] + a["m1"] * a["lc1"] ** 2
           + a["m2"] * (a["l1"] ** 2 + a["lc2"] ** 2) + 2 * h * mp.cos(q2))
    m12 = a["I2"] + a["m2"] * a["lc2"] ** 2 + h * mp.cos(q2)
    m22 = a["I2"] + a["m2"] * a["lc2"] ** 2
    c12 = mp.cos(q1 + q2)
    q_1 = (m11 * qdd1 + m12 * qdd2 - h * mp.sin(q2) * (2 * qd1 * qd2 + qd2 ** 2)
           + G * ((a["m1"] * a["lc1"] + a["m2"] * a["l1"]) * mp.cos(q1)
                  + a["m2"] * a["lc2"] * c12))
    q_2 = (m12 * qdd1 + m22 * qdd2 + h * mp.sin(q2) * qd1 ** 2
           + G * a["m2"] * a["lc2"] * c12)
    dl1 = mp.diff(lambda x: length(x, q2), q1)
    dl2 = mp.diff(lambda x: length(q1, x), q2)
    tension = -q_2 / dl2
    return float(q2), float(qd2), float(q_1 + tension * dl1), float(tension)


@pytest.mark.parametrize("q1, qd1, qdd1", [(0.0, 0.0, 0.0), (0.15, 0.0, 0.0),
                                           (-0.2, 1.5, 0.0), (0.1, -2.0, 3.0)])
def test_a_rigid_cable_four_bar_matches_minimal_coordinates(q1, qd1, qdd1):
    m = armature.compile(armature.reduce(tied_arm, rigid("tie", assumption="A1")),
                         {})
    assert m.dependent == ("elbow",)
    q2, qd2, torque, tension = four_bar(q1, qd1, qdd1)
    s = m.at(q={"shoulder": q1}, qd={"shoulder": qd1})
    assert s.q["elbow"] == pytest.approx(q2, abs=1e-12)
    assert s.qd["elbow"] == pytest.approx(qd2, abs=1e-10)
    inv = s.inverse(qdd={"shoulder": qdd1})
    assert inv.constraint["tie"] == pytest.approx(tension, rel=1e-8)
    assert inv.torque["motor"] == pytest.approx(torque, rel=1e-8)


def open_branch(q1, steps=40):
    """The tied elbow at shoulder angle `q1` on home's branch, walked out
    from home in 40-digit mpmath, each root seeding the next."""
    from mpmath import mp
    mp.dps = 40
    l1, l2 = mp.mpf(ARM["l1"]), mp.mpf(ARM["l2"])
    q2 = mp.mpf(0)
    for k in range(1, steps + 1):
        x1 = mp.mpf(q1) * k / steps
        q2 = mp.findroot(lambda x2: mp.hypot(
            l1 * mp.cos(x1) + l2 * mp.cos(x1 + x2) - ANCHOR[0],
            l1 * mp.sin(x1) + l2 * mp.sin(x1 + x2) - ANCHOR[1]) - TIE, q2)
    return float(q2)


def test_the_tie_is_walked_from_home_on_its_branch():
    """At a shoulder of −1 rad, a solve that jumps there in one step lands
    the elbow on the crossed branch, at 2.91 rad; walked from home along the
    joints around the tie, it stays on the open one."""
    m = armature.compile(armature.reduce(tied_arm, rigid("tie", assumption="A1")),
                         {})
    assert m.at(q={"shoulder": -1.0}).q["elbow"] == pytest.approx(
        open_branch(-1.0), abs=1e-10)


def pulled_arm(p):
    """The tied arm driven through a belt from a pulley on the world: the
    pulley's turn is the coordinate, and the shoulder follows it."""
    return [e for e in tied_arm(p) if getattr(e, "name", None) != "motor"] + [
        body("pulley", mass=0.1, com=(0, -0.2, 0), inertia=np.diag([1e-4] * 3)),
        joint("P", "hinge", parent="world", child="pulley", axis=(0, 0, 1),
              point=(0, -0.2, 0), range=(-3, 3)),
        actuator("motor", joint="P")]


def test_a_couple_walks_its_leader_from_home():
    """The pulley is outside the tie, but it drives the shoulder through the
    couple, so it is walked from home too, and the elbow stays on the open
    branch."""
    belted = armature.reduce(pulled_arm, rigid("tie", assumption="A1"),
                             couple("shoulder", "P", 1.0, assumption="A2"))
    m = armature.compile(belted, {})
    assert m.independent == ("P",)
    s = m.at(q={"P": -1.2})
    assert s.q["shoulder"] == pytest.approx(-1.2, abs=1e-12)
    assert s.q["elbow"] == pytest.approx(open_branch(-1.2), abs=1e-10)


# --- a compliant joint, held rigid ---------------------------------------------------
K_ELBOW, REST, L1, LC2, L2, M2 = 20.0, 0.2, 0.4, 0.15, 0.3, 0.6


def crane(p):
    """A shoulder that yaws about z, gravity doing no work on it, and a
    sprung elbow that pitches about y, so gravity turns the forearm down:
    about +y, +x goes to −z."""
    return [
        _ball("upper", 1.0, (0.2, 0, 0)),
        body("fore", mass=M2, com=(L1 + LC2, 0, 0),
             inertia=np.diag([1e-4, 2e-3, 2e-3])),
        joint("yaw", "hinge", parent="world", child="upper", axis=(0, 0, 1),
              point=(0, 0, 0), range=(-3, 3)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 1, 0),
              point=(L1, 0, 0), range=(-1.5, 1.5), stiffness=K_ELBOW,
              rest=REST),
        site("tip", body="fore", pos=(L1 + L2, 0, 0)),
        gravity((0, 0, -G))]


HELD = rigid("elbow", assumption="A2")


def test_a_rigid_joint_locks_where_its_spring_rests():
    v = armature.compile(armature.reduce(crane, HELD), {})
    assert v.coordinates == ("yaw",)
    assert v.model.neq == 0  # a weld
    assert v.description.locks["elbow"].at == REST
    assert v.description.locked_by["elbow"] == HELD
    tip = v.at(q={"yaw": 0.3}).pose("tip").position
    assert tip == pytest.approx(armature.compile(crane, {}).at(
        q={"yaw": 0.3, "elbow": REST}).pose("tip").position, abs=1e-12)


def test_a_rigid_joint_releases_with_the_droop_its_spring_shows():
    droop = brentq(lambda q: K_ELBOW * (q - REST) - M2 * G * LC2 * math.cos(q),
                   REST, 1.5)
    out = armature.compile(armature.reduce(crane, HELD), {}).at().release(
        quantity=lambda s: s.settle().q.get("elbow", REST))
    assert out.sized[HELD] == pytest.approx(droop - REST, abs=1e-6)


# --- validation ------------------------------------------------------------------
@pytest.mark.parametrize("mechanism, reductions, why", [
    (crane, (rigid("yaw", assumption="A1"),), "has no spring"),
    (crane, (rigid("ghost", assumption="A1"),),
     "no cable, compliant joint or contact named 'ghost'"),
    (crane, (rigid("elbow", assumption=None),), "carries no assumption"),
    (crane, (lock("elbow", 0.0, assumption="A1"),
             rigid("elbow", assumption="A2")), "already locked"),
    (on_cable, (rigid("hang", assumption="A1"),
                rigid("hang", assumption="A2")), "already rigid"),
])
def test_rigid_faults(mechanism, reductions, why):
    params = PARAMS if mechanism is on_cable else {}
    with pytest.raises(armature.DescriptionError, match=why):
        armature.compile(armature.reduce(mechanism, *reductions), params)
