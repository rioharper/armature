"""
dynamics/lagrangian_checks.py — self-tests for lagrangian.py, 02_dynamics.md §1–2.

Every check here but three is **self-consistency**: it holds M, C, g and V
against each other and against properties any correct Lagrangian has, using no
model but this one. That is exactly what a wrong assumption survives, since the
assumption sits on both sides of the comparison. The two truth checks — the
inverse dynamics and the modes — hold the equations against the truth model,
and the closed form holds them against a book's, computed from the same ledger
entries; keep the rest for what they are good at, which is catching an
arithmetic slip the moment it lands.
"""

import numpy as np
import sympy as sp

import armature
from armature.sampler import DEFAULT_SEED

from dynamics.lagrangian import (M_SYM, C_SYM, K_num, M_num, C_num, N, g_num,
                                 V_num, q, small_oscillation_modes, t,
                                 total_energy)
from mechanism import derived, named, truth, vector
from params import PARAMS, QDD_LIMITS, QD_LIMITS

# The configuration whose modes 02_dynamics.md quotes, and the rank the note
# claims the gravity stiffness has there. Both are claims; both are checked.
HANGING = (-np.pi / 2, 0.0)
STIFFNESS_RANK = 2

# What the small-oscillation form is a theorem about, named once so the truth
# check can hand it over when the comparison fails. Most wrong mode frequencies
# are not wrong by arithmetic; they are exactly right about a different
# mechanism — a taut-cable pendulum mode on a cable that goes slack, a bifilar
# yaw stiffness on cables that converge rather than hang parallel.
MODES_ASSUME = (
    "an equilibrium at this configuration and displacements small enough that "
    "K = dg/dq is constant over them; away from equilibrium the constant term "
    "of g moves the mechanism instead of restoring it, and a large-amplitude "
    "swing is a different frequency")

# What the closed form below is a theorem about, named once so its check can
# hand it over when the comparison fails.
ELBOW_ASSUME = (
    "a planar two-link chain, both joints about base z, the elbow angle "
    "measured from link 1, each COM on its link's line, and gravity along -y")


def closed_form(qv, qdv, p=PARAMS):
    """M, C, g and V of the planar elbow manipulator, from the ledger's
    numbers by the textbook route (Spong, Hutchinson and Vidyasagar, *Robot
    Modeling and Control*, 1st ed., ch. 7, the planar elbow manipulator), in
    the Christoffel form of C. It shares nothing with lagrangian.py but the
    ledger, so a rebuild of the symbolic construction has to produce the same
    equations, and an edit to an entry moves both sides at once."""
    l1, lc1, lc2 = p["l1"], p["lc1"], p["lc2"]
    m1, m2, grav = p["m1"], p["m2"], p["g"]
    i1, i2 = np.asarray(p["I1"])[2, 2], np.asarray(p["I2"])[2, 2]
    c2, s2 = np.cos(qv[1]), np.sin(qv[1])
    m12 = m2 * (lc2 ** 2 + l1 * lc2 * c2) + i2
    M = np.array([[m1 * lc1 ** 2 + i1 + m2 * (l1 ** 2 + lc2 ** 2
                                              + 2 * l1 * lc2 * c2) + i2, m12],
                  [m12, m2 * lc2 ** 2 + i2]])
    h = -m2 * l1 * lc2 * s2
    C = np.array([[h * qdv[1], h * (qdv[0] + qdv[1])], [-h * qdv[0], 0]])
    arm1, arm2 = (m1 * lc1 + m2 * l1) * grav, m2 * lc2 * grav
    g = np.array([arm1 * np.cos(qv[0]) + arm2 * np.cos(qv[0] + qv[1]),
                  arm2 * np.cos(qv[0] + qv[1])])
    V = arm1 * np.sin(qv[0]) + arm2 * np.sin(qv[0] + qv[1])
    return {"M": M, "C": C, "g": g, "V": np.array([V])}


def test_coordinates_match_the_variant():
    """The coordinates LagrangesMethod was given are the variant's, by name:
    a coordinate leaves these equations only through a reduction in DERIVED,
    never by being left out of the list. `armature.account` names any
    coordinate at fault."""
    armature.account(derived(), list(q))
    print(f"  [PASS] the equations are in the variant's coordinates "
          f"{list(derived().coordinates)}")


