"""
verification_checks.py — Milestone 3's self-tests, beside verification.py.

The holding margin itself is not a check here: `run_all.py` discovers
verification.HOLDING, searches it on the truth model, fails it where it does
not pass, and holds the derivation's g - J_v^T f to it at the worst point.
What is here is what holds the search to account: the exact answer over a
plane of headings, the load-case table searched whole, each case's worst
torque held in the truth model, and checks that the margin sizes on the truth
model and that its check can disagree.
"""

from dataclasses import replace

import numpy as np

import armature
from armature import Budget
from armature.sampler import DEFAULT_SEED

from armature.search import Point

from kinematics import J_num, fk_num
from mechanism import (BANDS, COORDINATES, TOOL, band_values, mechanism,
                       truth, vector)
from params import LOAD_CASES, PARAMS, PLANE_XY, WORKSPACE
from dynamics.statics import static_torques
from run_all import searched
from verification import (CASES, HOLD_DRIFT, HOLD_STEPS, HOLDING, LIMITS, N,
                          holding_torque, inverse_kinematics, joint_slack,
                          tool_force, worst_tip_force)


def test_ik_roundtrip(trials=8, seed=DEFAULT_SEED, tol=1e-4):
    """FK -> IK -> FK must return to the same end-effector position.

    Targets from the engine's sampler over the workspace, not from a generator
    of this file's own: the IK inverts J_v, so its conditioning is exactly the
    σ_min margin one milestone back, and the set it has to converge over is
    `params.WORKSPACE` — the region the requirements name — rather than the
    envelope, which contains the elbow singularity the IK cannot pass through.
    The start perturbation is not evidence, so it keeps a generator of its own.
    """
    rng = np.random.default_rng(seed)
    for s in armature.sample(truth(), trials, seed, within=WORKSPACE):
        q_true = vector(s.q)
        target = np.asarray(fk_num(*q_true), dtype=float)[:3, 3]
        start = q_true + rng.uniform(-0.2, 0.2, N)   # near a valid branch
        q_sol, _ok, res = inverse_kinematics(target, q0=start)
        p = np.asarray(fk_num(*q_sol), dtype=float)[:3, 3]
        assert np.linalg.norm(p - target) < tol, \
            f"IK position residual {res:.2e} at target {target}"
    print(f"  [PASS] SciPy IK round-trips against FK over {trials} sampled "
          f"workspace targets (seed {seed})")


def test_the_holding_margin_searches_every_load_case():
    """The margin's `case` axis is the whole load-case table, every row, so
    both signs of a signed class are searched. A row filtered out of the
    axis is a case read in one sign, however complete the table is."""
    searched_cases = set(HOLDING.over.axes["case"].values)
    table = {case.name for case in LOAD_CASES}
    assert searched_cases == table, (
        f"the holding margin searches {sorted(searched_cases)}; the load-case "
        f"table has {sorted(table)}")
    print(f"  [PASS] the holding margin searches all {len(table)} load-case "
          f"rows")


def test_the_search_agrees_with_the_exact_plane_answer(tol=1e-6):
    """Over a plane of headings the worst is exact: per joint, |g_j| plus the
    force times the Jacobian column's reach in the plane. At the posture and
    band value the search found for each plane case, that exact worst over
    every heading must equal the search's worst, within `tol` [N m].

    The search's worst can only be above the exact one at its own posture if
    the polish stopped short of the worst heading, and only below it if the
    margin read a heading the plane does not hold.
    """
    worst = searched(HOLDING)
    plane = [c for c in worst.cases if CASES[c.choices["case"]].direction
             == PLANE_XY]
    assert plane, "the load-case table names no plane; nothing to hold to"
    for found in plane:
        case = CASES[found.choices["case"]]
        band = {k: found.at[k] for k in BANDS}
        q = vector(found.at["state"])
        tau = static_torques(q, **band)
        Jv = np.asarray(J_num(*q, **band), dtype=float)[:3, :]
        exact = min(LIMITS[c] - abs(holding_torque(
            tau, Jv, worst_tip_force(tau, Jv, case, j))[j])
            for j, c in enumerate(COORDINATES))
        assert abs(exact - found.value) < tol, (
            f"{case.name}: the search's worst is {found.value:.9f} N m, the "
            f"exact answer over every heading {exact:.9f} N m, at "
            f"{found.at}")
        print(f"  [PASS] {case.name}: the search's worst {found.value:.7f} N m "
              f"matches the exact plane answer to {abs(exact - found.value):.1e}")


