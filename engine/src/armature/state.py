"""A named state of a compiled mechanism, and the queries asked of it.

Every query builds its own `MjData` from the state, so no query reads what
another call left behind, and every one returns a named record carrying its
residual and its method. Loads are forces at named sites, `{site: (fx, fy, fz)}`
in the base frame; the engine applies each at its site, so none picks up the
moment error of a force moved to a body's origin or COM.
"""

import math
from dataclasses import dataclass
from types import MappingProxyType

import mujoco
import numpy as np
from scipy.linalg import eigh

EPS = 1e-6
HOLD_STEPS = 500        # a settle runs at least this long, so "balanced here"
                        # has to become "stays here"
MAX_STEPS = 20000
REST_SPEED = 1e-6       # rad/s or m/s
REST_ACCEL = 1e-4       # rad/s² or m/s²


@dataclass(frozen=True, eq=False)
class State:
    """Coordinates `q` and rates `qd`, keyed by coordinate name. Immutable;
    make one with `Compiled.at()`.

    A kinematic record's `residual` is the state's closure residual, how far
    its loops are from closed (m); on an open chain it is zero.
    """
    compiled: object
    q: MappingProxyType
    qd: MappingProxyType

    def _data(self):
        model = self.compiled.model
        data = mujoco.MjData(model)
        for name in self.compiled.coordinates:
            joint = model.joint(name)
            data.qpos[model.jnt_qposadr[joint.id]] = self.q[name]
            data.qvel[model.jnt_dofadr[joint.id]] = self.qd[name]
        mujoco.mj_forward(model, data)
        return data

    def pose(self, site):
        """Where `site` is: its position and its orientation, in the base
        frame. A site's axes are parallel to the base frame's at home."""
        model, data = self.compiled.model, self._data()
        sid = _named(model, mujoco.mjtObj.mjOBJ_SITE, site, model.nsite)
        return Pose(site, _frozen(data.site_xpos[sid]),
                    _frozen(data.site_xmat[sid].reshape(3, 3)),
                    _closure(model, data), "mj_kinematics")

    def jacobian(self, site):
        """∂(site velocity)/∂(coordinate rates), linear and angular, in the
        base frame. Columns follow `coordinates`."""
        model, data = self.compiled.model, self._data()
        sid = _named(model, mujoco.mjtObj.mjOBJ_SITE, site, model.nsite)
        linear, angular = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        mujoco.mj_jacSite(model, data, linear, angular, sid)
        return Jacobian(site, self.compiled.coordinates, _frozen(linear),
                        _frozen(angular), _closure(model, data), "mj_jacSite")

    def inverse(self, qdd=None, loads=None):
        """The actuator torques that move this state at accelerations `qdd`
        (keyed by coordinate; omitted ones are zero) under `loads`.

        Solves [S J_cᵀ][τ; λ] = M q̈ + bias − passive − Σ J_siteᵀ f by least
        squares, where S maps each actuator's torque to generalised forces. It
        never calls `mj_inverse`, which answers for whatever constraint forces
        its solver happens to hold. A nonzero residual is the generalised
        force these actuators cannot supply: they cannot hold this state.
        """
        model, data = self.compiled.model, self._data()
        _refuse_constraints(model, data, "an inverse solve")
        accel = self._by_coordinate(qdd, "qdd")
        mass = np.zeros((model.nv, model.nv))
        mujoco.mj_fullM(model, data, mass)
        need = (mass @ accel + data.qfrc_bias - data.qfrc_passive
                - _load_force(model, data, loads))
        moment = np.zeros((model.nu, model.nv))
        if model.nu:
            mujoco.mju_sparse2dense(moment, data.actuator_moment,
                                    data.moment_rownnz, data.moment_rowadr,
                                    data.moment_colind)
        columns = moment.T
        if columns.shape[1]:
            torque, _, rank, singular = np.linalg.lstsq(columns, need,
                                                        rcond=None)
            condition = (singular[0] / singular[-1]
                         if rank == columns.shape[1] else math.inf)
        else:
            torque, rank, condition = np.zeros(0), 0, math.inf
        residual = float(np.max(np.abs(columns @ torque - need), initial=0.0))
        torques = dict(zip(self.compiled.actuators, (float(t) for t in torque)))
        return Inverse(MappingProxyType(torques), MappingProxyType({}),
                       MappingProxyType(dict(zip(self.compiled.coordinates,
                                                 (float(v) for v in need)))),
                       int(rank), float(condition), residual,
                       _over_limit(model, torques), INVERSE_METHOD)

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
        rest = {name: float(data.qpos[model.jnt_qposadr[model.joint(name).id]])
                for name in self.compiled.coordinates}
        moved = {name: rest[name] - self.q[name] for name in rest}
        rows = sorted({_constraint(model, data, i) for i in range(data.nefc)})
        return Settled(MappingProxyType(rest), MappingProxyType(moved), stable,
                       steps, _over_limit(model, command), tuple(rows),
                       _closure(model, data), SETTLE_METHOD)

    def wrench(self, body, qdd=None, loads=None):
        """The wrench `body`'s parent exerts on it across its joint, for this
        state moving at `qdd` under `loads`: a force and a torque about the
        joint's anchor, in the base frame.

        It is what the joint must carry for that motion, read from MuJoCo's
        `mj_rnePostConstraint`. Along the joint's axis it is the actuators'
        torque less what accelerates their rotors; the rest is the reaction.
        """
        model, data = self.compiled.model, self._data()
        _refuse_constraints(model, data, "a wrench")
        bid = _named(model, mujoco.mjtObj.mjOBJ_BODY, body, model.nbody)
        if bid == 0 or model.body_jntnum[bid] != 1:
            raise ValueError(f"body {body!r} has no joint of its own to carry "
                             f"a wrench across (the world, or welded by a "
                             f"lock)")
        data.qacc[:] = self._by_coordinate(qdd, "qdd")
        for site, force in _loads(model, loads):
            on = model.site_bodyid[site]
            lever = data.site_xpos[site] - data.xipos[on]  # xfrc acts at the COM
            data.xfrc_applied[on, :3] += force
            data.xfrc_applied[on, 3:] += np.cross(lever, force)
        mujoco.mj_rnePostConstraint(model, data)
        about = data.subtree_com[model.body_rootid[bid]]  # cfrc_int's reference
        joint = model.body_jntadr[bid]
        anchor = data.xanchor[joint].copy()
        force = data.cfrc_int[bid, 3:].copy()
        torque = data.cfrc_int[bid, :3] + np.cross(about - anchor, force)
        return Wrench(body, model.joint(joint).name, _frozen(anchor),
                      _frozen(force), _frozen(torque), _closure(model, data),
                      "mj_rnePostConstraint at qacc = qdd; torque about the "
                      "joint anchor")

    def release(self, hold=None, loads=None, min_steps=HOLD_STEPS,
                max_steps=MAX_STEPS):
        """Size a variant's assumptions: settle the full description from this
        state, each locked coordinate at its locked value, under the
        derivation's `hold` and `loads`, and report how far each locked
        coordinate moves.

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
        start = dict(self.q)
        start.update({name: float(r.at) for name, r in locks.items()})
        settled = compiled.full.at(q=start).settle(command, loads, min_steps,
                                                   max_steps)
        return Released(
            compiled.description.variant, compiled.description.reductions,
            MappingProxyType({n: float(r.at) for n, r in locks.items()}),
            MappingProxyType({n: settled.moved[n] for n in locks}),
            settled, settled.residual, RELEASE_METHOD)

    def linearise(self, eps=EPS):
        """Stiffness K, mass M and the mode frequencies about this state.

        K = ∂f/∂q for f = M q̈ + bias − passive at q̈ = 0, by MuJoCo's
        `mjd_inverseFD`. The passive force carries joint springs and cables,
        which a gradient of the bias force alone reads as zero. `mjd_inverseFD`
        differences one-sidedly, which leaves an error of order `eps` wherever
        K varies with q, so it runs at +eps and at −eps and K is their mean, a
        central difference. M is MuJoCo's own, exactly. The frequencies solve
        K v = ω² M v and are signed: a negative one is a divergent mode, the
        mechanism falling away from this state.
        """
        model, data = self.compiled.model, self._data()
        _refuse_constraints(model, data, "a linearisation")
        nv = model.nv
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
        stiffness = (sides[0] + sides[1]) / 2
        if nv:
            lam = eigh((stiffness + stiffness.T) / 2, mass, eigvals_only=True)
        else:
            lam = np.zeros(0)
        freq = np.sign(lam) * np.sqrt(np.abs(lam)) / (2 * np.pi)
        return Linearised(self.compiled.coordinates, _frozen(stiffness),
                          _frozen(mass), _frozen(freq), _closure(model, data),
                          LINEARISE_METHOD, eps)

    def _by_coordinate(self, values, label):
        """`values`, keyed by coordinate, as a vector over MuJoCo's dofs."""
        model, values = self.compiled.model, dict(values or {})
        unknown = sorted(set(values) - set(self.compiled.coordinates))
        if unknown:
            raise KeyError(f"{label}: no coordinate named {unknown}; this "
                           f"mechanism has {list(self.compiled.coordinates)}")
        out = np.zeros(model.nv)
        for name, value in values.items():
            out[model.jnt_dofadr[model.joint(name).id]] = float(value)
        return out


