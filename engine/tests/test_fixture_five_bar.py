"""The planar five-bar: loops through the description.

Answer: a minimal-coordinate model written here in closed form, independent of
the engine, evaluated in 40-digit arithmetic and differentiated by mpmath. The two actuated angles place B and D, the loop's pin C is where the
circles about them meet on home's branch, and the potential, the kinetic
energy, the static torques by virtual work and the modes all follow from it;
with E held, it is the four-bar that locking E leaves.
Trap: `mj_inverse`, which answers for the solver's soft constraint and was off
by 61 % and 78 % on a five-bar, and the full-DOF eigenproblem, which adds the
solver's constraint stiffness as modes.
"""

import math

import mujoco
import numpy as np
import pytest
import sympy as sp
from mpmath import mp

import armature
from armature import actuator, body, gravity, joint, lock, loop, site

POINTS = {"A": (-0.05, 0.0), "B": (-0.10, -0.10), "C": (0.0, -0.25),
          "E": (0.05, 0.0), "D": (0.11, -0.09)}
LINKS = {  # name: (from, to, mass, Izz)
    "l1": ("A", "B", 0.30, 1.0e-3), "l2": ("B", "C", 0.45, 2.0e-3),
    "l3": ("E", "D", 0.35, 1.5e-3), "l4": ("D", "C", 0.50, 2.5e-3)}
COM_AT = 0.4  # each link's COM, as a fraction from its first point
PARAMS = {f"{k}{axis}": v[i] for k, v in POINTS.items()
          for i, axis in enumerate("xy")}
PARAMS.update({f"m_{k}": v[2] for k, v in LINKS.items()})
PARAMS.update({f"I_{k}": v[3] for k, v in LINKS.items()})
PARAMS.update({"g": 9.81, "N": 20.0, "J": 1e-5, "kB": 2.0})
SEED = 20261011


def five_bar(p):
    """Ground pivots A and E; A drives l1 to B, E drives l3 to D, and l2 and
    l4 meet at the pin C. Gravity is −y, every hinge turns about z, and B
    carries a spring."""
    def at(name):
        return (p[f"{name}x"], p[f"{name}y"], 0)

    def com(start, end):
        return tuple(a + COM_AT * (b - a) for a, b in zip(at(start), at(end)))

    out = []
    for name, (start, end, _, _) in LINKS.items():
        i = p[f"I_{name}"]
        out.append(body(name, mass=p[f"m_{name}"], com=com(start, end),
                        inertia=np.diag([i, i, i])))
    span = (-math.pi, math.pi)
    out += [
        joint("A", "hinge", parent="world", child="l1", axis=(0, 0, 1),
              point=at("A"), range=span),
        joint("B", "hinge", parent="l1", child="l2", axis=(0, 0, 1),
              point=at("B"), range=span, stiffness=p["kB"]),
        joint("E", "hinge", parent="world", child="l3", axis=(0, 0, 1),
              point=at("E"), range=span),
        joint("D", "hinge", parent="l3", child="l4", axis=(0, 0, 1),
              point=at("D"), range=span),
        site("C2", body="l2", pos=at("C")),
        site("C4", body="l4", pos=at("C")),
        loop("pin", "C2", "C4"),
        actuator("motor_A", joint="A", gear=p["N"], rotor_inertia=p["J"]),
        actuator("motor_E", joint="E", gear=p["N"], rotor_inertia=p["J"]),
        gravity((0, -p["g"], 0)),
    ]
    return out


# --- the minimal-coordinate reference -----------------------------------------
# Closed-form geometry in 40-digit arithmetic, differentiated by mpmath, so
# every derivative is good to double precision.
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


def geometry(ya, ye):
    """The pin C, each link's turn ψ from home and COM, and the dependent
    joints' angles, with A and E turned by ya and ye."""
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
    return {"c": c, "psi": psi, "com": com,
            "q_B": psi["l2"] - ya, "q_D": psi["l4"] - ye}


assert max(abs(c - c0) for c, c0 in zip(geometry(0, 0)["c"], PT["C"])) < 1e-30


def potential(ya, ye):
    g = geometry(ya, ye)
    return (PARAMS["kB"] * g["q_B"] ** 2 / 2
            + sum(LINKS[n][2] * PARAMS["g"] * g["com"][n][1] for n in LINKS))