def test_truth_holding_sees_a_flipped_force(budget=Budget(global_points=16,
                                                          polish_starts=0)):
    """The check's teeth: the holding margin's check, the derivation, with
    its force's sign flipped, as `g + J^T f` would have it, must disagree
    with the margin, the truth model, beyond `agree`. The truth model takes
    the force as a force, so it cannot share the flip; a check that agreed
    here would agree with anything."""
    def flipped(p):
        q, band = vector(p.state.q), band_values(p)
        Jv = np.asarray(J_num(*q, **band), dtype=float)[:3, :]
        force = tool_force(CASES[p.case], p.load)
        return joint_slack(static_torques(q, **band) + Jv.T @ force)

    worst = armature.search(replace(HOLDING, check=flipped, budget=budget))
    assert not worst.check.agrees, (
        f"a flipped tool force agrees with the truth model: {worst}")
    print(f"  [PASS] a flipped tool force disagrees with the truth model by "
          f"{worst.check.gap:.3f} N m, beyond {worst.check.agree:g}")


def test_truth_holding_sizes_on_the_truth_model(dx=0.05, seed=DEFAULT_SEED):
    """The margin's side (ADR 0012): HOLDING's `fn` reads the truth model and
    its `check` the derivation. With the forearm's COM `dx` [m] further out
    in the truth model's state alone, which the derivation never sees, the
    two must disagree beyond `agree`: every joint carries the forearm. A
    `fn` pointed at the derivation agrees with its check wherever the truth
    model is, and sizes the part on whatever a reduction left out."""
    moved = armature.compile(mechanism, {**PARAMS, "lc2": PARAMS["lc2"] + dx})
    s = armature.sample(moved, 1, seed, within=WORKSPACE).states[0]
    p = Point({"case": LOAD_CASES[0].name, "load": np.array([1.0, 0.0, 0.0]),
               **{k: PARAMS[k] for k in BANDS}, "state": s})
    gap = abs(HOLDING.fn(p) - HOLDING.check(p))
    assert gap > HOLDING.agree, (
        f"the holding margin reads {HOLDING.fn(p):.6f} N m with the "
        f"forearm's COM {dx} m out in the truth model, as its check does on "
        f"the derivation: its fn is not the truth model")
    print(f"  [PASS] the holding margin sizes on the truth model: a COM {dx} m "
          f"out that the derivation never saw moves it {gap:.3f} N m from its "
          f"check")


def test_truth_the_worst_holding_torques_hold():
    """Each load case's worst torque, from the truth model's inverse
    dynamics, **held**: released for HOLD_STEPS under the same tool force,
    at the case's band values, the arm must stay within HOLD_DRIFT of the
    posture. A torque that only reproduces is not a torque that holds, and a
    settle clamps at the torque limit, so a hold beyond it falls here too."""
    worst = searched(HOLDING)
    for found in worst.cases:
        band = {k: found.at[k] for k in BANDS}
        s = armature.compile(mechanism, {**PARAMS, **band}).at(
            q=found.at["state"])
        force = tool_force(CASES[found.choices["case"]], found.at["load"])
        inv = s.inverse(loads={TOOL: force})
        out = s.settle(hold=inv.torque, loads={TOOL: force},
                       min_steps=HOLD_STEPS)
        drift = max(abs(v) for v in out.moved.values())
        assert out.stable and drift < HOLD_DRIFT, (
            f"{found.choices['case']}: holding {dict(inv.torque)} N m under a "
            f"{np.round(force, 3)} N tool force, the truth model left "
            f"{dict(s.q)} for {dict(out.q)} — the torque that sizes this "
            f"actuator does not hold the machine there")
    print(f"  [PASS] each of {len(worst.cases)} load cases' worst torque "
          f"holds the truth model for {HOLD_STEPS} steps")
