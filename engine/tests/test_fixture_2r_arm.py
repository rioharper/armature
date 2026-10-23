"""Fixture 1: the 2R arm, end to end through the description.

Answer: closed forms for FK, the Jacobian, M, g, its stiffness ∂g/∂q, the
static torques and the elbow's reaction wrench, written out here by hand.
Trap: a variant that locks the elbow. Every number in it is right for the
one-body arm it describes, and its release must fail, naming the elbow.
"""

import math

import mujoco
import numpy as np
import pytest
import sympy as sp

import armature
from armature import joint, lock
from golden import arm_2r

# The description is the golden project's: a planar 2R arm in the xy plane,
# gravity along −y, both links along +x at home, each link's inertia a
# slender rod's on every axis.
PARAMS = arm_2r.PARAMS
arm = arm_2r.mechanism
SEED = 20261011


def shoulder_only(p):
    return [e for e in arm(p) if getattr(e, "name", None) != "elbow_motor"]


RIGID_ELBOW = armature.reduce(arm, lock("elbow", 0.0, assumption="A3"),
                              name="rigid elbow")

# --- the closed forms ---------------------------------------------------------
P = PARAMS


def tip(q1, q2):
    return np.array([P["l1"] * math.cos(q1) + P["l2"] * math.cos(q1 + q2),
                     P["l1"] * math.sin(q1) + P["l2"] * math.sin(q1 + q2), 0])


def jacobian(q1, q2):
    s1, s12 = math.sin(q1), math.sin(q1 + q2)
    c1, c12 = math.cos(q1), math.cos(q1 + q2)
    return np.array([[-P["l1"] * s1 - P["l2"] * s12, -P["l2"] * s12],
                     [P["l1"] * c1 + P["l2"] * c12, P["l2"] * c12],
                     [0, 0]])


def mass_matrix(q2, rotors=True):
    h = P["m2"] * P["l1"] * P["lc2"] * math.cos(q2)
    m11 = (P["I1"] + P["I2"] + P["m1"] * P["lc1"] ** 2
           + P["m2"] * (P["l1"] ** 2 + P["lc2"] ** 2) + 2 * h)
    m12 = P["I2"] + P["m2"] * P["lc2"] ** 2 + h
    m22 = P["I2"] + P["m2"] * P["lc2"] ** 2
    if rotors:
        m11 += P["N1"] ** 2 * P["J1"]
        m22 += P["N2"] ** 2 * P["J2"]
    return np.array([[m11, m12], [m12, m22]])


def gravity_torque(q1, q2):
    c1, c12 = math.cos(q1), math.cos(q1 + q2)
    return P["g"] * np.array([(P["m1"] * P["lc1"] + P["m2"] * P["l1"]) * c1
                              + P["m2"] * P["lc2"] * c12,
                              P["m2"] * P["lc2"] * c12])


def gravity_potential(q1, q2):
    """V, the links' weight times their COMs' height along y; g = ∂V/∂q."""
    return P["g"] * ((P["m1"] * P["lc1"] + P["m2"] * P["l1"]) * np.sin(q1)
                     + P["m2"] * P["lc2"] * np.sin(q1 + q2))


def gravity_stiffness(q1, q2):
    """K = ∂g/∂q, the gravity torque's own derivative."""
    s1, s12 = math.sin(q1), math.sin(q1 + q2)
    a, b = P["m1"] * P["lc1"] + P["m2"] * P["l1"], P["m2"] * P["lc2"]
    return -P["g"] * np.array([[a * s1 + b * s12, b * s12],
                               [b * s12, b * s12]])


def coriolis(q2, qd1, qd2):
    h = P["m2"] * P["l1"] * P["lc2"] * math.sin(q2)
    return np.array([-h * (2 * qd1 * qd2 + qd2 ** 2), h * qd1 ** 2])


def joint_torque(q, qd, qdd, tip_force=np.zeros(3)):
    """τ = M q̈ + C q̇ + g − Jᵀ f at the joints."""
    return (mass_matrix(q[1]) @ qdd + coriolis(q[1], *qd)
            + gravity_torque(*q) - jacobian(*q)[:2].T @ tip_force[:2])


