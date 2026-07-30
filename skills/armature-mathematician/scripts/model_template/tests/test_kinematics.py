"""Milestone 1. The Jacobian is the claim; finite-difference FK is the check."""

import numpy as np
import pytest

pytestmark = pytest.mark.m1


def test_jacobian_matches_finite_difference(kin):
    """
    Check across randomized postures rather than one convenient pose — the
    workspace is large and a hand-picked spot check misses exactly the postures
    that matter. Seeded so a failure is reproducible.
    """
    rng = np.random.default_rng(0xA12)
    for _ in range(64):
        q = rng.uniform(-np.pi, np.pi, size=kin.N)
        J_analytic = np.asarray(kin.geometric_jacobian_num(q), dtype=float)
        J_fd = np.zeros_like(J_analytic)
        eps = 1e-7
        p0 = np.asarray(kin.forward_kinematics_num(q), dtype=float)[:3, 3]
        for j in range(kin.N):
            dq = np.zeros(kin.N)
            dq[j] = eps
            p1 = np.asarray(kin.forward_kinematics_num(q + dq), dtype=float)[:3, 3]
            J_fd[:3, j] = (p1 - p0) / eps
        np.testing.assert_allclose(
            J_analytic[:3, :], J_fd[:3, :], rtol=1e-4, atol=1e-6,
            err_msg=f"linear Jacobian disagrees with finite-difference FK at q={q}",
        )
