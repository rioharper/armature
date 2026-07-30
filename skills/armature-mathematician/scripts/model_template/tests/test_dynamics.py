"""Milestone 2. Structural properties that hold for any correct M, C, g."""

import numpy as np
import pytest

pytestmark = pytest.mark.m2


def test_mass_matrix_symmetric_positive_definite(dyn, kin):
    rng = np.random.default_rng(0xD17)
    for _ in range(32):
        q = rng.uniform(-np.pi, np.pi, size=kin.N)
        M = np.asarray(dyn.mass_matrix_num(q), dtype=float)
        np.testing.assert_allclose(M, M.T, rtol=1e-9, atol=1e-12,
                                   err_msg=f"M(q) not symmetric at q={q}")
        assert np.all(np.linalg.eigvalsh(M) > 0), f"M(q) not positive-definite at q={q}"


def test_energy_conserved_under_free_motion(dyn, kin):
    """
    With no applied torque and no dissipation, total energy is invariant. A drift
    here means a sign error or a dropped term — the failure this test exists for.
    """
    from scipy.integrate import solve_ivp

    q0 = np.full(kin.N, 0.3)
    qd0 = np.full(kin.N, 0.1)
    E0 = dyn.total_energy(q0, qd0)

    def rhs(_t, y):
        q, qd = y[: kin.N], y[kin.N:]
        M = np.asarray(dyn.mass_matrix_num(q), dtype=float)
        rest = np.asarray(dyn.nonlinear_terms_num(q, qd), dtype=float).ravel()
        return np.concatenate([qd, np.linalg.solve(M, -rest)])

    sol = solve_ivp(rhs, (0.0, 2.0), np.concatenate([q0, qd0]),
                    rtol=1e-10, atol=1e-12, dense_output=True)
    assert sol.success, "integration failed"

    for t in np.linspace(0.0, 2.0, 25):
        y = sol.sol(t)
        E = dyn.total_energy(y[: kin.N], y[kin.N:])
        assert abs(E - E0) / max(abs(E0), 1.0) < 1e-6, f"energy drifted at t={t:.2f}"
