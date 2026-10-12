"""
verification.py — Milestone 3: numeric IK and the worst-case actuator sizing.

Mirrors 03_results.md; self-tests in verification_checks.py, and the tables
the note cites are printed by report_results.py. Depends on kinematics.py
(fk_num, J_num) and dynamics/statics.py (static_torques).

**"Worst" is searched, never sampled or picked.** The holding margin below is
declared once, over every posture in WORKSPACE, every row of the load-case
table, every heading of a case that names a plane, and every tolerance band,
and `run_all.py` hands it to `armature.search` (ADR 0005): a seeded Sobol set,
every corner, then a Powell polish. Its truth re-derives the worst point's
torques in the truth model and holds them there under the load as a real
force. Over a plane of headings the answer is also exact, a norm
(`worst_tip_force`), and a check holds the search to it.
"""

import numpy as np
from scipy.optimize import least_squares

from armature import Choice, Coordinates, Direction, Margin, Space

from params import LOAD_CASES, PARAMS, PLANE_XY, WORKSPACE
from mechanism import (COORDINATES, TOOL, band_values, bands, mechanism, truth,
                       vector)
from kinematics import J_num, fk_num
from dynamics.statics import static_torques

# Run order and heading for `run_all.py`, which discovers this module by its
# margin and by the `test_*` callables in verification_checks.py, not by name.
MILESTONE = (3, "Milestone 3: verification")

N = len(COORDINATES)
# The load-case table by row name: the holding margin's `case` axis.
CASES = {case.name: case for case in LOAD_CASES}
# What each joint's actuator can supply [N m, joint side]: the description's
# derated torque limit through its gear.
LIMITS = {a.joint: float(a.torque_limit) * float(a.gear)
          for a in truth().description.actuators}
# The truth hold: released for at least this many steps, it must stay within
# HOLD_DRIFT [rad] of the posture.
HOLD_STEPS = 500
HOLD_DRIFT = 1e-3


def tip_force(case):
    """The world-frame force [N] a fixed-direction load case applies at the tool.

    `sign` multiplies the direction, which is what makes a signed case two rows
    rather than one reading. A case whose direction is a *set* has no single
    force and raises here; the holding margin searches its heading, and
    `worst_tip_force` answers it exactly per joint.
    """
    assert case.direction != PLANE_XY, (
        f"load case {case.name!r} names a direction set, not a direction; its "
        f"worst heading is per joint — use worst_tip_force")
    sense = case.sign if case.sign else 1
    return sense * case.magnitude * np.asarray(case.direction, dtype=float)


def tool_force(case, heading):
    """The world-frame force [N] `case` applies at the tool, with `heading` the
    searched unit vector where the case names a plane, ignored otherwise."""
    if case.direction == PLANE_XY:
        return case.magnitude * np.asarray(heading, dtype=float)
    return tip_force(case)


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
    sign of tau_j. It is what the holding margin's search over headings is held
    to, at the posture the search finds.
    """
    if case.direction != PLANE_XY:
        return tip_force(case)
    column = np.array([Jv[0, j], Jv[1, j], 0.0])
    reach = float(np.linalg.norm(column))
    if reach < 1e-12:            # this joint cannot feel a force in the plane
        return np.zeros(3)
    sense = -1.0 if tau[j] >= 0 else 1.0
    return sense * case.magnitude * column / reach


def joint_slack(tau):
    """The least torque any joint has left under its limit [N m]."""
    return min(LIMITS[c] - abs(float(t)) for c, t in zip(COORDINATES, tau))


def holding_slack(p):
    """The holding margin [N m]: the least torque any joint's actuator has
    left, holding `p.state` against gravity and `p.case`'s tool force, at the
    point's band values. The limit is the description's derated torque limit,
    and the derivation's g(q) and J_v give the torque."""
    q, band = vector(p.state.q), band_values(p)
    Jv = np.asarray(J_num(*q, **band), dtype=float)[:3, :]
    return joint_slack(holding_torque(static_torques(q, **band), Jv,
                                      tool_force(CASES[p.case], p.load)))


def holding_truth(p):
    """The holding margin from the truth model, which never saw g(q), J_v or
    the sign in `holding_torque`: its own inverse dynamics with the case's
    force applied at the tool, in the state compiled at the point's band
    values. Then the torque is **held** — released for HOLD_STEPS under the
    same force, the arm must stay put — so a torque that only reproduces is
    not a torque that holds. A settle clamps at the torque limit, so a hold
    beyond it falls here too."""
    s, force = p.state, tool_force(CASES[p.case], p.load)
    inv = s.inverse(loads={TOOL: force})
    tau = {a.joint: inv.torque[a.name] * float(a.gear)
           for a in s.compiled.description.actuators}
    out = s.settle(hold=inv.torque, loads={TOOL: force}, min_steps=HOLD_STEPS)
    drift = max(abs(v) for v in out.moved.values())
    assert out.stable and drift < HOLD_DRIFT, (
        f"{p.case}: holding {dict(inv.torque)} N m under a "
        f"{np.round(force, 3)} N tool force, the truth model left "
        f"{dict(s.q)} for {dict(out.q)} — the torque that sizes this "
        f"actuator does not hold the machine there")
    return joint_slack(tau[c] for c in COORDINATES)


# The actuators' holding margin, worst over every row of the load-case table
# (both signs of a signed class are rows, so both are searched), every heading
# where a case names a plane, every tolerance band, and every posture in
# WORKSPACE. `load` is read only by a plane case; the others carry it unused.
# The default budget (64 Sobol points per continuous dimension, every corner,
# three Powell starts) costs about 3,200 evaluations over the five rows, two
# seconds with the band recompiling the truth model per point, so none is set.
HOLDING = Margin(
    "holding torque", holding_slack, "N m",
    over=Space(case=Choice(list(CASES)), load=Direction("xy"), **bands(),
               state=Coordinates(mechanism, PARAMS, within=WORKSPACE)),
    truth=holding_truth, agree=1e-6)


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