def elbow_wrench(q, qd, qdd, tip_force):
    """Newton–Euler on the forearm: the force and the torque about the elbow
    that the upper link exerts on it."""
    q1, q12 = q[0], q[0] + q[1]
    w1, w12 = qd[0], qd[0] + qd[1]
    a1, a12 = qdd[0], qdd[0] + qdd[1]
    elbow = P["l1"] * np.array([math.cos(q1), math.sin(q1), 0])
    com = elbow + P["lc2"] * np.array([math.cos(q12), math.sin(q12), 0])
    accel = (P["l1"] * np.array([-math.sin(q1) * a1 - math.cos(q1) * w1 ** 2,
                                 math.cos(q1) * a1 - math.sin(q1) * w1 ** 2, 0])
             + P["lc2"] * np.array([-math.sin(q12) * a12
                                    - math.cos(q12) * w12 ** 2,
                                    math.cos(q12) * a12
                                    - math.sin(q12) * w12 ** 2, 0]))
    weight = P["m2"] * np.array([0, -P["g"], 0])
    force = P["m2"] * accel - weight - tip_force
    torque = (np.array([0, 0, P["I2"] * a12])
              + np.cross(com - elbow, P["m2"] * accel - weight)
              - np.cross(tip(*q) - elbow, tip_force))
    return force, torque


def sampled_states(n, seed=SEED):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        yield (rng.uniform([-3.0, 0.3], [3.0, 2.5]),
               rng.uniform(-1, 1, 2) * [3.0, 4.0],
               rng.uniform(-1, 1, 2) * [20.0, 30.0])


def _named(values):
    return dict(zip(("shoulder", "elbow"), values))


@pytest.fixture(scope="module")
def m():
    return armature.compile(arm, PARAMS)


# --- kinematics ---------------------------------------------------------------

@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(6)))
def test_pose_and_jacobian_are_the_closed_forms(m, q, qd, qdd):
    s = m.at(q=_named(q))
    pose, jac = s.pose("tip"), s.jacobian("tip")
    assert pose.position == pytest.approx(tip(*q), abs=1e-12)
    turn = q[0] + q[1]
    assert pose.rotation == pytest.approx(
        np.array([[math.cos(turn), -math.sin(turn), 0],
                  [math.sin(turn), math.cos(turn), 0], [0, 0, 1]]), abs=1e-12)
    assert jac.linear == pytest.approx(jacobian(*q), abs=1e-12)
    assert jac.angular == pytest.approx(np.array([[0, 0], [0, 0], [1, 1]]),
                                        abs=1e-12)
    assert jac.dofs == ("shoulder", "elbow")
    for record in (pose, jac):
        assert record.residual == 0.0 and record.method


# --- dynamics -----------------------------------------------------------------

@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(6)))
def test_mass_matrix_carries_the_reflected_rotors(m, q, qd, qdd):
    lin = m.at(q=_named(q)).linearise()
    assert lin.mass == pytest.approx(mass_matrix(q[1]), rel=1e-12)
    assert lin.mass[0, 0] - mass_matrix(q[1], rotors=False)[0, 0] == \
        pytest.approx(P["N1"] ** 2 * P["J1"])


@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(6)))
def test_stiffness_is_the_gravity_torques_derivative(m, q, qd, qdd):
    lin = m.at(q=_named(q)).linearise()
    assert lin.stiffness == pytest.approx(gravity_stiffness(*q), abs=1e-6)


def test_hanging_modes_are_the_closed_form(m):
    """Hanging straight down, the arm rests with K = g [[a + b, b], [b, b]],
    a = m1·lc1 + m2·l1 and b = m2·lc2, and its modes solve K v = ω² M v."""
    a, b = P["m1"] * P["lc1"] + P["m2"] * P["l1"], P["m2"] * P["lc2"]
    k = P["g"] * np.array([[a + b, b], [b, b]])
    mass = mass_matrix(0.0)
    expected = np.sqrt(np.sort(np.linalg.eigvals(np.linalg.solve(mass, k))
                               .real)) / (2 * math.pi)
    lin = m.at(q=_named((-math.pi / 2, 0.0))).linearise()
    assert lin.stiffness == pytest.approx(k, rel=1e-6)
    assert np.all(expected > 0)
    assert lin.frequencies == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(6)))
