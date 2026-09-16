"""
verification_checks.py — Milestone 3's self-tests, beside verification.py.
"""

import numpy as np

from params import N
from kinematics import fk_num
from truth.chain import TOOL_SITE, build, site_jacobian
from truth.envelope import DEFAULT_SEED, sample_workspace
from truth.equilibrium import settle, site_wrench
from truth.inverse import inverse_dynamics
from verification import (holding_torque, inverse_kinematics, worst_tip_force,
                          worst_over_load_cases)

HOLD_STEPS = 500
_WORST = []


def worst():
    """The worst-case search over every load case, run once per session.

    Memoised behind a call rather than assigned at module level: `pytest`
    reaches these checks through `test_derivation.py`, which calls
    `run_all.discover_milestones()` at module scope, so a search at import time
    would run during *collection* — where a failure is a collection error that
    takes the whole file down, including the discovery guard that exists to stop
    a silently green run.
    """
    if not _WORST:
        _WORST.extend(worst_over_load_cases())
    return _WORST


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

    A grid cannot see a peak narrower than its step; an optimiser cannot certify
    that the basin it climbed is the tallest. Neither alone is an answer to
    "worst", and a handful of samples is not a method at all. Run both and the
    pair bracket it — so a gap between them wider than `rel` is the finding, not
    a rounding: refine the grid or add starts until the two agree to the
    precision the margin is quoted at.
    """
    for w in worst():
        assert np.all(w.tau >= w.grid - 1e-12) and np.all(w.tau >= w.opt - 1e-12), \
            f"{w.case.name}: the reported worst case is below a method's own"
        scale = np.maximum(w.tau, 1e-9)
        gap = float(np.max(np.abs(w.opt - w.grid) / scale))
        assert gap < rel, (
            f"{w.case.name}: the grid says {w.grid} N m and the optimiser "
            f"{w.opt} N m, {gap:.1%} apart at a grid step of {w.step}; one of "
            f"them is not finding the peak")
    step = np.round(worst()[0].step, 4)
    print(f"  [PASS] grid (step {step} rad) and multi-start optimiser agree "
          f"within {rel:.0%} on {len(worst())} load cases")
    for w in worst():
        print(f"         {w.case.name:<10} worst |tau| {np.round(w.tau, 3)} N m")


def test_truth_worst_case_torque(tol=1e-6):
    """The mandatory Milestone 3 truth check: the worst case **held**, under the
    load case applied to the truth model as a real force.

    A worst case is the number an actuator gets bought against, and everything
    upstream of it is the derivation's own — g(q) from the Lagrangian, J_v from
    the FK, and the transpose that turns a tip force into joint torques. The
    tempting check is to recompute that expression from the truth model's
    gravity torque and site Jacobian, and it is not enough: the mapping
    `tau = g - J^T f` would sit on *both* sides, so a flipped sign in it is a
    flipped sign in the comparison too. That is the blindness this whole package
    exists to remove, and it is easy to rebuild one level up.

    So the load case goes to the truth model as a **force**, converted to a body
    wrench by `truth.site_wrench` and applied at the tool. The claimed torque is
    held, the model is released for `HOLD_STEPS` steps, and it has to still be
    there. Nothing of the derivation is on that side: MuJoCo feels the force,
    integrates the motion, and either stays or does not. A sign error in the
    Jacobian transpose sends the arm away from the posture, hard.

    `inverse_dynamics` asserts no constraint is active at the posture, so a
    worst case found *on* a joint limit — a torque the end-stop would be
    carrying — fails loudly here rather than being confirmed quietly.
    """
    model, data = build()
    rest = np.zeros(N)
    worst_gap, worst_at, worst_drift = 0.0, None, 0.0
    for w in worst():
        for j in range(N):
            qv = w.q[j]
            tau_truth = inverse_dynamics(model, data, qv, rest, rest)
            Jv = site_jacobian(model, data, qv)[:3, :]
            force = worst_tip_force(tau_truth, Jv, w.case, j)
            tau_hold = holding_torque(tau_truth, Jv, force)

            gap = abs(abs(tau_hold[j]) - w.tau[j])
            if gap > worst_gap:
                worst_gap, worst_at = gap, (w.case.name, j, qv)
            assert gap < tol, (
                f"{w.case.name}: joint {j + 1}'s worst case reads "
                f"{w.tau[j]:.6f} N m where the truth model reads "
                f"{abs(tau_hold[j]):.6f} N m at q={np.round(qv, 4)}")

            out = settle(model, data, qv, hold=tau_hold,
                         wrench=site_wrench(model, data, TOOL_SITE, force),
                         min_steps=HOLD_STEPS)
            drift = float(np.max(np.abs(out.pose - qv)))
            worst_drift = max(worst_drift, drift)
            assert out.stable and drift < 1e-3, (
                f"{w.case.name}: holding {np.round(tau_hold, 4)} N m under a "
                f"{np.round(force, 3)} N tool force, the truth model left "
                f"q={np.round(qv, 4)} for {np.round(out.pose, 4)} — the torque "
                f"that sizes this actuator does not hold the machine there")
    name, j, qv = worst_at
    print(f"  [PASS] every load case's worst torque holds the truth model "
          f"still under its own tool force ({len(worst())} cases, {N} joints, "
          f"{HOLD_STEPS} steps each)")
    print(f"         worst |dtau| {worst_gap:.2e} N m ({name} joint {j + 1} at "
          f"q = {np.round(qv, 4)}), worst drift {worst_drift:.2e} rad")
