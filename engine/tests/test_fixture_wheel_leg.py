"""Fixture 3: a five-bar leg on a wheel, Ibex-shaped.

A torso rides an x-y carriage; its five-bar leg, driven at the hip by two
motors, carries a wheel at the pin, and the wheel's hub motor drives it
against the leg's link. The wheel rolls on a level floor and carries the
weight of everything but the carriage's rail cart.

Answer: a minimal-coordinate model written here in closed form, independent
of the engine, in 40-digit arithmetic differentiated by mpmath. The torso's
travel X and the two hip angles are free; the loop places the pin, the floor
fixes the hub's height (so the torso's), and rolling turns the wheel. The
static motor torques follow by virtual work, the wheel's normal load is the
weight it carries less any lift, its friction is the push, and the cone holds
while the push stays under μ times the load.
Trap: the leg's own five-bar statics, which a solve without the contact row
answers with a torso that has nothing to stand on.
"""

import math

import mujoco
import numpy as np
import pytest
from mpmath import mp

import armature
from armature import actuator, body, contact, gravity, joint, loop, shape, site
from armature.contact import TOUCH

POINTS = {"A": (-0.05, 0.0), "B": (-0.10, -0.10), "C": (0.0, -0.25),
          "E": (0.05, 0.0), "D": (0.11, -0.09)}
LINKS = {  # name: (from, to, mass, Izz)
    "l1": ("A", "B", 0.30, 1.0e-3), "l2": ("B", "C", 0.45, 2.0e-3),
    "l3": ("E", "D", 0.35, 1.5e-3), "l4": ("D", "C", 0.50, 2.5e-3)}
COM_AT = 0.4  # each link's COM, as a fraction from its first point
TORSO_COM = (0.0, 0.08)
PUSH_AT = (0.0, 0.12)  # the torso site loads act at
PARAMS = {f"{k}{axis}": v[i] for k, v in POINTS.items()
          for i, axis in enumerate("xy")}
PARAMS.update({f"m_{k}": v[2] for k, v in LINKS.items()})
PARAMS.update({f"I_{k}": v[3] for k, v in LINKS.items()})
PARAMS.update({"g": 9.81, "N": 20.0, "N_hub": 10.0, "J": 1e-5, "kB": 2.0,
               "m_torso": 3.0, "I_torso": 0.02, "m_cart": 0.2,
               "m_wheel": 0.4, "r": 0.06, "w": 0.015, "mu": 0.7})
CARRIED = ["m_torso", "m_wheel"] + [f"m_{k}" for k in LINKS]
SEED = 20261011


def wheel_leg(p):
    """Ground is the floor, y = Cy − r. The torso rides slides x then y; the
    hip pivots A and E are on it; l2 and l4 meet at the pin C, where the
    wheel turns on l2. Gravity is −y and every hinge turns about z."""
    def at(name):
        return (p[f"{name}x"], p[f"{name}y"], 0)

    def com(start, end):
        return tuple(a + COM_AT * (b - a) for a, b in zip(at(start), at(end)))

    out = [body("cart", mass=p["m_cart"], com=(0, 0, 0),
                inertia=np.diag([1e-4] * 3)),
           body("torso", mass=p["m_torso"], com=(*TORSO_COM, 0),
                inertia=np.diag([p["I_torso"]] * 3))]
    for name, (start, end, _, _) in LINKS.items():
        i = p[f"I_{name}"]
        out.append(body(name, mass=p[f"m_{name}"], com=com(start, end),
                        inertia=np.diag([i, i, i])))
    i_w = p["m_wheel"] * p["r"] ** 2 / 2
    out.append(body("wheel", mass=p["m_wheel"], com=at("C"),
                    inertia=np.diag([i_w, i_w, i_w])))
    span, rail = (-math.pi, math.pi), (-0.5, 0.5)
    floor = (0, p["Cy"] - p["r"], 0)
    out += [
        joint("x", "slide", parent="world", child="cart", axis=(1, 0, 0),
              point=(0, 0, 0), range=rail),
        joint("y", "slide", parent="cart", child="torso", axis=(0, 1, 0),
              point=(0, 0, 0), range=rail),
        joint("A", "hinge", parent="torso", child="l1", axis=(0, 0, 1),
              point=at("A"), range=span),
        joint("B", "hinge", parent="l1", child="l2", axis=(0, 0, 1),
              point=at("B"), range=span, stiffness=p["kB"]),
        joint("E", "hinge", parent="torso", child="l3", axis=(0, 0, 1),
              point=at("E"), range=span),
        joint("D", "hinge", parent="l3", child="l4", axis=(0, 0, 1),
              point=at("D"), range=span),
        joint("hub", "hinge", parent="l2", child="wheel", axis=(0, 0, 1),
              point=at("C"), range=(-100.0, 100.0)),
        site("C2", body="l2", pos=at("C")),
        site("C4", body="l4", pos=at("C")),
        site("push", body="torso", pos=(*PUSH_AT, 0)),
        loop("pin", "C2", "C4"),
        actuator("motor_A", joint="A", gear=p["N"], rotor_inertia=p["J"]),
        actuator("motor_E", joint="E", gear=p["N"], rotor_inertia=p["J"]),
        actuator("hub_motor", joint="hub", gear=p["N_hub"],
                 rotor_inertia=p["J"]),
        contact("tyre", body="wheel",
                shape=shape("cylinder", pos=at("C"), axis=(0, 0, 1),
                            radius=p["r"], half_length=p["w"]),
                against=shape("plane", pos=floor, axis=(0, 1, 0)),
                mu=p["mu"]),
        gravity((0, -p["g"], 0)),
    ]
    return out


