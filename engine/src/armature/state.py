"""A named state of a compiled mechanism, and the queries asked of it.

Every query builds its own `MjData` from the state, so no query reads what
another call left behind, and every one returns a named record carrying its
residual and its method. Loads are forces at named sites, `{site: (fx, fy, fz)}`
in the base frame; the engine applies each at its site, so none picks up the
moment error of a force moved to a body's origin or COM.

A floating body's position is written through `jnt_qposadr` and its rates
through `jnt_dofadr`; they differ for every joint after a free one, which has
seven positions and six rates. Its rates and the rows of every matrix are
turned from MuJoCo's own (the COM's velocity, the angular velocity in body
axes) to the dofs': the point's velocity and the angular velocity, both along
base axes.

On a closed chain, every query that solves for forces carries the loops and
couples as explicit constraint rows, J_c, from MuJoCo's own Jacobians. None
reads the solver's constraint forces, which answer for whatever slack its soft
constraints hold: `mj_inverse` on a five-bar was off by 61 % and 78 %.
"""

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

import mujoco
import numpy as np
from scipy.linalg import eigh
from scipy.spatial.transform import Rotation

from .assembly import RANK_TOL, tangent, write_q
from .rotations import floating_rotation, turn

EPS = 1e-6
HOLD_STEPS = 500        # a settle runs at least this long, so "balanced here"
                        # has to become "stays here"
MAX_STEPS = 20000
REST_SPEED = 1e-6       # rad/s or m/s
REST_ACCEL = 1e-4       # rad/s² or m/s²
ROTATION_TOL = 1e-9     # |RᵀR − I| allowed in a given rotation
CLOSURE_BOUND = 1e-6    # m: the slack a settle's soft loops may hold
DETERMINED_TOL = 1e-9   # an unknown's share of the null space below which it
                        # is determined


class Placement(NamedTuple):
    """Where a floating body is: `position`, its point's position in the base
    frame (m), and `rotation`, the 3×3 turn from its home orientation (the
    body's axes in base components)."""
    position: np.ndarray
    rotation: np.ndarray


def placement(value, name):
    """`value`, a (position, rotation) pair, as a checked `Placement`."""
    try:
        position, rotation = value
        position = np.array(position, dtype=float)
        rotation = np.array(rotation, dtype=float)
    except (TypeError, ValueError):
        position = rotation = None
    if (position is None or position.shape != (3,)
            or rotation.shape != (3, 3)):
        raise ValueError(f"{name!r} is a floating body: its value is a "
                         f"(position, 3x3 rotation) pair, got {value!r}")
    if (np.max(np.abs(rotation.T @ rotation - np.eye(3))) > ROTATION_TOL
            or np.linalg.det(rotation) < 0):
        raise ValueError(f"{name!r}: {rotation.tolist()} is not a rotation")
    return Placement(_frozen(position), _frozen(rotation))


