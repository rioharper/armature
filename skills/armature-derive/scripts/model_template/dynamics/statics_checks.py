"""
dynamics/statics_checks.py — self-tests for statics.py, 02_dynamics.md §3.
"""

import numpy as np

from params import N, PARAMS
from dynamics.statics import static_torques
from truth.chain import build
from truth.envelope import DEFAULT_SEED, sample
from truth.equilibrium import settle

HOLD_STEPS = 500


def test_static_torques_match_moment_arms(tol=1e-9):
    """At q = 0 the arm lies along x: each joint holds the weight outboard of
    it times that weight's lever arm. Hand-written for the 2R example —
    replace with your mechanism's moment-arm calculation."""
    p = PARAMS
    by_hand = p["g"] * np.array([p["m1"] * p["lc1"] + p["m2"] * (p["l1"] + p["lc2"]),
                                 p["m2"] * p["lc2"]])
    tau = static_torques(np.zeros(N))
    assert np.allclose(tau, by_hand, atol=tol), \
        f"g(0) = {tau} disagrees with the moment-arm calculation {by_hand}"
    print("  [PASS] static torques match the moment-arm calculation")


def test_held_posture_stays_in_truth_model(n=8, seed=DEFAULT_SEED, tol=1e-4):
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


def test_wrong_torque_does_not_hold(seed=DEFAULT_SEED, moved=1e-2):
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
