"""The sampler's map from the unit cube to a state, shared with the search.

Answer: the seeded sampler's own output from before the map was split out of
it, pinned as a SHA-256 of every number it returned (each rounded to 1e-6,
so a platform's last bits keep it and any real change moves it), and the
ranges and envelopes each map was asked for. Trap: a map that draws its own randomness, so the same point gives two
states, or a split that moves the seeded draws by one call and changes every
sample a project's checks were written from.
"""

import hashlib
import math
from types import SimpleNamespace

import numpy as np
import pytest

import armature
from armature import Rejected, lock
from armature.sampler import unit_cube
from golden import arm_2r, cable_platform
from test_fixture_cable_platform import LEVEL, params
from test_fixture_five_bar import PARAMS as FIVE_BAR_PARAMS
from test_fixture_five_bar import five_bar
from test_fixture_wheel_leg import SKID_PARAMS, with_skid
from test_planar import P as IBEX_PARAMS
from test_planar import SAGITTAL
from test_sampler import BOX, ENVELOPE, SEED, swing_twist

ARM_PARAMS, arm = arm_2r.PARAMS, arm_2r.mechanism
HOME, platform = cable_platform.params.HOME, cable_platform.mechanism

QD = {"shoulder": 2.0, "elbow": 3.0}
QDD = {"shoulder": 10.0, "elbow": 20.0}
TORSO = armature.pose_envelope(box=((-0.2, 0.2), (0.0, 0.02), (0.45, 0.55)),
                               tilt=0.3, yaw=(-0.1, 0.1))


def _held_yaw():
    return armature.compile(armature.reduce(platform, lock(
        "hang:rz", 0.5, assumption="A9")), params(HOME, 2.0))


# Each case: what to compile, and how to sample it. Fixtures 1, 2 and 3 are
# the 2R arm, the cable platform (free, level and with its yaw held) and the
# five-bar leg on a wheel, resting on its tyre.
CASES = {
    "arm": (lambda: armature.compile(arm, ARM_PARAMS),
            lambda m: armature.sample(m, n=24, seed=SEED)),
    "arm, rates": (lambda: armature.compile(arm, ARM_PARAMS),
                   lambda m: armature.sample_states(
                       m, n=24, seed=SEED, qd_limits=QD, qdd_limits=QDD)),
    "platform": (lambda: armature.compile(platform, params(HOME, 2.0)),
                 lambda m: armature.sample(m, n=24, seed=SEED,
                                           poses={"hang": ENVELOPE})),
    "level platform": (lambda: armature.compile(LEVEL, params(HOME, 2.0)),
                       lambda m: armature.sample(m, n=24, seed=SEED,
                                                 poses={"hang": ENVELOPE})),
    "held yaw": (_held_yaw,
                 lambda m: armature.sample(m, n=24, seed=SEED,
                                           poses={"hang": ENVELOPE})),
    "wheel leg": (lambda: armature.compile(with_skid, SKID_PARAMS),
                  lambda m: armature.sample(m, n=24, seed=SEED,
                                            rest_on={"tyre": "y"})),
    "five-bar": (lambda: armature.compile(five_bar, FIVE_BAR_PARAMS),
                 lambda m: armature.sample(m, n=24, seed=SEED)),
    "five-bar, rates": (lambda: armature.compile(five_bar, FIVE_BAR_PARAMS),
                        lambda m: armature.sample_states(
                            m, n=8, seed=SEED, qd_limits={"A": 2.0, "E": 2.0},
                            qdd_limits={"A": 2.0, "E": 2.0})),
    "planar torso": (lambda: armature.compile(SAGITTAL, IBEX_PARAMS),
                     lambda m: armature.sample(m, n=24, seed=SEED,
                                               poses={"base": TORSO})),
}
SOLVED = {"wheel leg": ("y",)}  # what each case's rest_on solves

