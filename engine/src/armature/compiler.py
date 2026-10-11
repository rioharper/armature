"""Compiling a mechanism description into a MuJoCo model.

The compiler owns every MuJoCo setting a project might otherwise reach for:
radians (MjSpec defaults to degrees), explicit inertia on every body (the
default infers it from geoms), and the timestep. A description never sets them.

Each body's MuJoCo frame sits at its COM with axes parallel to the base frame at
home, so every local position is the description's base-frame position less
the body's COM, and every inertia goes in unrotated.
"""

from types import MappingProxyType

import mujoco
import numpy as np

from .description import describe
from .elements import WORLD
from .state import State

TIMESTEP = 1e-3

_KIND = {"hinge": mujoco.mjtJoint.mjJNT_HINGE,
         "slide": mujoco.mjtJoint.mjJNT_SLIDE}


def compile(mechanism, params):
    """Describe `mechanism(params)` with floats, validate it, and compile it.

    Validation finishes before MuJoCo is touched. Returns a `Compiled`.
    """
    description = describe(mechanism, params)
    return Compiled(description, _spec(description).compile())


class Compiled:
    """A compiled mechanism. Query it through `at()`.

    `model` is the compiled `MjModel`, the escape hatch for code that needs raw
    arrays. Treat it as read-only: every query reads it, and none expects it to
    change.
    """

    def __init__(self, description, model):
        self.description = description
        self.model = model
        self.coordinates = tuple(model.joint(i).name for i in range(model.njnt))
        self._joints = {j.name: j for j in description.joints}

    def at(self, q=None, qd=None):
        """The state with coordinates `q` and rates `qd`, each keyed by
        coordinate name. An omitted coordinate is at its home value, an
        omitted rate is zero. Raises on an unknown name or a coordinate outside
        its joint's range."""
        q, qd = dict(q or {}), dict(qd or {})
        for given in (q, qd):
            unknown = sorted(set(given) - set(self.coordinates))
            if unknown:
                raise KeyError(f"no coordinate named {unknown}; this mechanism "
                               f"has {list(self.coordinates)}")
        values, rates = {}, {}
        for name in self.coordinates:
            joint = self._joints[name]
            value = float(q.get(name, joint.home))
            lo, hi = (float(v) for v in joint.range)
            if not lo <= value <= hi:
                raise ValueError(f"joint {name!r}: {value} lies outside its "
                                 f"range ({lo}, {hi})")
            values[name] = value
            rates[name] = float(qd.get(name, 0.0))
        return State(self, MappingProxyType(values), MappingProxyType(rates))


def _spec(description):
    spec = mujoco.MjSpec()
    spec.modelname = "mechanism"
    spec.compiler.degree = False
    spec.compiler.inertiafromgeom = mujoco.mjtInertiaFromGeom.mjINERTIAFROMGEOM_FALSE
    spec.option.timestep = TIMESTEP
    spec.option.gravity = [float(g) for g in description.gravity]

    com = {WORLD: np.zeros(3)}
    com.update({b.name: _floats(b.com) for b in description.bodies})
    handle = {WORLD: spec.worldbody}
    parent_of = {j.child: j.parent for j in description.joints}
    pending = list(description.bodies)
    while pending:  # parents first; describe() has checked every body is reachable
        ready = [b for b in pending if parent_of[b.name] in handle]
        for b in ready:
            parent = parent_of[b.name]
            mj = handle[parent].add_body(name=b.name,
                                         pos=com[b.name] - com[parent])
            mj.mass = float(b.mass)
            mj.ipos = [0.0, 0.0, 0.0]
            inertia = _floats(b.inertia)
            mj.fullinertia = [inertia[0, 0], inertia[1, 1], inertia[2, 2],
                              inertia[0, 1], inertia[0, 2], inertia[1, 2]]
            mj.explicitinertial = True
            handle[b.name] = mj
        pending = [b for b in pending if b not in ready]

    for j in description.joints:
        mj = handle[j.child].add_joint(name=j.name, type=_KIND[j.kind],
                                       axis=_floats(j.axis),
                                       pos=_floats(j.point) - com[j.child])
        mj.range = [float(j.range[0]), float(j.range[1])]
        mj.limited = mujoco.mjtLimited.mjLIMITED_TRUE
        mj.ref = float(j.home)
        if j.stiffness is not None:
            mj.stiffness[0] = float(j.stiffness)  # a polynomial array; [0] is linear
            mj.springref = float(j.home if j.rest is None else j.rest)

    for s in description.sites:
        handle[s.body].add_site(name=s.name, pos=_floats(s.pos) - com[s.body])

    for c in description.cables:
        ends = []
        for label, (on, pos) in (("start", c.start), ("end", c.end)):
            name = f"{c.name}:{label}"
            handle[on].add_site(name=name, pos=_floats(pos) - com[on])
            ends.append(name)
        rest = float(c.rest_length)
        tendon = spec.add_tendon(name=c.name)
        tendon.stiffness[0] = float(c.ea) / rest
        tendon.springlength = [0.0, rest]  # a deadband: no force while slack
        for name in ends:
            tendon.wrap_site(name)

    return spec


def _floats(value):
    return np.array(value, dtype=float)