def _partials(f, ya, ye):
    """∂f/∂ya and ∂f/∂ye at (ya, ye)."""
    return [mp.diff(f, (ya, ye), order) for order in ((1, 0), (0, 1))]


def ref(key, ya, ye):
    ya, ye = mp.mpf(ya), mp.mpf(ye)
    if key in ("q_B", "q_D"):
        out = geometry(ya, ye)[key]
    elif key == "c":
        out = geometry(ya, ye)["c"]
    elif key == "jc":
        out = [_partials(lambda a, e, i=i: geometry(a, e)["c"][i], ya, ye)
               for i in range(2)]
    elif key == "grad":
        out = _partials(potential, ya, ye)
    elif key == "hessian":
        out = [[mp.diff(potential, (ya, ye),
                        tuple(int(k == i) + int(k == j) for k in range(2)))
                for j in range(2)] for i in range(2)]
    elif key == "mass":
        rotor = PARAMS["N"] ** 2 * PARAMS["J"]
        out = np.diag([rotor, rotor]).astype(object)
        for name, (_, _, mass, izz) in LINKS.items():
            jc = np.array([_partials(
                lambda a, e, i=i: geometry(a, e)["com"][name][i], ya, ye)
                for i in range(2)], dtype=object)
            jw = np.array([_partials(
                lambda a, e: geometry(a, e)["psi"][name], ya, ye)],
                dtype=object)
            out = out + mass * jc.T @ jc + izz * jw.T @ jw
    return np.array(out, dtype=float)


def static_torque(ya, ye, force=np.zeros(3)):
    """Virtual work: N τ = ∂V/∂y − J_Cᵀ f, per motor."""
    need = ref("grad", ya, ye).ravel() - ref("jc", ya, ye).T @ force[:2]
    return need / PARAMS["N"]


def postures(n, seed=SEED):
    rng = np.random.default_rng(seed)
    return [tuple(rng.uniform(-0.5, 0.5, 2)) for _ in range(n)]


@pytest.fixture(scope="module")
def m():
    return armature.compile(five_bar, PARAMS)


# --- assembly -----------------------------------------------------------------
def test_the_loop_compiles_on_its_sites(m):
    """A body-anchored connect takes its second anchor from home and would
    hold an assembly error in place; a site-based one holds the sites."""
    assert m.model.neq == 1
    assert m.model.eq_type[0] == mujoco.mjtEq.mjEQ_CONNECT
    assert m.model.eq_objtype[0] == mujoco.mjtObj.mjOBJ_SITE
    assert [m.model.site(int(i)).name for i in
            (m.model.eq_obj1id[0], m.model.eq_obj2id[0])] == ["C2", "C4"]


def test_the_unactuated_joints_are_solved(m):
    assert m.constraints == ("pin",)
    assert m.independent == ("A", "E")
    assert m.dependent == ("B", "D")


# (0.75, −1.25) is far enough that Newton started at home's dependent angles
# lands on the other branch; the solve must walk there from home.
@pytest.mark.parametrize("ya, ye", postures(8) + [(0.75, -1.25)])
def test_at_closes_the_loop_on_home_branch(m, ya, ye):
    s = m.at(q={"A": ya, "E": ye})
    c2, c4 = s.pose("C2"), s.pose("C4")
    assert np.max(np.abs(c2.position - c4.position)) <= 1e-10
    assert c2.residual <= 1e-10
    assert c2.position[:2] == pytest.approx(ref("c", ya, ye).ravel(),
                                            abs=1e-12)
    assert s.q["B"] == pytest.approx(float(ref("q_B", ya, ye)), abs=1e-11)
    assert s.q["D"] == pytest.approx(float(ref("q_D", ya, ye)), abs=1e-11)


def test_a_posture_that_cannot_close_names_the_loop(m):
    # B folded onto D: |BD| = 4.0 mm is under |l2 − l4| = 13.9 mm, so the two
    # circles about them never meet. (The bar cannot be pulled apart instead:
    # |BD| never exceeds |AE| + l1 + l3 = 0.32 m, inside l2 + l4 = 0.374 m.)
    with pytest.raises(ValueError, match="loop 'pin' cannot close"):
        m.at(q={"A": 0.93, "E": -1.07})


