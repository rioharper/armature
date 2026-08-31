"""
dynamics.py — Milestone 2: Euler-Lagrange dynamics + self-tests.

Mirrors 02_dynamics.md. Depends on kinematics.py (frames) and params.py
only — a red-team pass on Milestone 2 needs those two plus this file, not
verification.py. Run standalone: `python dynamics.py`.
"""

import numpy as np
import sympy as sp
from sympy import Matrix

from params import (COM_LOCAL, INERTIA, MASSES, GRAVITY_VEC, N, t,
                     q, qd, qdd, QS, QDS, SUB_Q, SUB_P)
from kinematics import FRAMES


def lagrangian_dynamics(frames):
    """Euler-Lagrange. Returns (M, C, gvec, V) with tau = M qdd + C qd + g.

    V (potential energy) is returned so the numeric layer can check total
    mechanical energy E = KE + V directly, rather than through a work
    integral — an honest conservation test instead of a bookkeeping trick.
    """
    KE = sp.S.Zero
    PE = sp.S.Zero
    for i in range(N):
        T_i = frames[i]
        R_i = T_i[:3, :3]
        p_com = T_i[:3, 3] + R_i * COM_LOCAL[i]
        v_com = p_com.diff(t)
        # angular velocity from R' = [w]x R  ->  [w]x = R' R^T
        Wx = sp.trigsimp(R_i.diff(t) * R_i.T)
        w = Matrix([Wx[2, 1], Wx[0, 2], Wx[1, 0]])
        I_base = R_i * INERTIA[i] * R_i.T
        KE += (MASSES[i] * (v_com.T * v_com)[0]
               + (w.T * I_base * w)[0]) / 2
        PE += -MASSES[i] * (GRAVITY_VEC.T * p_com)[0]

    L = sp.trigsimp(KE - PE)
    eqs = Matrix([sp.diff(sp.diff(L, qd[i]), t) - sp.diff(L, q[i])
                  for i in range(N)])
    eqs = sp.expand(sp.trigsimp(eqs))

    M = eqs.jacobian(qdd)
    gvec = eqs.subs([(v, 0) for v in qdd]).subs([(v, 0) for v in qd])
    Cqd = sp.simplify(eqs - M * qdd - gvec)   # Coriolis+centrifugal * qd
    # Standard Christoffel C matrix (needed for skew-symmetry check):
    Cmat = sp.zeros(N, N)
    for k in range(N):
        for j in range(N):
            Cmat[k, j] = sum(
                sp.Rational(1, 2)
                * (sp.diff(M[k, j], q[i]) + sp.diff(M[k, i], q[j])
                   - sp.diff(M[i, j], q[k])) * qd[i]
                for i in range(N))
    Cmat = sp.simplify(Cmat)
    assert sp.simplify(Cmat * qd - Cqd) == sp.zeros(N, 1), \
        "Christoffel C inconsistent with E-L expansion"
    return sp.simplify(M), Cmat, sp.simplify(gvec), sp.simplify(PE)


print("Building symbolic dynamics ...")
M_SYM, C_SYM, G_SYM, V_SYM = lagrangian_dynamics(FRAMES)
print("  Dynamics built.")

# --- numeric functions, lambdified, parameterized by params.PARAMS ---
M_num = sp.lambdify(QS, M_SYM.subs(SUB_Q).subs(SUB_P), "numpy")
C_num = sp.lambdify(QS + QDS, C_SYM.subs(SUB_Q).subs(SUB_P), "numpy")
g_num = sp.lambdify(QS, G_SYM.subs(SUB_Q).subs(SUB_P), "numpy")
V_num = sp.lambdify(QS, V_SYM.subs(SUB_Q).subs(SUB_P), "numpy")


def static_torques(q_vals):
    """Joint torques to hold posture q against gravity [N m]."""
    return np.asarray(g_num(*q_vals), dtype=float).flatten()


def total_energy(q_vals, qd_vals):
    """Total mechanical energy E = KE + V [J] at a state."""
    Mn = np.asarray(M_num(*q_vals), dtype=float)
    ke = 0.5 * np.asarray(qd_vals) @ Mn @ np.asarray(qd_vals)
    pe = float(np.asarray(V_num(*q_vals), dtype=float))
    return ke + pe


def test_mass_matrix_properties(trials=5, tol=1e-9):
    rng = np.random.default_rng(1)
    for _ in range(trials):
        qv = rng.uniform(-np.pi, np.pi, N)
        Mn = np.asarray(M_num(*qv), dtype=float)
        assert np.allclose(Mn, Mn.T, atol=tol), "M not symmetric"
        assert np.all(np.linalg.eigvalsh(Mn) > 0), "M not positive definite"
    print("  [PASS] M(q) symmetric positive-definite")


def test_skew_symmetry(tol=1e-8):
    """Mdot - 2C must be skew-symmetric (Christoffel C)."""
    Mdot = M_SYM.diff(t)
    S = sp.simplify(Mdot - 2 * C_SYM)
    assert sp.simplify(S + S.T) == sp.zeros(N, N), "Mdot-2C not skew"
    print("  [PASS] Mdot - 2C skew-symmetric")


def test_energy_conservation(T_end=2.0, tol_rel=1e-4):
    """Unforced, gravity-on dynamics conserve total mechanical energy.

    Integrate with SciPy's solve_ivp (RK45, tight tolerances) from a
    nonzero posture at rest and compare E(T) to E(0). Compact, and it
    exercises the numeric M, C, g and the potential-energy function
    together.
    """
    from scipy.integrate import solve_ivp

    def rhs(_t, s):
        qv, qdv = s[:N], s[N:]
        Mn = np.asarray(M_num(*qv), dtype=float)
        Cn = np.asarray(C_num(*qv, *qdv), dtype=float)
        gn = np.asarray(g_num(*qv), dtype=float).flatten()
        qddv = np.linalg.solve(Mn, -(Cn @ qdv) - gn)
        return np.concatenate([qdv, qddv])

    q0 = np.zeros(N)
    if N >= 1:
        q0[0] = 0.3
    if N >= 2:
        q0[1] = -0.4
    s0 = np.concatenate([q0, np.zeros(N)])
    E0 = total_energy(s0[:N], s0[N:])
    sol = solve_ivp(rhs, (0.0, T_end), s0, method="RK45",
                    rtol=1e-10, atol=1e-12, max_step=1e-2)
    assert sol.success, f"integration failed: {sol.message}"
    sf = sol.y[:, -1]
    E1 = total_energy(sf[:N], sf[N:])
    scale = max(abs(E0), 1e-6)
    assert abs(E1 - E0) / scale < tol_rel, \
        f"Energy drift {(E1 - E0) / scale:.2e} exceeds {tol_rel}"
    print("  [PASS] total energy conserved under SciPy integration")


if __name__ == "__main__":
    print("Running Milestone 2 self-tests ...")
    test_mass_matrix_properties()
    test_skew_symmetry()
    test_energy_conservation()
    print("Milestone 2 self-tests passed.\n")
    print("  M(q) =", M_SYM)
    print("  g(q) =", G_SYM)
