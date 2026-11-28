"""The closure basis G = ∂q/∂q_ind, on both sides (#190, #191).

Answer: the compiled model's own completion. `at(q, qd)` solves the dependent
rates so the loops stay closed, so G times the independent rates is every
dof's rate; a central difference of `at(q)`'s dependent coordinates is G's
dependent rows; and the symbolic G, from the view's closures alone, is the
truth model's at the same posture and `equations(...).basis`.
Trap: a dof Jacobian's SVD on a closed chain, which treats the dependent
joints as free and so is the open chain's, not the mechanism's.
"""

import dataclasses

import numpy as np
import pytest
import sympy as sp

import armature
from armature import body, joint
from test_fixture_five_bar import PARAMS, five_bar

SEED = 20261127


@pytest.fixture(scope="module")
def m():
    return armature.compile(five_bar, PARAMS)


def floating_five_bar(p):
    """The five-bar with its ground pivots on a base that floats."""
    out = [body("base", mass=1.0, com=(0, 0, 0), inertia=np.diag([1e-2] * 3)),
           joint("float", "free", parent="world", child="base",
                 point=(0, 0, 0))]
    for e in five_bar(p):
        if getattr(e, "parent", None) == "world" and e.kind == "hinge":
            e = dataclasses.replace(e, parent="base")
        out.append(e)
    return out


def test_g_times_the_independent_rates_is_every_rate(m):
    for s in armature.sample_states(m, 6, SEED, qd_limits={"A": 2, "E": 2},
                                    qdd_limits={"A": 0, "E": 0}):
        b = s.closure_basis()
        assert b.independent == ("A", "E") and b.dependent == ("B", "D")
        rates = np.array([s.qd[d] for d in b.independent])
        assert b.G @ rates == pytest.approx(
            [s.qd[d] for d in b.coordinates], abs=1e-9)


def test_g_is_the_derivative_of_the_closed_posture(m):
    h = 1e-6
    for s in armature.sample(m, 4, SEED):
        b, at = s.closure_basis(), {n: s.q[n] for n in m.independent}
        for k, n in enumerate(b.independent):
            up, down = (m.at(q={**at, n: at[n] + d}).q for d in (h, -h))
            column = [(up[c] - down[c]) / (2 * h) for c in b.coordinates]
            assert b.G[:, k] == pytest.approx(column, abs=1e-6)


def test_the_reduced_jacobian_is_the_tools_velocity_per_independent_rate(m):
    """J @ G against the site's velocity at a unit rate of each independent
    dof, which `at` closes itself: the reduced Jacobian is the mechanism's,
    and the dof Jacobian alone is not."""
    for s in armature.sample(m, 4, SEED):
        jac, b = s.jacobian("C2"), s.closure_basis()
        reduced = jac.linear @ b.G
        at = {n: s.q[n] for n in m.independent}
        for k, d in enumerate(b.independent):
            moving = m.at(q=at, qd={d: 1.0})
            rates = np.array([moving.qd[c] for c in b.coordinates])
            assert reduced[:, k] == pytest.approx(jac.linear @ rates,
                                                  abs=1e-9)
        assert jac.linear.shape[1] == 4 and reduced.shape[1] == 2


def test_an_open_chain_basis_is_the_identity():
    from golden import arm_2r
    arm = armature.compile(arm_2r.mechanism, arm_2r.PARAMS)
    s = next(iter(armature.sample(arm, 1, SEED)))
    b = s.closure_basis()
    assert b.dependent == () and b.independent == b.coordinates
    assert np.array_equal(b.G, np.eye(len(b.coordinates)))


def test_the_symbolic_basis_is_the_truth_models_and_the_equations(m):
    sym = armature.closure_basis(five_bar, PARAMS)
    view = armature.symbolic(five_bar, PARAMS)
    assert (sym.independent, sym.dependent) == (("A", "E"), ("B", "D"))
    g = armature.numeric(view, sym.G, PARAMS)
    for s in armature.sample(m, 4, SEED):
        got = np.asarray(g(*(s.q[n] for n in sym.coordinates)), dtype=float)
        assert got == pytest.approx(s.closure_basis().G, abs=1e-9)
    e = armature.equations(five_bar, PARAMS)
    assert sp.simplify(e.basis - sym.G) == sp.zeros(4, 2)


def test_numeric_off_the_view_is_the_equations(m):
    e = armature.equations(five_bar, PARAMS, bands=("kB",))
    view = armature.symbolic(five_bar, PARAMS)
    off_view = armature.numeric(view, e.g, PARAMS, bands=("kB",))
    on_eqs = e.numeric(e.g)
    s = next(iter(armature.sample(m, 1, SEED)))
    q = [s.q[n] for n in e.coordinates]
    assert np.ravel(off_view(*q, kB=3.0)) == pytest.approx(
        np.ravel(on_eqs(*q, kB=3.0)), abs=1e-12)
    with pytest.raises(TypeError, match="no band"):
        off_view(*q, m_l1=1.0)


def test_on_a_floating_base_g_is_in_the_views_rates():
    """A view state's G maps the view's independent rates, the turns'
    included, to every view rate: against `at(view=True)`'s own completion,
    read back in the view's coordinates by the dofs' V."""
    fm = armature.compile(floating_five_bar, PARAMS)
    sym = armature.closure_basis(floating_five_bar, PARAMS)
    view = armature.symbolic(floating_five_bar, PARAMS)
    g = armature.numeric(view, sym.G, PARAMS)
    rng = np.random.default_rng(SEED)
    q = {n: v for n, v in zip(
        ("float:x", "float:y", "float:z", "float:rx", "float:ry", "float:rz",
         "A", "E"), [*rng.uniform(-0.1, 0.1, 3), *rng.uniform(-0.4, 0.4, 3),
                     *rng.uniform(-0.3, 0.3, 2)])}
    s = fm.at(q=q, view=True)
    b = s.closure_basis()
    assert set(b.dependent) == {"B", "D"}
    full = {**q, **{n: s.q[n] for n in ("B", "D")}}
    got = np.asarray(g(*(full[n] for n in sym.coordinates)), dtype=float)
    order = [b.coordinates.index(n) for n in sym.coordinates]
    columns = [b.independent.index(n) for n in sym.independent]
    assert got == pytest.approx(b.G[np.ix_(order, columns)], abs=1e-9)

