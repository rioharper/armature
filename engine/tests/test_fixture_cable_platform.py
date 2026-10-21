"""Fixture 2: a platform on four cables, Plumb Rev 1.0's rig.

The anchor square (4 m, at 2.4 m) is a scaled copy of the attachment square
(0.15 m), so the six rows of the structure matrix span only three dimensions
(Pott 2018, ch. 3): all three rotations are free at first order, and gravity
alone sets the orientation. Each pose's cable rest lengths come from the
level-platform tension law of Plumb's Milestone 1 Rev 1.0 (01_kinematics.md
§3), written out below.

Answer: the settle table in docs/research/2026-09-15-derive-one-shot-
correctness.md §2, reproduced by an independent minimisation of the potential
here, and K_yaw = m g A d / z0 (Plumb's M1 review, F2). Trap: the
level-platform assumption, exact at the room centre and wrong everywhere else.
"""

import math

import mujoco
import numpy as np
import pytest
import sympy as sp
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation

import armature
from armature import body, joint, lock, site
from golden import cable_platform
from golden.answers import PLATFORM_TILT

# The description is the golden project's, hung at HOME, the room centre; its
# own PARAMS are the law's rest lengths at its POSE. Every other pose here
# takes `params(point, m)`. The platform's inertia is a tensor, one of
# PARAMS, which every pose's parameters carry.
RIG = cable_platform.params
G, EA, ANCHORS, ATTACH, COM, HOME = (RIG.G, RIG.EA, RIG.ANCHORS, RIG.ATTACH,
                                     RIG.COM, RIG.HOME)
I_P = cable_platform.PARAMS["I_P"]
platform = cable_platform.mechanism
T_HARD, T_PREF, T_CEIL = 3.0, 10.0, 60.0

# (pose, point, mass, tilt °, |Δp| mm, tensions N) from §2's table. Its top
# edge row printed 35.73 / 8.84 N from a damped settle stopped at 20 s; the
# review's own minimisation, this settle and the one below all give 35.68 and
# 8.82 (8.8245).
POSES = [
    ("room centre", (2.0, 2.0, 1.2), 2.0, 0.0, 0.0, (12.16, 12.16, 12.16, 12.16)),
    ("edge midpoint", (0.5, 2.0, 1.2), 2.0, 20.8, 26.8, (16.71, 3.93, 3.93, 16.71)),
    ("top edge midpoint", (2.0, 0.5, 1.9), 2.0, 14.7, 13.0, (35.68, 35.68, 8.82, 8.82)),
    ("low corner", (0.5, 0.5, 0.4), 2.5, 26.3, 52.3, (22.61, 0.0, 7.72, 0.0)),
]
OFF_CENTRE = [pose for pose in POSES if pose[0] != "room centre"]


LEVEL = armature.reduce(platform, *(lock(f"hang:{c}", 0.0, assumption="A5")
                                    for c in ("rx", "ry", "rz")),
                        name="level platform")


# --- the answers, none of them from the engine --------------------------------
def law(point, m):
    """Plumb Rev 1.0's tension law at a level pose: T = T_p + λ n on the
    force rows, the floor the largest the pose admits clamped to [T_hard,
    T_pref], λ the midpoint of the interval that floor and T_ceil leave.
    Returns the tensions and the rest lengths that carry them."""
    span = ANCHORS - (point + ATTACH)
    length = np.linalg.norm(span, axis=1)
    rows = (span / length[:, None]).T
    t_p = np.linalg.pinv(rows) @ (m * G * np.array([0.0, 0.0, 1.0]))
    n = np.linalg.svd(rows)[2][-1]

    def interval(lo, hi):
        a, b = -np.inf, np.inf
        for t, k in zip(t_p, n):
            if k > 0:
                a, b = max(a, (lo - t) / k), min(b, (hi - t) / k)
            elif k < 0:
                a, b = max(a, (hi - t) / k), min(b, (lo - t) / k)
        return a, b

    cap_lo, cap_hi = interval(-np.inf, T_CEIL)
    candidates = [c for c in (cap_lo, cap_hi) if np.isfinite(c)]
    candidates += [(t_p[j] - t_p[i]) / (n[i] - n[j])
                   for i in np.flatnonzero(n > 0) for j in np.flatnonzero(n < 0)]
    floor = min(max(np.min(t_p + c * n) for c in candidates
                    if cap_lo <= c <= cap_hi), T_PREF)
    lo, hi = interval(floor, T_CEIL)
    tension = t_p + 0.5 * (lo + hi) * n
    return tension, length / (1 + tension / EA)