def test_static_torques_are_the_closed_form(m, q, qd, qdd):
    inv = m.at(q=_named(q)).inverse()
    expected = gravity_torque(*q) / [P["N1"], P["N2"]]
    assert [inv.torque["shoulder_motor"], inv.torque["elbow_motor"]] == \
        pytest.approx(expected, rel=1e-10)
    assert dict(inv.generalised) == pytest.approx(_named(gravity_torque(*q)),
                                                  rel=1e-10)
    assert inv.rank == 2 and math.isfinite(inv.condition)
    assert inv.residual < 1e-12
    assert inv.constraint == {}
    assert "never mj_inverse" in inv.method


@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(6)))
def test_inverse_is_the_closed_form_at_sampled_states(m, q, qd, qdd):
    force = np.array([3.0, -7.0, 0.0])
    inv = m.at(q=_named(q), qd=_named(qd)).inverse(qdd=_named(qdd),
                                                   loads={"tip": force})
    expected = joint_torque(q, qd, qdd, force) / [P["N1"], P["N2"]]
    assert [inv.torque["shoulder_motor"], inv.torque["elbow_motor"]] == \
        pytest.approx(expected, rel=1e-9)


def sprung_arm(p):
    """The arm with a spring at the elbow, so the passive force is not zero."""
    out = arm(p)
    out[3] = joint("elbow", "hinge", parent="upper", child="fore",
                   axis=(0, 0, 1), point=(p["l1"], 0, 0), range=(-2.6, 2.6),
                   stiffness=4.0, rest=0.5)
    return out


@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(4)))
def test_inverse_agrees_with_mj_inverse_on_an_open_chain(q, qd, qdd):
    m = armature.compile(sprung_arm, PARAMS)
    inv = m.at(q=_named(q), qd=_named(qd)).inverse(qdd=_named(qdd))
    data = mujoco.MjData(m.model)
    data.qpos[:], data.qvel[:], data.qacc[:] = q, qd, qdd
    mujoco.mj_inverse(m.model, data)
    assert data.qfrc_passive[1] != 0.0
    assert [inv.torque["shoulder_motor"] * P["N1"],
            inv.torque["elbow_motor"] * P["N2"]] == \
        pytest.approx(data.qfrc_inverse, rel=1e-10)


def test_an_unactuated_coordinate_leaves_a_residual():
    """With no elbow motor, nothing can supply the elbow's gravity torque: the
    solve reports it as its residual rather than a torque."""
    q = (0.4, 0.9)
    inv = armature.compile(shoulder_only, PARAMS).at(q=_named(q)).inverse()
    assert inv.residual == pytest.approx(gravity_torque(*q)[1], rel=1e-10)
    assert inv.rank == 1 and set(inv.torque) == {"shoulder_motor"}


def test_inverse_names_torques_beyond_the_limit(m):
    q = _named((0.0, 0.5))
    assert m.at(q=q).inverse().over_limit == ()
    heavy = m.at(q=q).inverse(loads={"tip": (0, -200.0, 0)})
    assert heavy.over_limit == ("shoulder_motor", "elbow_motor")


# --- the wrench ---------------------------------------------------------------

@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(6)))
def test_elbow_wrench_is_the_closed_form(m, q, qd, qdd):
    force = np.array([3.0, -7.0, 0.0])
    s = m.at(q=_named(q), qd=_named(qd))
    w = s.wrench("fore", qdd=_named(qdd), loads={"tip": force})
    expected_force, expected_torque = elbow_wrench(q, qd, qdd, force)
    assert w.joint == "elbow"
    assert w.point == pytest.approx(
        [P["l1"] * math.cos(q[0]), P["l1"] * math.sin(q[0]), 0], abs=1e-12)
    assert w.force == pytest.approx(expected_force, abs=1e-9)
    assert w.torque == pytest.approx(expected_torque, abs=1e-9)

    # Consistent with the explicit solve: along the axis, the elbow carries
    # its motor's torque less what accelerates the rotor.
    inv = s.inverse(qdd=_named(qdd), loads={"tip": force})
    rotor = P["N2"] ** 2 * P["J2"] * qdd[1]
    assert w.torque[2] == pytest.approx(
        P["N2"] * inv.torque["elbow_motor"] - rotor, rel=1e-9)