@dataclass(frozen=True, eq=False)
class State:
    """Coordinates `q`, keyed by coordinate name, and rates `qd`, keyed by
    dof. Immutable; make one with `Compiled.at()`.

    A kinematic record's `residual` is the state's closure residual, how far
    its loops are from closed (m); on an open chain it is zero. On a closed
    chain, `q` and `qd` include the dependent coordinates `at()` solved.
    """
    compiled: object
    q: MappingProxyType
    qd: MappingProxyType

    def _data(self):
        compiled = self.compiled
        model = compiled.model
        data = mujoco.MjData(model)
        write_q(compiled, data, self.q)
        mujoco.mj_kinematics(model, data)
        data.qvel[:] = tangent(compiled, data)[0] @ self._rates()
        mujoco.mj_forward(model, data)
        return data

    def _rates(self):
        return np.array([self.qd[d] for d in self.compiled.dofs])

    def pose(self, site):
        """Where `site` is: its position and its orientation, in the base
        frame. A site's axes are parallel to the base frame's at home."""
        model, data = self.compiled.model, self._data()
        sid = _named(model, mujoco.mjtObj.mjOBJ_SITE, site, model.nsite)
        return Pose(site, _frozen(data.site_xpos[sid]),
                    _frozen(data.site_xmat[sid].reshape(3, 3)),
                    _closure(model, data), "mj_kinematics")

    def jacobian(self, site):
        """∂(site velocity)/∂(dof rates), linear and angular, in the base
        frame. Columns follow `dofs`."""
        model, data = self.compiled.model, self._data()
        sid = _named(model, mujoco.mjtObj.mjOBJ_SITE, site, model.nsite)
        linear, angular = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        mujoco.mj_jacSite(model, data, linear, angular, sid)
        turned = tangent(self.compiled, data)[0]
        return Jacobian(site, self.compiled.dofs, _frozen(linear @ turned),
                        _frozen(angular @ turned), _closure(model, data),
                        "mj_jacSite")

    def inverse(self, qdd=None, loads=None):
        """The actuator torques that move this state at accelerations `qdd`
        (keyed by dof; omitted ones are zero) under `loads`.

        Solves [S J_cᵀ][τ; λ] = M q̈ + bias − passive − Σ J_siteᵀ f by least
        squares, where S maps each actuator's torque to generalised forces
        and J_c carries each loop's and couple's rows. It never calls
        `mj_inverse`, which answers for whatever constraint forces its solver
        happens to hold. A nonzero residual is the generalised force these
        actuators cannot supply: they cannot hold this state. Where the solve
        has lost rank, as at a singularity, an unknown it cannot determine
        reads NaN, never a least-norm number.

        On a closed chain, `qdd` takes the independent dofs; the dependent
        accelerations are solved so the loops stay closed.
        """
        return self._solve(self._data(), qdd, loads)[0]

    def _solve(self, data, qdd, loads):
        """The inverse record, and the unknowns [τ; λ], at `data`."""
        compiled = self.compiled
        model, closure = compiled.model, compiled.closure
        _refuse_constraints(model, data, "an inverse solve")
        turned, drift = tangent(compiled, data, self._rates())
        if closure:
            wanted, jac = self._dependent_accel(data, qdd)
        else:
            wanted, jac = self._by_dof(qdd, "qdd"), np.zeros((0, model.nv))
        accel = turned @ wanted + drift
        mass = np.zeros((model.nv, model.nv))
        mujoco.mj_fullM(model, data, mass)
        need = turned.T @ (mass @ accel + data.qfrc_bias - data.qfrc_passive
                           - _load_force(model, data, loads))
        columns = turned.T @ np.hstack([_moment(model, data).T, jac.T])
        unknowns, rank, condition, residual = _least_squares(columns, need)
        torques = dict(zip(compiled.actuators,
                           (float(t) for t in unknowns[:model.nu])))
        forces = closure.forces(unknowns[model.nu:]) if closure else {}
        record = Inverse(
            MappingProxyType(torques), MappingProxyType(forces),
            MappingProxyType(dict(zip(compiled.dofs,
                                      (float(v) for v in need)))),
            rank, columns.shape[1], condition, residual,
            _over_limit(model, torques), INVERSE_METHOD)
        return record, unknowns

    def _dependent_accel(self, data, qdd):
        """`qdd` over the dofs, the dependent accelerations solved so the
        loops stay closed (J q̈ + J̇ q̇ = 0), and the rows' Jacobian."""
        compiled = self.compiled
        closure = compiled.closure
        solved = sorted(set(dict(qdd or {})) & set(compiled.dependent))
        if solved:
            raise ValueError(f"qdd: {solved} {'is' if len(solved) == 1 else 'are'}"
                             f" solved from the loops, not given")
        drift = tangent(compiled, data, self._rates())[1]
        _, jac = closure.rows(data)
        wanted = closure.complete(data, jac, self._by_dof(qdd, "qdd"),
                                  closure.drift(data) + jac @ drift)
        return wanted, jac

    def settle(self, hold=None, loads=None, min_steps=HOLD_STEPS,
               max_steps=MAX_STEPS):
        """Release the mechanism from rest at this posture, with each actuator
        held at its torque in `hold` (keyed by actuator; omitted ones carry
        nothing) and `loads` applied, and let it find rest.

        Energy leaves by quench, not damping: the velocity is zeroed whenever
        the mechanism turns back on itself (q̇·q̈ < 0). It runs at least
        `min_steps`, so a start that is already balanced has to stay. A torque
        beyond an actuator's limit is clamped there, as the motor would be, and
        named in `over_limit`. A settle that diverges or runs out of steps
        returns `stable = False` rather than raising.

        On a closed chain the loops are MuJoCo's soft constraints, at the
        solver parameters the compiler sets. `residual` is how far open they
        are at rest, and a settle that leaves one open past 1e-6 m raises.
        """
        model, data = self.compiled.model, self._data()
        data.qvel[:] = 0.0
        command = dict(hold or {})
        unknown = sorted(set(command) - set(self.compiled.actuators))
        if unknown:
            raise KeyError(f"no actuator named {unknown}; this mechanism has "
                           f"{list(self.compiled.actuators)}")
        for name, torque in command.items():
            data.ctrl[model.actuator(name).id] = float(torque)

        stable, steps = False, max_steps
        for step in range(1, max_steps + 1):
            mujoco.mj_step1(model, data)
            data.qfrc_applied[:] = _load_force(model, data, loads)  # here, now
            mujoco.mj_step2(model, data)
            if not (np.all(np.isfinite(data.qpos))
                    and np.all(np.isfinite(data.qvel))):
                steps = step
                break
            if float(data.qvel @ data.qacc) < 0.0:
                data.qvel[:] = 0.0
            if (step >= min_steps and np.max(np.abs(data.qvel)) < REST_SPEED
                    and np.max(np.abs(data.qacc)) < REST_ACCEL):
                stable, steps = True, step
                break

        mujoco.mj_forward(model, data)
        closure = self.compiled.closure
        if closure:
            which, gap = closure.worst(closure.rows(data)[0])
            if not gap <= CLOSURE_BOUND:
                raise RuntimeError(
                    f"the settle left {which} {gap:.3g} open, past the "
                    f"{CLOSURE_BOUND:g} bound: the solver's soft constraint "
                    f"is not holding it, so the rest pose is not the "
                    f"mechanism's")
        rest = {name: self._read(data, name)
                for name in self.compiled.coordinates}
        moved = {name: _moved(self.q[name], rest[name]) for name in rest}
        rows = sorted({_constraint(model, data, i) for i in range(data.nefc)})
        return Settled(MappingProxyType(rest), MappingProxyType(moved),
                       MappingProxyType(_tensions(model, data)), stable, steps,
                       _over_limit(model, command), tuple(rows),
                       _closure(model, data), SETTLE_METHOD)

    def wrench(self, body, qdd=None, loads=None):
        """The wrench `body`'s parent exerts on it across its joint, for this
        state moving at `qdd` under `loads`: a force and a torque about the
        joint's point, riding on the body, in the base frame.

        It is what the joint must carry for that motion, read from MuJoCo's
        `mj_rnePostConstraint`, which counts cable forces as applied. Along a
        hinge's axis it is the actuators' torque less what accelerates their
        rotors; the rest is the reaction. A free joint carries nothing at
        equilibrium, and what a level platform's locked turns must carry
        shows up across its slides.

        On a closed chain each loop's force comes from the explicit solve
        `inverse` makes for the same `qdd` and `loads`, applied at its two
        sites; the solver's own constraint forces are not read.
        """
        compiled = self.compiled
        model, data = compiled.model, self._data()
        _refuse_constraints(model, data, "a wrench")
        loop_forces = []
        if compiled.closure:
            forces = self._solve(data, qdd, loads)[0].constraint
            for loop in compiled.description.loops:
                force = forces[loop.name]
                if not np.all(np.isfinite(force)):
                    raise ValueError(f"loop {loop.name!r}'s force is not "
                                     f"determined here (the solve lost "
                                     f"rank), so no wrench is")
                loop_forces += [(loop.a, force), (loop.b, -force)]
            data.efc_force[:] = 0.0  # the solver's, not the mechanism's
            qdd = dict(zip(compiled.dofs, self._dependent_accel(data, qdd)[0]))
        bid = _named(model, mujoco.mjtObj.mjOBJ_BODY, body, model.nbody)
        if bid == 0 or model.body_jntnum[bid] == 0:
            raise ValueError(f"body {body!r} has no joint of its own to carry "
                             f"a wrench across (the world, or welded by a "
                             f"lock)")
        joint = compiled._joint_into[body]
        turned, drift = tangent(compiled, data, self._rates())
        data.qacc[:] = turned @ self._by_dof(qdd, "qdd") + drift
        named = [(_named(model, mujoco.mjtObj.mjOBJ_SITE, s, model.nsite), f)
                 for s, f in loop_forces]
        for site, force in _loads(model, loads) + named:
            on = model.site_bodyid[site]
            lever = data.site_xpos[site] - data.xipos[on]  # xfrc acts at the COM
            data.xfrc_applied[on, :3] += force
            data.xfrc_applied[on, 3:] += np.cross(lever, force)
        mujoco.mj_rnePostConstraint(model, data)
        about = data.subtree_com[model.body_rootid[bid]]  # cfrc_int's reference
        point = (data.xpos[bid] - data.xmat[bid].reshape(3, 3)
                 @ compiled._offset[joint.name])
        force = data.cfrc_int[bid, 3:].copy()
        torque = data.cfrc_int[bid, :3] + np.cross(about - point, force)
        return Wrench(body, joint.name, _frozen(point), _frozen(force),
                      _frozen(torque), _closure(model, data),
                      "mj_rnePostConstraint at qacc = qdd; torque about the "
                      "joint's point")

    def release(self, hold=None, loads=None, min_steps=HOLD_STEPS,
                max_steps=MAX_STEPS):
        """Size a variant's assumptions: settle the full description from this
        state, each locked coordinate at its locked value, under the
        derivation's `hold` and `loads`, and report how far each locked
        coordinate moves.

        A locked component of a floating body reports the same way: a
        position as the point's displacement along that base axis, and a turn
        as that angle of the intrinsic x-y-z turn from the start orientation
        to the rest one.

        `hold` names this variant's actuators only. A locked coordinate carries
        no command, because the assumption claims nothing needs to hold it.
        """
        compiled = self.compiled
        locks = compiled.description.locks
        if not locks:
            raise ValueError("this model is not a variant; there is nothing to "
                             "release")
        command = dict(hold or {})
        unknown = sorted(set(command) - set(compiled.actuators))
        if unknown:
            raise KeyError(f"variant {compiled.description.variant!r} has no "
                           f"actuator named {unknown}; it has "
                           f"{list(compiled.actuators)}, and a locked "
                           f"coordinate carries no command")
        full = compiled.full
        start = {}
        for name in full.coordinates:
            if name in self.q:
                start[name] = self.q[name]
            elif name in locks:
                start[name] = float(locks[name].at)
            else:  # a floating body this variant rebuilt as a chain
                start[name] = self._assembled(name)
        start = {n: v for n, v in start.items() if n not in full.dependent}
        settled = full.at(q=start).settle(command, loads, min_steps, max_steps)
        moved = {}
        for name in locks:
            joint, component = compiled._coordinate[name]
            moved[name] = (settled.moved[name] if component is None else
                           _component_moved(component, start[joint.name],
                                            settled.q[joint.name]))
        return Released(
            compiled.description.variant, compiled.description.reductions,
            MappingProxyType({n: float(r.at) for n, r in locks.items()}),
            MappingProxyType(moved), settled, settled.residual, RELEASE_METHOD)

    def linearise(self, eps=EPS):
        """Stiffness K, mass M and the mode frequencies about this state.

        K = ∂f/∂q for f = M q̈ + bias − passive at q̈ = 0, by MuJoCo's
        `mjd_inverseFD`. The passive force carries joint springs and cables,
        which a gradient of the bias force alone reads as zero. `mjd_inverseFD`
        differences one-sidedly, which leaves an error of order `eps` wherever
        K varies with q, so it runs at +eps and at −eps and K is their mean, a
        central difference. M is MuJoCo's own, exactly. A floating body's rows
        are turned to its dofs, which is exact at an equilibrium. The
        frequencies solve K v = ω² M v and are signed: a negative one is a
        divergent mode, the mechanism falling away from this state.

        On a closed chain the modes are on the constraint manifold only. K is
        the central difference of the reduced force Gᵀ(bias − passive − S τ)
        in the independent dofs, the loops re-closed at each step, with each
        actuator holding the torque `inverse` gives here; G is the dofs'
        motion per unit independent motion, and M = Gᵀ M G. Projecting the
        full K onto the manifold instead misses the geometric stiffness of
        the closing loop, and the full eigenproblem adds the solver's
        constraint stiffness as modes. Rows follow the independent dofs, and
        the posture is taken at rest.
        """
        compiled = self.compiled
        model, data = compiled.model, self._data()
        _refuse_constraints(model, data, "a linearisation")
        if compiled.closure:
            return self._linearise_closed(eps)
        nv = model.nv
        turned = tangent(compiled, data)[0]
        mass = np.zeros((nv, nv))
        mujoco.mj_fullM(model, data, mass)  # before mjd_inverseFD, which
        sides = []                          # leaves qM at a perturbed posture
        for step in (eps, -eps):
            data = self._data()
            data.qacc[:] = 0.0  # mj_forward wrote the free acceleration here
            dfdq = np.zeros((nv, nv))
            mujoco.mjd_inverseFD(model, data, step, False, dfdq, None, None,
                                 None, None, None, None)
            sides.append(dfdq.T)  # MuJoCo returns it transposed
        stiffness = turned.T @ ((sides[0] + sides[1]) / 2) @ turned
        mass = turned.T @ mass @ turned
        return Linearised(compiled.dofs, _frozen(stiffness), _frozen(mass),
                          _frozen(_frequencies(stiffness, mass)),
                          _closure(model, data), LINEARISE_METHOD, eps)

    def _linearise_closed(self, eps):
        compiled = self.compiled
        model, closure = compiled.model, compiled.closure
        at_rest = State(compiled, self.q,
                        MappingProxyType({d: 0.0 for d in compiled.dofs}))
        data = at_rest._data()
        hold = np.nan_to_num(at_rest._solve(data, None, None)[1][:model.nu])
        independent = [compiled.dofs[i] for i in closure.independent_dofs]

        def reduced(data):
            turned = tangent(compiled, data)[0]
            _, jac = closure.rows(data)
            basis = closure.basis(jac @ turned)
            force = turned.T @ (data.qfrc_bias - data.qfrc_passive
                                - _moment(model, data).T @ hold)
            return basis.T @ force, basis, turned

        _, basis, turned = reduced(data)
        mass = np.zeros((model.nv, model.nv))
        mujoco.mj_fullM(model, data, mass)
        mass = basis.T @ turned.T @ mass @ turned @ basis
        stiffness = np.zeros((len(independent),) * 2)
        worst = 0.0
        for i, dof in enumerate(independent):
            sides = []
            for step in (eps, -eps):
                moved = at_rest._data()
                write_q(compiled, moved, self._nudged(dof, step))
                gap = closure.close(moved)
                worst = max(worst, float(np.max(np.abs(gap), initial=0.0)))
                mujoco.mj_forward(model, moved)
                sides.append(reduced(moved)[0])
            stiffness[:, i] = (sides[0] - sides[1]) / (2 * eps)
        return Linearised(tuple(independent), _frozen(stiffness),
                          _frozen(mass),
                          _frozen(_frequencies(stiffness, mass)),
                          max(_closure(model, data), worst),
                          LINEARISE_CLOSED_METHOD, eps)

    def _nudged(self, dof, step):
        """The coordinate independent `dof` belongs to, moved `step` along
        it: a hinge or slide by `step`, a floating body's point along a base
        axis, or its orientation turned about one."""
        if dof in self.compiled.coordinates:
            return {dof: self.q[dof] + step}
        name, component = dof.rsplit(":", 1)
        value = self.q[name]
        i = ("x", "y", "z", "rx", "ry", "rz").index(component)
        if i < 3:
            return {name: Placement(value.position + step * np.eye(3)[i],
                                    value.rotation)}
        return {name: Placement(value.position,
                                turn(np.eye(3)[i - 3], step) @ value.rotation)}

    def _by_dof(self, values, label):
        """`values`, keyed by dof, as a vector over the dofs."""
        dofs, values = self.compiled.dofs, dict(values or {})
        unknown = sorted(set(values) - set(dofs))
        if unknown:
            raise KeyError(f"{label}: no dof named {unknown}; this mechanism "
                           f"has {list(dofs)}")
        return np.array([float(values.get(d, 0.0)) for d in dofs])

    def _read(self, data, name):
        """Coordinate `name`'s value in `data`."""
        model = self.compiled.model
        jid = model.joint(name).id
        if model.jnt_type[jid] != mujoco.mjtJoint.mjJNT_FREE:
            return float(data.qpos[model.jnt_qposadr[jid]])
        bid = model.jnt_bodyid[jid]
        rotation = data.xmat[bid].reshape(3, 3)
        return Placement(_frozen(data.xpos[bid] - rotation
                                 @ self.compiled._offset[name]),
                         _frozen(rotation))

    def _assembled(self, joint):
        """The `Placement` of floating `joint` from its components: locked
        ones at their locked values, the rest at this state's."""
        locks, values = self.compiled.description.locks, {}
        for c in ("x", "y", "z", "rx", "ry", "rz"):
            name = f"{joint}:{c}"
            values[c] = float(locks[name].at) if name in locks else self.q[name]
        held = {c: values[c] for c in ("rx", "ry", "rz")
                if f"{joint}:{c}" in locks}
        free = {c: values[c] for c in ("rx", "ry", "rz") if c not in held}
        return Placement(_frozen([values["x"], values["y"], values["z"]]),
                         _frozen(floating_rotation(held, free)))