def params(point, m):
    _, rest = law(np.asarray(point, float), m)
    return {"m": m, **{f"l0_{i + 1}": rest[i] for i in range(4)}, "I_P": I_P}


def potential(point, m, rest, turn=None):
    """The rig's potential over (Δp, rotation vector), cables as unilateral
    springs: the review's own model. The rotation vector turns the platform
    about base axes through its point, from the orientation `turn` (level if
    None)."""
    k = EA / rest
    turn = np.eye(3) if turn is None else turn

    def v(x):
        rot = Rotation.from_rotvec(x[3:]).as_matrix() @ turn
        at = point + x[:3]
        span = np.linalg.norm(ANCHORS - (at + ATTACH @ rot.T), axis=1)
        return (0.5 * np.sum(k * np.maximum(span - rest, 0) ** 2)
                + m * G * (at + rot @ COM)[2])
    return v


def gradient(v, x, h=1e-6):
    """∇v at x, by central differences."""
    e = np.eye(len(x))
    return np.array([(v(x + h * e[i]) - v(x - h * e[i])) / (2 * h)
                     for i in range(len(x))])


def tilt(rotation):
    return math.degrees(math.acos(min(1.0, rotation[2, 2])))


def settled(point, m):
    p = params(point, m)
    return armature.compile(platform, p).at(
        q={"hang": (point, np.eye(3))}).settle()


# --- the settle table ----------------------------------------------------------
@pytest.mark.parametrize("name, point, m, tilt_deg, dp_mm, tensions", POSES,
                         ids=[p[0] for p in POSES])
def test_settle_reproduces_the_table(name, point, m, tilt_deg, dp_mm, tensions):
    out = settled(point, m)
    assert out.stable, name
    rest = out.q["hang"]
    assert tilt(rest.rotation) == pytest.approx(tilt_deg, abs=0.05)
    assert np.linalg.norm(out.moved["hang"].position) * 1e3 == pytest.approx(
        dp_mm, abs=0.05)
    assert list(out.tension.values()) == pytest.approx(list(tensions), abs=0.005)
    assert np.allclose(rest.position - point, out.moved["hang"].position)


@pytest.mark.parametrize("name, point, m", [p[:3] for p in OFF_CENTRE],
                         ids=[p[0] for p in OFF_CENTRE])
def test_settle_is_the_potential_minimum(name, point, m):
    point = np.asarray(point, float)
    rest = law(point, m)[1]
    found = minimize(potential(point, m, rest), np.zeros(6), method="BFGS",
                     options={"gtol": 1e-10})
    rotation = Rotation.from_rotvec(found.x[3:]).as_matrix()
    out = settled(point, m)
    assert out.q["hang"].position == pytest.approx(point + found.x[:3],
                                                   abs=2e-6)
    assert np.max(np.abs(out.q["hang"].rotation - rotation)) < 2e-5