# --- the minimal-coordinate reference -----------------------------------------
mp.dps = 40
PT = {k: [mp.mpf(v) for v in xy] for k, xy in POINTS.items()}
R2 = mp.sqrt(sum((c - b) ** 2 for b, c in zip(PT["B"], PT["C"])))
R4 = mp.sqrt(sum((c - d) ** 2 for d, c in zip(PT["D"], PT["C"])))


def _rot(v, t):
    return [mp.cos(t) * v[0] - mp.sin(t) * v[1],
            mp.sin(t) * v[0] + mp.cos(t) * v[1]]


def _add(a, b, k=1):
    return [x + k * y for x, y in zip(a, b)]


def _turned(v0, v):  # the angle from v0 to v
    return mp.atan2(v0[0] * v[1] - v0[1] * v[0], v0[0] * v[0] + v0[1] * v[1])


def leg(ya, ye):
    """The pin C, each link's turn ψ from home and COM, and B's angle, in
    the torso's frame, with the hips turned by ya and ye."""
    b = _add(PT["A"], _rot(_add(PT["B"], PT["A"], -1), ya))
    d = _add(PT["E"], _rot(_add(PT["D"], PT["E"], -1), ye))
    bd = _add(d, b, -1)
    dist = mp.sqrt(bd[0] ** 2 + bd[1] ** 2)
    along = (R2 ** 2 - R4 ** 2 + dist ** 2) / (2 * dist)
    height = mp.sqrt(R2 ** 2 - along ** 2)
    ex = [bd[0] / dist, bd[1] / dist]
    c = _add(_add(b, ex, along), [ex[1], -ex[0]], height)  # home's branch
    psi = {"l1": ya, "l3": ye,
           "l2": _turned(_add(PT["C"], PT["B"], -1), _add(c, b, -1)),
           "l4": _turned(_add(PT["C"], PT["D"], -1), _add(c, d, -1))}
    pivot = {"l1": PT["A"], "l2": b, "l3": PT["E"], "l4": d}
    com = {}
    for name, (start, end, _, _) in LINKS.items():
        com0 = _add(PT[start], _add(PT[end], PT[start], -1), COM_AT)
        com[name] = _add(pivot[name], _rot(_add(com0, PT[start], -1),
                                           psi[name]))
    return {"c": c, "psi": psi, "com": com, "q_B": psi["l2"] - ya}