def test_a_dependent_coordinate_is_not_given(m):
    with pytest.raises(ValueError, match=r"\['B'\].*solved, not given"):
        m.at(q={"A": 0.1, "B": 0.0})


def test_dependent_rates_keep_the_loop_closed(m):
    s = m.at(q={"A": 0.2, "E": -0.1}, qd={"A": 1.5, "E": -0.7})
    jac = ref("jc", 0.2, -0.1)
    pin = m.at(q={"A": 0.2, "E": -0.1})
    j2, j4 = pin.jacobian("C2"), pin.jacobian("C4")
    rates = np.array([s.qd[d] for d in s.compiled.dofs])
    assert (j2.linear - j4.linear) @ rates == pytest.approx(np.zeros(3),
                                                            abs=1e-12)
    assert j2.linear[:2] @ rates == pytest.approx(jac @ [1.5, -0.7],
                                                  abs=1e-12)


# --- statics and dynamics -----------------------------------------------------
@pytest.mark.parametrize("ya, ye", postures(8))
def test_static_torques_match_virtual_work(m, ya, ye):
    force = np.array([3.0, -5.0, 0.0])
    inv = m.at(q={"A": ya, "E": ye}).inverse(loads={"C2": force})
    expected = static_torque(ya, ye, force)
    got = np.array([inv.torque["motor_A"], inv.torque["motor_E"]])
    assert got == pytest.approx(expected, rel=1e-8, abs=1e-12)
    assert (inv.rank, inv.unknowns) == (4, 4)
    assert inv.residual < 1e-12
    assert inv.constraint["pin"][2] == 0.0  # a planar loop: no normal row


@pytest.mark.parametrize("solref, solimp", [
    ((0.002, 1.0), (0.99, 0.999, 1e-4, 0.5, 2)),
    ((0.02, 1.0), (0.9, 0.95, 1e-3, 0.5, 2)),
    ((0.5, 0.2), (0.5, 0.6, 0.1, 0.5, 2))])
def test_static_torques_ignore_the_solver_settings(solref, solimp):
    m = armature.compile(five_bar, PARAMS)
    m.model.eq_solref[:] = solref
    m.model.eq_solimp[:] = solimp
    ya, ye = 0.3, -0.2
    inv = m.at(q={"A": ya, "E": ye}).inverse()
    got = [inv.torque["motor_A"], inv.torque["motor_E"]]
    assert got == pytest.approx(static_torque(ya, ye), rel=1e-8, abs=1e-12)


def test_mj_inverse_answers_for_the_solver_not_the_mechanism(m):
    """The trap: MuJoCo's own inverse dynamics here returns what the soft
    constraint's slack happens to push, not the motors' torques."""
    s = m.at(q={"A": 0.3, "E": -0.2})
    data = mujoco.MjData(m.model)
    data.qpos[:] = [s.q[n] for n in m.coordinates]
    mujoco.mj_forward(m.model, data)
    data.qacc[:] = 0.0
    mujoco.mj_inverse(m.model, data)
    expected = static_torque(0.3, -0.2) * PARAMS["N"]
    naive = data.qfrc_inverse[[0, 2]]
    assert np.max(np.abs(naive - expected) / np.abs(expected)) > 0.1


def test_mj_inverse_is_never_called_with_constraint_rows(m, monkeypatch):
    def refuse(*args):
        raise AssertionError("mj_inverse called on a state with constraint "
                             "rows")
    monkeypatch.setattr(mujoco, "mj_inverse", refuse)
    s = m.at(q={"A": 0.3, "E": -0.2}, qd={"A": 0.4})
    s.inverse(qdd={"E": 2.0})
    s.wrench("l2")
    s.linearise()


def dynamic_torque(y, yd, ydd, step=1e-5):
    """τ N = M ÿ + (Ṁ ẏ − ½ ∂(ẏᵀ M ẏ)/∂y) + ∂V/∂y, with ∂M/∂y by central
    differences of the reference M."""
    dm = [(ref("mass", *(y + step * e)) - ref("mass", *(y - step * e)))
          / (2 * step) for e in np.eye(2)]
    mdot = sum(dm[k] * yd[k] for k in range(2))
    coriolis = mdot @ yd - 0.5 * np.array([yd @ dm[k] @ yd for k in range(2)])
    need = ref("mass", *y) @ ydd + coriolis + ref("grad", *y).ravel()
    return need / PARAMS["N"]