# Main's samples at 32aba6b, before the map was split out, on Windows x86-64
# with NumPy's PCG64; recorded rounded at b0e38f3 from the same samples,
# still bit-identical to 32aba6b's there, so Linux's last bits agree too.
# On Windows every number sits at least 1.6e-10 from a rounding edge.
GOLDEN = {
    "arm": "46b1133670f2a299dfc2f1ea6827fcb39529a7f9dfcd1519b0ce24551f344812",
    "arm, rates":
        "704d6287a9ee6d3514056e7f927b99394c517d5395ce7ddc00a3b5c4b313939e",
    "platform":
        "c826792eb64afd453d3e1fcbc82eaa3161dd6715cdfdf6faf7db31cbdf39fb44",
    "level platform":
        "72208b0507e0c170841ce5fcb9f9bf035ff04b6cb1ec95d7430c8d622e3e5f50",
    "held yaw":  # the chain's two tilts redrawn until inside the envelope
        "fceec940ed2b57a0cb48bb3160aef7f64557152356f3f8e7271f8e02c7f3d72b",
    "wheel leg":  # 9 of 33 draws refused
        "abcc6e73064a68e6c7397b1d7ceeabcbab21851a69cd09a001a3395e742ee4a4",
    "five-bar":  # 6 of 30 draws refused
        "1578f51baa51f49bc63af7df41aeff5abb9d55405fe5f1966dcd62b2ec4fe58f",
    "five-bar, rates":
        "d301505a5627ee14147637fe5181f59caa36ea29219f44640531713d947c4240",
    "planar torso":  # 14 of 38 draws refused
        "fffb140decfe02e24c2aa1c6854776f988569e65746e4f8173c876642d2e06eb",
}


def digest(samples, solved=()):
    """A SHA-256 over every number `samples` returned, in order: each
    state's coordinates and rates, the accelerations, every rejected draw
    and its reason, the clearances and the residual. Each number is
    rounded to 1e-6 (metres, radians, per second) first.

    A rejected draw's `solved` coordinates, the ones `rest_on` solves, are
    left out: main drew a value for each and kept it in the rejection,
    though nothing read it, and the map has no axis for it."""
    h = hashlib.sha256()

    def put(value):
        if isinstance(value, str):
            h.update(value.encode())
        elif isinstance(value, tuple):  # a Placement, or (position, rotation)
            for part in value:
                put(part)
        else:  # whole micro-units, so -0.0 and 0.0 are one number
            micro = np.rint(np.asarray(value, dtype=float) * 1e6)
            h.update(np.ascontiguousarray(micro, dtype="<i8").tobytes())

    put(float(samples.drawn))
    for s in samples.states:
        for value in s.q.values():
            put(value)
        for value in s.qd.values():
            put(value)
    for qdd in samples.qdd or ():
        for name, value in qdd.items():
            put(name)
            put(value)
    for r in samples.rejected:
        put(r.reason)
        for name, value in r.q.items():
            if name not in solved:
                put(name)
                put(value)
    for name, gaps in samples.clearance.items():
        put(name)
        put(gaps)
    put(samples.residual)
    return h.hexdigest()


@pytest.mark.parametrize("case", list(CASES))
def test_the_seeded_samples_are_unchanged_from_main(case):
    build, draw = CASES[case]
    assert digest(draw(build()), SOLVED.get(case, ())) == GOLDEN[case]


def nudged(samples, f):
    """`samples` with `f` applied to every number it holds."""
    def each(value):
        if isinstance(value, tuple):
            return tuple(each(part) for part in value)
        return f(np.asarray(value, dtype=float))

    def keyed(values):
        return {name: each(value) for name, value in values.items()}

    return SimpleNamespace(
        drawn=samples.drawn,
        states=[SimpleNamespace(q=keyed(s.q), qd=keyed(s.qd))
                for s in samples.states],
        qdd=[keyed(qdd) for qdd in samples.qdd or ()],
        rejected=[r._replace(q=keyed(r.q)) for r in samples.rejected],
        clearance=keyed(samples.clearance),
        residual=each(samples.residual))