def placed(x, ya, ye):
    """The whole mechanism with the torso at travel x and the hips at ya,
    ye, the torso lifted so the hub stays at its home height: the torso's
    lift, the pushed site, the hub joint's angle (rolling), the potential."""
    g = leg(ya, ye)
    lift = PT["C"][1] - g["c"][1]
    hub_x = x + g["c"][0]
    wheel_turn = -(hub_x - PT["C"][0]) / mp.mpf(PARAMS["r"])  # no slip
    weight = PARAMS["g"]
    potential = (PARAMS["kB"] * g["q_B"] ** 2 / 2
                 + weight * PARAMS["m_torso"] * (TORSO_COM[1] + lift)
                 + weight * PARAMS["m_wheel"] * PT["C"][1]
                 + sum(LINKS[n][2] * weight * (g["com"][n][1] + lift)
                       for n in LINKS))
    return {"lift": lift, "push": [x + PUSH_AT[0], lift + PUSH_AT[1]],
            "q_hub": wheel_turn - g["psi"]["l2"], "V": potential}


def _gradient(key, y, index=None):
    def f(*v):
        out = placed(*v)[key]
        return out if index is None else out[index]
    return [mp.diff(f, y, tuple(int(k == i) for k in range(3)))
            for i in range(3)]


def static_torque(x, ya, ye, push=(0.0, 0.0)):
    """Virtual work over (x, ya, ye): Σ N τ ∂q/∂y = ∂V/∂y − f · ∂p/∂y."""
    y = [mp.mpf(x), mp.mpf(ya), mp.mpf(ye)]
    need = np.array(_gradient("V", y), dtype=float)
    for i in range(2):
        need -= push[i] * np.array(_gradient("push", y, i), dtype=float)
    hub = np.array(_gradient("q_hub", y), dtype=float)
    moves = np.array([[0, 1, 0], [0, 0, 1], hub]).T  # ∂(q_A, q_E, q_hub)/∂y
    gears = np.array([PARAMS["N"], PARAMS["N"], PARAMS["N_hub"]])
    return np.linalg.solve(moves * gears, need)


def weight_carried():
    return PARAMS["g"] * sum(PARAMS[m] for m in CARRIED)


def postures(n, seed=SEED):
    rng = np.random.default_rng(seed)
    return [(rng.uniform(-0.2, 0.2), *rng.uniform(-0.4, 0.4, 2))
            for _ in range(n)]


@pytest.fixture(scope="module")
def m():
    return armature.compile(wheel_leg, PARAMS)


def _standing(m, x, ya, ye):
    lift = float(placed(mp.mpf(x), mp.mpf(ya), mp.mpf(ye))["lift"])
    return m.at(q={"x": x, "y": lift, "A": ya, "E": ye})


# --- the contact and the loop together -----------------------------------------
def test_the_leg_stands_on_its_wheel(m):
    assert m.dependent == ("B", "D")
    s = _standing(m, 0.05, 0.2, -0.3)
    data = s._data()
    assert data.ncon == 2
    assert np.max(np.abs(data.contact.dist[:data.ncon])) < 1e-12


@pytest.mark.parametrize("x, ya, ye", postures(6))
def test_static_torques_match_virtual_work(m, x, ya, ye):
    push = np.array([4.0, -6.0, 0.0])
    inv = _standing(m, x, ya, ye).inverse(loads={"push": push})
    got = [inv.torque[a] for a in ("motor_A", "motor_E", "hub_motor")]
    assert got == pytest.approx(static_torque(x, ya, ye, push[:2]),
                                rel=1e-8, abs=1e-12)
    assert (inv.rank, inv.unknowns) == (7, 7)
    assert inv.residual < 1e-10


@pytest.mark.parametrize("x, ya, ye", postures(4))
def test_the_wheel_carries_the_weight(m, x, ya, ye):
    push = np.array([4.0, -6.0, 0.0])
    tyre = _standing(m, x, ya, ye).inverse(loads={"push": push}).contacts[
        "tyre"]
    assert tyre.normal == pytest.approx(weight_carried() - push[1], rel=1e-10)
    assert tyre.friction == pytest.approx([-push[0], 0, 0], abs=1e-10)


