"""The seeded sampler: independent coordinates, closed loops, floating poses.

Answer: the ranges, envelopes and rate limits each sample was asked for, and
closed forms for what each sample must be: the five-bar's dependent angles
from its circle intersection (fixture 4's reference, in 40-digit mpmath), a
floating body's tilt and yaw from a swing-twist split written here with
SciPy's rotations, not the engine's. Trap: a sampler that draws a box of
joint angles, so a loop's dependent joints come out of the box rather than
closing it, and a floating body's quaternion components come out as angles.
"""

import math

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

import armature
from armature import ClosureError, lock, pose_envelope
from golden import arm_2r, cable_platform
from test_fixture_cable_platform import LEVEL, params
from test_fixture_five_bar import PARAMS as FIVE_BAR_PARAMS
from test_fixture_five_bar import five_bar, ref
from test_planar import P as IBEX_PARAMS
from test_planar import SAGITTAL

ARM_PARAMS, arm = arm_2r.PARAMS, arm_2r.mechanism
HOME, platform = cable_platform.params.HOME, cable_platform.mechanism

SEED = 20261011
UP = np.array([0.0, 0.0, 1.0])  # the platform hangs under gravity along −z
BOX = ((1.5, 2.5), (1.6, 2.2), (0.9, 1.4))
ENVELOPE = pose_envelope(box=BOX, tilt=0.4, yaw=(-0.3, 0.6))


@pytest.fixture(scope="module")
def arm_m():
    return armature.compile(arm, ARM_PARAMS)


@pytest.fixture(scope="module")
def five_bar_m():
    return armature.compile(five_bar, FIVE_BAR_PARAMS)


@pytest.fixture(scope="module")
def platform_m():
    return armature.compile(platform, params(HOME, 2.0))


def ranges(m):
    return {j.name: tuple(float(v) for v in j.range)
            for j in m.description.joints if j.range is not None}


def postures(samples):
    return [dict(s.q) for s in samples.states]


# --- seeded, uniform over the independent coordinates' ranges -----------------
def test_the_same_seed_gives_the_same_states(arm_m):
    first, again = (armature.sample(arm_m, n=24, seed=SEED) for _ in range(2))
    other = armature.sample(arm_m, n=24, seed=SEED + 1)
    assert postures(first) == postures(again)
    assert postures(first) != postures(other)
    assert (first.n, first.seed, len(first.states)) == (24, SEED, 24)


def test_every_state_lies_inside_its_ranges_and_fills_them(arm_m):
    samples = armature.sample(arm_m, n=400, seed=SEED)
    for name, (lo, hi) in ranges(arm_m).items():
        values = np.array([s.q[name] for s in samples.states])
        assert np.all((lo <= values) & (values <= hi))
        # uniform: each tenth of the range holds its share, to 4 σ
        counts = np.histogram(values, bins=10, range=(lo, hi))[0]
        assert np.all(np.abs(counts - 40) < 4 * math.sqrt(40 * 0.9))


def test_states_are_at_rest(arm_m):
    s = armature.sample(arm_m, n=4, seed=SEED).states[0]
    assert set(s.qd.values()) == {0.0}


def test_within_narrows_the_draw(arm_m):
    samples = armature.sample(arm_m, n=50, seed=SEED,
                              within={"elbow": (0.2, 0.3)})
    elbow = np.array([s.q["elbow"] for s in samples.states])
    shoulder = np.array([s.q["shoulder"] for s in samples.states])
    assert np.all((0.2 <= elbow) & (elbow <= 0.3))
    assert shoulder.min() < -1.5 and shoulder.max() > 1.5  # still its range


@pytest.mark.parametrize("within, match", [
    ({"elbow": (-3.0, 0.0)}, "outside elbow's range"),
    ({"elbow": (0.3, 0.2)}, "low above its high"),
    ({"wrist": (0.0, 1.0)}, "no coordinate named"),
])
def test_within_is_checked(arm_m, within, match):
    with pytest.raises(ValueError, match=match):
        armature.sample(arm_m, within=within)


