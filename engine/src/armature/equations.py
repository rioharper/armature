"""The equations of motion of a description or a variant, formed once, in the
engine (ADR 0012).

`equations(variant, params)` hangs a `RigidBody` on each of the symbolic
view's frames and hands them to a `sympy.physics.mechanics` `System`, Kane's
method, with each generalized speed u set to its coordinate's rate q̇, so the
mass matrix is Lagrange's. The view's closures (loops, couples, rigid cables)
are its holonomic constraints; joint springs are torques (a hinge) or forces
(a slide) on their coordinate, and elastic cables `LinearSpring`s between
their end sites, read from the description as the truth model reads them.
An elastic cable is taut here: its deadband, the slack the truth model
leaves unpulled, is not symbolic.

On a closed chain the equations are reduced onto the independent
coordinates, chosen as the compiled model chooses them: u = G u_i, with
u̇_dep solved from the closures' second derivative, so

    M q̈_i + C q̇ + g = Gᵀ τ,

M square over the independent coordinates, and C q̇ and g functions of every
coordinate and the independent rates. The constraint forces drop out.

Nothing here simplifies: simplification in the build path was what timed
the template's Lagrangian out at four links. Rotor inertia is the derivation's to
add, and actuator torques are the generalized-force side. A rigid contact is
a one-sided constraint, its force on that side with τ, and `contacts` names
each one left there; a compliant contact is a spring the equations do not
carry, so it raises.
"""

from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np
import sympy as sp
from sympy.physics.mechanics import (LinearPathway, LinearSpring, Point,
                                     RigidBody, System, dynamicsymbols)

from .assembly import RANK_TOL
from .compiler import compile
from .description import compliant_contacts, rigid_cables
from .elements import WORLD
from .symbolic import symbolic

t = dynamicsymbols._t


@dataclass(frozen=True, eq=False)
class Equations:
    """M q̈ + C q̇ + g = τ, in the view's coordinates.

    `M`, `Cqd` (the velocity-product vector) and `g` (gravity and springs)
    are SymPy matrices over the `independent` coordinates, in their order;
    on an open chain those are all of `coordinates`. They are written in the
    view's coordinate functions and their rates. `contacts` names the rigid
    contacts whose forces sit with τ. `view` is the symbolic view they were
    formed on.
    """
    view: object
    coordinates: tuple
    independent: tuple
    dependent: tuple
    M: sp.Matrix
    Cqd: sp.Matrix
    g: sp.Matrix
    contacts: tuple
    _params: MappingProxyType
    _bands: tuple
    _basis: sp.Matrix  # ∂q/∂q_i, every coordinate by the independent ones
    _christoffel: list = field(default_factory=list, init=False, repr=False)

    def numeric(self, expr, rates=False):
        """`expr`, written in the view's coordinates (and their rates), as a
        NumPy function of every coordinate's value in `coordinates` order,
        then every rate's when `rates`, with the parameters substituted. A
        parameter named in the bands stays a keyword, at its nominal unless
        given: `g_num(*q, m2=0.88)`. An unknown keyword raises `TypeError`."""
        view, bands = self.view, self._bands
        qs = sp.symbols(f"x0:{len(self.coordinates)}")
        vs = sp.symbols(f"v0:{len(self.coordinates)}")
        coordinates = list(view.q.values())
        swap = {**{c.diff(t): v for c, v in zip(coordinates, vs)},
                **{c: x for c, x in zip(coordinates, qs)},
                **view.numbers({k: x for k, x in self._params.items()
                                if k not in bands})}
        f = sp.lambdify(list(qs + vs if rates else qs)
                        + [view.params[k] for k in bands],
                        sp.sympify(expr).xreplace(swap), "numpy", cse=True)
        nominal = [self._params[k] for k in bands]

        def at(*x, **band):
            unknown = sorted(set(band) - set(bands))
            if unknown:
                raise TypeError(f"{unknown} have no band; the banded "
                                f"parameters are {sorted(bands)}")
            return f(*x, *(band.get(k, v) for k, v in zip(bands, nominal)))
        return at

    def christoffel(self):
        """C, the Christoffel matrix with C q̇ the velocity-product vector,
        over the independent coordinates: formed on the first call only. On
        a closed chain each ∂/∂q_i is the total derivative along the
        closures."""
        if not self._christoffel:
            view = self.view
            q = list(view.q.values())
            ind = [view.q[n] for n in self.independent]
            rates = [c.diff(t) for c in ind]

            n, M = len(ind), self.M
            partial = [M.diff(c) for c in q]
            # dM/dq_i along the closures: Σ_k ∂M/∂q_k ∂q_k/∂q_i
            dM = [sum((partial[k] * self._basis[k, i] for k in range(len(q))
                       if self._basis[k, i] != 0), sp.zeros(n, n))
                  for i in range(n)]
            self._christoffel.append(sp.Matrix(n, n, lambda k, j: sum(
                (sp.Rational(1, 2) * (dM[i][k, j] + dM[j][k, i]
                                      - dM[k][i, j]) * rates[i]
                 for i in range(n)), sp.S.Zero)))
        return self._christoffel[0]


