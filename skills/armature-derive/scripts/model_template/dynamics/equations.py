"""
dynamics/equations.py — 02_dynamics.md §1–2: T, V, and M(q) q̈ + C q̇ + g = τ.

Formed by the engine, `armature.equations` (ADR 0012), on the description's
own frames: the symbolic view's bodies, each a RigidBody on its frame, COM,
mass and inertia dyadic, with gravity, handed to Kane's method with every
generalized speed set to q̇, so M is Lagrange's M. The view's closures are its
holonomic constraints, and joint springs and elastic cables are carried. The
angular velocities, the partial velocities and the velocity products are the
method's to compute: written out by hand, they are where an ω sign or a
dropped Coriolis term hides behind arithmetic that still reproduces. Nothing
here simplifies; `report_results.py` simplifies what it prints.

This module adds what only this machine has. The view carries no rotors, so a
geared actuator's reflected N²J is added to M here. V is the note's potential,
which the engine does not return: here gravity's, and a spring the mechanism
has joins it, ½ k (q − rest)², or the energy check drifts. C, the Christoffel
matrix, is formed only because this note uses it as a matrix (Ṁ − 2C is
skew); the truth check needs only C q̇.

That buys construction, not verification: these equations agree with
themselves whatever mechanism they describe. Whether they describe *this* one
is the truth model's inverse-dynamics check, and the checks one file over —
symmetry, skew-symmetry, energy conservation — are self-consistency only. The
truth model carries the rotors, and will say so if one is missing here.

Self-tests in equations_checks.py.
"""

import numpy as np
import sympy as sp
from sympy.physics.mechanics import dynamicsymbols

from mechanism import equations, numeric

EQ = equations()
VIEW = EQ.view
t = dynamicsymbols._t
# The generalized coordinates, the variant's, in order. On a closed chain M is
# over the independent ones, `EQ.independent`.
q = sp.Matrix([VIEW.q[n] for n in EQ.coordinates])
N = len(q)


def reflected_inertia():
    """N²J on each geared actuator's joint: its rotor turns N times as fast
    as the joint, so it adds ½ N²J q̇² to T. Zero for a direct drive."""
    R = sp.zeros(len(EQ.independent), len(EQ.independent))
    for a in VIEW.description.actuators:
        if not a.rotor_inertia:
            continue
        assert a.joint in EQ.independent, (
            f"{a.name} drives {a.joint}, a dependent coordinate; its rotor "
            f"reflects through the closures, and is the derivation's to write")
        i = EQ.independent.index(a.joint)
        R[i, i] += sp.sympify(a.gear) ** 2 * sp.sympify(a.rotor_inertia)
    return R


def potential_energy():
    """V, gravity's: each body's −m g·r_COM, from the base origin."""
    return sum(-VIEW.mass[b] * VIEW.gravity.dot(
        VIEW.com[b].pos_from(VIEW.origin)) for b in VIEW.frames)


print("Building symbolic dynamics ...")
M_SYM = EQ.M + reflected_inertia()
CQD_SYM, G_SYM, V_SYM = EQ.Cqd, EQ.g, potential_energy()
C_SYM = EQ.christoffel()
print("  Dynamics built.")

# --- numeric functions, lambdified, parameterized by params.PARAMS ---
M_num = numeric(M_SYM)
Cqd_num = numeric(CQD_SYM, rates=True)
C_num = numeric(C_SYM, rates=True)
Mdot_num = numeric(M_SYM.diff(t), rates=True)
g_num = numeric(G_SYM)
V_num = numeric(V_SYM)


# The stiffness of the gravity field, K = dg/dq: the matrix a small-oscillation
# mode actually comes from. Derived from g rather than separately derived,
# which is why it sits here rather than in a module of its own.
K_SYM = G_SYM.jacobian(q)
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