@pytest.mark.parametrize("fraction", [0.0, 0.5, 0.95, 1.05, 2.0])
def test_the_cone_margin_is_positive_where_the_closed_form_holds(m, fraction):
    """The cone holds while the push stays under μ times the load."""
    load = weight_carried()
    push = np.array([fraction * PARAMS["mu"] * load, 0.0, 0.0])
    tyre = _standing(m, 0.02, 0.15, -0.1).inverse(
        loads={"push": push}).contacts["tyre"]
    expected = PARAMS["mu"] * load - abs(push[0])
    assert tyre.margin == pytest.approx(expected, abs=1e-9)
    assert (tyre.margin > 0) == (fraction < 1)


def test_without_the_floor_the_torso_has_nothing_to_stand_on(m):
    """The trap: lifted 1 mm, the contact is gone, and the motors alone
    cannot hold the torso up; the residual says so."""
    s = _standing(m, 0.0, 0.1, -0.1)
    lifted = m.at(q={n: s.q[n] for n in m.independent} | {"y": s.q["y"] + 1e-3})
    inv = lifted.inverse()
    assert inv.contacts == {}
    assert inv.residual > 1.0


def test_wrench_across_the_hub_is_the_hub_torque(m):
    push = np.array([4.0, -6.0, 0.0])
    s = _standing(m, 0.05, 0.2, -0.3)
    wrench = s.wrench("wheel", loads={"push": push})
    expected = static_torque(0.05, 0.2, -0.3, push[:2])[2] * PARAMS["N_hub"]
    assert wrench.torque[2] == pytest.approx(expected, rel=1e-8)


def test_mj_inverse_is_never_called(m, monkeypatch):
    def refuse(*args):
        raise AssertionError("mj_inverse called with contact and a loop")
    monkeypatch.setattr(mujoco, "mj_inverse", refuse)
    s = _standing(m, 0.05, 0.2, -0.3)
    s.inverse(loads={"push": (4.0, -6.0, 0.0)})
    s.wrench("l2")


# --- the trap: a skid the leg reaches only away from α = 0 ---------------------
# α is the leg's angle: the pin C's direction from the hips' midpoint, from
# straight down, in the torso's frame. A skid pad round the knee pivot B
# reaches the floor only when the leg swings; a check run at α = 0 alone,
# over every leg length, never sees it touch.
SKID_PARAMS = PARAMS | {"r_skid": 0.09}
HIPS = [(PT["A"][i] + PT["E"][i]) / 2 for i in range(2)]


def with_skid(p):
    def at(name):
        return (p[f"{name}x"], p[f"{name}y"], 0)
    floor = (0, p["Cy"] - p["r"], 0)
    return wheel_leg(p) + [
        contact("skid", body="l1",
                shape=shape("sphere", pos=at("B"), radius=p["r_skid"]),
                against=shape("plane", pos=floor, axis=(0, 1, 0)),
                mu=p["mu"])]


def alpha(ya, ye):
    c = leg(mp.mpf(ya), mp.mpf(ye))["c"]
    return float(mp.atan2(c[0] - HIPS[0], HIPS[1] - c[1]))


def skid_clearance(ya, ye):
    """The skid's height above the floor, with the hub on it: the knee B
    above the pin C, plus the wheel's radius, less the pad's."""
    ya, ye = mp.mpf(ya), mp.mpf(ye)
    b = _add(PT["A"], _rot(_add(PT["B"], PT["A"], -1), ya))
    c = leg(ya, ye)["c"]
    return float(b[1] - c[1] + PARAMS["r"] - SKID_PARAMS["r_skid"])