@pytest.mark.parametrize("seed", range(4))
def test_dynamic_torques_match_lagrange(m, seed):
    rng = np.random.default_rng(seed)
    y, yd, ydd = (rng.uniform(-0.4, 0.4, 2), rng.uniform(-2, 2, 2),
                  rng.uniform(-10, 10, 2))
    s = m.at(q=dict(zip("AE", y)), qd=dict(zip("AE", yd)))
    inv = s.inverse(qdd=dict(zip("AE", ydd)))
    got = [inv.torque["motor_A"], inv.torque["motor_E"]]
    assert got == pytest.approx(dynamic_torque(y, yd, ydd), rel=1e-7)


# --- modes --------------------------------------------------------------------
@pytest.mark.parametrize("ya, ye", [(0.0, 0.0), (0.3, -0.2), (-0.25, 0.35)])
def test_modes_are_on_the_manifold_and_match_minimal_coordinates(m, ya, ye):
    lin = m.at(q={"A": ya, "E": ye}).linearise()
    assert lin.dofs == ("A", "E")
    stiffness, mass = ref("hessian", ya, ye), ref("mass", ya, ye)
    assert lin.stiffness == pytest.approx(stiffness, rel=1e-8, abs=1e-9)
    assert lin.mass == pytest.approx(mass, rel=1e-10)
    lam = np.linalg.eigvals(np.linalg.solve(mass, stiffness)).real
    freq = np.sort(np.sign(lam) * np.sqrt(np.abs(lam)) / (2 * np.pi))
    assert len(lin.frequencies) == 2  # no solver-stiffness mode
    assert lin.frequencies == pytest.approx(freq, rel=1e-8)
    assert lin.residual <= 1e-10


# --- settle and wrench --------------------------------------------------------
def test_settle_under_the_static_torques_stays(m):
    """Held at the virtual-work torques, not the engine's own `inverse`, the
    loop stays where it was put."""
    s = m.at(q={"A": 0.3, "E": -0.2})
    hold = dict(zip(("motor_A", "motor_E"), static_torque(0.3, -0.2)))
    settled = s.settle(hold)
    assert settled.stable
    assert settled.residual <= 1e-6
    for name in m.coordinates:
        assert abs(settled.moved[name]) < 1e-5


def test_settle_raises_when_the_loop_is_left_open():
    m = armature.compile(five_bar, PARAMS)
    m.model.eq_solref[:] = (0.5, 1.0)  # a constraint as soft as a rubber band
    m.model.eq_solimp[:] = (0.1, 0.2, 0.1, 0.5, 2)
    with pytest.raises(RuntimeError, match="loop 'pin'.*open"):
        m.at(q={"A": 0.3, "E": -0.2}).settle()


def test_wrench_counts_the_loop_force(m):
    ya, ye = 0.3, -0.2
    force = np.array([3.0, -5.0, 0.0])
    s = m.at(q={"A": ya, "E": ye})
    # Across the spring joint B the axis carries only the spring's torque,
    # which holds only once the pin's force on l2 is counted.
    wrench_b = s.wrench("l2", loads={"C2": force})
    assert wrench_b.torque[2] == pytest.approx(
        -PARAMS["kB"] * float(ref("q_B", ya, ye)), abs=1e-10)
    wrench_a = s.wrench("l1", loads={"C2": force})
    assert wrench_a.torque[2] == pytest.approx(
        PARAMS["N"] * static_torque(ya, ye, force)[0], rel=1e-8)


def test_symbolic_closure_is_the_pin_gap():
    view = armature.symbolic(five_bar, PARAMS)
    gap = view.closures["pin"]
    home = {s: PARAMS[n] for n, s in view.params.items()}
    home.update({q: 0 for q in view.q.values()})
    assert [sp.N(gap.dot(u).subs(home)) for u in (view.world.x, view.world.y,
                                                  view.world.z)] == [0, 0, 0]


