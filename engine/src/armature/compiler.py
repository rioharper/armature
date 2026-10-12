"""Compiling a mechanism description into a MuJoCo model.

The compiler owns every MuJoCo setting a project might otherwise reach for:
radians (MjSpec defaults to degrees), explicit inertia on every body (the
default infers it from geoms), the timestep and the integrator, and each
actuator's limits, and the solver parameters of every loop and couple. A
description never sets them.

Each body's MuJoCo frame sits at its COM with axes parallel to the base frame at
home, so every local position is the description's base-frame position less
the body's COM, and every inertia goes in unrotated. A variant's locked joint is
deleted and its child posed at the locked value, a weld; the subtree's local
numbers are unchanged, since they ride on the child's frame.

A free joint compiles as MuJoCo's free joint, kept at the top level. Locking any
of its components rebuilds it as a chain of the scalar joints that remain:
slides along the base axes, then hinges about the body's own axes through its
point, with the locked turns applied first as the body's fixed orientation. A
level platform is three slides.

A loop compiles as a `connect` between its two sites, a couple as a joint
equality, and a rigid cable as a tendon equality at its rest length. All are
soft in MuJoCo, so the queries never lean on the solver's forces: `at()`
closes them exactly, and `inverse` and `linearise` carry them as explicit
constraint rows.

MuJoCo refuses a moving body without mass or inertia, so a body a lump left
without them compiles with `MASS_FLOOR` of its own mass and inertia, and the
variant is flagged `approximate`.
"""

from types import MappingProxyType

import mujoco
import numpy as np

from .assembly import Closure, write_q
from .description import (coordinate_joints, describe, rigid_cables,
                          tree_order)
from .elements import FREE_COMPONENTS, WORLD
from .rotations import AXES, floating_rotation, turn
from .state import Placement, State, placement
from .variants import reduce

TIMESTEP = 1e-3
CLOSURE_SOLREF = (2 * TIMESTEP, 1.0)  # the stiffest MuJoCo keeps stable, at
                                      # critical damping
CLOSURE_SOLIMP = (0.9999, 0.9999, 1e-3, 0.5, 2.0)  # MuJoCo's highest impedance
    # at every violation: a loop's slack goes as (1 - d)/d, so a five-bar at
    # rest holds 3e-9 m, where (0.99, 0.999) held 4e-7 m and left a
    # parallelogram creeping for 20 s
MASS_FLOOR = 1e-6  # of a body's own mass and inertia, where a lump left none:
                   # MuJoCo refuses a moving body without either (mjMINVAL)

_KIND = {"hinge": mujoco.mjtJoint.mjJNT_HINGE,
         "slide": mujoco.mjtJoint.mjJNT_SLIDE}


def compile(mechanism, params):
    """Describe `mechanism(params)` with floats, validate it, and compile it.

    `mechanism` may be a variant from `reduce`. Validation finishes before
    MuJoCo is touched. Returns a `Compiled`.
    """
    description = describe(mechanism, params)
    model = _spec(description).compile()
    _hold_rigid(model, description)
    return Compiled(description, model, source=(mechanism, params))


def _hold_rigid(model, description):
    """Set each rigid cable's tendon equality to its rest length. MuJoCo holds
    L − L₀ = data[0], with L₀ the length at the compiled home posture, which
    a lock away from home moves, so it is read once compiled."""
    for c in rigid_cables(description):
        tendon = model.tendon(c.name).id
        model.eq_data[model.equality(c.name).id, 0] = (
            float(c.rest_length) - model.tendon_length0[tendon])