INVERSE_METHOD = ("least squares on [S J_c^T][tau; lambda] = M qdd + bias - "
                  "passive - J_site^T f; M from mj_fullM, never mj_inverse")
SETTLE_METHOD = (f"quench from rest, Euler steps split around the loads, at "
                 f"least {HOLD_STEPS} steps by default; rest at |qd| < "
                 f"{REST_SPEED:g} and |qdd| < {REST_ACCEL:g}")
RELEASE_METHOD = ("the full description settled from the locked values, "
                  "locked coordinates uncommanded")
LINEARISE_METHOD = ("K: mjd_inverseFD at qacc = 0, central (mean of +eps and "
                    "-eps); M: mj_fullM; free joints turned to their dofs")
LINEARISE_CLOSED_METHOD = (
    "on the constraint manifold: K by central differences of the reduced "
    "force G^T (bias - passive - S tau) in the independent dofs, loops "
    "re-closed by Newton at each step; M = G^T M G from mj_fullM")


@dataclass(frozen=True, eq=False)
class Pose:
    """A site's `position` (m) and `rotation` (3×3, site axes in base
    components), in the base frame."""
    site: str
    position: np.ndarray
    rotation: np.ndarray
    residual: float
    method: str


@dataclass(frozen=True, eq=False)
class Jacobian:
    """A site's `linear` (m per unit rate) and `angular` (rad per unit rate)
    Jacobians, 3 × len(dofs), in the base frame."""
    site: str
    dofs: tuple
    linear: np.ndarray
    angular: np.ndarray
    residual: float
    method: str


