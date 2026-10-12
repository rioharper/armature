"""The derivation's view of a description: frames and points in SymPy.

The same `mechanism(p)` the truth model compiles is called with SymPy symbols
named after the parameters, so frames are written once and cannot drift. Each
body's frame is its parent's turned about (or slid along) its joint's home axis
by the coordinate's distance from home, parent to child: the product of
exponentials (Lynch and Park, ch. 4) written as a chain of frames. A locked
coordinate is turned by its locked value instead and drops out of the
coordinates.

The derivation hangs its own `RigidBody`s on these frames and points and runs
`LagrangesMethod` or `KanesMethod`; the view does not form equations.
"""

from dataclasses import dataclass
from types import MappingProxyType

import sympy as sp
from sympy.physics.mechanics import (Point, ReferenceFrame, dynamicsymbols,
                                     inertia)

from .description import describe, tree_order
from .elements import WORLD


@dataclass(frozen=True, eq=False)
class Symbolic:
    """The symbolic view of a description or a variant.

    `q` maps each coordinate's name to its `dynamicsymbol`, in the compiled
    model's order; `params` maps each parameter's name to its symbol. `world`
    and `origin` are the base frame and its origin. Per body: `frames`, `com`
    (a Point), `mass`, and `inertia`, the dyadic about the COM. Per joint:
    `axes` (a Vector) and `anchors` (a Point on the axis). `sites` includes
    each cable's ends as `<cable>:start` and `<cable>:end`. `gravity` is a
    Vector. Every point's velocity in `world` is set.
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

    @property
    def coordinates(self):
        return tuple(self.q)


def symbolic(mechanism, params):
    """The symbolic view of `mechanism` (or a variant), with a real SymPy
    symbol for each key of `params`; the values are not read."""
    symbols = {k: sp.Symbol(k, real=True) for k in params}
    d = describe(mechanism, symbols)
    world, origin = ReferenceFrame("world"), Point("origin")
    origin.set_vel(world, 0)

    joint_into = {j.child: j for j in d.joints}
    bodies = tree_order(d)
    q = {joint_into[b.name].name: dynamicsymbols(joint_into[b.name].name)
         for b in bodies if joint_into[b.name].name not in d.locks}
    frames, com, at = {WORLD: world}, {WORLD: origin}, {WORLD: (0, 0, 0)}
    axes, anchors = {}, {}
    for b in bodies:
        j = joint_into[b.name]
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

    tensors = {}
    for b in d.bodies:
        i = [[sp.sympify(v) for v in row] for row in b.inertia]
        tensors[b.name] = inertia(frames[b.name], i[0][0], i[1][1], i[2][2],
                                  i[0][1], i[1][2], i[2][0])
    del frames[WORLD], com[WORLD]
    return Symbolic(d, _ro(q), _ro(symbols), world, origin, _ro(frames),
                    _ro(com), _ro({b.name: sp.sympify(b.mass) for b in d.bodies}),
                    _ro(tensors), _ro(axes), _ro(anchors), _ro(sites),
                    _vector(d.gravity, world))


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
