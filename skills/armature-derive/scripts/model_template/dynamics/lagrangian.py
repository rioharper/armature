"""
dynamics/lagrangian.py — 02_dynamics.md §1–2: T, V, and M(q) q̈ + C q̇ + g = τ.

Built with `sympy.physics.mechanics`: reference frames turned off the DH table,
points placed and given velocities by the one- and two-point velocity theorems,
rigid bodies carrying mass and an inertia dyadic, and `LagrangesMethod` for the
equations. Two hand-rolled steps used to live here and no longer do — the
angular velocity read out of Ṙ Rᵀ, and the d/dt(∂L/∂q̇) − ∂L/∂q loop — because
each was a place a sign error or a missing Coriolis term could hide in a
derivation whose every printed number still reproduced.

That buys construction, not verification: these equations agree with themselves
whatever mechanism they describe. Whether they describe *this* one is the truth
model's inverse-dynamics check, and the checks one file over — symmetry,
skew-symmetry, energy conservation — are self-consistency only.

Self-tests in lagrangian_checks.py.
"""

import numpy as np
import sympy as sp
from sympy.physics.mechanics import (Lagrangian, LagrangesMethod, Point,
                                     ReferenceFrame, RigidBody, inertia)

from params import (COM_LOCAL, DH, GRAVITY_VEC, INERTIA, MASSES, N,
                    q, qd, qdd, QS, QDS, SUB_Q, SUB_P)


def link_frames():
    """The chain as mechanics frames and points, read off the DH table.

    Modified DH (Craig): frame {i} is frame {i-1} turned by alpha about its x,
    then by theta about the new z, with its origin a along the parent's x plus
    d along that same new z. Returns (base frame, base origin, [(frame, origin)
    per link]) with every velocity in the base frame already set.
    """
    base = ReferenceFrame("N")
    root = Point("O0")
    root.set_vel(base, 0)
    parent, origin, chain = base, root, []
    for i, (alpha, a, d, theta) in enumerate(DH):
        tilt = parent.orientnew(f"A{i + 1}", "Axis", (alpha, parent.x))
        frame = tilt.orientnew(f"F{i + 1}", "Axis", (theta, tilt.z))
        offset = a * parent.x + d * tilt.z
        point = origin.locatenew(f"O{i + 1}", offset)
        # One-point theory covers both joint types, so there is no branch on
        # the row to get wrong. For a revolute joint `offset` is constant in
        # the parent, the sliding term is zero, and this *is* the two-point
        # theorem; for a prismatic joint d carries q and the term is the slide.
        point.set_vel(parent, offset.dt(parent))
        point.v1pt_theory(origin, base, parent)
        chain.append((frame, point))
        parent, origin = frame, point
    return base, root, chain


def rigid_bodies(base, root, chain):
    """One RigidBody per link: COM, link frame, mass, inertia dyadic, weight.

    Gravity enters as each body's potential energy rather than as an applied
    force, so `V_SYM` below is the same object the Lagrangian was built from
    and the energy check cannot drift from the equations it checks.
    """
    gravity = sum((GRAVITY_VEC[k] * axis
                   for k, axis in enumerate((base.x, base.y, base.z))),
                  0 * base.x)
    bodies = []
    for i, (frame, joint) in enumerate(chain):
        c = COM_LOCAL[i]
        com = joint.locatenew(f"C{i + 1}",
                              c[0] * frame.x + c[1] * frame.y + c[2] * frame.z)
        com.v2pt_theory(joint, base, frame)   # the COM is fixed in its link
        J = INERTIA[i]
        dyadic = inertia(frame, J[0, 0], J[1, 1], J[2, 2],
                         J[0, 1], J[1, 2], J[0, 2])
        body = RigidBody(f"link{i + 1}", com, frame, MASSES[i], (dyadic, com))
        body.potential_energy = -MASSES[i] * gravity.dot(com.pos_from(root))
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
    base, root, chain = link_frames()
    bodies = rigid_bodies(base, root, chain)
    method = LagrangesMethod(Lagrangian(base, *bodies), list(q), frame=base)
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
M_num = sp.lambdify(QS, M_SYM.subs(SUB_Q).subs(SUB_P), "numpy")
C_num = sp.lambdify(QS + QDS, C_SYM.subs(SUB_Q).subs(SUB_P), "numpy")
g_num = sp.lambdify(QS, G_SYM.subs(SUB_Q).subs(SUB_P), "numpy")
V_num = sp.lambdify(QS, V_SYM.subs(SUB_Q).subs(SUB_P), "numpy")


def total_energy(q_vals, qd_vals):
    """Total mechanical energy E = KE + V [J] at a state."""
    Mn = np.asarray(M_num(*q_vals), dtype=float)
    ke = 0.5 * np.asarray(qd_vals) @ Mn @ np.asarray(qd_vals)
    pe = float(np.asarray(V_num(*q_vals), dtype=float))
    return ke + pe