@dataclass(frozen=True, eq=False)
class Inverse:
    """The inverse-dynamics record.

    `torque` is each actuator's motor torque (N·m; N on a slide), and
    `constraint` each loop's and couple's force: a loop's is the force on
    its first site's body, a 3-vector in the base frame (a planar loop's
    has no component along its plane's normal); a couple's, keyed by its
    follower, the generalised force it applies there. `generalised` is the
    generalised force the solve had to supply, keyed by dof.

    `rank` is the solve's, out of `unknowns` (the torques and the rows'
    multipliers); a rank below `unknowns` leaves some of them undetermined,
    and those read NaN. `condition` is infinite then, or when there are no
    unknowns. `residual` is the largest generalised force left unsupplied,
    and `over_limit` names the actuators whose torque exceeds their limit.
    """
    torque: MappingProxyType
    constraint: MappingProxyType
    generalised: MappingProxyType
    rank: int
    unknowns: int
    condition: float
    residual: float
    over_limit: tuple
    method: str


@dataclass(frozen=True, eq=False)
class Settled:
    """The settle record. `q` is where it came to rest and `moved` how far
    each coordinate went, both keyed by coordinate; a floating body moves by
    a `Placement` of its point's displacement and the turn from its start
    orientation to its rest one, in base axes. `tension` is each cable's
    tension at rest (N), exactly zero when slack. `stable` says whether it
    came to rest within `steps`. `over_limit` names actuators held beyond
    their limit, and `constraints` the constraint rows active at rest, such
    as a joint limit the mechanism came to lean on."""
    q: MappingProxyType
    moved: MappingProxyType
    tension: MappingProxyType
    stable: bool
    steps: int
    over_limit: tuple
    constraints: tuple
    residual: float
    method: str