@pytest.mark.parametrize("case", ["planar torso", "wheel leg"])
def test_the_digest_survives_last_bit_noise_but_not_a_real_change(case):
    """Linux's libm and BLAS differ from Windows' in the last bits of the
    closures and rotations, so a few ulps either way must keep the digest;
    a micrometre or a microradian must not."""
    build, draw = CASES[case]
    samples, solved = draw(build()), SOLVED.get(case, ())
    pinned = digest(samples, solved)

    def ulps(k):
        def f(x):
            for _ in range(abs(k)):
                x = np.nextafter(x, math.copysign(math.inf, k))
            return x
        return f

    for k in (-4, -1, 1, 4):
        assert digest(nudged(samples, ulps(k)), solved) == pinned
    assert digest(nudged(samples, lambda x: x + 2e-12), solved) == pinned
    assert digest(nudged(samples, lambda x: x + 2e-6), solved) != pinned


# --- the map: a point in the unit cube to a state -----------------------------
@pytest.fixture(scope="module")
def arm_m():
    return armature.compile(arm, ARM_PARAMS)


@pytest.fixture(scope="module")
def five_bar_m():
    return armature.compile(five_bar, FIVE_BAR_PARAMS)


@pytest.fixture(scope="module")
def platform_m():
    return armature.compile(platform, params(HOME, 2.0))


def corners(d):
    return np.array([[(i >> k) & 1 for k in range(d)] for i in range(2 ** d)],
                    dtype=float)


def numbers(state):
    """Every coordinate of `state`, as bytes, so equal means bit-equal."""
    return b"".join(np.ascontiguousarray(part, dtype="<f8").tobytes()
                    for value in state.q.values()
                    for part in (value if isinstance(value, tuple)
                                 else (value,)))


def test_the_axes_are_the_independent_coordinates_in_order(arm_m, five_bar_m):
    for m in (arm_m, five_bar_m):
        cube = unit_cube(m)
        assert cube.axes == m.independent and cube.d == len(m.independent)


def test_a_floating_body_spans_six_axes(platform_m):
    cube = unit_cube(platform_m, poses={"hang": ENVELOPE})
    assert cube.axes == ("hang:x", "hang:y", "hang:z", "hang:tilt",
                         "hang:azimuth", "hang:yaw")
    assert cube.d == 6


def test_a_coordinate_rest_on_solves_is_no_axis():
    m = armature.compile(with_skid, SKID_PARAMS)
    cube = unit_cube(m, rest_on={"tyre": "y"})
    assert cube.axes == ("x", "A", "hub", "E")
    results = cube.map(np.random.default_rng(SEED).random((24, 4)))
    refused = [r for r in results if isinstance(r, Rejected)]
    assert refused and all("y" not in r.q for r in refused)
    for s in results:
        if not isinstance(s, Rejected):
            assert abs(armature.clearance(s, "tyre")) <= 1e-10


def test_the_same_point_gives_the_same_state(arm_m, five_bar_m, platform_m):
    for m, poses in ((arm_m, None), (five_bar_m, None),
                     (platform_m, {"hang": ENVELOPE})):
        cube = unit_cube(m, poses=poses)
        points = np.random.default_rng(SEED).random((8, cube.d))
        first, again = cube.map(points), cube.map(points.copy())
        for a, b in zip(first, again):
            assert type(a) is type(b)
            if isinstance(a, Rejected):
                assert a.reason == b.reason
            else:
                assert numbers(a) == numbers(b)


def test_the_corners_are_the_ranges_ends(arm_m):
    """0 and 1 on each axis are its range's ends, or `within`'s."""
    cube = unit_cube(arm_m, within={"elbow": (0.2, 0.3)})
    shoulder = tuple(float(v) for v in arm_m.description.joints[0].range)
    low, high = cube.map([[0.0, 0.0], [1.0, 1.0]])
    assert (low.q["shoulder"], low.q["elbow"]) == (shoulder[0], 0.2)
    assert (high.q["shoulder"], high.q["elbow"]) == (shoulder[1], 0.3)


