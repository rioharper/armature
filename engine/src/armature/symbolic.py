"""The derivation's view of a description: frames and points in SymPy.

The same `mechanism(p)` the truth model compiles is called with SymPy symbols
named after the parameters, so frames are written once and cannot drift. Each
body's frame is its parent's turned about (or slid along) its joint's home axis
by the coordinate's distance from home, parent to child: the product of
exponentials (Lynch and Park, ch. 4) written as a chain of frames. A locked
coordinate is turned by its locked value instead and drops out of the
coordinates.

A floating body is the chain its compiled variant uses: its point's position
along the base axes, then turns about the body's own axes in x, y, z order,
locked turns first. Its coordinates are the components left unlocked, named
`<joint>:x` to `<joint>:rz` like the compiled dofs. Where the truth model keeps
the free joint whole, its rates are the angular velocity instead of these
angles' rates; the two agree at home, and a state made with
`at(..., view=True)` answers in the view's.

The derivation hangs its own `RigidBody`s on these frames and points and runs
`LagrangesMethod` or `KanesMethod`; the view does not form equations.
"""

from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
import sympy as sp
from sympy.physics.mechanics import (Point, ReferenceFrame, dynamicsymbols,
                                     inertia)

from .description import describe, rigid_cables, tree_order
from .elements import FREE_COMPONENTS, WORLD


@dataclass(frozen=True, eq=False)
class Symbolic:
    """The symbolic view of a description or a variant.

    `q` maps each coordinate's name to its `dynamicsymbol`, in the order of
    the compiled model's dofs; `params` maps each parameter's name to its
    symbol. `world` and `origin` are the base frame and its origin. Per body:
    `frames`, `com` (a Point), `mass`, and `inertia`, the dyadic about the
    COM. Per coordinate: `axes` (a Vector). Per joint: `anchors` (a Point on
    the axis; a floating body's point). `sites` includes
    each cable's ends as `<cable>:start` and `<cable>:end`. `gravity` is a
    Vector. Every point's velocity in `world` is set. `closures` holds what
    each loop, couple and rigid cable keeps at zero: a loop's gap from its
    second site to its first (a Vector), a couple's q_a − home_a − ratio
    (q_b − home_b), keyed by its follower, and a rigid cable's length less
    its rest length. A variant's masses, COMs and dyadics are its lumped
    ones, exactly: a body lumped away has mass 0.

    A parameter whose value is a 3-vector is an array of three symbols,
    `<name>_x` to `<name>_z`, and one whose value is a 3×3 tensor a
    symmetric array of six, `<name>_xx` to `<name>_zz`, `_xy` standing for
    `_yx` too. `numbers(values)` is the substitution for every symbol.
    """
    description: object
    q: MappingProxyType
    params: MappingProxyType
    world: ReferenceFrame
    origin: Point
    frames: MappingProxyType
    com: MappingProxyType
    mass: MappingProxyType
    inertia: MappingProxyType
    axes: MappingProxyType
    anchors: MappingProxyType
    sites: MappingProxyType
    gravity: object
    closures: MappingProxyType

    @property
    def coordinates(self):
        return tuple(self.q)

    def numbers(self, values):
        """Each parameter symbol's number in `values`, a mapping keyed as
        the parameters are: what `.subs` takes. A vector's or a tensor's
        symbols take its elements."""
        numbers = {}
        for name, value in values.items():
            symbols = np.asarray(self.params[name], dtype=object)
            if symbols.shape != np.shape(value):
                raise ValueError(f"parameter {name!r} is shaped "
                                 f"{symbols.shape}; got {np.shape(value)}")
            if symbols.ndim == 2 and not np.allclose(value,
                                                     np.transpose(value)):
                raise ValueError(f"parameter {name!r} is a tensor and not "
                                 f"symmetric; its _xy stands for _yx")
            numbers.update(zip(symbols.ravel(),
                               np.ravel(value).astype(float).tolist()))
        return numbers