def test_the_result_prints_n_and_the_seed(arm_m):
    samples = armature.sample(arm_m, n=24, seed=SEED)
    text = str(samples)
    assert "n = 24" in text and f"seed = {SEED}" in text
    assert samples.method in text


# --- closed loops -------------------------------------------------------------
def test_loop_closed_states_close_and_match_the_closed_form(five_bar_m):
    """Every state is closed to 1e-10 m, its dependent joints are the closed
    form's, and only the independent coordinates were drawn."""
    samples = armature.sample(five_bar_m, n=24, seed=SEED)
    assert len(samples.states) == 24
    assert samples.residual <= 1e-10
    for s in samples.states:
        c2, c4 = s.pose("C2"), s.pose("C4")
        assert np.max(np.abs(c2.position - c4.position)) <= 1e-10
        ya, ye = s.q["A"], s.q["E"]
        assert -math.pi <= ya <= math.pi and -math.pi <= ye <= math.pi
        assert s.q["B"] == pytest.approx(float(ref("q_B", ya, ye)), abs=1e-9)
        assert s.q["D"] == pytest.approx(float(ref("q_D", ya, ye)), abs=1e-9)


def test_draws_that_cannot_close_are_counted_and_named(five_bar_m):
    """Over ±π at both hips, some draws cannot close on home's branch. Each
    is counted under the constraint that refused it, and really is refused:
    `at()` raises on it again, naming the same one."""
    samples = armature.sample(five_bar_m, n=24, seed=SEED)
    assert samples.rejected, "the five-bar over ±π should refuse some draws"
    assert samples.drawn == 24 + len(samples.rejected)
    assert sum(samples.reasons.values()) == len(samples.rejected)
    for draw in samples.rejected:
        with pytest.raises(ClosureError) as refused:
            five_bar_m.at(q=draw.q)
        assert refused.value.constraint == draw.reason
        assert draw.reason in ("loop 'pin'", "joint 'B'", "joint 'D'")
    text = str(samples)
    assert f"{len(samples.rejected)} of {samples.drawn} draws" in text
    for reason, count in samples.reasons.items():
        assert f"{reason}: {count}" in text


def test_a_box_where_nothing_closes_raises_with_the_counts(five_bar_m):
    """With both hips turned a half-turn back, the dependent knees leave
    their ±π ranges at every draw."""
    with pytest.raises(ValueError, match=r"0 of \d+ draws closed"):
        armature.sample(five_bar_m, n=4, seed=SEED,
                        within={"A": (3.0, 3.1), "E": (-3.1, -3.0)})


def test_the_sampler_never_draws_a_dependent_coordinate(five_bar_m):
    with pytest.raises(ValueError, match="solved, not drawn"):
        armature.sample(five_bar_m, within={"B": (0.0, 0.1)})


# --- floating poses -----------------------------------------------------------
def swing_twist(rotation):
    """The tilt and the yaw of `rotation` about UP: the swing that takes UP
    to where the body's up now points, then what is left, which turns about
    UP. Matrices and rotation vectors, not quaternions."""
    r = Rotation.from_matrix(rotation)
    w = rotation @ UP
    axis = np.cross(UP, w)
    tilt = math.atan2(np.linalg.norm(axis), UP @ w)
    swing = (Rotation.from_rotvec(axis / np.linalg.norm(axis) * tilt)
             if np.linalg.norm(axis) > 0 else Rotation.identity())
    twist = (swing.inv() * r).as_rotvec()
    assert np.linalg.norm(np.cross(twist, UP)) < 1e-9  # about UP alone
    return tilt, float(twist @ UP)