@pytest.mark.parametrize("ya, ye", postures(4))
def test_symbolic_closure_vanishes_on_the_reference_loop(ya, ye):
    """Away from home, the gap is zero at the dependent angles the closed
    form gives, to 1e-14 m, the double precision they are handed over in
    (1e-17 measured); and it opens when B is off them, so the zero is the
    loop's and not the expression's."""
    view = armature.symbolic(five_bar, PARAMS)
    q = view.q

    def gap(q_b):
        at = {s: PARAMS[n] for n, s in view.params.items()}
        at.update({q["A"]: ya, q["E"]: ye, q["B"]: q_b,
                   q["D"]: ref("q_D", ya, ye)})
        return max(abs(sp.N(view.closures["pin"].dot(u).subs(at)))
                   for u in (view.world.x, view.world.y, view.world.z))

    closed = float(ref("q_B", ya, ye))
    assert gap(closed) < 1e-14
    assert gap(closed + 0.01) > 1e-3


# --- the four-bar left by locking E -------------------------------------------
E_HELD = -0.2


def four_bar_torque(y, yd=0.0, ydd=0.0):
    """The motor at A's torque on the four-bar A-B-C-D, D fixed where E is
    held: the reference's Lagrange torque at y_E = E_HELD with ẏ_E = ÿ_E = 0,
    whose A row is τ N = M₁₁ ÿ + ½ ∂M₁₁/∂y ẏ² + ∂V/∂y, l3 still and E's
    rotor with it."""
    return dynamic_torque(np.array([y, E_HELD]), np.array([yd, 0.0]),
                          np.array([ydd, 0.0]))[0]


@pytest.fixture(scope="module")
def four_bar():
    return armature.compile(armature.reduce(
        five_bar, lock("E", E_HELD, assumption="A4")), PARAMS)


def test_locking_e_leaves_a_four_bar_on_one_motor(four_bar):
    assert four_bar.actuators == ("motor_A",)
    assert four_bar.independent == ("A",)
    assert four_bar.dependent == ("B", "D")


@pytest.mark.parametrize("ya, yd, ydd", [(0.3, 0.0, 0.0), (-0.35, 0.0, 0.0),
                                         (0.3, 1.2, -4.0), (-0.1, -2.0, 8.0)])
def test_the_locked_variant_inverse_is_the_four_bar(four_bar, ya, yd, ydd):
    """To 1e-7, the central difference in M′; with E held, the motor at A
    needs what the five-bar's motor A would, the loop closed the same way."""
    s = four_bar.at(q={"A": ya}, qd={"A": yd})
    got = s.inverse(qdd={"A": ydd}).torque["motor_A"]
    assert got == pytest.approx(four_bar_torque(ya, yd, ydd), rel=1e-7)
    assert s.q["D"] == pytest.approx(float(ref("q_D", ya, E_HELD)), abs=1e-11)


def test_release_settles_where_the_five_bar_balances(four_bar):
    """Motor A held at the four-bar's torque, E let go and uncommanded: the
    full five-bar comes to rest where ∂V/∂y_A = N τ_A and ∂V/∂y_E = 0,
    solved in mpmath from the locked posture, a minimum (the Hessian there is
    positive definite). E moves by that root's y_E − E_HELD, about 0.32 rad,
    to 1e-5, the settle's rest."""
    ya = 0.3
    tau = four_bar_torque(ya)
    out = four_bar.at(q={"A": ya}).release(hold={"motor_A": tau})

    def balance(a, e):
        grad = _partials(potential, a, e)
        return [grad[0] - PARAMS["N"] * mp.mpf(tau), grad[1]]

    rest = [float(x) for x in mp.findroot(balance, (mp.mpf(ya),
                                                    mp.mpf(E_HELD)))]
    assert np.all(np.linalg.eigvalsh(ref("hessian", *rest)) > 0)
    assert out.settled.stable
    assert out.residual <= 1e-6  # the pin closed at rest
    assert out.assumed == {"E": E_HELD}
    assert list(out.sized.values()) == [out.moved["E"]]
    assert out.moved["E"] == pytest.approx(rest[1] - E_HELD, abs=1e-5)
    assert out.settled.moved["A"] == pytest.approx(rest[0] - ya, abs=1e-5)
    assert abs(out.moved["E"]) > 0.3  # the lock was wrong, and sized