def symbolic(mechanism, params):
    """The symbolic view of `mechanism` (or a variant), with a real SymPy
    symbol for each key of `params`, or an array of them where its value is
    a vector or a tensor; the values are read for their shapes only."""
    symbols = {k: _symbols(k, np.shape(v)) for k, v in params.items()}
    d = describe(mechanism, symbols)
    world, origin = ReferenceFrame("world"), Point("origin")
    origin.set_vel(world, 0)

    joint_into = {j.child: j for j in d.joints}
    bodies = tree_order(d)
    q = {}
    for b in bodies:
        j = joint_into[b.name]
        names = ([f"{j.name}:{c}" for c in FREE_COMPONENTS]
                 if j.kind == "free" else [j.name])
        q.update({n: _coordinate(n) for n in names if n not in d.locks})
    frames, com, at = {WORLD: world}, {WORLD: origin}, {WORLD: (0, 0, 0)}
    axes, anchors = {}, {}
    for b in bodies:
        j = joint_into[b.name]
        if j.kind == "free":
            frames[b.name], anchors[j.name] = _floating(j, b, q, d.locks, world,
                                                        origin, axes)
            com[b.name] = anchors[j.name].locatenew(
                b.name, _vector(_minus(b.com, j.point), frames[b.name]))
            at[b.name] = b.com
            continue
        parent = frames[j.parent]
        lock = d.locks.get(j.name)
        moved = (lock.at if lock else q[j.name]) - sp.sympify(j.home)
        axis = _vector(j.axis, parent)
        anchor = com[j.parent].locatenew(j.name,
                                         _vector(_minus(j.point, at[j.parent]),
                                                 parent))
        frame = ReferenceFrame(b.name)
        if j.kind == "hinge":
            frame.orient_axis(parent, axis, moved)
            offset = _vector(_minus(b.com, j.point), frame)
        else:
            frame.orient_explicit(parent, sp.eye(3))
            offset = _vector(_minus(b.com, j.point), frame) + axis * moved
        frames[b.name] = frame
        com[b.name] = anchor.locatenew(b.name, offset)
        at[b.name] = b.com
        axes[j.name], anchors[j.name] = axis, anchor

    sites = {}
    for s in d.sites:
        sites[s.name] = _on(s.name, s.body, s.pos, frames, com, at)
    for c in d.cables:
        for label, (on, pos) in (("start", c.start), ("end", c.end)):
            name = f"{c.name}:{label}"
            sites[name] = _on(name, on, pos, frames, com, at)

    for point in [*com.values(), *anchors.values(), *sites.values()]:
        if point is not origin:
            point.set_vel(world, point.pos_from(origin).dt(world))

    closures = {loop.name: sites[loop.a].pos_from(sites[loop.b])
                for loop in d.loops}
    homes = {j.name: sp.sympify(j.home) for j in d.joints}
    for c in d.couples:
        closures[c.a] = (q[c.a] - homes[c.a]
                         - sp.sympify(c.ratio) * (q[c.b] - homes[c.b]))
    for c in rigid_cables(d):
        closures[c.name] = (sites[f"{c.name}:end"].pos_from(
            sites[f"{c.name}:start"]).magnitude() - sp.sympify(c.rest_length))

    tensors = {}
    for b in d.bodies:
        i = [[sp.sympify(v) for v in row] for row in b.inertia]
        tensors[b.name] = inertia(frames[b.name], i[0][0], i[1][1], i[2][2],
                                  i[0][1], i[1][2], i[2][0])
    del frames[WORLD], com[WORLD]
    return Symbolic(d, _ro(q), _ro(symbols), world, origin, _ro(frames),
                    _ro(com), _ro({b.name: sp.sympify(b.mass) for b in d.bodies}),
                    _ro(tensors), _ro(axes), _ro(anchors), _ro(sites),
                    _vector(d.gravity, world), _ro(closures))


def _floating(j, b, q, locks, world, origin, axes):
    """A floating body's frame and its moving point, built as its compiled
    chain: the point along the base axes, then the locked turns, then the
    free ones. Records each free component's axis in `axes`."""
    def value(c):
        name = f"{j.name}:{c}"
        return sp.sympify(locks[name].at) if name in locks else q[name]

    point = origin.locatenew(j.name, value("x") * world.x
                             + value("y") * world.y + value("z") * world.z)
    for c, u in zip("xyz", (world.x, world.y, world.z)):
        if f"{j.name}:{c}" not in locks:
            axes[f"{j.name}:{c}"] = u
    turns = [c for c in ("rx", "ry", "rz") if f"{j.name}:{c}" in locks]
    turns += [c for c in ("rx", "ry", "rz") if c not in turns]
    frame = world
    for k, c in enumerate(turns):
        last = k == len(turns) - 1
        turned = ReferenceFrame(b.name if last else f"{b.name}_{c}")
        axis = (frame.x, frame.y, frame.z)[("rx", "ry", "rz").index(c)]
        turned.orient_axis(frame, axis, value(c))
        if f"{j.name}:{c}" not in locks:
            axes[f"{j.name}:{c}"] = axis
        frame = turned
    return frame, point


def _symbols(name, shape):
    """Parameter `name`'s symbol, or its array of them for a 3-vector or a
    symmetric 3×3 tensor."""
    if shape == ():
        return sp.Symbol(name, real=True)
    if shape == (3,):
        return np.array([sp.Symbol(f"{name}_{c}", real=True) for c in "xyz"],
                        dtype=object)
    if shape == (3, 3):
        return np.array([[sp.Symbol(f"{name}_{''.join(sorted(a + b))}",
                                    real=True) for b in "xyz"] for a in "xyz"],
                        dtype=object)
    raise ValueError(f"parameter {name!r} is a number, a 3-vector or a 3×3 "
                     f"tensor; got shape {shape}")


def _coordinate(name):
    """A coordinate's dynamicsymbol. `dynamicsymbols` would read the colon in
    `platform:x` as a range."""
    return sp.Function(name)(dynamicsymbols._t)


def _on(name, body, pos, frames, com, at):
    """The point `pos` (base frame, at home) fixed on `body`."""
    return com[body].locatenew(name, _vector(_minus(pos, at[body]),
                                             frames[body]))


def _minus(a, b):
    return tuple(sp.sympify(x) - sp.sympify(y) for x, y in zip(a, b))


def _vector(components, frame):
    x, y, z = (sp.sympify(c) for c in components)
    return x * frame.x + y * frame.y + z * frame.z


def _ro(mapping):
    return MappingProxyType(dict(mapping))
