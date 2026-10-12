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

from armature.sampler import DEFAULT_SEED

from params import LOAD_CASES, PLANE_XY, WORKSPACE
from mechanism import COORDINATES
from kinematics import J_num, fk_num
from dynamics.statics import static_torques

# Run order and heading for `run_all.py`, which discovers this module
# by the `test_*` callables in verification_checks.py, not by name.
MILESTONE = (3, "Milestone 3: verification")

GRID_POINTS = 25        # per coordinate; the step is reported with the result
OPT_STARTS = 8          # multi-start count, the grid's best among them

# The search runs over the intended workspace, the box the sampler's `within`
# reads, laid out in the order the numeric functions take their coordinates.
N = len(COORDINATES)
LO = np.array([WORKSPACE[c][0] for c in COORDINATES], dtype=float)
HI = np.array([WORKSPACE[c][1] for c in COORDINATES], dtype=float)

# `tau` and `q` are the answer — the worse of the two methods per joint, and
# the posture it happens at. `grid` and `opt` are what each method alone found,
# carried out so the note can say whether they agreed, and `step` is the grid's
# spacing per coordinate, which bounds how far off the grid's own answer can be.
Worst = namedtuple("Worst", "case tau q grid opt step")


def tip_force(case):
    """The world-frame force [N] a fixed-direction load case applies at the tool.

    `sign` multiplies the direction, which is what makes a signed case two rows
    rather than one reading. A case whose direction is a *set* has no single
    force and raises here; ask `worst_tip_force` for the heading that binds a
    given joint.
    """
    assert case.direction != PLANE_XY, (
        f"load case {case.name!r} names a direction set, not a direction; its "
        f"worst heading is per joint — use worst_tip_force")
    sense = case.sign if case.sign else 1
    return sense * case.magnitude * np.asarray(case.direction, dtype=float)


def holding_torque(tau, Jv, force):
    """Joint torque holding a posture against gravity and a tip force [N m].

    Signed, and the sign is the whole point. Statics reads
    `g(q) = tau + J_v(q)^T f` — the actuators and the external force *together*
    balance gravity — so the torque the actuator must supply is

        tau_hold = g(q) - J_v(q)^T f

    with `f` the force the world applies to the tool. A load that pulls the tool
    down loads the shoulder *more*, and the minus sign is what says so; the plus
    sign gives a payload that lightens the arm carrying it, which is the kind of
    result that looks like a number and is a direction error.
    """
    return tau - Jv.T @ np.asarray(force, dtype=float)


def worst_tip_force(tau, Jv, case, j):
    """The force in `case`'s direction set that loads joint j hardest [N].

    For a fixed direction, that is just the case's force. For the unit circle in
    the base plane it is exact rather than searched: `tau_hold_j` is
    `tau_j - F (col_j . u)`, whose magnitude over unit u in the plane peaks at
    `|tau_j| + F ||col_j restricted to the plane||`, reached with u opposing the
    sign of tau_j. A handful of headings tried instead of this is the failure
    the computed-worst-case rule exists to stop.
    """
    if case.direction != PLANE_XY:
        return tip_force(case)
    column = np.array([Jv[0, j], Jv[1, j], 0.0])
    reach = float(np.linalg.norm(column))
    if reach < 1e-12:            # this joint cannot feel a force in the plane
        return np.zeros(3)
    sense = -1.0 if tau[j] >= 0 else 1.0
    return sense * case.magnitude * column / reach


def combine(tau, Jv, case):
    """Worst |holding torque| per joint under one load case [N m].

    `holding_torque` at the worst force in the case's direction set, per joint
    independently, which is what sizing an actuator asks. Split out from
    `case_torque` so the truth check can push the same load case through the
    *truth model's* gravity torque and site Jacobian.

    That sharing is also this function's limit, and worth knowing before you
    lean on it: a comparison whose two sides both call this cannot see an error
    *in* it — a flipped force sign here is a flipped force sign on both sides,
    which is the same blindness the truth model exists to remove, one level up.
    Which is why Milestone 3's truth check does not stop at recomputing this: it
    hands the force to the truth model as a real load at the tool and settles.
    """
    return np.array([abs(holding_torque(tau, Jv,
                                        worst_tip_force(tau, Jv, case, j))[j])
                     for j in range(N)])


def case_torque(q_vals, case):
    """Worst |holding torque| at `q_vals` under one load case [N m], per joint."""
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


def optimiser_search(case, starts=OPT_STARTS, seed=DEFAULT_SEED, q0=None):
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