def test_a_point_that_cannot_close_is_a_rejection_naming_what_refused(
        five_bar_m):
    """Both hips a half-turn back: the knees leave their ranges, or the pin
    cannot meet. The map names it, as `at()` does, and does not raise."""
    cube = unit_cube(five_bar_m)
    refused, kept = cube.map([[(3.05 + math.pi) / (2 * math.pi),
                               (-3.05 + math.pi) / (2 * math.pi)],
                              [0.5, 0.5]])
    assert isinstance(refused, Rejected)
    assert refused.reason in ("loop 'pin'", "joint 'B'", "joint 'D'")
    with pytest.raises(armature.ClosureError) as again:
        five_bar_m.at(q=refused.q)
    assert again.value.constraint == refused.reason
    assert kept.q["A"] == kept.q["E"] == 0.0  # the middle is home


def test_floating_poses_lie_inside_the_envelope_as_unit_quaternions(
        platform_m):
    """At every corner of the six axes, and at random points, the pose is
    inside the envelope, its rotation a rotation, and what reaches MuJoCo a
    unit quaternion that turns the body by it."""
    import mujoco
    cube = unit_cube(platform_m, poses={"hang": ENVELOPE})
    points = np.vstack([corners(6),
                        np.random.default_rng(SEED).random((64, 6))])
    adr = platform_m.model.jnt_qposadr[platform_m.model.joint("hang").id]
    tilts = []
    for s in cube.map(points):
        where = s.q["hang"]
        assert all(lo <= x <= hi for x, (lo, hi) in zip(where.position, BOX))
        tilt, yaw = swing_twist(where.rotation)
        assert tilt <= 0.4 + 1e-12 and -0.3 - 1e-12 <= yaw <= 0.6 + 1e-12
        tilts.append(tilt)
        rotation = where.rotation
        assert rotation.T @ rotation == pytest.approx(np.eye(3), abs=1e-12)
        assert np.linalg.det(rotation) == pytest.approx(1.0, abs=1e-12)
        quat = s._data().qpos[adr + 3:adr + 7]
        assert np.linalg.norm(quat) == pytest.approx(1.0, abs=1e-12)
        back = np.zeros(9)
        mujoco.mju_quat2Mat(back, quat)
        assert back.reshape(3, 3) == pytest.approx(rotation, abs=1e-12)
    # the tilt axis runs from upright to the envelope's full lean
    assert min(tilts) == pytest.approx(0.0, abs=1e-12)
    assert max(tilts) == pytest.approx(0.4, abs=1e-12)


def test_a_rebuilt_chain_outside_its_envelope_is_a_rejection():
    """With the yaw held at 0.5 rad, the two tilts each span ±0.4; leaned
    fully about both, the platform leans past 0.4, and the map rejects the
    point, naming the envelope. Leaned about one, it is inside."""
    cube = unit_cube(_held_yaw(), poses={"hang": ENVELOPE})
    assert cube.axes == ("hang:x", "hang:y", "hang:z", "hang:rx", "hang:ry")
    past, inside = cube.map([[0.5, 0.5, 0.5, 1.0, 1.0],
                             [0.5, 0.5, 0.5, 1.0, 0.5]])
    assert isinstance(past, Rejected)
    assert past.reason == "pose envelope 'hang'"
    assert past.q["hang:rx"] == past.q["hang:ry"] == 0.4
    tilt, yaw = swing_twist(inside.pose("centre").rotation)
    assert tilt == pytest.approx(0.4, abs=1e-12)
    assert yaw == pytest.approx(0.5, abs=1e-12)


@pytest.mark.parametrize("points, match", [
    ([[0.5]], "2 axes"),
    ([0.5, 0.5], "2 axes"),
    ([[0.5, 1.5]], r"\[0, 1\]"),
    ([[-0.1, 0.5]], r"\[0, 1\]"),
    ([[0.5, math.nan]], r"\[0, 1\]"),
])
def test_points_are_checked(arm_m, points, match):
    with pytest.raises(ValueError, match=match):
        unit_cube(arm_m).map(points)


def test_the_map_is_checked_as_the_sampler_is(arm_m, platform_m):
    with pytest.raises(ValueError, match="outside elbow's range"):
        unit_cube(arm_m, within={"elbow": (-3.0, 0.0)})
    with pytest.raises(ValueError, match="'hang' is a floating body"):
        unit_cube(platform_m)