def test_floating_samples_respect_the_envelope(platform_m):
    samples = armature.sample(platform_m, n=200, seed=SEED,
                              poses={"hang": ENVELOPE})
    tilts, yaws = [], []
    for s in samples.states:
        where = s.q["hang"]
        assert all(lo <= x <= hi for x, (lo, hi) in zip(where.position, BOX))
        tilt, yaw = swing_twist(where.rotation)
        assert tilt <= 0.4 + 1e-12 and -0.3 - 1e-12 <= yaw <= 0.6 + 1e-12
        tilts.append(tilt)
        yaws.append(yaw)
    # the envelope is filled to its edges, and the tilt leans every way
    assert max(tilts) > 0.38 and min(yaws) < -0.28 and max(yaws) > 0.58
    leans = [s.q["hang"].rotation @ UP for s in samples.states]
    assert {bool(v[0] > 0) for v in leans} == {True, False}
    assert {bool(v[1] > 0) for v in leans} == {True, False}
    # uniform over the cap of up directions, not over the tilt angle: the
    # inner half-angle cap holds (1 − cos 0.2)/(1 − cos 0.4) of it, to 4 σ
    share = (1 - math.cos(0.2)) / (1 - math.cos(0.4))
    inner = np.mean(np.array(tilts) <= 0.2)
    assert abs(inner - share) < 4 * math.sqrt(share * (1 - share) / 200)


@pytest.mark.parametrize("rotation, inside", [
    (Rotation.from_rotvec([0, 0, 0.55]), True),
    (Rotation.from_rotvec([0, 0, 0.65]), False),     # past the yaw's high
    (Rotation.from_rotvec([0, 0, -0.25]), True),
    (Rotation.from_rotvec([0, 0, -0.35]), False),    # past the yaw's low
    (Rotation.from_rotvec([0.39, 0, 0]), True),
    (Rotation.from_rotvec([0, -0.41, 0]), False),    # leans past the tilt
    (Rotation.from_rotvec([0.3, 0, 0]) * Rotation.from_rotvec([0, 0, 0.5]),
     True),
    (Rotation.from_rotvec([0, 0.3, 0]) * Rotation.from_rotvec([0, 0, 0.7]),
     False),
])
def test_the_envelope_holds_what_its_bounds_say(rotation, inside):
    """Yaw is what is left about up once the lean is taken out, so a body
    leaned 0.3 rad and yawed 0.5 is inside, and yawed 0.7 is not."""
    assert ENVELOPE.contains(HOME, rotation.as_matrix(), UP) is inside
    assert not ENVELOPE.contains(HOME + [0, 0.3, 0], np.eye(3), UP)


def test_a_chain_yaw_turn_is_bounded_by_the_yaw_either_way_up():
    """Gravity along +z: up is −z, so the body's turn about its own z is a
    yaw of the opposite sign, and the bounds turn with it."""
    def hanging_up(p):
        return [armature.body("b", mass=1.0, com=(0, 0, 0),
                              inertia=np.diag([0.1] * 3)),
                armature.joint("f", "free", parent="world", child="b",
                               point=(0, 0, 0)),
                armature.gravity((0, 0, 9.81))]
    flat = armature.reduce(hanging_up, lock("f:rx", 0.0, assumption="A1"),
                           lock("f:ry", 0.0, assumption="A1"))
    m = armature.compile(flat, {})
    samples = armature.sample(m, n=50, seed=SEED, poses={"f": pose_envelope(
        box=((-1, 1),) * 3, tilt=0.1, yaw=(0.1, 0.5))})
    turns = np.array([s.q["f:rz"] for s in samples.states])
    assert np.all((-0.5 <= turns) & (turns <= -0.1))
    assert turns.min() < -0.45 and turns.max() > -0.15


def test_floating_orientations_are_unit_quaternions(platform_m):
    """The placement is a rotation, and what reaches MuJoCo is a unit
    quaternion that turns the body by it."""
    import mujoco
    samples = armature.sample(platform_m, n=24, seed=SEED,
                              poses={"hang": ENVELOPE})
    adr = platform_m.model.jnt_qposadr[platform_m.model.joint("hang").id]
    for s in samples.states:
        rotation = s.q["hang"].rotation
        assert rotation.T @ rotation == pytest.approx(np.eye(3), abs=1e-12)
        assert np.linalg.det(rotation) == pytest.approx(1.0, abs=1e-12)
        quat = s._data().qpos[adr + 3:adr + 7]
        assert np.linalg.norm(quat) == pytest.approx(1.0, abs=1e-12)
        back = np.zeros(9)
        mujoco.mju_quat2Mat(back, quat)
        assert back.reshape(3, 3) == pytest.approx(rotation, abs=1e-12)


