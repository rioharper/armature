"""MuJoCo's M, C q̇ and g at a state, for the `equations` cells (ADR 0012).

The independent computation is MuJoCo's own: `State.inverse` assembles
M q̈ + bias − passive from `mj_fullM`, `qfrc_bias` and `qfrc_passive`, with
the dependent accelerations solved from the closures. On a closed chain both
sides are projected onto the independent dofs by G, the dofs' motion per unit
of the independent ones, from MuJoCo's own closure Jacobians. MuJoCo's M
carries each actuator's reflected rotor inertia as the dof's armature, which
the equations leave to the derivation, so it is taken off.
"""

import numpy as np

import armature
from armature.assembly import tangent


def reduced(state):
    """(M, C q̇ + g) of `state`'s compiled model there, over its
    independent dofs."""
    compiled = state.compiled
    model = compiled.model
    with state._scratch() as data:
        turned = tangent(compiled, data)[0]
        if compiled.closure:
            _, jac = compiled.closure.rows(data)
            basis = compiled.closure.basis(jac @ turned)
        else:
            basis = np.eye(model.nv)
    independent = ([compiled.dofs[k] for k in compiled.closure.independent_dofs]
                   if compiled.closure else compiled.dofs)
    rest = np.array(list(state.inverse().generalised.values()))
    columns = []
    for d in independent:
        moved = np.array(list(state.inverse(qdd={d: 1.0})
                              .generalised.values()))
        columns.append(moved - rest)
    mass = basis.T @ np.array(columns).T - basis.T @ np.diag(
        model.dof_armature) @ basis
    return mass, basis.T @ rest


def sampled(compiled, n, seed, rate=2.0):
    """`n` states of `compiled` from `sample_states`, every independent dof's
    rate and acceleration within ±`rate`."""
    limits = {d: rate for d in compiled.independent}
    return armature.sample_states(compiled, n, seed, qd_limits=limits,
                                  qdd_limits=limits)


def assert_agree(equations, states, tol=1e-9):
    """`equations`' M and C q̇ + g are MuJoCo's at each of `states`."""
    e = equations
    mass, bias = e.numeric(e.M), e.numeric(e.Cqd + e.g, rates=True)
    for s in states:
        q = [s.q[n] for n in e.coordinates]
        qd = [s.qd[n] for n in e.coordinates]
        want_m, want_b = reduced(s)
        got_m = np.asarray(mass(*q), dtype=float)
        got_b = np.ravel(bias(*q, *qd))
        assert np.max(np.abs(got_m - want_m)) < tol, (s.q, got_m, want_m)
        assert np.max(np.abs(got_b - want_b)) < tol, (s.q, got_b, want_b)