@dataclass(frozen=True, eq=False)
class Wrench:
    """The wrench across `body`'s `joint`: the `force` (N) and the `torque`
    about `point` (N·m) that the parent exerts on the body, in the base frame,
    with `point` the joint's point where it rides on the body."""
    body: str
    joint: str
    point: np.ndarray
    force: np.ndarray
    torque: np.ndarray
    residual: float
    method: str


@dataclass(frozen=True, eq=False)
class Released:
    """A variant's release. For each locked coordinate, `assumed` is the value
    the lock held it at and `moved` its signed displacement when the full
    description settled; `settled` is that settle. A few microradians is an
    assumption sized and kept; degrees is an assumption that was wrong."""
    variant: str
    reductions: tuple
    assumed: MappingProxyType
    moved: MappingProxyType
    settled: Settled
    residual: float
    method: str

    def __str__(self):
        by_name = {getattr(r, "coordinate", None): r for r in self.reductions}
        parts = [f"{by_name[n]} moved {self.moved[n]:+.4g}" for n in self.moved]
        tail = "" if self.settled.stable else "; the full model never came to rest"
        return f"variant {self.variant!r}: {', '.join(parts)}{tail}"


@dataclass(frozen=True, eq=False)
class Linearised:
    """The linearisation record. Rows and columns of `stiffness` (N/m, N·m/rad)
    and `mass` follow `dofs`, which on a closed chain are its independent
    dofs only; `frequencies` are in Hz, signed and ascending.
    `method` and `eps`, the finite-difference step, say how it was computed,
    since a finite-difference stiffness is only as good as its step."""
    dofs: tuple
    stiffness: np.ndarray
    mass: np.ndarray
    frequencies: np.ndarray
    residual: float
    method: str
    eps: float

    def __str__(self):
        freqs = ", ".join(f"{f:.6g}" for f in self.frequencies)
        return (f"modes [{freqs}] Hz over {list(self.dofs)}; "
                f"{self.method}, eps = {self.eps:g}")


