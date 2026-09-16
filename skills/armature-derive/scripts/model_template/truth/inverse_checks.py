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
from truth.inverse import inverse_dynamics
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
