"""
kinematics_checks.py — Milestone 1's self-tests, beside kinematics.py.

Discovered through kinematics.py by `run_all.py`; pytest never collects this
file directly (it doesn't match `test_*.py`), so `test_derivation.py` stays
the one bridge and the two entry points cannot disagree. The bound on σ_min
over the workspace is not a check here: it is kinematics.py's margin, SIGMA,
which `run_all.py` searches and confirms in the truth model.
"""

import numpy as np

import armature
from armature.sampler import DEFAULT_SEED

from kinematics import J_num, Q, fk_num
from mechanism import COORDINATES, TOOL, derived, truth, vector


def test_coordinates_match_the_variant():
    """The coordinates this milestone differentiates against are its
    variant's, by name: none dropped without a reduction, none a reduction
    holds. `armature.account` names any coordinate at fault."""
    armature.account(derived(), Q)
    print(f"  [PASS] the Jacobian's columns are the variant's coordinates "
          f"{list(COORDINATES)}")


def test_jacobian_vs_finite_difference(trials=5, seed=DEFAULT_SEED,
                                       h=1e-7, tol=1e-5):
    """Self-consistency: the Jacobian against derivatives of the same FK.

    The configurations come from the engine's sampler like every other
    check's, rather than from a generator of this file's own — one sampler is
    what makes "over the envelope" the same set here, in the dynamics check and
    in the worst-case search, and a check with a private seed is a check whose
    configurations a reviewer cannot reproduce from the note.
    """
    for s in armature.sample(truth(), trials, seed):
        qv = vector(s.q)
        Jn = np.asarray(J_num(*qv), dtype=float)[:3, :]   # linear part
        for i in range(len(qv)):
            dq = np.zeros(len(qv)); dq[i] = h
            p1 = np.asarray(fk_num(*(qv + dq)), dtype=float)[:3, 3]
            p0 = np.asarray(fk_num(*(qv - dq)), dtype=float)[:3, 3]
            fd = (p1 - p0) / (2 * h)
            assert np.allclose(Jn[:, i], fd, atol=tol), \
                f"Jacobian col {i} mismatch at q={qv}"
    print("  [PASS] Jacobian matches finite-difference FK")


def test_truth_fk_and_jacobian(n=24, seed=DEFAULT_SEED, tol=1e-9):
    """The mandatory Milestone 1 truth check: FK and the Jacobian against the
    truth model, at configurations nobody chose.

    The finite-difference check above compares the Jacobian with derivatives of
    the same position function, so a Jacobian in the wrong representation —
    body rather than space, an angular row read in the wrong frame — passes it.
    Both sides read the description, so a frame written wrong in mechanism.py
    is on both sides of this check too, and the review artifact is its check.
    What this one sees is everything the derivation builds on the frames: the
    tool on the wrong body, a velocity read in the wrong frame, a closed form
    the note writes out by hand. The right-hand side is MuJoCo's own site pose
    and site Jacobian, `s.pose` and `s.jacobian`.
    """
    samples = armature.sample(truth(), n, seed)
    worst_p, worst_J, worst_at = 0.0, 0.0, None
    for s in samples:
        qv = vector(s.q)
        T_model = np.asarray(fk_num(*qv), dtype=float)
        pose, jac = s.pose(TOOL), s.jacobian(TOOL)
        J_model = np.asarray(J_num(*qv), dtype=float)
        J_truth = np.vstack([jac.linear, jac.angular])
        dp = float(np.max(np.abs(T_model[:3, 3] - pose.position)))
        dR = float(np.max(np.abs(T_model[:3, :3] - pose.rotation)))
        dJ = float(np.max(np.abs(J_model - J_truth)))
        if max(dp, dJ) > max(worst_p, worst_J):
            worst_at = qv
        worst_p, worst_J = max(worst_p, dp, dR), max(worst_J, dJ)
        assert dp < tol and dR < tol, (
            f"the tool pose {T_model[:3, 3]} disagrees with the truth model's "
            f"{pose.position} at q={qv} (rotation off by {dR:.2e})")
        assert dJ < tol, (f"Jacobian disagrees with the truth model's by {dJ:.2e} "
                          f"at q={qv}")
    print(f"  [PASS] FK and Jacobian match the truth model over {samples}")
    print(f"         worst |dp|, |dR| {worst_p:.2e}, worst |dJ| {worst_J:.2e}, "
          f"at q = {np.round(worst_at, 4)}")
