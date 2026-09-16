"""
truth/inverse_checks.py — self-tests for inverse.py.

Internal to the package, like chain_checks.py: they check that the truth
model's inverse dynamics is wired to the right coordinates and agrees with the
truth model's own forward dynamics. Whether it agrees with the *derivation* is
Milestone 2's check, one package over.
"""

import mujoco
import numpy as np

from params import N
from truth.chain import build
from truth.inverse import (MUJOCO, PINOCCHIO, available, inverse_dynamics,
                           resolve)
from truth.envelope import DEFAULT_SEED, sample_states


def test_inverse_dynamics_round_trips_forward(n=16, seed=DEFAULT_SEED, tol=1e-9):
    """Forces from inverse dynamics, applied, reproduce the accelerations.

    The one thing this package can get wrong on its own is the wiring — a
    coordinate ordering, a stale `qacc`, an applied force left set from the
    call before. Feeding the answer back through MuJoCo's forward dynamics
    catches all three; it says nothing about the physics, and is not meant to.
    """
    model, data = build()
    Q, QD, QDD = sample_states(n, seed)
    worst = 0.0
    for qv, qdv, qddv in zip(Q, QD, QDD):
        tau = inverse_dynamics(model, data, qv, qdv, qddv)
        assert tau.shape == (N,), f"inverse dynamics returned {tau.shape}"
        data.qpos[:], data.qvel[:] = qv, qdv
        data.qfrc_applied[:] = tau
        mujoco.mj_forward(model, data)
        worst = max(worst, float(np.max(np.abs(data.qacc - qddv))))
        assert np.allclose(data.qacc, qddv, atol=tol), \
            f"applying tau={tau} at q={qv} gave qacc={data.qacc}, not {qddv}"
    data.qfrc_applied[:] = 0.0
    print(f"  [PASS] inverse dynamics round-trips forward dynamics over {n} "
          f"states (seed {seed}, worst |dqacc| {worst:.2e})")


def test_the_second_backend_agrees_or_is_absent(n=8, seed=DEFAULT_SEED,
                                                tol=1e-9):
    """Pinocchio against MuJoCo where Pinocchio imports; the fallback where not.

    Two engines, two recursive algorithms, two codebases, one parameter block:
    where both are present this is a third independent implementation of the
    dynamics for free, and where only one is, the check says so out loud rather
    than passing quietly under a backend name that never ran. Pinocchio is
    never the mandatory model — no Windows pip wheel, no unilateral
    constraints — so its absence is a printed line, not a failure.
    """
    assert MUJOCO in available(), "MuJoCo is a required dependency of this model"
    model, data = build()
    if resolve(PINOCCHIO) != PINOCCHIO:
        fell_back = inverse_dynamics(model, data, np.zeros(N), np.zeros(N),
                                     np.zeros(N), backend=PINOCCHIO)
        assert np.allclose(fell_back, inverse_dynamics(model, data, np.zeros(N),
                                                       np.zeros(N), np.zeros(N)))
        print(f"  [PASS] backends available: {available()}; Pinocchio is absent "
              f"and the call fell back to MuJoCo")
        return
    worst = 0.0
    for qv, qdv, qddv in zip(*sample_states(n, seed)):
        gap = float(np.max(np.abs(
            inverse_dynamics(model, data, qv, qdv, qddv, backend=MUJOCO)
            - inverse_dynamics(model, data, qv, qdv, qddv, backend=PINOCCHIO))))
        worst = max(worst, gap)
        assert gap < tol, (
            f"MuJoCo and Pinocchio disagree by {gap:.2e} N m at q={qv}, "
            f"qd={qdv}, qdd={qddv} — two engines from one parameter block")
    print(f"  [PASS] MuJoCo and Pinocchio agree over {n} states (seed {seed}, "
          f"worst |dtau| {worst:.2e} N m)")
