"""Fixture 4: a balanced parallelogram arm, CineWave-shaped.

The upper arm turns about O on J1. The forearm hangs from its far end P, and
its direction is set by a crank on J2, also at O, through a coupler that stays
parallel to the upper arm: O, P, Q and C are a parallelogram, and the forearm
turns with the crank. Every hinge is about z, and gravity is −y.

Answer: each body's COM moves with u(θ1), the upper arm's direction, or u(φ),
the crank's, so the total moment of mass is B1 u(θ1) + B2 u(φ), with

    B1 = m1 r1 + m4 r4 + m2 a,    B2 = m3 r3 + m4 c + m2 r2.

Counterweights that zero both give zero gravity torque at every posture; a
wrong one leaves τ1 = g B1 cos θ1 / N1 and τ2 = g B2 cos φ / N2. Traps: a wrong
counterweight must fail the balance check, and at the singularity, where the
four links lie on one line, the solve must report its lost rank rather than a
number.
"""

import math

import numpy as np
import pytest

import armature
from armature import joint
from golden import parallelogram

# The description is the golden project's, its counterweights' COMs solved
# from the balance condition in its params.py.
PARAMS = parallelogram.PARAMS
arm = parallelogram.mechanism
WRONG = {**PARAMS, "m1": 2.5}  # the upper counterweight 0.5 kg light
SEED = 20261011


def postures(n, seed=SEED):
    """Upper-arm angle and crank coordinate, kept 0.3 rad or more from the
    singularity θ1 = φ."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        j1 = rng.uniform(-1.0, 1.0)
        out.append((j1, j1 + rng.uniform(-1.2, 1.2)))
    return out


def gravity_torque(p, j1, j2):
    """τ1, τ2 per motor, from the moment of mass B1 u(θ1) + B2 u(φ)."""
    b1 = p["m1"] * p["r1"] + p["m4"] * p["r4"] + p["m2"] * p["a"]
    b2 = p["m3"] * p["r3"] + p["m4"] * p["c"] + p["m2"] * p["r2"]
    phi = j2 + math.pi / 2
    return np.array([p["g"] * b1 * math.cos(j1) / p["N1"],
                     p["g"] * b2 * math.cos(phi) / p["N2"]])


def assert_balanced(m, n=12):
    for j1, j2 in postures(n):
        inv = m.at(q={"J1": j1, "J2": j2}).inverse()
        assert abs(inv.torque["J1_motor"]) < 1e-10
        assert abs(inv.torque["J2_motor"]) < 1e-10


@pytest.fixture(scope="module")
def m():
    return armature.compile(arm, PARAMS)


def test_the_motors_drive_and_the_parallelogram_follows(m):
    assert m.independent == ("J1", "J2")
    assert m.dependent == ("elbow", "pin")


@pytest.mark.parametrize("j1, j2", postures(6))
def test_the_parallelogram_closes(m, j1, j2):
    s = m.at(q={"J1": j1, "J2": j2})
    # The forearm turns with the crank; the coupler stays with the upper arm.
    assert s.q["elbow"] == pytest.approx(j2 - j1, abs=1e-11)
    assert s.q["pin"] == pytest.approx(j1 - j2, abs=1e-11)
    assert s.pose("Q_fore").residual <= 1e-10


@pytest.mark.parametrize("short", [0.05, 0.013, 1e-3, 1e-6, 0.0])
def test_the_parallelogram_holds_its_branch_up_to_the_singularity(m, short):
    # At the singularity the antiparallelogram branch crosses this one, and
    # just short of it the two are close. The closure pins the dependent
    # angles only to (gap)/σ_min there, with σ_min shrinking as `short`, so
    # the tolerance scales with it: well inside the other branch, which lies
    # some 2 × short away.
    j1 = 0.3
    j2 = j1 - math.pi / 2 + short
    s = m.at(q={"J1": j1, "J2": j2})
    assert s.pose("Q_fore").residual <= 1e-10
    assert s.q["elbow"] == pytest.approx(j2 - j1, abs=1e-12 + 1e-2 * short)
    assert s.q["pin"] == pytest.approx(j1 - j2, abs=1e-12 + 1e-2 * short)


def test_a_closure_outside_a_joint_range_raises():
    def stiff_elbow(p):
        return [joint("elbow", "hinge", parent="upper", child="fore",
                      axis=(0, 0, 1), point=(p["a"], 0, 0), range=(-1.0, 1.0))
                if getattr(e, "name", None) == "elbow" else e for e in arm(p)]
    m = armature.compile(stiff_elbow, PARAMS)
    # elbow = J2 − J1 = 1.2, past its range of ±1.0, with the parallelogram
    # clear of its singularity at J2 − J1 = ±π/2.
    with pytest.raises(ValueError, match="joint 'elbow': closing the loops"):
        m.at(q={"J1": 0.0, "J2": 1.2})


def test_gravity_torque_is_zero_over_the_envelope(m):
    assert_balanced(m)


def test_a_wrong_counterweight_fails_the_balance():
    wrong = armature.compile(arm, WRONG)
    with pytest.raises(AssertionError):
        assert_balanced(wrong)


@pytest.mark.parametrize("j1, j2", postures(6))
def test_a_wrong_counterweight_reads_its_closed_form(j1, j2):
    inv = armature.compile(arm, WRONG).at(q={"J1": j1, "J2": j2}).inverse()
    got = [inv.torque["J1_motor"], inv.torque["J2_motor"]]
    assert got == pytest.approx(gravity_torque(WRONG, j1, j2), rel=1e-9,
                                abs=1e-12)


def test_the_singularity_reports_its_rank_loss(m):
    regular = m.at(q={"J1": 0.3, "J2": 0.0}).inverse()
    assert (regular.rank, regular.unknowns) == (4, 4)
    assert math.isfinite(regular.condition)
    # θ1 = φ: O, C, P and Q on one line, and the loop's rows lose a rank.
    s = m.at(q={"J1": 0.3, "J2": 0.3 - math.pi / 2})
    for loads in (None, {"tip": (0.0, -20.0, 0.0)}):
        inv = s.inverse(loads=loads)
        assert (inv.rank, inv.unknowns) == (3, 4)
        assert math.isinf(inv.condition)
        # The force along the line is anyone's: NaN, not a least-norm number.
        assert np.all(np.isnan(inv.constraint["parallelogram"]))
        # The flip into the antiparallelogram is free here, and the weights
        # push along it, balanced or not: these motors cannot hold it.
        assert inv.residual > 1.0
    # A milliradian away the solve has its rank, and its loop force is the
    # number the singularity would otherwise have printed.
    near = m.at(q={"J1": 0.3, "J2": 0.3 - math.pi / 2 + 1e-3}).inverse()
    assert near.rank == 4
    assert near.condition > 1e5
    assert np.linalg.norm(near.constraint["parallelogram"]) > 1e4


def test_released_with_the_motors_off_it_stays(m):
    """Balanced means neutral: let go anywhere, the arm stays there."""
    settled = m.at(q={"J1": 0.5, "J2": 0.1}).settle()
    assert settled.stable
    assert settled.residual <= 1e-6
    for name in m.coordinates:
        assert abs(settled.moved[name]) < 1e-6


def test_released_with_a_wrong_counterweight_it_falls():
    settled = armature.compile(arm, WRONG).at(q={"J1": 0.5, "J2": 0.1}).settle()
    assert abs(settled.moved["J1"]) > 0.1
