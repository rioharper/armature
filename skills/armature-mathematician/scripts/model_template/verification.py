"""
verification.py — Milestone 3: numeric IK, worst-case actuator sizing,
self-tests. Mirrors 03_results.md.

Depends on kinematics.py (fk_num) and dynamics.py (static_torques). This is
the last module — a red-team pass here gets the full picture (all four
milestones), unlike the M1/M2 checkpoints which deliberately see less.
"""

import numpy as np
from scipy.optimize import least_squares

from params import N
from kinematics import fk_num
from dynamics import static_torques


def inverse_kinematics(target_xyz, q0=None, tol=1e-12):
    """Numeric position IK via SciPy least-squares.

    Returns (q, converged, residual_norm). Solves for end-effector
    position only (3 residuals); append an orientation error to `resid`
    if you need full-pose IK. Multiple postures can reach the same point —
    the seed q0 selects the branch.
    """
    target = np.asarray(target_xyz, dtype=float).flatten()[:3]
    if q0 is None:
        q0 = np.zeros(N)

    def resid(qv):
        p = np.asarray(fk_num(*qv), dtype=float)[:3, 3]
        return p - target

    sol = least_squares(resid, np.asarray(q0, dtype=float),
                        xtol=tol, ftol=tol)
    return sol.x, bool(np.linalg.norm(sol.fun) < 1e-8), float(np.linalg.norm(sol.fun))


def worst_case_static_torque(samples=5000, seed=0, limits=None):
    """Search the joint space for the largest-magnitude static (gravity)
    torque each joint must hold, and the posture that produces it.

    This is the number to size actuators against: for a spatial mechanism
    the worst gravity posture is not always the obvious outstretched one,
    so we sample rather than guess. `limits` is an optional list of
    (lo, hi) per joint in radians/metres; defaults to [-pi, pi].
    """
    rng = np.random.default_rng(seed)
    if limits is None:
        limits = [(-np.pi, np.pi)] * N
    lo = np.array([a for a, _ in limits])
    hi = np.array([b for _, b in limits])
    Q = lo + (hi - lo) * rng.random((samples, N))
    worst_tau = np.zeros(N)
    worst_q = np.zeros((N, N))
    for qv in Q:
        tau = np.abs(static_torques(qv))
        upd = tau > worst_tau
        worst_tau = np.where(upd, tau, worst_tau)
        for j in np.where(upd)[0]:
            worst_q[j] = qv
    return worst_tau, worst_q


def test_ik_roundtrip(trials=5, tol=1e-4):
    """FK -> IK -> FK must return to the same end-effector position."""
    rng = np.random.default_rng(3)
    for _ in range(trials):
        q_true = rng.uniform(-1.0, 1.0, N)
        target = np.asarray(fk_num(*q_true), dtype=float)[:3, 3]
        seed = q_true + rng.uniform(-0.2, 0.2, N)   # near a valid branch
        q_sol, _ok, res = inverse_kinematics(target, q0=seed)
        p = np.asarray(fk_num(*q_sol), dtype=float)[:3, 3]
        assert np.linalg.norm(p - target) < tol, \
            f"IK position residual {res:.2e} at target {target}"
    print("  [PASS] SciPy IK round-trips against FK")


if __name__ == "__main__":
    print("Running Milestone 3 self-tests ...")
    test_ik_roundtrip()
    print("Milestone 3 self-tests passed.\n")

    q_demo = np.zeros(N)   # fully outstretched: worst gravity case for a 2R arm
    print("Example numbers (outstretched posture, params.PARAMS):")
    print("  static holding torques [N m]:", static_torques(q_demo))

    # Actuator sizing: the worst static torque anywhere in the workspace,
    # not just at the demo posture. Feeds 03_results.md's implications.
    wt, wq = worst_case_static_torque()
    print("\n  worst-case static torque per joint [N m]:", wt)
    for j in range(N):
        print(f"    joint {j+1}: {wt[j]:.3f} N m at posture "
              f"{np.round(wq[j], 3)} rad")