# Placements away from rest: the edge midpoint level, where the law leaves a
# moment; and turned and displaced there, and at the low corner.
OFF_REST = [
    ((0.5, 2.0, 1.2), 2.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
    ((0.5, 2.0, 1.2), 2.0, (0.01, -0.02, 0.003), (0.1, -0.2, 0.05)),
    ((0.5, 0.5, 0.4), 2.5, (-0.004, 0.006, 0.002), (-0.3, 0.25, 0.05)),
]


@pytest.mark.parametrize("point, m, shift, euler", OFF_REST)
def test_floating_need_is_the_potentials_gradient(point, m, shift, euler):
    """With no actuator to supply it, the generalised force the platform
    needs to stay put is ∇V, by central differences of the potential: the
    force on it is −∇V. Its rows are the point's three translations and turns
    about base axes through it, which the potential's rotation vector is."""
    point = np.asarray(point, float)
    turn = Rotation.from_euler("xyz", euler).as_matrix()
    at = point + shift
    grad = gradient(potential(at, m, law(point, m)[1], turn), np.zeros(6))
    inv = armature.compile(platform, params(point, m)).at(
        q={"hang": (at, turn)}).inverse()
    assert inv.torque == {} and inv.rank == 0
    assert list(inv.generalised.values()) == pytest.approx(grad, rel=1e-6,
                                                           abs=1e-6)
    assert inv.residual == pytest.approx(np.max(np.abs(grad)), rel=1e-6)
    assert np.max(np.abs(grad)) > 1.0  # away from rest


def test_slack_cables_read_exactly_zero():
    out = settled((0.5, 0.5, 0.4), 2.5)
    assert out.tension["c2"] == 0.0 and out.tension["c4"] == 0.0
    assert out.tension["c1"] > 20 and out.tension["c3"] > 7


def test_level_start_is_balanced_only_at_the_centre():
    # The law balances the force rows only; the moment it leaves is what the
    # platform tilts to absorb.
    assert settled(HOME, 2.0).moved["hang"].rotation == pytest.approx(
        np.eye(3), abs=1e-12)


def test_the_golden_rest_lengths_are_the_law_at_its_pose():
    m = cable_platform.PARAMS["m"]
    want = params(RIG.POSE, m)
    assert cable_platform.PARAMS.keys() == want.keys()
    rest = [f"l0_{i + 1}" for i in range(4)]
    assert [cable_platform.PARAMS[k] for k in rest] == pytest.approx(
        [want[k] for k in rest], rel=1e-12)


def test_settle_tilts_to_the_answer_at_the_stated_pose():
    """The golden project, hung at its POSE: the tilt is the answer's,
    found in mpmath from the same cables."""
    out = armature.compile(platform, cable_platform.PARAMS).at(
        q={"hang": (RIG.POSE, np.eye(3))}).settle()
    assert out.stable
    assert tilt(out.q["hang"].rotation) == pytest.approx(PLATFORM_TILT.value,
                                                         abs=1e-3)


# --- the level-platform variant and its release ----------------------------------
def test_level_platform_compiles_to_three_slides():
    m = armature.compile(LEVEL, params(HOME, 2.0))
    assert m.coordinates == ("hang:x", "hang:y", "hang:z")
    assert m.dofs == m.coordinates
    assert all(t == mujoco.mjtJoint.mjJNT_SLIDE for t in m.model.jnt_type)
    s = m.at(q={"hang:x": 0.5})
    assert s.pose("centre").position == pytest.approx([0.5, 2.0, 1.2])
    assert s.pose("centre").rotation == pytest.approx(np.eye(3))
    assert armature.compile(platform, params(HOME, 2.0)).coordinates == ("hang",)


def _release(point, m):
    v = armature.compile(LEVEL, params(point, m))
    return v.at(q=dict(zip(("hang:x", "hang:y", "hang:z"), point))).release()


def test_release_names_the_turns_at_the_edge_midpoint():
    out = _release((0.5, 2.0, 1.2), 2.0)
    assert set(out.moved) == {"hang:rx", "hang:ry", "hang:rz"}
    assert math.degrees(out.moved["hang:ry"]) == pytest.approx(
        PLATFORM_TILT.value, abs=0.01)
    assert abs(out.moved["hang:rx"]) < 1e-9 and abs(out.moved["hang:rz"]) < 1e-9
    assert tilt(out.settled.q["hang"].rotation) == pytest.approx(
        PLATFORM_TILT.value, abs=0.01)
    assert "lock 'hang:ry' at 0.0 (assumption A5) moved +0.3623" in str(out)


def test_release_splits_the_low_corner_tilt():
    out = _release((0.5, 0.5, 0.4), 2.5)
    turns = {k: math.degrees(v) for k, v in out.moved.items()}
    # the review's "26° (18° pitch, 19° roll, 3° yaw)"
    assert turns == pytest.approx({"hang:rx": -19.24, "hang:ry": 18.23,
                                   "hang:rz": 3.12}, abs=0.01)


@pytest.mark.parametrize(
    "name, point, m",
    [pytest.param(*pose[:3], marks=[] if pose[0] == "room centre" else
                  pytest.mark.xfail(strict=True, reason="the level-platform "
                                    "assumption is wrong off the centreline"))
     for pose in POSES], ids=[p[0] for p in POSES])
def test_level_platform_assumption_holds(name, point, m):
    # The trap: written as the derivation would assert it. It must hold at
    # the room centre and fail at every other pose in the table.
    out = _release(point, m)
    assert out.settled.stable
    assert max(abs(v) for v in out.moved.values()) < math.radians(1.0), str(out)


def test_lock_carries_the_residual_moment():
    # Across the level platform's slides, the wrench is what its welded turns
    # carry: the moment the law leaves, about the point (01_kinematics eq. 19).
    point, m = np.array([0.5, 2.0, 1.2]), 2.0
    tension, _ = law(point, m)
    span = ANCHORS - (point + ATTACH)
    pull = tension[:, None] * span / np.linalg.norm(span, axis=1)[:, None]
    moment = (np.cross(ATTACH, pull).sum(axis=0)
              + np.cross(COM, [0.0, 0.0, -m * G]))
    v = armature.compile(LEVEL, params(point, m))
    w = v.at(q=dict(zip(("hang:x", "hang:y", "hang:z"), point))).wrench(
        "platform")
    assert w.joint == "hang"
    assert w.point == pytest.approx(point)
    assert w.force == pytest.approx(np.zeros(3), abs=1e-9)
    assert w.torque == pytest.approx(-moment, abs=1e-9)
    assert abs(w.torque[1]) > 1.0


def test_free_joint_carries_nothing_at_rest():
    # The cables are counted as applied forces (MuJoCo ≥ 3.14), so a hanging
    # platform's free joint carries nothing, not its weight.
    point, m = (0.5, 2.0, 1.2), 2.0
    rest = settled(point, m).q["hang"]
    w = armature.compile(platform, params(point, m)).at(
        q={"hang": rest}).wrench("platform")
    assert np.max(np.abs(w.force)) < 1e-3   # m × the settle's rest acceleration
    assert np.max(np.abs(w.torque)) < 1e-4


def test_symbolic_level_platform_is_three_slides():
    view = armature.symbolic(LEVEL, params(HOME, 2.0))
    assert view.coordinates == ("hang:x", "hang:y", "hang:z")
    x, y, z = view.q.values()
    assert view.frames["platform"].dcm(view.world) == sp.eye(3)
    below = (view.com["platform"].pos_from(view.origin).to_matrix(view.world)
             - sp.Matrix([x, y, z]))
    assert [float(c) for c in below] == pytest.approx([0, 0, -0.1], abs=1e-15)
    assert view.sites["centre"].vel(view.world).to_matrix(view.world) == \
        sp.Matrix([x.diff(), y.diff(), z.diff()])


# --- stiffness and modes ---------------------------------------------------------
def test_hanging_platform_stiffness_and_modes():
    p = params(HOME, 2.0)
    lin = armature.compile(platform, p).at(
        q={"hang": (HOME, np.eye(3))}).linearise()
    assert lin.dofs == tuple(f"hang:{c}" for c in
                             ("x", "y", "z", "rx", "ry", "rz"))
    assert lin.stiffness.shape == (6, 6)
    assert np.min(np.abs(np.diag(lin.stiffness))) > 4.0  # not zero anywhere

    # the potential's Hessian, by central differences of the review's model
    v, h, e = potential(HOME, 2.0, law(HOME, 2.0)[1]), 1e-4, np.eye(6)
    hessian = np.array([[(v(h * e[i] + h * e[j]) - v(h * e[i] - h * e[j])
                          - v(-h * e[i] + h * e[j]) + v(-h * e[i] - h * e[j]))
                         / (4 * h * h) for j in range(6)] for i in range(6)])
    assert lin.stiffness == pytest.approx(hessian, rel=1e-5, abs=1e-3)

    # K_yaw = m g A d / z0: A the anchors' horizontal reach, d the
    # attachments', z0 the drop (Plumb M1 review, F2)
    k_yaw = 2.0 * G * (2 * math.sqrt(2)) * (0.075 * math.sqrt(2)) / 1.2
    assert lin.stiffness[5, 5] == pytest.approx(k_yaw, rel=1e-3)

    lever = np.array([[0, 0.1, 0], [-0.1, 0, 0], [0, 0, 0]])  # [COM]×, COM 0.1 below
    mass = np.block([[2.0 * np.eye(3), -2.0 * lever],
                     [2.0 * lever, I_P - 2.0 * lever @ lever]])
    assert lin.mass == pytest.approx(mass, abs=1e-12)
    assert np.all(lin.frequencies > 0)
    # yaw 2.49 Hz and vertical 11.0 Hz as the review has them; tilt-sway
    # 2.09 Hz, where the review printed 0.78 Hz
    assert lin.frequencies == pytest.approx(
        [2.0920, 2.0920, 2.4924, 11.0499, 20.1056, 20.1056], abs=1e-4)


# --- floating bodies in general ----------------------------------------------------
def _swinging(p):
    """The platform with a pendulum hung from its point on a hinge about x."""
    return [*platform(p),
            body("bob", mass=0.3, com=HOME + (0, 0, -0.2),
                 inertia=np.diag([1e-4] * 3)),
            joint("swing", "hinge", parent="platform", child="bob",
                  axis=(1, 0, 0), point=HOME, range=(-1.5, 1.5)),
            site("tip", body="bob", pos=HOME + (0, 0, -0.2))]


def test_hinge_on_a_floating_body_reads_its_own_angle():
    top_edge = (2.0, 0.5, 1.9)  # where the platform rolls, about x
    m = armature.compile(_swinging, params(top_edge, 2.0))
    swing = m.model.joint("swing").id
    assert (m.model.jnt_qposadr[swing], m.model.jnt_dofadr[swing]) == (7, 6)
    turned = Rotation.from_euler("xyz", [0.1, -0.2, 0.3]).as_matrix()
    s = m.at(q={"hang": ((1.0, 2.0, 1.0), turned), "swing": 0.4})
    assert s.q["swing"] == 0.4
    hang = turned @ np.array([0, -0.2 * math.sin(-0.4), -0.2 * math.cos(0.4)])
    assert s.pose("tip").position == pytest.approx(np.array([1.0, 2.0, 1.0])
                                                   + hang, abs=1e-12)
    # Settled from 0.4 rad, the bob comes to hang plumb under the point: the
    # swing's angle is the platform's roll, undone.
    out = m.at(q={"hang": (top_edge, np.eye(3)), "swing": 0.4}).settle(
        max_steps=60000)
    assert out.stable
    rest = out.q["hang"].rotation
    roll = math.atan2(rest[2, 1], rest[2, 2])
    assert abs(roll) > math.radians(5)
    assert out.q["swing"] == pytest.approx(-roll, abs=1e-5)


def test_partial_lock_turns_first_then_the_free_ones():
    p = params(HOME, 2.0)
    held = armature.reduce(platform, lock("hang:rx", 0.2, assumption="A1"),
                           lock("hang:z", 1.0, assumption="A2"))
    v = armature.compile(held, p)
    assert v.coordinates == ("hang:x", "hang:y", "hang:ry", "hang:rz")
    s = v.at(q={"hang:x": 1.5, "hang:y": 2.5, "hang:ry": 0.1, "hang:rz": -0.3})
    whole = Rotation.from_euler("XYZ", [0.2, 0.1, -0.3]).as_matrix()
    full = armature.compile(platform, p).at(q={"hang": ((1.5, 2.5, 1.0), whole)})
    for name in ("centre", "c1:end", "c3:end"):
        assert s.pose(name).position == pytest.approx(full.pose(name).position,
                                                      abs=1e-12)

    # The symbolic view builds the same chain.
    view = armature.symbolic(held, p)
    at = dict(zip(view.q.values(), (1.5, 2.5, 0.1, -0.3)))
    rotation = view.world.dcm(view.frames["platform"]).subs(at)
    assert np.array(rotation, dtype=float) == pytest.approx(whole, abs=1e-12)
    corner = view.sites["c3:end"].pos_from(view.origin).to_matrix(view.world)
    assert np.array(corner.subs(at), dtype=float).ravel() == pytest.approx(
        full.pose("c3:end").position, abs=1e-12)


def test_release_starts_the_full_model_at_the_variants_pose():
    # Weightless and unhung, the body rests where release starts it, so the
    # settle's rest is that start: the locked turn first, then the free ones.
    def drifting(p):
        return [body("disc", mass=1.0, com=(0.1, 0, 0),
                     inertia=np.diag([0.01, 0.02, 0.03])),
                joint("float", "free", parent="world", child="disc",
                      point=(0, 0, 0)),
                armature.gravity((0, 0, 0))]
    held = armature.reduce(drifting, lock("float:rx", 0.2, assumption="A1"))
    out = armature.compile(held, {}).at(
        q={"float:x": 0.5, "float:ry": 0.1, "float:rz": -0.3}).release()
    whole = Rotation.from_euler("XYZ", [0.2, 0.1, -0.3]).as_matrix()
    assert out.settled.q["float"].rotation == pytest.approx(whole, abs=1e-12)
    assert out.settled.q["float"].position == pytest.approx([0.5, 0, 0])
    assert out.moved["float:rx"] == pytest.approx(0.0, abs=1e-12)


def test_floating_dofs_are_the_point_and_base_axes():
    turned = Rotation.from_euler("xyz", [0.3, 0.2, -0.1]).as_matrix()
    s = armature.compile(platform, params(HOME, 2.0)).at(
        q={"hang": ((1.0, 1.5, 1.1), turned)})
    corner = s.pose("c3:end").position
    jac = s.jacobian("c3:end")
    lever = corner - np.array([1.0, 1.5, 1.1])
    assert jac.linear[:, :3] == pytest.approx(np.eye(3), abs=1e-12)
    for i, axis in enumerate(np.eye(3)):
        assert jac.linear[:, 3 + i] == pytest.approx(np.cross(axis, lever),
                                                     abs=1e-12)
    assert jac.angular[:, 3:] == pytest.approx(np.eye(3), abs=1e-12)


def test_a_spinning_floating_body_needs_the_centripetal_force():
    # No gravity, no cables: spinning at ω about the vertical through its
    # point, with its COM a = 0.1 m off it, the body needs m ω² a toward the
    # point and nothing else.
    def spinner(p):
        return [body("disc", mass=2.0, com=(0.1, 0, 0),
                     inertia=np.diag([0.01, 0.01, 0.02])),
                joint("float", "free", parent="world", child="disc",
                      point=(0, 0, 0)),
                armature.gravity((0, 0, 0))]
    s = armature.compile(spinner, {}).at(qd={"float:rz": 3.0})
    need = s.inverse().generalised
    assert need["float:x"] == pytest.approx(-2.0 * 9.0 * 0.1, rel=1e-12)
    for dof in ("float:y", "float:z", "float:rx", "float:ry", "float:rz"):
        assert need[dof] == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("value, match", [
    (((0, 0, 1),), "pair"),
    (((0, 0), np.eye(3)), "pair"),
    (((0, 0, 1), np.diag([1, 1, -1])), "not a rotation"),
    (((0, 0, 1), 2 * np.eye(3)), "not a rotation"),
])
def test_a_placement_must_be_a_position_and_a_rotation(value, match):
    m = armature.compile(platform, params(HOME, 2.0))
    with pytest.raises(ValueError, match=match):
        m.at(q={"hang": value})


def test_rates_are_keyed_by_dof():
    m = armature.compile(platform, params(HOME, 2.0))
    with pytest.raises(KeyError, match="no dof named"):
        m.at(qd={"hang": 1.0})
    assert m.at(qd={"hang:rz": 1.0}).qd["hang:rz"] == 1.0