def test_closed_form(n=8, seed=DEFAULT_SEED, tol=1e-12, p=PARAMS):
    """M, C, g and V at sampled states, against `closed_form`: the expected
    values are computed from the ledger by a second route, never pinned from
    this model's output (the standards, *A check's expected value*)."""
    samples = armature.sample_states(truth(), n, seed, qd_limits=QD_LIMITS,
                                     qdd_limits=QDD_LIMITS)
    for s in samples:
        qv, qdv = vector(s.q), vector(s.qd)
        got = {
            "M": np.asarray(M_num(*qv), dtype=float),
            "C": np.asarray(C_num(*qv, *qdv), dtype=float),
            "g": np.asarray(g_num(*qv), dtype=float).flatten(),
            "V": np.asarray(V_num(*qv), dtype=float).flatten(),
        }
        for name, want in closed_form(qv, qdv, p).items():
            assert np.allclose(got[name], want, atol=tol), (
                f"{name} at q={qv}, qd={qdv} is {got[name]}, the closed form "
                f"{want}. The form assumes {ELBOW_ASSUME}")
    print(f"  [PASS] M, C, g and V match the planar elbow's closed form over "
          f"{samples}")


def test_mass_matrix_properties(trials=5, seed=DEFAULT_SEED, tol=1e-9):
    """Postures from the engine's sampler, like every other check's, so "over
    the envelope" is one set of configurations across the model."""
    for s in armature.sample(truth(), trials, seed):
        Mn = np.asarray(M_num(*vector(s.q)), dtype=float)
        assert np.allclose(Mn, Mn.T, atol=tol), "M not symmetric"
        assert np.all(np.linalg.eigvalsh(Mn) > 0), "M not positive definite"
    print("  [PASS] M(q) symmetric positive-definite")


def test_skew_symmetry(tol=1e-8):
    """Mdot - 2C must be skew-symmetric (Christoffel C)."""
    Mdot = M_SYM.diff(t)
    S = sp.simplify(Mdot - 2 * C_SYM)
    assert sp.simplify(S + S.T) == sp.zeros(N, N), "Mdot-2C not skew"
    print("  [PASS] Mdot - 2C skew-symmetric")


def test_energy_conservation(T_end=2.0, seed=DEFAULT_SEED, tol_rel=1e-4):
    """Unforced, gravity-on dynamics conserve total mechanical energy.

    RK45 at tight tolerances from a sampled posture at rest, E(T) against
    E(0): one check that exercises the numeric M, C, g and V together. Sampled
    rather than the tidy posture this once started from — a posture on a
    symmetry plane releases into a planar swing that exercises fewer of the
    coupling terms than the machine ever will.
    """
    from scipy.integrate import solve_ivp

    def rhs(_t, s):
        qv, qdv = s[:N], s[N:]
        Mn = np.asarray(M_num(*qv), dtype=float)
        Cn = np.asarray(C_num(*qv, *qdv), dtype=float)
        gn = np.asarray(g_num(*qv), dtype=float).flatten()
        qddv = np.linalg.solve(Mn, -(Cn @ qdv) - gn)
        return np.concatenate([qdv, qddv])

    q0 = vector(armature.sample(truth(), 1, seed).states[0].q)
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


