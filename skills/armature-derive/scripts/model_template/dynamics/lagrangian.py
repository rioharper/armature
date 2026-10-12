"""
dynamics/lagrangian.py — 02_dynamics.md §1–2: T, V, and M(q) q̈ + C q̇ + g = τ.

Built with `sympy.physics.mechanics` on the description's own frames: the
engine's symbolic view gives every body's ReferenceFrame, its COM as a Point
with its velocity already set, its mass, its inertia dyadic and gravity, all as
functions of the variant's coordinates. This module hangs a RigidBody on each
and hands the Lagrangian to `LagrangesMethod`. Two hand-rolled steps used to
live here and no longer do — the angular velocity read out of Ṙ Rᵀ, and the
d/dt(∂L/∂q̇) − ∂L/∂q loop — because each was a place a sign error or a missing
Coriolis term could hide in a derivation whose every printed number still
reproduced. The frames are not this module's either: it reads the view rather
than kinematics.py's matrices, so the two milestones share the description and
nothing else.

That buys construction, not verification: these equations agree with themselves
whatever mechanism they describe. Whether they describe *this* one is the truth
model's inverse-dynamics check, and the checks one file over — symmetry,
skew-symmetry, energy conservation — are self-consistency only. The view
carries no rotor inertia: a geared actuator's reflected N²J is the derivation's
to add to M, and the truth model, which does carry it, will say so if it is
missing.

Self-tests in lagrangian_checks.py.
"""

import numpy as np
import sympy as sp
from sympy.physics.mechanics import (Lagrangian, LagrangesMethod, RigidBody,
                                     dynamicsymbols)

from mechanism import numeric, view

VIEW = view()
t = dynamicsymbols._t
# The generalized coordinates, the variant's, in order; and their rates.
q = sp.Matrix(list(VIEW.q.values()))
qd = q.diff(t)
qdd = qd.diff(t)
N = len(q)


def rigid_bodies():
    """One RigidBody per body of the view: COM, frame, mass, inertia dyadic
    about the COM, and its weight.

    Gravity enters as each body's potential energy rather than as an applied
    force, so `V_SYM` below is the same object the Lagrangian was built from
    and the energy check cannot drift from the equations it checks.
    """
    bodies = []
    for name, frame in VIEW.frames.items():
        com = VIEW.com[name]
        body = RigidBody(name, com, frame, VIEW.mass[name],
                         (VIEW.inertia[name], com))
        body.potential_energy = -VIEW.mass[name] * VIEW.gravity.dot(
            com.pos_from(VIEW.origin))
        bodies.append(body)
    return bodies


def lagrangian_dynamics():
    """Returns (M, C, gvec, V) with tau = M qdd + C qd + gvec.

    C is the Christoffel form, the one the skew-symmetry check needs. V is
    returned so energy is checked as KE + V directly, not through a work
    integral. M, C and gvec are read back out of the equations of motion rather
    than assembled, so what is checked downstream is what Lagrange's method
    produced.
    """
    bodies = rigid_bodies()
    method = LagrangesMethod(Lagrangian(VIEW.world, *bodies), list(q),
                             frame=VIEW.world)
    eqs = sp.expand(sp.trigsimp(method.form_lagranges_equations()))

    M = eqs.jacobian(qdd)
    gvec = eqs.subs([(v, 0) for v in qdd]).subs([(v, 0) for v in qd])
    Cqd = sp.simplify(eqs - M * qdd - gvec)   # Coriolis+centrifugal * qd
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
        "Christoffel C inconsistent with the equations of motion"
    V = sp.simplify(sum(body.potential_energy for body in bodies))
    return sp.simplify(M), Cmat, sp.simplify(gvec), V


print("Building symbolic dynamics ...")
M_SYM, C_SYM, G_SYM, V_SYM = lagrangian_dynamics()
print("  Dynamics built.")

# --- numeric functions, lambdified, parameterized by params.PARAMS ---
M_num = numeric(M_SYM)
C_num = numeric(C_SYM, rates=True)
g_num = numeric(G_SYM)
V_num = numeric(V_SYM)


# The stiffness of the gravity field, K = dg/dq: the matrix a small-oscillation
# mode actually comes from. Derived from g rather than separately derived,
# which is why it sits here rather than in a module of its own.
K_SYM = sp.simplify(G_SYM.jacobian(q))
K_num = numeric(K_SYM)


def small_oscillation_modes(q_vals):
    """Mode frequencies [Hz] about `q_vals`, held in equilibrium.

    Eigenvalues of (K, M), **not** the diagonal of K. An entry K_ii is the
    stiffness felt by coordinate i moving alone; a mode is a shape the whole
    mechanism moves in, and the two coincide only when M and K are both
    diagonal. Signed, so a divergent configuration reads negative instead of
    producing a plausible-looking frequency.
    """
    from scipy.linalg import eigh
    lam = eigh(np.asarray(K_num(*q_vals), dtype=float),
               np.asarray(M_num(*q_vals), dtype=float), eigvals_only=True)
    return np.sign(lam) * np.sqrt(np.abs(lam)) / (2 * np.pi)


def total_energy(q_vals, qd_vals):
    """Total mechanical energy E = KE + V [J] at a state."""
    Mn = np.asarray(M_num(*q_vals), dtype=float)
    ke = 0.5 * np.asarray(qd_vals) @ Mn @ np.asarray(qd_vals)
    pe = float(np.asarray(V_num(*q_vals), dtype=float))
    return ke + pe