def test_a_floating_body_without_an_envelope_is_refused(platform_m):
    with pytest.raises(ValueError, match="'hang' is a floating body"):
        armature.sample(platform_m)


def test_the_level_platform_draws_its_slides_from_the_box():
    m = armature.compile(LEVEL, params(HOME, 2.0))
    samples = armature.sample(m, n=24, seed=SEED, poses={"hang": ENVELOPE})
    for s in samples.states:
        point = [s.q[f"hang:{c}"] for c in "xyz"]
        assert all(lo <= x <= hi for x, (lo, hi) in zip(point, BOX))
        assert s.pose("centre").position == pytest.approx(point, abs=1e-12)
        assert s.pose("centre").rotation == pytest.approx(np.eye(3),
                                                          abs=1e-12)


def test_a_planar_torso_draws_its_pitch_as_tilt():
    """Under planar("xz") the torso keeps x, z and its pitch about y, which
    is a tilt from gravity's −z: the pitch fills ±tilt, the slides fill the
    box, and both legs close."""
    m = armature.compile(SAGITTAL, IBEX_PARAMS)
    box = ((-0.2, 0.2), (0.0, 0.02), (0.45, 0.55))
    samples = armature.sample(m, n=24, seed=SEED, poses={
        "base": pose_envelope(box=box, tilt=0.3, yaw=(-0.1, 0.1))})
    pitch = np.array([s.q["base:ry"] for s in samples.states])
    assert np.all(np.abs(pitch) <= 0.3) and pitch.min() < -0.2 < 0.2 < pitch.max()
    for s in samples.states:
        assert box[0][0] <= s.q["base:x"] <= box[0][1]
        assert box[2][0] <= s.q["base:z"] <= box[2][1]
        for side in ("l", "r"):
            gap = (s.pose(f"axle_f_{side}").position
                   - s.pose(f"axle_r_{side}").position)
            assert np.max(np.abs(gap)) <= 1e-10


def test_a_held_component_outside_the_envelope_is_refused():
    """Planar locks the torso's y at 0.01 m; a box that leaves it out holds
    no pose the chain allows."""
    m = armature.compile(SAGITTAL, IBEX_PARAMS)
    box = ((-0.2, 0.2), (0.5, 0.6), (0.45, 0.55))
    with pytest.raises(ValueError, match="holds no pose"):
        armature.sample(m, n=2, seed=SEED, poses={
            "base": pose_envelope(box=box, tilt=0.3, yaw=(-0.1, 0.1))})


def test_a_held_yaw_counts_against_the_envelope():
    """With the platform's yaw held at 0.5 rad its two tilts stay free. An
    envelope whose yaw reaches 0.6 holds its poses; one that stops at 0.4
    holds none of them."""
    held = armature.reduce(platform, lock("hang:rz", 0.5, assumption="A9"))
    m = armature.compile(held, params(HOME, 2.0))
    samples = armature.sample(m, n=24, seed=SEED, poses={"hang": ENVELOPE})
    for s in samples.states:
        tilt, yaw = swing_twist(s.pose("centre").rotation)
        assert tilt <= 0.4 + 1e-12 and 0.4 < yaw <= 0.6 + 1e-12
    with pytest.raises(ValueError, match="holds no pose"):
        armature.sample(m, n=2, seed=SEED, poses={"hang": pose_envelope(
            box=BOX, tilt=0.4, yaw=(-0.3, 0.4))})


def test_a_turn_neither_tilt_nor_yaw_is_refused():
    """With the platform's roll held at 0.5 rad, its pitch turns about an
    axis that is neither level nor upright."""
    rolled = armature.reduce(platform, lock("hang:rx", 0.5, assumption="A9"))
    m = armature.compile(rolled, params(HOME, 2.0))
    with pytest.raises(ValueError, match="'hang:ry' turns about"):
        armature.sample(m, poses={"hang": ENVELOPE})


