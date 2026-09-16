"""
verification.py — Milestone 3: numeric IK and the worst-case actuator sizing.

Mirrors 03_results.md; self-tests in verification_checks.py, and the tables
the note cites are printed by report_results.py. Depends on kinematics.py
(fk_num, J_num) and dynamics/statics.py (static_torques).

**"Worst" is computed, never sampled.** The search below answers each load case
in the parameter block by a dense grid whose step it reports and by a
multi-start optimiser, and returns the worse of the two — because a grid cannot
see a peak between its points and an optimiser cannot promise it found the
global one, while the pair bracket the answer and disagree out loud when they
do. Over a *set* of directions the answer is exact instead: the worst tip force
over the unit circle is a norm, not a search.
"""

from collections import namedtuple

import numpy as np
from scipy.optimize import least_squares, minimize

from params import LOAD_CASES, N, PLANE_XY, WORKSPACE
from kinematics import J_num, fk_num
from dynamics.statics import static_torques

# Run order and heading for `run_all.py`, which discovers this module
# by the `test_*` callables in verification_checks.py, not by name.
MILESTONE = (3, "Milestone 3: verification")

GRID_POINTS = 25        # per coordinate; the step is reported with the result
OPT_STARTS = 8          # multi-start count, the grid's best among them
OPT_SEED = 20260915

LO = np.array([lo for lo, _ in WORKSPACE], dtype=float)
HI = np.array([hi for _, hi in WORKSPACE], dtype=float)

# `tau` and `q` are the answer — the worse of the two methods per joint, and
# the posture it happens at. `grid` and `opt` are what each method alone found,
# carried out so the note can say whether they agreed, and `step` is the grid's
# spacing per coordinate, which bounds how far off the grid's own answer can be.
Worst = namedtuple("Worst", "case tau q grid opt step")


def combine(tau, Jv, case):
    """Worst |joint torque| from a gravity torque and a position Jacobian [N m].

    Gravity plus the tip force the case names, mapped through the Jacobian
    transpose. For a case whose direction is a *set* (`PLANE_XY`) this is the
    exact maximum over that set rather than a search across it: the worst of
    |tau_j + F (col_j . u)| over unit u in the plane is |tau_j| + F times the
    norm of column j projected onto it, taking u along whichever sign of tau_j
    is worse. Per joint independently, which is what sizing an actuator asks.

    Split out from `case_torque` so the truth check can push the same load case
    through the *truth model's* gravity torque and site Jacobian. What the two
    sides share is this algebra, which is an identity; what differs is the
    physics, which is the whole comparison.
    """
    if case.direction == PLANE_XY:
        return np.abs(tau) + case.magnitude * np.linalg.norm(Jv[:2, :], axis=0)
    sense = case.sign if case.sign else 1
    force = sense * case.magnitude * np.asarray(case.direction, dtype=float)
    return np.abs(tau + Jv.T @ force)


def case_torque(q_vals, case):
    """Worst |joint torque| at `q_vals` under one load case [N m], per joint."""
    return combine(static_torques(q_vals),
                   np.asarray(J_num(*q_vals), dtype=float)[:3, :], case)


def grid_search(case, points=GRID_POINTS):
    """Worst |tau| per joint on a dense grid over WORKSPACE, and the grid step.

    The step is returned, and printed beside the result, because it is the
    caveat: a peak narrower than the step is a peak this method cannot see.
    That is why the optimiser runs too.
    """
    axes = [np.linspace(lo, hi, points) for lo, hi in zip(LO, HI)]
    mesh = np.stack([a.ravel() for a in np.meshgrid(*axes, indexing="ij")], -1)
    tau = np.zeros(N)
    q = np.zeros((N, N))
    for qv in mesh:
        value = case_torque(qv, case)
        for j in np.where(value > tau)[0]:
            tau[j], q[j] = value[j], qv
    return tau, q, (HI - LO) / (points - 1)


def optimiser_search(case, starts=OPT_STARTS, seed=OPT_SEED, q0=None):
    """Worst |tau| per joint by multi-start L-BFGS-B over WORKSPACE.

    One maximisation per joint, from `starts` starting postures: the grid's
    best for that joint where the caller passes one, and the rest drawn from
    the workspace at random. Multi-start rather than one start because
    |tau_j|(q) is not convex and a single descent finds the basin it began in.
    """
    rng = np.random.default_rng(seed)
    tau = np.zeros(N)
    q = np.zeros((N, N))
    for j in range(N):
        seeds = list(rng.uniform(LO, HI, (starts, N)))
        if q0 is not None:
            seeds.insert(0, np.asarray(q0[j], dtype=float))
        for start in seeds:
            out = minimize(lambda qv: -case_torque(qv, case)[j], start,
                           method="L-BFGS-B", bounds=list(zip(LO, HI)))
            if -out.fun > tau[j]:
                tau[j], q[j] = -float(out.fun), np.array(out.x)
    return tau, q


def worst_case_torque(case, points=GRID_POINTS, starts=OPT_STARTS):
    """The worse of the grid and the optimiser for one load case.

    Both, not either: the grid is blind between its points and the optimiser
    cannot certify a global maximum, so the pair bracket the answer and a gap
    between them is itself the finding — widen the grid or add starts until the
    two agree to the precision the margin needs.
    """
    g_tau, g_q, step = grid_search(case, points)
    o_tau, o_q = optimiser_search(case, starts, q0=g_q)
    better = o_tau > g_tau
    tau = np.where(better, o_tau, g_tau)
    q = np.where(better[:, None], o_q, g_q)
    return Worst(case, tau, q, g_tau, o_tau, step)


def worst_over_load_cases(cases=None, points=GRID_POINTS, starts=OPT_STARTS):
    """One `Worst` per row of the parameter block's load-case table.

    Every row, including both signs of a signed one — the table is the set of
    cases this design is sized against, and picking from it here would be the
    one-sign reading the table exists to prevent.
    """
    return [worst_case_torque(case, points, starts)
            for case in (LOAD_CASES if cases is None else cases)]


def inverse_kinematics(target_xyz, q0=None, tol=1e-12):
    """Numeric position IK via SciPy least-squares.

    Returns (q, converged, residual_norm). Position only (3 residuals);
    append an orientation error to `resid` for full-pose IK. The seed q0
    selects the branch when several postures reach the point.
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