def test_wrench_refuses_a_body_without_a_joint():
    s = armature.compile(RIGID_ELBOW, PARAMS).at()
    with pytest.raises(ValueError, match="'fore'"):
        s.wrench("fore")
    with pytest.raises(KeyError, match="'hand'"):
        s.wrench("hand")


# --- settle -------------------------------------------------------------------

@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(8)))
def test_settle_holds_the_analytic_static_torque(m, q, qd, qdd):
    hold = gravity_torque(*q) / [P["N1"], P["N2"]]
    out = m.at(q=_named(q)).settle(
        hold={"shoulder_motor": hold[0], "elbow_motor": hold[1]})
    assert out.stable and out.steps >= 500
    assert max(abs(v) for v in out.moved.values()) < 1e-4, dict(out.moved)
    assert out.constraints == () and out.over_limit == ()


def test_settle_does_not_hold_a_20_percent_wrong_torque(m):
    q, _, _ = next(sampled_states(1))
    hold = gravity_torque(*q) / [P["N1"], P["N2"]]
    out = m.at(q=_named(q)).settle(
        hold={"shoulder_motor": 1.2 * hold[0], "elbow_motor": hold[1]})
    assert max(abs(v) for v in out.moved.values()) > 1e-2, dict(out.moved)


def test_settle_holds_a_site_load(m):
    """A tip load, applied where it acts: the closed form −Jᵀf holds it."""
    q, force = (0.3, 1.1), np.array([2.0, -5.0, 0.0])
    tau = (gravity_torque(*q) - jacobian(*q)[:2].T @ force[:2]) / [P["N1"],
                                                                 P["N2"]]
    out = m.at(q=_named(q)).settle(
        hold={"shoulder_motor": tau[0], "elbow_motor": tau[1]},
        loads={"tip": force})
    assert out.stable
    assert max(abs(v) for v in out.moved.values()) < 1e-4, dict(out.moved)


def test_settle_clamps_a_hold_beyond_the_limit_and_names_it(m):
    out = m.at(q=_named((0.0, 0.5))).settle(hold={"shoulder_motor": 2.0})
    assert out.over_limit == ("shoulder_motor",)


def test_settle_refuses_an_unknown_actuator(m):
    with pytest.raises(KeyError, match="'wrist_motor'"):
        m.at().settle(hold={"wrist_motor": 1.0})


# --- variants and the locked elbow ---------------------------------------------

def one_link_shoulder_torque(q1):
    """The locked-elbow derivation's holding torque at the shoulder: the arm
    as one body, each mass times its lever about the base. Right for the
    machine it describes, and that machine does not exist."""
    return P["g"] * math.cos(q1) * (P["m1"] * P["lc1"]
                                    + P["m2"] * (P["l1"] + P["lc2"]))


def test_lock_compiles_as_a_weld():
    v = armature.compile(RIGID_ELBOW, PARAMS)
    assert v.coordinates == ("shoulder",)
    assert v.actuators == ("shoulder_motor",)
    assert v.model.neq == 0  # no joint equality: a weld is exact
    assert v.model.body("fore").weldid[0] == v.model.body("upper").id
    assert v.description.reductions[0].assumption == "A3"
    assert v.description.variant == "rigid elbow"


def test_lock_poses_the_child_at_the_locked_value():
    locked = armature.reduce(arm, lock("elbow", 0.7, assumption="A3"))
    v, full = armature.compile(locked, PARAMS), armature.compile(arm, PARAMS)
    for q1 in (-1.2, 0.0, 2.1):
        assert v.at(q={"shoulder": q1}).pose("tip").position == pytest.approx(
            full.at(q={"shoulder": q1, "elbow": 0.7}).pose("tip").position,
            abs=1e-12)
    # Locked, the elbow's rate is zero: the one body's inertia about the
    # shoulder is the full arm's M11 there, and the elbow's rotor is gone.
    assert v.at().linearise().mass[0, 0] == pytest.approx(
        full.at(q={"elbow": 0.7}).linearise().mass[0, 0], rel=1e-12)


def test_the_variant_inverse_is_the_one_body_arm():
    v = armature.compile(RIGID_ELBOW, PARAMS)
    inv = v.at(q={"shoulder": 0.4}).inverse()
    assert inv.torque["shoulder_motor"] * P["N1"] == pytest.approx(
        one_link_shoulder_torque(0.4), rel=1e-10)