def test_truth_inverse_dynamics(n=24, seed=DEFAULT_SEED, tol=1e-9):
    """The mandatory Milestone 2 truth check: tau = M qdd + C qd + g against
    the truth model's inverse dynamics, `s.inverse(qdd)`, at sampled states.

    This is the check that makes the dynamics *right*, as against
    self-consistent. Everything else in this file holds M, C and g against each
    other or against a property every correct Lagrangian has, and a term
    missing from T or V is missing from both sides of all of them. The engine's
    explicit solve never saw T, V or this file — it reads MuJoCo's mass matrix
    and bias forces — so a missing term, or a rotor the derivation forgot to
    reflect, shows up here as a torque that does not match. `generalised` is
    the torque each coordinate needs, whatever its actuators' gearing.

    Sampled *states*, not postures: at rest C multiplies zero and the whole
    Coriolis matrix goes unexercised. Velocity and acceleration come from the
    rate envelope in the parameter block, both signs.
    """
    samples = armature.sample_states(truth(), n, seed, qd_limits=QD_LIMITS,
                                     qdd_limits=QDD_LIMITS)
    worst, worst_at = 0.0, None
    for s, accel in zip(samples, samples.qdd):
        qv, qdv, qddv = vector(s.q), vector(s.qd), vector(accel)
        Mn = np.asarray(M_num(*qv), dtype=float)
        Cn = np.asarray(C_num(*qv, *qdv), dtype=float)
        gn = np.asarray(g_num(*qv), dtype=float).flatten()
        tau_model = Mn @ qddv + Cn @ qdv + gn
        tau_truth = vector(s.inverse(qdd=accel).generalised)
        gap = float(np.max(np.abs(tau_model - tau_truth)))
        if gap > worst:
            worst, worst_at = gap, (qv, qdv)
        assert gap < tol, (
            f"tau = M qdd + C qd + g reads {tau_model} where the truth model's "
            f"inverse dynamics reads {tau_truth} at q={qv}, qd={qdv}, "
            f"qdd={qddv}")
    print(f"  [PASS] tau matches the truth model's inverse dynamics over "
          f"{samples}")
    print(f"         worst |dtau| {worst:.2e} N m, at q = "
          f"{np.round(worst_at[0], 4)}, qd = {np.round(worst_at[1], 4)}")


def test_stiffness_has_the_rank_the_note_claims(tol=1e-9):
    """K = dg/dq at the hanging configuration, and its rank.

    A rank the note assumes and never computes is the error that turns a
    stiffness matrix into modes it does not have: read a diagonal entry of a
    rank-deficient K as a mode and the number is plausible, dimensionally
    right, and about a motion the mechanism cannot make. Print the singular
    values, claim the rank, and check it.
    """
    K = np.asarray(K_num(*HANGING), dtype=float)
    svals = np.linalg.svd(K, compute_uv=False)
    rank = int(np.sum(svals > tol * max(svals[0], 1.0)))
    assert rank == STIFFNESS_RANK, (
        f"K at the hanging configuration has rank {rank}, not the "
        f"{STIFFNESS_RANK} the note claims; singular values {svals}")
    print(f"  [PASS] K has rank {rank}, singular values "
          f"{np.array2string(svals, precision=4)}")


def test_truth_modes(tol=1e-4):
    """The mandatory truth check for any mode the note cites: the analytic
    small-oscillation frequencies against the truth model's linearisation,
    `s.linearise()`.

    Nothing in this file's self-consistency checks constrains a mode. The
    engine linearises the truth model by central differences of MuJoCo's own
    inverse dynamics at the same configuration — springs and cables included,
    which a gradient of gravity alone reads as zero — having been told nothing
    about what the modes were meant to be, so a diagonal read as a mode, a mode
    named for a motion the mechanism cannot make, or a closed form used outside
    its assumptions all show up here as frequencies that do not match.

    Like the moment-arm form one submodule over, the small-oscillation form is
    a theorem about a class, and MODES_ASSUME names the class. Where the
    comparison fails, the failure hands that assumption over — because the
    number is almost never wrong by arithmetic, and almost always wrong by
    being about a different mechanism than this one.
    """
    lin = truth().at(q=named(HANGING)).linearise()
    analytic = small_oscillation_modes(HANGING)
    gap = float(np.max(np.abs(np.sort(analytic) - np.sort(lin.frequencies))))
    assert gap < tol, (
        f"modes at the hanging configuration read {np.sort(analytic)} Hz "
        f"where the truth model's linearisation reads "
        f"{np.sort(lin.frequencies)} Hz. The form assumes {MODES_ASSUME}")
    print(f"  [PASS] modes match the truth model's linearisation at the "
          f"hanging configuration (eps {lin.eps:g})")
    print(f"         {np.array2string(np.sort(analytic), precision=4)} Hz "
          f"analytic, worst |df| {gap:.2e} Hz")
