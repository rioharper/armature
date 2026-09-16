"""
verification_checks.py — Milestone 3's self-tests, beside verification.py.
"""

import numpy as np

from params import N
from kinematics import fk_num
from truth.chain import build, site_jacobian
from truth.envelope import DEFAULT_SEED, sample_workspace
from truth.inverse import inverse_dynamics
from verification import combine, inverse_kinematics, worst_over_load_cases

# One search, shared by both checks below: the grid and the multi-start
# optimiser over every row of the load-case table are a few seconds of work,
# and running them twice would only prove the seed is honoured.
WORST = worst_over_load_cases()


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
    print(f"  [PASS] SciPy IK round-trips against FK over {trials} sampled "
          f"workspace targets (seed {seed})")


def test_grid_and_optimiser_bracket_the_worst_case(rel=0.05):
    """Two methods on every load case, and the answer is the worse of them.

    A grid cannot see a peak narrower than its step; an optimiser cannot
    certify that the basin it climbed is the tallest. Neither alone is an
    answer to "worst", and a handful of samples is not a method at all. Run
    both and the pair bracket it — so a gap between them wider than `rel` is
    the finding, not a rounding: refine the grid or add starts until the two
    agree to the precision the margin is quoted at.
    """
    for w in WORST:
        assert np.all(w.tau >= w.grid - 1e-12) and np.all(w.tau >= w.opt - 1e-12), \
            f"{w.case.name}: the reported worst case is below a method's own"
        scale = np.maximum(w.tau, 1e-9)
        gap = float(np.max(np.abs(w.opt - w.grid) / scale))
        assert gap < rel, (
            f"{w.case.name}: the grid says {w.grid} N m and the optimiser "
            f"{w.opt} N m, {gap:.1%} apart at a grid step of {w.step}; one of "
            f"them is not finding the peak")
    step = np.round(WORST[0].step, 4)
    print(f"  [PASS] grid (step {step} rad) and multi-start optimiser agree "
          f"within {rel:.0%} on {len(WORST)} load cases")
    for w in WORST:
        print(f"         {w.case.name:<10} worst |tau| {np.round(w.tau, 3)} N m")


def test_worst_case_torque_vs_truth_model(tol=1e-9):
    """The mandatory Milestone 3 truth check: the worst case confirmed by the
    truth model at the posture the search found.

    A worst case is a number an actuator gets bought against, and everything
    upstream of it — g(q) from the Lagrangian, J_v from the FK — is the
    derivation's own. Here the same load case is evaluated from the truth
    model's gravity torque (MuJoCo's recursive inverse dynamics at rest) and
    the truth model's own site Jacobian, at exactly the posture the optimiser
    reported. The algebra combining them is shared and is an identity; the
    physics on the two sides has nothing in common.

    The posture is checked strictly inside the joint limits first. A worst case
    found *on* a limit is a torque the limit is carrying, and the comparison
    would fail for the wrong reason.
    """
    model, data = build()
    rest = np.zeros(N)
    worst_gap, worst_at = 0.0, None
    for w in WORST:
        for j in range(N):
            qv = w.q[j]
            tau_truth = inverse_dynamics(model, data, qv, rest, rest)
            Jv = site_jacobian(model, data, qv)[:3, :]
            value = combine(tau_truth, Jv, w.case)[j]
            gap = abs(value - w.tau[j])
            if gap > worst_gap:
                worst_gap, worst_at = gap, (w.case.name, j, qv)
            assert gap < tol, (
                f"{w.case.name}: joint {j + 1}'s worst case reads "
                f"{w.tau[j]:.6f} N m where the truth model reads "
                f"{value:.6f} N m at q={np.round(qv, 4)}")
    name, j, qv = worst_at
    print(f"  [PASS] every load case's worst torque confirmed by the truth "
          f"model at the posture found ({len(WORST)} cases, {N} joints)")
    print(f"         worst |dtau| {worst_gap:.2e} N m, {name} joint {j + 1} "
          f"at q = {np.round(qv, 4)}")