def test_a_true_lock_releases_to_nothing():
    """With the forearm hanging straight down, the elbow carries no gravity
    torque: the lock is sized at nothing, and it passes. The lock sits away
    from home, so the release has to start the full model at the locked
    value."""
    bent = armature.reduce(arm, lock("elbow", 0.7, assumption="A3"))
    s = armature.compile(bent, PARAMS).at(q={"shoulder": -math.pi / 2 - 0.7})
    out = s.release(hold=s.inverse().torque)
    assert out.settled.stable
    assert set(out.moved) == {"elbow"}
    assert abs(out.moved["elbow"]) < 1e-6
    assert abs(out.settled.moved["shoulder"]) < 1e-6
    assert out.assumed == {"elbow": 0.7}


def test_release_names_the_elbow_and_its_displacement():
    q1 = 0.4
    out = armature.compile(RIGID_ELBOW, PARAMS).at(q={"shoulder": q1}).release(
        hold={"shoulder_motor": one_link_shoulder_torque(q1) / P["N1"]})
    assert out.moved["elbow"] < -1e-2  # it falls, and the sign says which way
    assert "'elbow'" in str(out) and "A3" in str(out)
    assert out.variant == "rigid elbow"
    assert set(out.settled.moved) == {"shoulder", "elbow"}


def test_release_refuses_a_command_on_the_locked_coordinate():
    s = armature.compile(RIGID_ELBOW, PARAMS).at()
    with pytest.raises(KeyError, match="elbow_motor"):
        s.release(hold={"elbow_motor": 0.1})


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="the trap: a locked-elbow derivation must fail its "
                          "release")
def test_the_locked_elbow_trap_fails_its_release():
    """The check a milestone writes for the locked-elbow derivation: hold what
    it says holds this posture, release, and assert the elbow stays put. It
    must fail, naming the elbow; a check nobody has watched fail is a check
    with no evidence behind it."""
    q1 = 0.4
    out = armature.compile(RIGID_ELBOW, PARAMS).at(q={"shoulder": q1}).release(
        hold={"shoulder_motor": one_link_shoulder_torque(q1) / P["N1"]})
    assert abs(out.moved["elbow"]) < 1e-3, str(out)


def test_lock_validation_names_the_reduction():
    for bad, words in ((lock("wrist", 0.0, assumption="A3"), "'wrist'"),
                       (lock("elbow", 3.0, assumption="A3"), "outside"),
                       (lock("elbow", 0.0, assumption=None), "assumption")):
        with pytest.raises(armature.DescriptionError, match=words):
            armature.compile(armature.reduce(arm, bad), PARAMS)


# --- the symbolic view ---------------------------------------------------------

@pytest.fixture(scope="module")
def view():
    return armature.symbolic(arm, PARAMS)


def test_symbolic_fk_is_the_closed_form(view):
    p, q = view.params, view.q
    q1, q2 = q["shoulder"], q["elbow"]
    closed = sp.Matrix([p["l1"] * sp.cos(q1) + p["l2"] * sp.cos(q1 + q2),
                        p["l1"] * sp.sin(q1) + p["l2"] * sp.sin(q1 + q2), 0])
    got = view.sites["tip"].pos_from(view.origin).to_matrix(view.world)
    assert sp.simplify(sp.expand_trig(got - closed)) == sp.zeros(3, 1)
    assert view.coordinates == armature.compile(arm, PARAMS).coordinates


def test_symbolic_inertia_dyadics_match_the_description(view):
    p = view.params
    for name, (ix, i) in (("upper", ("Ix1", "I1")), ("fore", ("Ix2", "I2"))):
        tensor = view.inertia[name].to_matrix(view.frames[name])
        assert tensor == sp.diag(p[ix], p[i], p[i])
    assert view.mass == {"upper": p["m1"], "fore": p["m2"]}
    assert view.gravity == -p["g"] * view.world.y
    assert view.axes["elbow"].to_matrix(view.world) == sp.Matrix([0, 0, 1])