def equations(mechanism, params, bands=()):
    """The equations of motion of `mechanism` (or a variant) as an
    `Equations`, the parameters' symbols those of `armature.symbolic`, and
    `bands` the parameters `numeric` keeps as keywords (a mapping's keys or
    names)."""
    view = symbolic(mechanism, params)
    d = view.description
    soft = sorted(compliant_contacts(d))
    if soft:
        raise ValueError(f"contact {soft[0]!r} is compliant: a spring the "
                         f"equations do not carry. A variant that makes it "
                         f"rigid, `rigid({soft[0]!r}, assumption=...)`, puts "
                         f"its force with τ")
    dependent = compile(mechanism, params).dependent if _closed(d) else ()
    names = view.coordinates
    independent = tuple(n for n in names if n not in dependent)
    q = {n: view.q[n] for n in names}
    u = {n: sp.Function(f"u_{n}")(t) for n in names}

    system = System(view.world, view.origin)
    system.add_coordinates(*(q[n] for n in independent))
    system.add_speeds(*(u[n] for n in independent))
    if dependent:
        system.add_coordinates(*(q[n] for n in dependent), independent=False)
        system.add_speeds(*(u[n] for n in dependent), independent=False)
        system.add_holonomic_constraints(*_closures(view, params, dependent))
    system.add_kdes(*(u[n] - q[n].diff(t) for n in names))
    for name, frame in view.frames.items():
        com = view.com[name]
        system.add_bodies(RigidBody(name, com, frame, view.mass[name],
                                    (view.inertia[name], com)))
    system.apply_uniform_gravity(view.gravity)
    system.add_loads(*_springs(view))
    system.form_eoms(explicit_kinematics=True)

    rates = {u[n]: q[n].diff(t) for n in names}
    mass, forcing = system.mass_matrix, system.forcing
    p, m = len(independent), len(dependent)
    if m:
        # The top rows are Gᵀ(M u̇ + ...), the bottom the closures' second
        # derivative, A u̇ + b = 0: u̇_dep = −A_d⁻¹ (A_i u̇_i + b).
        a = mass[p:, :]
        solved = a[:, p:].LUsolve(a[:, :p].row_join(-forcing[p:, :]))
        top = mass[:p, :]
        basis = sp.eye(p).col_join(-solved[:, :p])
        M = top * basis
        bias = top[:, p:] * -solved[:, p:] - forcing[:p, :]
        ind_rates = sp.Matrix([u[n] for n in independent])
        dep_rates = dict(zip((u[n] for n in dependent),
                             -solved[:, :p] * ind_rates))
        bias = bias.xreplace(dep_rates)
    else:
        M, bias, basis = mass, -forcing, sp.eye(p)
    g = bias.xreplace({v: 0 for v in u.values()})
    Cqd = (bias - g).xreplace(rates)
    rows = dict(zip((*independent, *dependent), basis.tolist()))
    basis = sp.Matrix([rows[n] for n in names])
    return Equations(view, names, independent, tuple(dependent),
                     M.xreplace(rates), Cqd, g.xreplace(rates),
                     tuple(c.name for c in d.contacts),
                     MappingProxyType(dict(params)), tuple(bands),
                     basis.xreplace(rates))