def _least_squares(columns, need):
    """Solve columns · x = need by least squares through the SVD: x, the
    rank at `RANK_TOL`, the condition, and the residual. An unknown with a
    share in the null space is not determined and reads NaN."""
    n = columns.shape[1]
    if not n:
        return (np.zeros(0), 0, math.inf,
                float(np.max(np.abs(need), initial=0.0)))
    u, s, vt = np.linalg.svd(columns)
    rank = int(np.sum(s > RANK_TOL * s[0])) if s[0] > 0 else 0
    x = vt[:rank].T @ ((u[:, :rank].T @ need) / s[:rank])
    residual = float(np.max(np.abs(columns @ x - need), initial=0.0))
    x[np.linalg.norm(vt[rank:], axis=0) > DETERMINED_TOL] = np.nan
    condition = s[0] / s[n - 1] if rank == n else math.inf
    return x, rank, float(condition), residual


def _moment(model, data):
    """The actuators' moment arms, actuators × MuJoCo's rates."""
    moment = np.zeros((model.nu, model.nv))
    if model.nu:
        mujoco.mju_sparse2dense(moment, data.actuator_moment,
                                data.moment_rownnz, data.moment_rowadr,
                                data.moment_colind)
    return moment


def _frequencies(stiffness, mass):
    """The signed mode frequencies (Hz) of K v = ω² M v, ascending."""
    if not len(stiffness):
        return np.zeros(0)
    lam = eigh((stiffness + stiffness.T) / 2, (mass + mass.T) / 2,
               eigvals_only=True)
    return np.sign(lam) * np.sqrt(np.abs(lam)) / (2 * np.pi)