def test_symbolic_kinetic_energy_gives_the_closed_form_mass_matrix(view):
    """The view is enough to form the dynamics: ½ Σ (m v·v + ω·I·ω) from its
    frames, points and dyadics has the closed-form M (without rotors, which
    the derivation adds from the actuators)."""
    rates = [sp.Symbol(f"v{i}") for i in range(2)]
    swap = dict(zip([c.diff() for c in view.q.values()], rates))
    energy = 0
    for name, frame in view.frames.items():
        v = view.com[name].vel(view.world)
        w = frame.ang_vel_in(view.world)
        energy += (view.mass[name] * v.dot(v)
                   + w.dot(view.inertia[name].dot(w))) / 2
    energy = energy.subs(swap)
    mass = sp.hessian(energy, rates)
    numbers = {view.params[k]: v for k, v in PARAMS.items()}
    q2 = 0.9
    numbers[view.q["elbow"]] = q2
    got = np.array(mass.subs(numbers), dtype=float)
    assert got == pytest.approx(mass_matrix(q2, rotors=False), rel=1e-12)


def test_symbolic_view_agrees_with_the_compiled_model(view):
    m = armature.compile(arm, PARAMS)
    numbers = {view.params[k]: v for k, v in PARAMS.items()}
    for q, _, _ in sampled_states(3):
        at = {**numbers, **dict(zip(view.q.values(), q))}
        point = view.sites["tip"].pos_from(view.origin).to_matrix(view.world)
        rotation = view.world.dcm(view.frames["fore"])
        s = m.at(q=_named(q))
        assert np.array(point.subs(at), dtype=float).ravel() == \
            pytest.approx(s.pose("tip").position, abs=1e-12)
        assert np.array(rotation.subs(at), dtype=float) == \
            pytest.approx(s.pose("tip").rotation, abs=1e-12)


# The same arm as a ledger states it (ADR 0010): each link's inertia one
# tensor parameter, and the tool's seat one vector parameter, in place of l2.
TENSOR_PARAMS = {
    **{k: v for k, v in PARAMS.items()
       if k not in ("I1", "I2", "Ix1", "Ix2", "l2")},
    "I_upper": np.diag([P["Ix1"], P["I1"], P["I1"]]),
    "I_fore": np.diag([P["Ix2"], P["I2"], P["I2"]]),
    "tip_at": np.array([P["l1"] + P["l2"], 0.0, 0.0])}


def tensor_arm(p):
    return [
        armature.body("upper", mass=p["m1"], com=(p["lc1"], 0, 0),
                      inertia=p["I_upper"]),
        armature.body("fore", mass=p["m2"], com=(p["l1"] + p["lc2"], 0, 0),
                      inertia=p["I_fore"]),
        joint("shoulder", "hinge", parent="world", child="upper",
              axis=(0, 0, 1), point=(0, 0, 0), range=(-math.pi, math.pi)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 0, 1),
              point=(p["l1"], 0, 0), range=(-2.6, 2.6)),
        armature.site("tip", body="fore", pos=p["tip_at"]),
        armature.actuator("shoulder_motor", joint="shoulder", gear=p["N1"],
                          rotor_inertia=p["J1"], torque_limit=p["limit"]),
        armature.actuator("elbow_motor", joint="elbow", gear=p["N2"],
                          rotor_inertia=p["J2"], torque_limit=p["limit"]),
        armature.gravity((0, -p["g"], 0)),
    ]


def test_symbolic_view_of_tensor_and_vector_parameters():
    """A tensor parameter is a symmetric 3×3 of symbols, a vector one a
    3-vector, and `numbers` substitutes each element: the view then gives
    the closed-form M and tip, as the scalar arm's does."""
    view = armature.symbolic(tensor_arm, TENSOR_PARAMS)
    tensor = view.params["I_upper"]
    assert tensor.shape == (3, 3) and len({*tensor.ravel()}) == 6
    assert all(tensor[i, j] == tensor[j, i] for i in range(3)
               for j in range(3))
    assert view.params["tip_at"].shape == (3,)
    assert isinstance(view.params["m1"], sp.Symbol)

    q2 = 0.9
    numbers = {**view.numbers(TENSOR_PARAMS), view.q["shoulder"]: 0.4,
               view.q["elbow"]: q2}
    rates = [sp.Symbol(f"v{i}") for i in range(2)]
    swap = dict(zip([c.diff() for c in view.q.values()], rates))
    energy = sum((view.mass[name] * view.com[name].vel(view.world).dot(
        view.com[name].vel(view.world)) + frame.ang_vel_in(view.world).dot(
        view.inertia[name].dot(frame.ang_vel_in(view.world)))) / 2
        for name, frame in view.frames.items()).subs(swap)
    got = np.array(sp.hessian(energy, rates).subs(numbers), dtype=float)
    assert got == pytest.approx(mass_matrix(q2, rotors=False), rel=1e-12)
    point = view.sites["tip"].pos_from(view.origin).to_matrix(view.world)
    assert np.array(point.subs(numbers), dtype=float).ravel() == \
        pytest.approx(tip(0.4, q2), abs=1e-12)

    skew = TENSOR_PARAMS["I_upper"] + np.array([[0, 1e-3, 0], [0, 0, 0],
                                                [0, 0, 0]])
    with pytest.raises(ValueError, match="I_upper.*not symmetric"):
        view.numbers({"I_upper": skew})