def _closed(d):
    return bool(d.loops or d.couples or rigid_cables(d))


def _closures(view, params, dependent):
    """The view's closures as scalars, a loop's gap one row per world
    component, keeping rows until they carry the closures' rank on the
    dependent coordinates at home. A planar loop's gap across its plane is
    zero at every posture, so it is never kept."""
    rows = []
    for closure in view.closures.values():
        if isinstance(closure, sp.Expr):
            rows.append(closure)
        else:
            rows.extend(closure.to_matrix(view.world))
    home = _home(view)
    numbers = {**view.numbers(params), **home}
    dep = [view.q[n] for n in dependent]
    kept, jacobian = [], np.zeros((0, len(dep)))
    for row in rows:
        trial = np.vstack([jacobian, [float(row.diff(c).xreplace(
            {k.diff(t): 0 for k in view.q.values()}).xreplace(numbers))
            for c in dep]])
        if _rank(trial) > len(kept):
            kept.append(row)
            jacobian = trial
        if len(kept) == len(dep):
            break
    if len(kept) < len(dep):
        raise ValueError(f"the closures carry rank {len(kept)} on the "
                         f"dependent coordinates {list(dependent)} at home; "
                         f"the compiled model chose {len(dep)}")
    return kept


def _home(view):
    """Each coordinate's value at home: a hinge's or a slide's `home`, a
    floating body's point where the description places it, its turns 0."""
    homes = {}
    joints = {j.name: j for j in view.description.joints}
    for name, c in view.q.items():
        joint, _, component = name.partition(":")
        j = joints[joint]
        if not component:
            homes[c] = sp.sympify(j.home)
        elif component in "xyz":
            homes[c] = sp.sympify(j.point["xyz".index(component)])
        else:
            homes[c] = sp.S.Zero
    return homes


def _rank(matrix):
    s = np.linalg.svd(matrix, compute_uv=False)
    return int(np.sum(s > RANK_TOL * max(s.max(initial=0.0), 1.0)))


def _springs(view):
    """The loads of the springs: each joint spring's −k (q − rest) on its
    coordinate alone, as a torque pair across a hinge or a force pair across
    a slide, at the child's COM and the parent's point there; and each
    elastic cable's `LinearSpring` of EA/L between its end sites."""
    d = view.description
    loads = []
    for j in d.joints:
        if j.stiffness is None or j.name not in view.q:
            continue
        if j.kind == "free":
            raise ValueError(f"joint {j.name!r}: a free joint's spring is "
                             f"not one the equations carry")
        rest = sp.sympify(j.home if j.rest is None else j.rest)
        load = (-sp.sympify(j.stiffness) * (view.q[j.name] - rest)
                * view.axes[j.name])
        parent = view.world if j.parent == WORLD else view.frames[j.parent]
        if j.kind == "hinge":
            loads += [(view.frames[j.child], load), (parent, -load)]
            continue
        com, anchor = view.com[j.child], view.anchors[j.name]
        there = Point(f"{j.name}_on_{j.parent}")
        there.set_pos(anchor, com.pos_from(anchor))
        there.v2pt_theory(anchor, view.world, parent)
        loads += [(com, load), (there, -load)]
    rigid = {c.name for c in rigid_cables(d)}
    for c in d.cables:
        if c.name in rigid:
            continue
        rest = sp.sympify(c.rest_length)
        pathway = LinearPathway(view.sites[f"{c.name}:start"],
                                view.sites[f"{c.name}:end"])
        loads += LinearSpring(sp.sympify(c.ea) / rest, pathway,
                              rest).to_loads()
    return loads
