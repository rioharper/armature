"""
dynamics/statics_checks.py — self-tests for statics.py, 02_dynamics.md §3.
"""

import numpy as np

from params import N, PARAMS
from dynamics.statics import static_torques
from truth.chain import build
from truth.envelope import DEFAULT_SEED, sample
from truth.equilibrium import settle
from truth.inverse import inverse_dynamics

HOLD_STEPS = 500

# The assumption the moment-arm closed form rests on, named once and quoted by
# both checks below. A closed form is a theorem about a class of mechanism, and
# the only question that matters about one in a derivation is whether *this*
# mechanism is in that class — so the assumption is written down, and the
# failure message hands it to whoever reads the red bar.
MOMENT_ARM_ASSUMES = (
    "every joint axis parallel to z and gravity lying in the x-y plane, so "
    "each weight's lever arm about a joint is its horizontal offset; a DH row "
    "with a nonzero alpha, or a GRAVITY_VEC out of the plane, leaves the class")


def moment_arm_torques(q_vals):
    """Holding torque by lever arms, the closed form 02_dynamics.md §3 cites.

    Each joint carries every weight outboard of it times that weight's
    horizontal offset from the joint. Hand-written for the 2R example — replace
    it with your mechanism's, and replace MOMENT_ARM_ASSUMES with the class of
    mechanism yours is a theorem about.
    """
    p = PARAMS
    q1, q12 = q_vals[0], q_vals[0] + q_vals[1]
    shoulder = (p["m1"] * p["lc1"] + p["m2"] * p["l1"]) * np.cos(q1) \
        + p["m2"] * p["lc2"] * np.cos(q12)
    elbow = p["m2"] * p["lc2"] * np.cos(q12)
    return p["g"] * np.array([shoulder, elbow])


def test_truth_moment_arm_form(n=24, seed=DEFAULT_SEED, tol=1e-9):
    """The closed form against the truth model, before the note cites it.

    A formula out of a book is the cheapest wrong number a derivation can
    produce: the arithmetic is somebody else's and it reproduces, the units are
    right, and the only thing that can be wrong is whether this mechanism is in
    the class the formula is a theorem about — a bifilar yaw stiffness on
    converging rather than parallel cables, a taut-cable pendulum mode on a
    cable that goes slack, a small-angle form past its range. So the form is
    checked against a model that never read the book, at sampled configurations
    rather than at the tidy posture where the cosines are all one, and the
    assumption it rests on is named in the failure.
    """
    model, data = build()
    rest = np.zeros(N)
    worst, worst_at = 0.0, None
    for qv in sample(n, seed):
        gap = float(np.max(np.abs(moment_arm_torques(qv)
                                  - inverse_dynamics(model, data, qv, rest, rest))))
        if gap > worst:
            worst, worst_at = gap, qv
        assert gap < tol, (
            f"the moment-arm form reads {moment_arm_torques(qv)} N m where the "
            f"truth model reads "
            f"{inverse_dynamics(model, data, qv, rest, rest)} N m at "
            f"q={np.round(qv, 4)}. The form assumes {MOMENT_ARM_ASSUMES}")
    print(f"  [PASS] the moment-arm closed form matches the truth model over "
          f"{n} sampled postures (seed {seed})")
    print(f"         worst |dtau| {worst:.2e} N m at q = {np.round(worst_at, 4)}; "
          f"the form assumes {MOMENT_ARM_ASSUMES.split(',')[0]}")


def test_static_torques_match_moment_arms(n=24, seed=DEFAULT_SEED, tol=1e-9):
    """Self-consistency: g(q) from the Lagrangian against the same closed form.

    Worth having for the arithmetic slip it catches the moment it lands, and
    not evidence of anything else — both sides are this project's own. The
    check above is what says the closed form describes this machine.
    """
    for qv in sample(n, seed):
        tau = static_torques(qv)
        assert np.allclose(tau, moment_arm_torques(qv), atol=tol), \
            f"g({np.round(qv, 4)}) = {tau} disagrees with the moment-arm " \
            f"calculation {moment_arm_torques(qv)}"
    print(f"  [PASS] static torques match the moment-arm calculation over {n} "
          f"sampled postures (seed {seed})")


def test_truth_held_posture_stays(n=8, seed=DEFAULT_SEED, tol=1e-4):
    """The mandatory equilibrium truth check: hold g(q) and see whether the
    machine actually stays there.

    `g(q)` is an algebraic balance written in the coordinates this derivation
    kept. It is silent about every coordinate the derivation froze, so on paper
    it balances whatever the machine would really do. Here the torque is held
    and the truth model is left to move in all the coordinates it has, for
    `HOLD_STEPS` steps — long enough that "balanced at this instant" has to
    become "still there", which is where a frozen degree of freedom shows up.

    For this 2R arm every coordinate is modelled and the check is a formality;
    it earns its place on the mechanism where it is not — a platform assumed
    level, a base assumed rigid — and it is written the same way here so the
    pattern is inherited rather than invented under pressure.
    """
    model, data = build()
    worst, worst_at = 0.0, None
    for q0 in sample(n, seed):
        out = settle(model, data, q0, hold=static_torques(q0),
                     min_steps=HOLD_STEPS)
        assert out.stable, \
            f"held at q={np.round(q0, 4)} by g(q) it never came to rest"
        drift = float(np.max(np.abs(out.pose - q0)))
        if drift > worst:
            worst, worst_at = drift, q0
        assert drift < tol, (
            f"held by g(q) = {static_torques(q0)} the truth model drifted from "
            f"q={np.round(q0, 4)} to {np.round(out.pose, 4)}")
        assert np.max(np.abs(out.forces)) < tol, \
            f"a constraint carried load at q={np.round(q0, 4)}: {out.forces}"
    print(f"  [PASS] g(q) holds the truth model still over {n} sampled "
          f"postures (seed {seed}, {HOLD_STEPS} steps each)")
    print(f"         worst drift {worst:.2e} rad, at q = {np.round(worst_at, 4)}")


def test_truth_wrong_torque_does_not_hold(seed=DEFAULT_SEED, moved=1e-2):
    """And the check has teeth: a torque that is not g(q) lets the arm fall.

    A check that passes is only evidence if it could have failed. Twenty per
    cent off on the shoulder is a plausible derivation error — a lever arm to
    the wrong point, a link's mass left out — and the truth model must not
    stand still under it.
    """
    model, data = build()
    q0 = sample(1, seed)[0]
    wrong = static_torques(q0) * np.array([1.2] + [1.0] * (N - 1))
    out = settle(model, data, q0, hold=wrong, min_steps=HOLD_STEPS)
    drift = float(np.max(np.abs(out.pose - q0)))
    assert drift > moved, (
        f"a 20% error in the shoulder torque moved the truth model only "
        f"{drift:.2e} rad — this check cannot see a wrong g(q)")
    print(f"  [PASS] a 20% wrong holding torque moves it {drift:.3f} rad")