def _moved(start, rest):
    if isinstance(rest, Placement):
        return Placement(_frozen(rest.position - start.position),
                         _frozen(rest.rotation @ start.rotation.T))
    return rest - start


def _component_moved(component, start, rest):
    """How far a floating body's `component` went from `start` to `rest`."""
    if component in ("x", "y", "z"):
        i = "xyz".index(component)
        return float(rest.position[i] - start.position[i])
    angles = Rotation.from_matrix(start.rotation.T @ rest.rotation).as_euler(
        "XYZ")
    return float(angles[("rx", "ry", "rz").index(component)])


def _tensions(model, data):
    """Each cable's tension: EA/rest × stretch, and exactly zero when slack,
    as MuJoCo's deadband spring applies it."""
    out = {}
    for i in range(model.ntendon):
        stretch = data.ten_length[i] - model.tendon_lengthspring[i, 1]
        out[model.tendon(i).name] = (float(model.tendon_stiffness[i] * stretch)
                                     if stretch > 0 else 0.0)
    return out


def _named(model, kind, name, count):
    """The id of the `kind` element called `name`, or a KeyError listing them."""
    found = mujoco.mj_name2id(model, kind, name)
    if found < 0:
        names = [mujoco.mj_id2name(model, kind, i) for i in range(count)]
        label = kind.name.removeprefix("mjOBJ_").lower()
        raise KeyError(f"no {label} named {name!r}; this mechanism has "
                       f"{[n for n in names if n]}")
    return found