INVERSE_METHOD = ("least squares on [S J_c^T][tau; lambda] = M qdd + bias - "
                  "passive - J_site^T f; M from mj_fullM, never mj_inverse")
SETTLE_METHOD = (f"quench from rest, Euler steps split around the loads, at "
                 f"least {HOLD_STEPS} steps by default; rest at |qd| < "
                 f"{REST_SPEED:g} and |qdd| < {REST_ACCEL:g}")
RELEASE_METHOD = ("the full description settled from the locked values, "
                  "locked coordinates uncommanded")
LINEARISE_METHOD = ("K: mjd_inverseFD at qacc = 0, central (mean of +eps and "
                    "-eps); M: mj_fullM")


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
    Jacobians, 3 × len(coordinates), in the base frame."""
    site: str
    coordinates: tuple
    linear: np.ndarray
    angular: np.ndarray
    residual: float
    method: str


@dataclass(frozen=True, eq=False)
class Inverse:
    """The inverse-dynamics record.

    `torque` is each actuator's motor torque (N·m; N on a slide), and
    `constraint` each constraint's force. `generalised` is the generalised
    force the solve had to supply, keyed by coordinate. `rank` and `condition`
    are the solve's; `condition` is infinite when the actuators are
    rank-deficient or there are none. `residual` is the largest generalised
    force left unsupplied, and `over_limit` names the actuators whose torque
    exceeds their limit.
    """
    torque: MappingProxyType
    constraint: MappingProxyType
    generalised: MappingProxyType
    rank: int
    condition: float
    residual: float
    over_limit: tuple
    method: str


@dataclass(frozen=True, eq=False)
class Settled:
    """The settle record. `q` is where it came to rest and `moved` how far
    each coordinate went, both keyed by coordinate. `stable` says whether it
    came to rest within `steps`. `over_limit` names actuators held beyond
    their limit, and `constraints` the constraint rows active at rest, such
    as a joint limit the mechanism came to lean on."""
    q: MappingProxyType
    moved: MappingProxyType
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
    with `point` the joint's anchor."""
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
    and `mass` follow `coordinates`; `frequencies` are in Hz, signed and
    ascending. `method` and `eps`, the finite-difference step, say how it was
    computed, since a finite-difference stiffness is only as good as its step."""
    coordinates: tuple
    stiffness: np.ndarray
    mass: np.ndarray
    frequencies: np.ndarray
    residual: float
    method: str
    eps: float

    def __str__(self):
        freqs = ", ".join(f"{f:.6g}" for f in self.frequencies)
        return (f"modes [{freqs}] Hz over {list(self.coordinates)}; "
                f"{self.method}, eps = {self.eps:g}")


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
        if a.forcelimited[0] and not (a.forcerange[0] <= torque <= a.forcerange[1]):
            out.append(name)
    return tuple(out)


def _closure(model, data):
    """How far the state's loops are from closed: the largest equality-row
    violation, zero where there are none."""
    rows = data.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY
    return float(np.max(np.abs(data.efc_pos[rows]), initial=0.0))


def _refuse_constraints(model, data, what):
    if data.nefc:
        rows = sorted({_constraint(model, data, i) for i in range(data.nefc)})
        raise RuntimeError(
            f"{data.nefc} constraint row(s) active at this state "
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