@pytest.mark.parametrize("kwargs, match", [
    ({"box": BOX[:2], "tilt": 0.1, "yaw": (0, 1)}, "three"),
    ({"box": ((1, 0), *BOX[1:]), "tilt": 0.1, "yaw": (0, 1)}, "low above"),
    ({"box": BOX, "tilt": -0.1, "yaw": (0, 1)}, "tilt"),
    ({"box": BOX, "tilt": 0.1, "yaw": (1, 0)}, "yaw"),
    ({"box": BOX, "tilt": 0.1, "yaw": (-4, 0)}, "yaw"),
])
def test_the_envelope_is_checked(kwargs, match):
    with pytest.raises(ValueError, match=match):
        pose_envelope(**kwargs)


# --- rates --------------------------------------------------------------------
QD = {"shoulder": 2.0, "elbow": 3.0}
QDD = {"shoulder": 10.0, "elbow": 20.0}


def test_sample_states_rates_lie_within_their_limits_in_both_signs(arm_m):
    samples = armature.sample_states(arm_m, n=24, seed=SEED, qd_limits=QD,
                                     qdd_limits=QDD)
    for limits, values in ((QD, [s.qd for s in samples.states]),
                           (QDD, samples.qdd)):
        for name, limit in limits.items():
            v = np.array([row[name] for row in values])
            assert np.all(np.abs(v) <= limit)
            assert v.min() < -0.5 * limit and v.max() > 0.5 * limit


def test_sample_states_postures_are_the_samples(arm_m):
    states = armature.sample_states(arm_m, n=24, seed=SEED, qd_limits=QD,
                                    qdd_limits=QDD)
    assert postures(states) == postures(armature.sample(arm_m, n=24,
                                                        seed=SEED))
    again = armature.sample_states(arm_m, n=24, seed=SEED, qd_limits=QD,
                                   qdd_limits=QDD)
    assert [dict(s.qd) for s in states.states] == [dict(s.qd)
                                                   for s in again.states]
    assert [dict(q) for q in states.qdd] == [dict(q) for q in again.qdd]


@pytest.mark.parametrize("qd, match", [
    ({"shoulder": 2.0}, "no limit for"),
    ({**QD, "wrist": 1.0}, "no dof named"),
    ({**QD, "elbow": -1.0}, "negative"),
])
def test_rate_limits_are_checked(arm_m, qd, match):
    with pytest.raises(ValueError, match=match):
        armature.sample_states(arm_m, qd_limits=qd, qdd_limits=QDD)


def test_closed_chain_rates_keep_the_loop_closed(five_bar_m):
    """The independent dofs' rates are drawn; the dependent ones are solved,
    so the pin's two sites move together. The accelerations are keyed by the
    independent dofs, as `inverse` takes them."""
    limits = {"A": 2.0, "E": 2.0}
    samples = armature.sample_states(five_bar_m, n=8, seed=SEED,
                                     qd_limits=limits, qdd_limits=limits)
    for s, qdd in zip(samples.states, samples.qdd):
        assert set(qdd) == {"A", "E"}
        rates = np.array([s.qd[d] for d in five_bar_m.dofs])
        moving = [s.jacobian(site).linear @ rates for site in ("C2", "C4")]
        assert moving[0] == pytest.approx(moving[1], abs=1e-9)
        assert s.inverse(qdd=qdd).residual < 1e-9


def test_a_dependent_dof_takes_no_limit(five_bar_m):
    limits = {"A": 2.0, "E": 2.0, "B": 1.0}
    with pytest.raises(ValueError, match="solved, not drawn"):
        armature.sample_states(five_bar_m, qd_limits=limits,
                               qdd_limits=limits)


def test_floating_rates_are_keyed_by_dof(platform_m):
    limits = {d: 0.5 for d in platform_m.dofs}
    samples = armature.sample_states(platform_m, n=24, seed=SEED,
                                     poses={"hang": ENVELOPE},
                                     qd_limits=limits, qdd_limits=limits)
    for d in platform_m.dofs:
        v = np.array([s.qd[d] for s in samples.states])
        assert np.all(np.abs(v) <= 0.5) and v.min() < 0 < v.max()