def test_symbolic_variant_drops_the_locked_coordinate():
    locked = armature.reduce(arm, lock("elbow", 0.7, assumption="A3"))
    view = armature.symbolic(locked, PARAMS)
    assert view.coordinates == ("shoulder",)
    p, q1 = view.params, view.q["shoulder"]
    closed = sp.Matrix([p["l1"] * sp.cos(q1) + p["l2"] * sp.cos(q1 + 0.7),
                        p["l1"] * sp.sin(q1) + p["l2"] * sp.sin(q1 + 0.7), 0])
    got = view.sites["tip"].pos_from(view.origin).to_matrix(view.world)
    numbers = {**{p[k]: v for k, v in PARAMS.items()}, q1: 0.3}
    assert np.array((got - closed).subs(numbers), dtype=float) == \
        pytest.approx(np.zeros((3, 1)), abs=1e-14)


# --- the equations -------------------------------------------------------------

@pytest.fixture(scope="module")
def equations():
    return armature.equations(arm, PARAMS)


@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(6)))
def test_equations_are_the_closed_form(equations, q, qd, qdd):
    """M, C q̇ and g, formed by the engine, against the closed forms above
    (without rotors, which the derivation adds from the actuators)."""
    e = equations
    assert e.coordinates == ("shoulder", "elbow")
    got_m = np.asarray(e.numeric(e.M)(*q), dtype=float)
    got_c = np.asarray(e.numeric(e.Cqd, rates=True)(*q, *qd),
                       dtype=float).ravel()
    got_g = np.asarray(e.numeric(e.g)(*q), dtype=float).ravel()
    assert got_m == pytest.approx(mass_matrix(q[1], rotors=False), abs=1e-12)
    assert got_c == pytest.approx(coriolis(q[1], *qd), abs=1e-12)
    assert got_g == pytest.approx(gravity_torque(*q), abs=1e-12)


@pytest.mark.parametrize("q, qd, qdd", list(sampled_states(3)))
def test_christoffel_is_the_closed_form(equations, q, qd, qdd):
    """C, formed on demand, against the planar elbow's Christoffel form
    (Spong, Hutchinson and Vidyasagar, ch. 7)."""
    e = equations
    h = -P["m2"] * P["l1"] * P["lc2"] * math.sin(q[1])
    closed = np.array([[h * qd[1], h * (qd[0] + qd[1])], [-h * qd[0], 0.0]])
    got = np.asarray(e.numeric(e.christoffel(), rates=True)(*q, *qd),
                     dtype=float)
    assert got == pytest.approx(closed, abs=1e-12)
    assert e.christoffel() is e.christoffel()


def test_numeric_takes_a_band_and_refuses_an_unknown_one():
    e = armature.equations(arm, PARAMS, bands=("m2",))
    g = e.numeric(e.g)
    q = (0.3, 0.9)
    heavier = {**PARAMS, "m2": PARAMS["m2"] * 1.1}
    want = P["g"] * heavier["m2"] * P["lc2"] * math.cos(q[0] + q[1])
    assert float(np.ravel(g(*q, m2=heavier["m2"]))[1]) == \
        pytest.approx(want, rel=1e-12)
    assert np.ravel(g(*q)) == pytest.approx(gravity_torque(*q), abs=1e-12)
    with pytest.raises(TypeError, match="no band"):
        g(*q, m1=1.0)
