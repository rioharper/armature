"""
verification_checks.py — Milestone 3's self-tests, beside verification.py.
"""

import numpy as np

from params import N
from kinematics import fk_num
from truth.envelope import DEFAULT_SEED, sample_workspace
from verification import inverse_kinematics


def test_ik_roundtrip(trials=8, seed=DEFAULT_SEED, tol=1e-4):
    """FK -> IK -> FK must return to the same end-effector position.

    Targets from the truth package's workspace sampler, not from a generator of
    this file's own: the IK inverts J_v, so its conditioning is exactly the
    singular-value sweep one milestone back, and the set it has to converge over
    is `params.WORKSPACE` — the region the requirements name — rather than the
    envelope, which contains the elbow singularity the IK cannot pass through.
    """
    rng = np.random.default_rng(seed)
    for q_true in sample_workspace(trials, seed):
        target = np.asarray(fk_num(*q_true), dtype=float)[:3, 3]
        start = q_true + rng.uniform(-0.2, 0.2, N)   # near a valid branch
        q_sol, _ok, res = inverse_kinematics(target, q0=start)
        p = np.asarray(fk_num(*q_sol), dtype=float)[:3, 3]
        assert np.linalg.norm(p - target) < tol, \
            f"IK position residual {res:.2e} at target {target}"
    print("  [PASS] SciPy IK round-trips against FK")
