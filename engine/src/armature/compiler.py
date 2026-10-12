"""Compiling a mechanism description into a MuJoCo model.

The compiler owns every MuJoCo setting a project might otherwise reach for:
radians (MjSpec defaults to degrees), explicit inertia on every body (the
default infers it from geoms), the timestep and the integrator, and each
actuator's limits. A description never sets them.

Each body's MuJoCo frame sits at its COM with axes parallel to the base frame at
home, so every local position is the description's base-frame position less
the body's COM, and every inertia goes in unrotated. A variant's locked joint is
deleted and its child posed at the locked value, a weld; the subtree's local
numbers are unchanged, since they ride on the child's frame.
"""

from types import MappingProxyType

import mujoco
import numpy as np

from .description import describe, tree_order
from .elements import WORLD
from .state import State

TIMESTEP = 1e-3

_KIND = {"hinge": mujoco.mjtJoint.mjJNT_HINGE,
         "slide": mujoco.mjtJoint.mjJNT_SLIDE}


def compile(mechanism, params):
    """Describe `mechanism(params)` with floats, validate it, and compile it.

    `mechanism` may be a variant from `reduce`. Validation finishes before
    MuJoCo is touched. Returns a `Compiled`.
    """
    description = describe(mechanism, params)
    return Compiled(description, _spec(description).compile(),
                    source=(mechanism, params))


class Compiled:
    """A compiled mechanism. Query it through `at()`.

    `coordinates` and `actuators` are named in MuJoCo's order. A variant's
    compiled model leaves its locked coordinates out; `full` is the full
    description, compiled, which its release settles.

    `model` is the compiled `MjModel`, the escape hatch for code that needs raw
    arrays. Treat it as read-only: every query reads it, and none expects it to
    change.
    """

    def __init__(self, description, model, source=None):
        self.description = description
        self.model = model
        self.coordinates = tuple(model.joint(i).name for i in range(model.njnt))
        self.actuators = tuple(model.actuator(i).name for i in range(model.nu))
        self._joints = {j.name: j for j in description.joints}
        self._source = source
        self._full = None

    @property
    def full(self):
        """The full description, compiled; this model itself when it is not a
        variant."""
        if not self.description.locks:
            return self
        if self._full is None:
            mechanism, params = self._source
            self._full = compile(mechanism.mechanism, params)
        return self._full

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
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_EULER  # settle splits mj_step
    spec.option.gravity = [float(g) for g in description.gravity]

    locks = description.locks
    armature = {}
    for a in description.actuators:  # each rotor reflected through its gear
        armature[a.joint] = (armature.get(a.joint, 0.0)
                             + float(a.gear) ** 2 * float(a.rotor_inertia))

    com = {WORLD: np.zeros(3)}
    com.update({b.name: _floats(b.com) for b in description.bodies})
    handle = {WORLD: spec.worldbody}
    joint_into = {j.child: j for j in description.joints}
    for b in tree_order(description):  # parents first
        j = joint_into[b.name]
        pos, quat = com[b.name] - com[j.parent], [1.0, 0.0, 0.0, 0.0]
        if j.name in locks:  # a weld: no joint, the child posed at the lock
            pos, quat = _posed(j, com[b.name], com[j.parent],
                               float(locks[j.name].at) - float(j.home))
        mj = handle[j.parent].add_body(name=b.name, pos=pos, quat=quat)
        mj.mass = float(b.mass)
        mj.ipos = [0.0, 0.0, 0.0]
        inertia = _floats(b.inertia)
        mj.fullinertia = [inertia[0, 0], inertia[1, 1], inertia[2, 2],
                          inertia[0, 1], inertia[0, 2], inertia[1, 2]]
        mj.explicitinertial = True
        handle[b.name] = mj
        if j.name not in locks:
            _add_joint(mj, j, com[b.name], armature.get(j.name, 0.0))

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

    for a in description.actuators:
        if a.joint in locks:  # its joint is gone, and its rotor with it
            continue
        mj = spec.add_actuator(name=a.name, target=a.joint,
                               trntype=mujoco.mjtTrn.mjTRN_JOINT)
        mj.gear = [float(a.gear), 0.0, 0.0, 0.0, 0.0, 0.0]  # all six are read
        mj.ctrllimited = mujoco.mjtLimited.mjLIMITED_FALSE
        if a.torque_limit is None:
            mj.forcelimited = mujoco.mjtLimited.mjLIMITED_FALSE
        else:
            mj.forcelimited = mujoco.mjtLimited.mjLIMITED_TRUE
            mj.forcerange = [-float(a.torque_limit), float(a.torque_limit)]

    return spec


def _add_joint(body, j, com, armature):
    mj = body.add_joint(name=j.name, type=_KIND[j.kind], axis=_floats(j.axis),
                        pos=_floats(j.point) - com)
    mj.range = [float(j.range[0]), float(j.range[1])]
    mj.limited = mujoco.mjtLimited.mjLIMITED_TRUE
    mj.ref = float(j.home)
    mj.armature = armature
    if j.stiffness is not None:
        mj.stiffness[0] = float(j.stiffness)  # a polynomial array; [0] is linear
        mj.springref = float(j.home if j.rest is None else j.rest)


def _posed(j, com, parent_com, delta):
    """The child's frame, relative to its parent's, with joint `j` moved
    `delta` from home: the position of its COM and its orientation."""
    axis, point = _floats(j.axis), _floats(j.point)
    if j.kind == "slide":
        return com + axis * delta - parent_com, [1.0, 0.0, 0.0, 0.0]
    c, s = np.cos(delta), np.sin(delta)
    k = np.array([[0, -axis[2], axis[1]],
                  [axis[2], 0, -axis[0]],
                  [-axis[1], axis[0], 0]])
    rot = np.eye(3) + s * k + (1 - c) * k @ k
    quat = [np.cos(delta / 2), *(np.sin(delta / 2) * axis)]
    return rot @ (com - point) + point - parent_com, quat


def _floats(value):
    return np.array(value, dtype=float)