class Compiled:
    """A compiled mechanism. Query it through `at()`.

    `coordinates` are named in MuJoCo's order: a hinge or slide's value is a
    number, and a floating body's free joint a `Placement`. `dofs` name the
    rates, one per degree of freedom, in the same order: a free joint `f`
    has `f:x`, `f:y` and `f:z`, its point's velocity, then `f:rx`, `f:ry`
    and `f:rz`, its angular velocity, all along base axes. Every rate,
    acceleration, Jacobian column and matrix row follows `dofs`. A variant's
    compiled model leaves its locked coordinates out; `full` is the full
    description, compiled, which its release settles.

    On a closed chain, `constraints` names each loop, couple and rigid
    cable, and the coordinates split into `independent` ones, which `at()`
    takes, and `dependent` ones, which it solves so every loop closes.

    `approximate` says why this model is not exactly its description, one
    reason per floored body; it is empty when it is exact.

    `model` is the compiled `MjModel`, the escape hatch for code that needs raw
    arrays. Treat it as read-only: every query reads it, and none expects it to
    change. Its free joints' rates are MuJoCo's own (the COM's velocity, and
    the angular velocity in body axes), not the dofs'.
    """

    def __init__(self, description, model, source=None):
        self.description = description
        self.model = model
        self.coordinates = tuple(model.joint(i).name for i in range(model.njnt))
        self.actuators = tuple(model.actuator(i).name for i in range(model.nu))
        free = mujoco.mjtJoint.mjJNT_FREE
        self.dofs = tuple(
            label for i in range(model.njnt) for label in (
                [f"{model.joint(i).name}:{c}" for c in FREE_COMPONENTS]
                if model.jnt_type[i] == free else [model.joint(i).name]))
        self._joint_into = {j.child: j for j in description.joints}
        self._coordinate = coordinate_joints(description)
        self._coordinate.update({j.name: (j, None) for j in description.joints
                                 if j.kind == "free"})
        com = {b.name: _floats(b.com) for b in description.bodies}
        self._offset = {j.name: com[j.child] - _floats(j.point)  # point to COM
                        for j in description.joints}
        self._source = source
        self._full, self._without = None, {}
        self.closure = (Closure(self) if description.loops
                        or description.couples or rigid_cables(description)
                        else None)
        self.constraints = self.closure.names if self.closure else ()
        self.dependent = self.closure.dependent if self.closure else ()
        self.independent = tuple(n for n in self.coordinates
                                 if n not in self.dependent)

    @property
    def full(self):
        """The full description, compiled; this model itself when it is not a
        variant."""
        if not self.description.reductions:
            return self
        if self._full is None:
            mechanism, params = self._source
            self._full = compile(mechanism.mechanism, params)
        return self._full

    def without(self, reduction):
        """This variant without `reduction`, compiled: what releasing that
        one reduction compares against."""
        if reduction not in self._without:
            mechanism, params = self._source
            rest = tuple(r for r in self.description.reductions
                         if r is not reduction)
            self._without[reduction] = compile(
                reduce(mechanism.mechanism, *rest,
                       name=f"{self.description.variant} without {reduction}")
                if rest else mechanism.mechanism, params)
        return self._without[reduction]

    @property
    def approximate(self):
        mass = {b.name: float(b.mass) for b in self.description.bodies}
        return tuple(
            f"{r} leaves {r.body!r} without "
            f"{'mass' if mass[r.body] == 0 else 'inertia'}; it compiles with "
            f"{MASS_FLOOR:g} of its own mass and inertia, since MuJoCo "
            f"refuses a moving body without either"
            for r in self.description.reductions
            if getattr(r, "body", None) in self.description.floored)

    def home(self, coordinate):
        """`coordinate`'s value at the home posture."""
        joint, component = self._coordinate[coordinate]
        if joint.kind != "free":
            return float(joint.home)
        point = _floats(joint.point)
        if component is None:
            return Placement(point, np.eye(3))
        i = FREE_COMPONENTS.index(component)
        return float(point[i]) if i < 3 else 0.0

    def at(self, q=None, qd=None):
        """The state with coordinates `q`, keyed by coordinate name, and rates
        `qd`, keyed by dof. An omitted coordinate is at its home value, an
        omitted rate is zero. A floating body's value is a `Placement`, or a
        (position, rotation) pair. Raises on an unknown name or a coordinate
        outside its joint's range.

        On a closed chain, `q` and `qd` take the independent coordinates only.
        The dependent ones are solved so that every loop and couple closes to
        within 1e-10 m, on the branch reached from home, and their rates so
        that the loops stay closed. A posture that cannot close raises,
        naming the loop."""
        q, qd = dict(q or {}), dict(qd or {})
        for given, names, label in ((q, self.coordinates, "coordinate"),
                                    (qd, self.dofs, "dof")):
            unknown = sorted(set(given) - set(names))
            if unknown:
                raise KeyError(f"no {label} named {unknown}; this mechanism "
                               f"has {list(names)}")
            solved = sorted(set(given) & set(self.dependent))
            if solved:
                raise ValueError(
                    f"{solved} closing the loops {list(self.constraints)} "
                    f"{'is' if len(solved) == 1 else 'are'} solved, not given; "
                    f"give the independent coordinates "
                    f"{list(self.independent)}")
        values = {}
        for name in self.independent:
            joint, component = self._coordinate[name]
            if joint.kind == "free" and component is None:
                values[name] = (placement(q[name], name) if name in q
                                else self.home(name))
                continue
            value = float(q.get(name, self.home(name)))
            if joint.range is not None:
                lo, hi = (float(v) for v in joint.range)
                if not lo <= value <= hi:
                    raise ValueError(f"joint {name!r}: {value} lies outside "
                                     f"its range ({lo}, {hi})")
            values[name] = value
        rates = {name: float(qd.get(name, 0.0)) for name in self.dofs}
        if self.closure:
            values, rates = self._close(values, rates)
        return State(self, MappingProxyType(values), MappingProxyType(rates))

    def _close(self, values, rates):
        """`values` and `rates` with the dependent coordinates and rates
        solved."""
        solved = self.closure.assemble(values)
        for name, value in solved.items():
            lo, hi = (float(v) for v in self._coordinate[name][0].range)
            if not lo <= value <= hi:
                raise ValueError(f"joint {name!r}: closing the loops puts it "
                                 f"at {value}, outside its range ({lo}, {hi})")
        values = {n: values[n] if n in values else solved[n]
                  for n in self.coordinates}
        data = mujoco.MjData(self.model)
        write_q(self, data, values)
        mujoco.mj_kinematics(self.model, data)
        mujoco.mj_comPos(self.model, data)
        _, jac = self.closure.rows(data)
        given = np.array([rates[d] for d in self.dofs])
        full = self.closure.complete(data, jac, given, 0.0)
        return values, dict(zip(self.dofs, (float(v) for v in full)))


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
        chain = ()
        if j.kind == "free":
            pos, quat, chain = _floating(j, com[b.name], locks)
        elif j.name in locks:  # a weld: no joint, the child posed at the lock
            pos, quat = _posed(j, com[b.name], com[j.parent],
                               float(locks[j.name].at) - float(j.home))
        else:
            pos, quat = com[b.name] - com[j.parent], [1.0, 0.0, 0.0, 0.0]
        mj = handle[j.parent].add_body(name=b.name, pos=pos, quat=quat)
        mj.mass = float(b.mass)
        mj.ipos = [0.0, 0.0, 0.0]
        inertia = _floats(b.inertia)
        if b.name in description.floored:  # a lump left it without either
            was = description.floored[b.name]
            mj.mass += MASS_FLOOR * float(was.mass)
            inertia = inertia + MASS_FLOOR * _floats(was.inertia)
        mj.fullinertia = [inertia[0, 0], inertia[1, 1], inertia[2, 2],
                          inertia[0, 1], inertia[0, 2], inertia[1, 2]]
        mj.explicitinertial = True
        handle[b.name] = mj
        if j.kind == "free" and len(chain) == len(FREE_COMPONENTS):
            mj.add_freejoint(name=j.name)
        elif j.kind == "free":
            for component, kind, axis, ref in chain:
                c = mj.add_joint(name=f"{j.name}:{component}", type=_KIND[kind],
                                 axis=axis, pos=_floats(j.point) - com[b.name])
                c.limited = mujoco.mjtLimited.mjLIMITED_FALSE
                c.ref = ref
        elif j.name not in locks:
            _add_joint(mj, j, com[b.name], armature.get(j.name, 0.0))

    for s in description.sites:
        handle[s.body].add_site(name=s.name, pos=_floats(s.pos) - com[s.body])

    rigid = {c.name for c in rigid_cables(description)}
    for c in description.cables:
        ends = []
        for label, (on, pos) in (("start", c.start), ("end", c.end)):
            name = f"{c.name}:{label}"
            handle[on].add_site(name=name, pos=_floats(pos) - com[on])
            ends.append(name)
        rest = float(c.rest_length)
        tendon = spec.add_tendon(name=c.name)
        for name in ends:
            tendon.wrap_site(name)
        if c.name in rigid:  # no spring: held at its rest length, both ways
            eq = spec.add_equality(name=c.name, type=mujoco.mjtEq.mjEQ_TENDON,
                                   objtype=mujoco.mjtObj.mjOBJ_TENDON,
                                   name1=c.name)
            eq.solref, eq.solimp = CLOSURE_SOLREF, CLOSURE_SOLIMP
            continue  # its length is set once compiled, by _hold_rigid
        tendon.stiffness[0] = float(c.ea) / rest
        tendon.springlength = [0.0, rest]  # a deadband: no force while slack

    for loop in description.loops:  # sites, so the sites themselves meet
        eq = spec.add_equality(name=loop.name, type=mujoco.mjtEq.mjEQ_CONNECT,
                               objtype=mujoco.mjtObj.mjOBJ_SITE,
                               name1=loop.a, name2=loop.b)
        eq.solref, eq.solimp = CLOSURE_SOLREF, CLOSURE_SOLIMP
    for c in description.couples:  # q_a − home_a = ratio (q_b − home_b)
        eq = spec.add_equality(type=mujoco.mjtEq.mjEQ_JOINT,
                               objtype=mujoco.mjtObj.mjOBJ_JOINT,
                               name1=c.a, name2=c.b)
        eq.data[:5] = [0.0, float(c.ratio), 0.0, 0.0, 0.0]
        eq.solref, eq.solimp = CLOSURE_SOLREF, CLOSURE_SOLIMP

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
    rot = turn(axis, delta)
    return rot @ (com - point) + point - parent_com, _quat(rot)


def _floating(j, com, locks):
    """A floating body's frame, and the chain of scalar joints its locks
    leave: (component, kind, local axis, home value) each. All six, when
    nothing is locked, compile as MuJoCo's free joint instead."""
    point = _floats(j.point)
    held = {c: float(locks[f"{j.name}:{c}"].at) for c in FREE_COMPONENTS
            if f"{j.name}:{c}" in locks}
    turned = floating_rotation(held, {})
    shift = np.array([held.get(c, v) for c, v in zip("xyz", point)])
    chain = [(c, "slide", turned.T @ AXES[i], float(point[i]))  # base axes
             for i, c in enumerate("xyz") if c not in held]
    chain += [(c, "hinge", AXES[i], 0.0)  # the body's own axes
              for i, c in enumerate(("rx", "ry", "rz")) if c not in held]
    return shift + turned @ (com - point), _quat(turned), chain


def _quat(rot):
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, np.ascontiguousarray(rot, dtype=float).ravel())
    return quat


def _floats(value):
    return np.array(value, dtype=float)
