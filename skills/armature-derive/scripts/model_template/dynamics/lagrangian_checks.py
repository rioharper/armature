"""
dynamics/lagrangian_checks.py — self-tests for lagrangian.py, 02_dynamics.md §1–2.

Every check here is **self-consistency**: it holds M, C, g and V against each
other and against properties any correct Lagrangian has, using no model but
this one. That is exactly what a wrong assumption survives, since the
assumption sits on both sides of the comparison. The check that these equations
describe the mechanism is the truth model's inverse dynamics, one milestone
over; keep these for what they are good at, which is catching an arithmetic
slip the moment it lands.
"""

import numpy as np
import sympy as sp

from params import N, t
from dynamics.lagrangian import (M_SYM, C_SYM, M_num, C_num, g_num, V_num,
                                 total_energy)
from truth.chain import build
from truth.envelope import DEFAULT_SEED, sample_states
from truth.inverse import inverse_dynamics

# One state, and what M, C, g and V read there. Hand-checked for the shipped
# 2R arm and pinned so a rebuild of the symbolic construction — the move onto
# sympy.physics.mechanics was one — has to produce the same equations, not
# merely equations with the same properties. Replace these with your own
# mechanism's numbers, from a source that is not this file.
PINNED_Q = (0.3, -0.4)
PINNED_QD = (0.7, 1.1)
PINNED = {
    "M": [[0.1847636596401731, 0.04613182982008655],
          [0.04613182982008655, 0.0185]],
    "C": [[0.012850805296185468, 0.02102859048466713],
          [-0.00817778518848166, 0.0]],
    "g": [4.912276488633065, 0.9760990861377432],
    "V": 1.1196657737555127,
}


def test_pinned_sample(tol=1e-12):
    """M, C, g and V at one state, against the values pinned above."""
    got = {
        "M": np.asarray(M_num(*PINNED_Q), dtype=float),
        "C": np.asarray(C_num(*PINNED_Q, *PINNED_QD), dtype=float),
        "g": np.asarray(g_num(*PINNED_Q), dtype=float).flatten(),
        "V": np.asarray(V_num(*PINNED_Q), dtype=float).flatten(),
    }
    for name, want in PINNED.items():
        expected = np.asarray(want, dtype=float).flatten()
        assert np.allclose(got[name].flatten(), expected, atol=tol),             f"{name} at q={PINNED_Q} is {got[name]}, pinned value {want}"
    print("  [PASS] M, C, g and V match the pinned sample")


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

    RK45 at tight tolerances from a nonzero posture at rest, E(T) against
    E(0): one check that exercises the numeric M, C, g and V together.
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


def test_inverse_dynamics_vs_truth_model(n=24, seed=DEFAULT_SEED, tol=1e-9):
    """The mandatory Milestone 2 truth check: tau = M qdd + C qd + g against
    the truth model's inverse dynamics, at sampled states.

    This is the check that makes the dynamics *right*, as against
    self-consistent. Everything else in this file holds M, C and g against each
    other or against a property every correct Lagrangian has, and a term
    missing from T or V is missing from both sides of all of them. MuJoCo's
    recursive inverse dynamics never saw T, V or this file, so a missing term
    shows up here as a torque that does not match.

    Sampled *states*, not postures: at rest C multiplies zero and the whole
    Coriolis matrix goes unexercised. Velocity and acceleration come from the
    rate envelope in the parameter block, both signs.
    """
    model, data = build()
    Q, QD, QDD = sample_states(n, seed)
    worst, worst_at = 0.0, None
    for qv, qdv, qddv in zip(Q, QD, QDD):
        Mn = np.asarray(M_num(*qv), dtype=float)
        Cn = np.asarray(C_num(*qv, *qdv), dtype=float)
        gn = np.asarray(g_num(*qv), dtype=float).flatten()
        tau_model = Mn @ qddv + Cn @ qdv + gn
        tau_truth = inverse_dynamics(model, data, qv, qdv, qddv)
        gap = float(np.max(np.abs(tau_model - tau_truth)))
        if gap > worst:
            worst, worst_at = gap, (qv, qdv)
        assert gap < tol, (
            f"tau = M qdd + C qd + g reads {tau_model} where the truth model's "
            f"inverse dynamics reads {tau_truth} at q={qv}, qd={qdv}, "
            f"qdd={qddv}")
    print(f"  [PASS] tau matches the truth model's inverse dynamics over {n} "
          f"sampled states (seed {seed})")
    print(f"         worst |dtau| {worst:.2e} N m, at q = "
          f"{np.round(worst_at[0], 4)}, qd = {np.round(worst_at[1], 4)}")