def alpha_zero(count):
    """About `count` hip pairs with α = 0, from the shortest leg to the
    longest: for each A, the E that puts the pin straight below the hips,
    walked out from home so each root seeds the next."""
    out = [(0.0, 0.0)]
    for end in (-1.2, 0.9):
        ye = mp.mpf(0)
        for ya in np.linspace(0, end, count // 2 + 1)[1:]:
            ye = mp.findroot(lambda e, a=mp.mpf(ya): leg(a, e)["c"][0]
                             - HIPS[0], ye)
            out.append((float(ya), float(ye)))
    return out


@pytest.fixture(scope="module")
def skid_m():
    return armature.compile(with_skid, SKID_PARAMS)


def test_resting_on_the_tyre_matches_the_closed_form_lift(skid_m):
    """`rest_on` solves the torso's height so the tyre touches the floor,
    at every sample: the closed form's lift, and a touching contact."""
    samples = armature.sample(skid_m, n=8, seed=SEED, rest_on={"tyre": "y"})
    for s in samples.states:
        x, ya, ye = s.q["x"], s.q["A"], s.q["E"]
        lift = float(placed(mp.mpf(x), mp.mpf(ya), mp.mpf(ye))["lift"])
        assert s.q["y"] == pytest.approx(lift, abs=1e-9)
        assert abs(armature.clearance(s, "tyre")) <= 1e-10
    assert all(abs(c) <= 1e-10 for c in samples.clearance["tyre"])
    # within a milliradian of home the tyre starts 1e-4 m off the floor,
    # and is still brought down to touching
    near = armature.sample(skid_m, n=4, seed=SEED, rest_on={"tyre": "y"},
                           within={"A": (-1e-3, 1e-3), "E": (-1e-3, 1e-3)})
    for s in near.states:
        lift = placed(mp.mpf(s.q["x"]), mp.mpf(s.q["A"]), mp.mpf(s.q["E"]))
        assert s.q["y"] == pytest.approx(float(lift["lift"]), abs=1e-12)


def test_the_skid_is_missed_at_alpha_zero_alone(skid_m):
    """Over every leg length at α = 0, from 7 cm to 29 cm, the skid stays
    clear of the floor by at least 4 cm; the engine's clearance is the
    closed form's."""
    hips = alpha_zero(24)
    lengths = [-float(leg(mp.mpf(a), mp.mpf(e))["c"][1]) for a, e in hips]
    assert min(lengths) < 0.08 and max(lengths) > 0.28
    for ya, ye in hips:
        assert abs(alpha(ya, ye)) < 1e-12
        s = _standing(skid_m, 0.0, ya, ye)
        gap = armature.clearance(s, "skid")
        assert gap == pytest.approx(skid_clearance(ya, ye), abs=1e-9)
        assert gap > 0.04
        assert "skid" not in s.inverse().contacts


def test_sampling_finds_the_skid_away_from_alpha_zero(skid_m):
    """Sampled over the hips' ranges, with the tyre on the floor, the skid
    reaches the floor, and only where the leg swings well away from α = 0."""
    samples = armature.sample(skid_m, n=24, seed=SEED, rest_on={"tyre": "y"})
    reached = samples.reached("skid")
    assert reached, str(samples)
    for s in reached:
        ya, ye = s.q["A"], s.q["E"]
        assert skid_clearance(ya, ye) <= TOUCH
        assert abs(alpha(ya, ye)) > 0.5
    assert f"skid: {len(reached)} of 24" in str(samples)


def test_a_far_turned_wheel_closes_in_the_legs_steps(m, monkeypatch):
    """The hub joint is outside the loop, so turning the wheel 90 rad adds
    no continuation steps: the loop is walked only as far as the hips go."""
    from armature.assembly import CONTINUATION_STEP, Closure
    calls = []
    close = Closure.close
    monkeypatch.setattr(Closure, "close",
                        lambda self, data: calls.append(1) or close(self, data))
    s = m.at(q={"A": 0.3, "E": -0.2, "hub": 90.0})
    assert len(calls) == math.ceil(0.3 / CONTINUATION_STEP)
    assert s.q["hub"] == 90.0


@pytest.mark.parametrize("rest_on, match", [
    ({"wheel": "y"}, "no contact named"),
    ({"tyre": "B"}, "solved, not drawn"),
    ({"tyre": "q"}, "no coordinate named"),
])
def test_rest_on_is_checked(skid_m, rest_on, match):
    with pytest.raises(ValueError, match=match):
        armature.sample(skid_m, rest_on=rest_on)


def test_rest_on_is_for_postures_only(skid_m):
    limits = {d: 1.0 for d in skid_m.independent}
    with pytest.raises(ValueError, match="postures only"):
        armature.sample_states(skid_m, qd_limits=limits, qdd_limits=limits,
                               rest_on={"tyre": "y"})
