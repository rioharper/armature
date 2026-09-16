"""
kinematics_checks.py — Milestone 1's self-tests, beside kinematics.py.

Discovered through kinematics.py by `run_all.py`; pytest never collects this
file directly (it doesn't match `test_*.py`), so `test_derivation.py` stays
the one bridge and the two entry points cannot disagree.
"""

import numpy as np

from params import N
from kinematics import J_num, fk_num
from truth.chain import build, site_jacobian, site_pose
from truth.envelope import DEFAULT_SEED, sample


def test_jacobian_vs_finite_difference(trials=5, h=1e-7, tol=1e-5):
    rng = np.random.default_rng(0)
    for _ in range(trials):
        qv = rng.uniform(-np.pi, np.pi, N)
        Jn = np.asarray(J_num(*qv), dtype=float)[:3, :]   # linear part
        for i in range(N):
            dq = np.zeros(N); dq[i] = h
            p1 = np.asarray(fk_num(*(qv + dq)), dtype=float)[:3, 3]
            p0 = np.asarray(fk_num(*(qv - dq)), dtype=float)[:3, 3]
            fd = (p1 - p0) / (2 * h)
            assert np.allclose(Jn[:, i], fd, atol=tol), \
                f"Jacobian col {i} mismatch at q={qv}"
    print("  [PASS] Jacobian matches finite-difference FK")


def test_fk_and_jacobian_vs_truth_model(n=24, seed=DEFAULT_SEED, tol=1e-9):
    """The mandatory Milestone 1 truth check: FK and the Jacobian against a
    model that never saw this derivation, at configurations nobody chose.

    The finite-difference check above compares the Jacobian with derivatives of
    the same length function — it cannot see a frame assigned to the wrong
    axis, a DH row transcribed wrong, or a tool offset applied in the wrong
    frame, because both sides carry the mistake. This one can: the positions
    and the Jacobian on the right are MuJoCo's, computed from a body tree built
    off the parameter block.
    """
    model, data = build()
    configs = sample(n, seed)
    worst_p, worst_J, worst_at = 0.0, 0.0, None
    for qv in configs:
        p_model = np.asarray(fk_num(*qv), dtype=float)[:3, 3]
        p_truth, _R = site_pose(model, data, qv)
        J_model = np.asarray(J_num(*qv), dtype=float)
        J_truth = site_jacobian(model, data, qv)
        dp = float(np.max(np.abs(p_model - p_truth)))
        dJ = float(np.max(np.abs(J_model - J_truth)))
        if max(dp, dJ) > max(worst_p, worst_J):
            worst_at = qv
        worst_p, worst_J = max(worst_p, dp), max(worst_J, dJ)
        assert dp < tol, (f"end-effector position {p_model} disagrees with the "
                          f"truth model's {p_truth} at q={qv}")
        assert dJ < tol, (f"Jacobian disagrees with the truth model's by {dJ:.2e} "
                          f"at q={qv}")
    print(f"  [PASS] FK and Jacobian match the truth model over {n} sampled "
          f"configurations (seed {seed})")
    print(f"         worst |dp| {worst_p:.2e} m, worst |dJ| {worst_J:.2e}, "
          f"at q = {np.round(worst_at, 4)}")
