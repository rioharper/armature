"""
kinematics_checks.py — Milestone 1's self-tests, beside kinematics.py.

Discovered through kinematics.py by `run_all.py`; pytest never collects this
file directly (it doesn't match `test_*.py`), so `test_derivation.py` stays
the one bridge and the two entry points cannot disagree.
"""

import numpy as np

from params import N, SIGMA_MIN
from kinematics import J_num, fk_num, singular_values
from truth.chain import build, site_jacobian, site_pose
from truth.envelope import DEFAULT_SEED, sample, sample_workspace

# Large enough that the sweep's minimum is near the envelope's, cheap because
# the Jacobian is lambdified: a sweep is not a settle and need not be frugal.
SWEEP_SAMPLES = 400


def test_jacobian_vs_finite_difference(trials=5, seed=DEFAULT_SEED,
                                       h=1e-7, tol=1e-5):
    """Self-consistency: the Jacobian against derivatives of the same FK.

    The configurations come from the truth package's sampler like every other
    check's, rather than from a generator of this file's own — one sampler is
    what makes "over the envelope" the same set here, in the dynamics check and
    in the worst-case search, and a check with a private seed is a check whose
    configurations a reviewer cannot reproduce from the note.
    """
    for qv in sample(trials, seed):
        Jn = np.asarray(J_num(*qv), dtype=float)[:3, :]   # linear part
        for i in range(N):
            dq = np.zeros(N); dq[i] = h
            p1 = np.asarray(fk_num(*(qv + dq)), dtype=float)[:3, 3]
            p0 = np.asarray(fk_num(*(qv - dq)), dtype=float)[:3, 3]
            fd = (p1 - p0) / (2 * h)
            assert np.allclose(Jn[:, i], fd, atol=tol), \
                f"Jacobian col {i} mismatch at q={qv}"
    print("  [PASS] Jacobian matches finite-difference FK")


def test_truth_fk_and_jacobian(n=24, seed=DEFAULT_SEED, tol=1e-9):
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


def test_jacobian_singular_values_swept(n=SWEEP_SAMPLES, seed=DEFAULT_SEED):
    """The mandatory Milestone 1 sweep: σ(J_v) over the envelope, and the bound
    on σ_min inside the intended workspace.

    A matrix the derivation inverts or pseudo-inverts is a matrix whose rank is
    a claim, and a rank claimed at a handful of named postures is no claim at
    all — the postures a derivation reaches for are its symmetry planes, and a
    structure matrix that is rank-deficient *everywhere* is still full rank
    nowhere more convincingly than there. So the singular values are swept over
    the sampled envelope and the smallest is printed, whatever it is.

    Then the bound, and the two are different assertions. The envelope contains
    the elbow singularity at q2 = 0, so σ_min over the envelope goes to zero
    and must: that is the machine. What has to hold is that σ_min stays above
    `params.SIGMA_MIN` everywhere in `params.WORKSPACE`, the region the
    requirements actually name — a singularity inside the intended workspace is
    a Milestone 3 finding, and this is where it surfaces.
    """
    over_envelope = singular_values(sample(n, seed))
    configs = sample_workspace(n, seed)
    over_workspace = singular_values(configs)
    worst = float(np.min(over_workspace[:, -1]))
    at = configs[int(np.argmin(over_workspace[:, -1]))]
    assert worst > SIGMA_MIN, (
        f"the position Jacobian's smallest singular value falls to {worst:.4f} "
        f"m/rad at q={np.round(at, 4)}, inside WORKSPACE, below the "
        f"{SIGMA_MIN} m/rad the derivation needs; the intended workspace "
        f"contains a singularity")
    print(f"  [PASS] sigma_min(J_v) >= {SIGMA_MIN} m/rad over {n} sampled "
          f"workspace configurations (seed {seed})")
    print(f"         worst {worst:.4f} m/rad at q = {np.round(at, 4)}; over "
          f"the full envelope it falls to "
          f"{float(np.min(over_envelope[:, -1])):.4f} (the elbow singularity)")