def _loads(model, loads):
    """`loads` as (site id, force) pairs."""
    out = []
    for site, force in dict(loads or {}).items():
        force = np.asarray(force, dtype=float)
        if force.shape != (3,):
            raise ValueError(f"load at site {site!r}: a force is three numbers "
                             f"in the base frame, got {force}")
        out.append((_named(model, mujoco.mjtObj.mjOBJ_SITE, site, model.nsite),
                    force))
    return out


def _load_force(model, data, loads):
    """The generalised force of `loads`, each applied at its site."""
    total = np.zeros(model.nv)
    for site, force in _loads(model, loads):
        mujoco.mj_applyFT(model, data, force, np.zeros(3),
                          data.site_xpos[site].copy(),
                          int(model.site_bodyid[site]), total)
    return total


def _over_limit(model, torques):
    out = []
    for name, torque in torques.items():
        a = model.actuator(name)
        if (a.forcelimited[0] and math.isfinite(torque)
                and not a.forcerange[0] <= torque <= a.forcerange[1]):
            out.append(name)
    return tuple(out)


def _closure(model, data):
    """How far the state's loops are from closed: the largest equality-row
    violation, zero where there are none."""
    rows = data.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY
    return float(np.max(np.abs(data.efc_pos[rows]), initial=0.0))


def _refuse_constraints(model, data, what):
    """Raise on any active row but a loop's or a couple's, which the queries
    carry explicitly."""
    other = np.flatnonzero(data.efc_type[:data.nefc]
                           != mujoco.mjtConstraint.mjCNSTR_EQUALITY)
    if len(other):
        rows = sorted({_constraint(model, data, i) for i in other})
        raise RuntimeError(
            f"{len(other)} constraint row(s) active at this state "
            f"({', '.join(rows)}); {what} here would read the solver's "
            f"constraint forces, not the mechanism's")


def _constraint(model, data, row):
    kind = mujoco.mjtConstraint(data.efc_type[row]).name.removeprefix("mjCNSTR_")
    if kind == "LIMIT_JOINT":
        return f"limit on joint {model.joint(data.efc_id[row]).name!r}"
    return kind.lower()


def _frozen(array):
    array = np.array(array, dtype=float)
    array.flags.writeable = False
    return array
