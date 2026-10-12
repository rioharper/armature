"""Writing a posture into MuJoCo, and closing the loops, couples and rigid
cables a closed chain adds.

A loop's rows are the gap between its two sites, p_a − p_b, with the Jacobian
J_a − J_b, both from MuJoCo's own kinematics (`mj_jacSite`); a couple's row is
q_a − home_a − ratio (q_b − home_b); a rigid cable's is its length less its
rest length, |p_end − p_start| − L, with the Jacobian u·(J_end − J_start)
along the unit span u. A loop whose moving joints all turn about
one direction n (and slide across it) is planar: its row along n is zero at
every posture, so only its two in-plane rows are kept, and a rank lost reads
the same on a planar loop as on a spatial one.

A closed chain's coordinates split into independent ones, which `at()` takes,
and dependent ones, solved from them. The dependent ones are chosen once, at
home: hinges and slides in a loop or a couple, unactuated before actuated, a
couple's follower first, until their columns carry the rows' rank.

Only the joints around a constraint can open or close it: a joint both of a
loop's sites hang from moves the loop rigidly, and a joint off its path does
not move it at all. So assembly walks from home only along the independent
coordinates around a constraint, and sets the rest at their targets from the
first step, as it does a floating body: a wheel turned 90 rad adds no steps.
"""

import math

import mujoco
import numpy as np
from scipy.linalg import null_space

from .description import rigid_cables
from .elements import WORLD

RANK_TOL = 1e-9          # a singular value below this times the largest is
                         # lost: what it would carry is not a number worth
                         # reporting
CLOSE_TOL = 1e-10        # m (rad, for a couple): the gap `at()` accepts
NEWTON_STEPS = 60
CONTINUATION_STEP = 0.05  # rad or m of an independent coordinate per step,
                          # so a posture is reached along the branch from home
PARALLEL_TOL = 1e-9


class ClosureError(ValueError):
    """A posture `at()` cannot close. `constraint` names what refused it:
    the loop, couple or rigid cable that stays open (`"loop 'pin'"`), or the
    joint that closing would put outside its range (`"joint 'B'"`)."""

    def __init__(self, message, constraint):
        super().__init__(message)
        self.constraint = constraint


def write_q(compiled, data, values):
    """Write coordinate `values` (keyed by name) into `data.qpos`. A
    floating body's `Placement` places its joint's point and turns the body;
    MuJoCo's own position is its COM's."""
    model = compiled.model
    for name, value in values.items():
        adr = model.jnt_qposadr[model.joint(name).id]
        if isinstance(value, tuple):  # a Placement, a NamedTuple
            data.qpos[adr:adr + 3] = (value.position + value.rotation
                                      @ compiled._offset[name])
            quat = np.zeros(4)
            mujoco.mju_mat2Quat(quat, np.ascontiguousarray(value.rotation).ravel())
            data.qpos[adr + 3:adr + 7] = quat
        else:
            data.qpos[adr] = value


def tangent(compiled, data, rates=None):
    """T, with MuJoCo's rates q̇ = T ẋ for dof rates ẋ, and the drift Ṫẋ at
    `rates` (zero when None), so q̈ = T ẍ + Ṫẋ. Both are trivial except at a
    free joint, whose MuJoCo rates are the COM's velocity and the angular
    velocity in body axes, where the dofs' are the point's velocity and the
    angular velocity in base axes. Reads the kinematics already in `data`."""
    model = compiled.model
    out, drift = np.eye(model.nv), np.zeros(model.nv)
    for jid in compiled._free:  # read once, at compile: every query asks
        d = model.jnt_dofadr[jid]
        rotation = data.xmat[model.jnt_bodyid[jid]].reshape(3, 3)
        lever = rotation @ compiled._offset[model.joint(jid).name]  # point→COM
        out[d:d + 3, d + 3:d + 6] = -skew(lever)  # v_COM = v + ω × lever
        out[d + 3:d + 6, d + 3:d + 6] = rotation.T
        if rates is not None:
            omega = rates[d + 3:d + 6]
            drift[d:d + 3] = np.cross(omega, np.cross(omega, lever))
    return out, drift


def skew(v):
    return np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])


def rank(matrix):
    """The rank of `matrix` at `RANK_TOL`."""
    if not matrix.size:
        return 0
    s = np.linalg.svd(matrix, compute_uv=False)
    return int(np.sum(s > RANK_TOL * s[0])) if s[0] > 0 else 0


class Closure:
    """The loops and couples of a compiled mechanism: their rows, the split
    into independent and dependent coordinates, and the solve that closes
    them."""

    def __init__(self, compiled):
        self.compiled = compiled
        model, description = compiled.model, compiled.description
        self.model = model
        sites = {s.name: s for s in description.sites}
        self.blocks = []  # (name, kind, size, detail)
        around = set()  # the joints that can open or close a constraint
        for loop in description.loops:
            around.update(j.name for j in _around(
                description, sites[loop.a].body, sites[loop.b].body))
            a, b = (mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, n)
                    for n in (loop.a, loop.b))
            directions = _directions(compiled, sites[loop.a].body,
                                     sites[loop.b].body)
            self.blocks.append((loop.name, "loop", len(directions),
                                (a, b, directions)))
        for c in description.couples:
            around.update((c.a, c.b))
            ja, jb = model.joint(c.a).id, model.joint(c.b).id
            self.blocks.append((c.a, "couple", 1, (
                model.jnt_qposadr[ja], model.jnt_qposadr[jb],
                model.jnt_dofadr[ja], model.jnt_dofadr[jb],
                float(model.qpos0[model.jnt_qposadr[ja]]),
                float(model.qpos0[model.jnt_qposadr[jb]]), float(c.ratio))))
        for c in rigid_cables(description):
            around.update(j.name for j in _around(description, c.start[0],
                                                  c.end[0]))
            ends = (mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE,
                                      f"{c.name}:{label}")
                    for label in ("start", "end"))
            self.blocks.append((c.name, "cable", 1,
                                (*ends, float(c.rest_length))))
        self.around = frozenset(around)
        self.names = tuple(name for name, *_ in self.blocks)
        self.size = sum(size for _, _, size, _ in self.blocks)
        self._choose_dependent()

    def rows(self, data):
        """The gap and its Jacobian (rows × MuJoCo's rates) at `data`, whose
        kinematics and `mj_comPos` must be current."""
        model = self.model
        gap, jac = np.zeros(self.size), np.zeros((self.size, model.nv))
        row = 0
        for _, kind, size, detail in self.blocks:
            if kind == "loop":
                a, b, directions = detail
                ja, jb = np.zeros((3, model.nv)), np.zeros((3, model.nv))
                mujoco.mj_jacSite(model, data, ja, None, a)
                mujoco.mj_jacSite(model, data, jb, None, b)
                gap[row:row + size] = directions @ (data.site_xpos[a]
                                                    - data.site_xpos[b])
                jac[row:row + size] = directions @ (ja - jb)
            elif kind == "cable":
                start, end, rest = detail
                span, js, je = self._span(data, start, end)
                length = np.linalg.norm(span)
                gap[row] = length - rest
                jac[row] = span / length @ (je - js)
            else:
                qa, qb, da, db, home_a, home_b, ratio = detail
                gap[row] = (data.qpos[qa] - home_a
                            - ratio * (data.qpos[qb] - home_b))
                jac[row, da], jac[row, db] = 1.0, -ratio
            row += size
        return gap, jac

    def drift(self, data):
        """J̇ q̇ at `data`, whose velocities must be current."""
        model = self.model
        out, row = np.zeros(self.size), 0
        for _, kind, size, detail in self.blocks:
            if kind == "loop":
                a, b, directions = detail
                for site, sign in ((a, 1.0), (b, -1.0)):
                    jdot = np.zeros((3, model.nv))
                    mujoco.mj_jacDot(model, data, jdot, None,
                                     data.site_xpos[site].copy(),
                                     int(model.site_bodyid[site]))
                    out[row:row + size] += sign * directions @ (jdot @ data.qvel)
            if kind == "cable":  # d²L/dt² − J q̈ = u·(J̇_e − J̇_s) q̇ + |v⊥|²/L
                start, end, _ = detail
                span, js, je = self._span(data, start, end)
                length = np.linalg.norm(span)
                u, v = span / length, (je - js) @ data.qvel
                for site, sign in ((end, 1.0), (start, -1.0)):
                    jdot = np.zeros((3, model.nv))
                    mujoco.mj_jacDot(model, data, jdot, None,
                                     data.site_xpos[site].copy(),
                                     int(model.site_bodyid[site]))
                    out[row] += sign * u @ (jdot @ data.qvel)
                out[row] += (v @ v - (u @ v) ** 2) / length
            row += size
        return out

    def _span(self, data, start, end):
        """A cable's span, end less start, and its two ends' Jacobians."""
        model = self.model
        js, je = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        mujoco.mj_jacSite(model, data, js, None, start)
        mujoco.mj_jacSite(model, data, je, None, end)
        return data.site_xpos[end] - data.site_xpos[start], js, je

    def forces(self, multipliers):
        """Each constraint's force from its rows' multipliers: a loop's force
        on its first site's body (a 3-vector in the base frame), a couple's
        generalised force on its follower, a rigid cable's tension (it pulls
        along −∂L/∂q, so the tension is the multiplier's negative)."""
        out, row = {}, 0
        for name, kind, size, detail in self.blocks:
            part = multipliers[row:row + size]
            out[name] = (detail[2].T @ part if kind == "loop"
                         else -float(part[0]) if kind == "cable"
                         else float(part[0]))
            row += size
        return out

    def worst(self, gap):
        """The constraint with the largest gap, and that gap."""
        best, row = (None, -1.0), 0
        for name, kind, size, _ in self.blocks:
            size_here = float(np.max(np.abs(gap[row:row + size]), initial=0.0))
            if size_here > best[1]:
                best = (f"{kind} {name!r}", size_here)
            row += size
        return best

    def close(self, data):
        """Newton on the dependent coordinates in `data.qpos`, from where they
        are, until the gap stops shrinking. Leaves the kinematics current and
        returns the gap."""
        model, best = self.model, math.inf
        for k in range(NEWTON_STEPS + 1):
            mujoco.mj_kinematics(model, data)
            mujoco.mj_comPos(model, data)
            gap, jac = self.rows(data)
            size = float(np.max(np.abs(gap), initial=0.0))
            if (k == NEWTON_STEPS or not math.isfinite(size) or size == 0.0
                    or (size < CLOSE_TOL and size > 0.5 * best)):
                return gap
            best = min(best, size)
            data.qpos[self._dep_adr] -= _solve(jac[:, self._dep_dof], gap)

    def assemble(self, values):
        """The dependent coordinates that close every loop and couple with
        the independent coordinates at `values`, reached from home in steps
        so the solve stays on the branch connected to home. Raises, naming
        the constraint, where the posture cannot close."""
        compiled, model = self.compiled, self.model
        start = {n: compiled.home(n) for n in values}
        scalar = [n for n in values if not isinstance(values[n], tuple)
                  and compiled._coordinate[n][0].name in self.around]
        span = max((abs(values[n] - start[n]) for n in scalar), default=0.0)
        steps = max(1, math.ceil(span / CONTINUATION_STEP))
        adr = [model.jnt_qposadr[model.joint(n).id] for n in scalar]
        dof = [model.jnt_dofadr[model.joint(n).id] for n in scalar]
        with compiled._scratch() as data:  # reset, so qpos0: home
            mujoco.mj_kinematics(model, data)
            mujoco.mj_comPos(model, data)
            for k in range(1, steps + 1):
                now = {n: (start[n] + k / steps * (values[n] - start[n])
                           if n in scalar else values[n]) for n in values}
                # Predict along the branch's tangent before correcting: near
                # a singularity the other branch is close, and Newton started
                # from the last step's posture can fall onto it.
                _, jac = self.rows(data)
                move = np.array([now[n] for n in scalar]) - data.qpos[adr]
                data.qpos[self._dep_adr] -= _solve(jac[:, self._dep_dof],
                                                   jac[:, dof] @ move)
                write_q(compiled, data, now)
                gap = self.close(data)
                if not np.max(np.abs(gap), initial=0.0) <= CLOSE_TOL:
                    which, size = self.worst(gap)
                    unit = "" if which.startswith("couple") else "m"
                    raise ClosureError(
                        f"{which} cannot close at this posture: it is still "
                        f"{size:.3g} {unit} apart after the solve (from home, "
                        f"{k - 1} of {steps} steps along the way closed)",
                        which)
            return {n: float(data.qpos[a])
                    for n, a in zip(self.dependent, self._dep_adr)}

    def complete(self, data, jac, given, constant):
        """`given` (over the dofs, dependent entries ignored) with the
        dependent entries solved from J T x = −`constant`."""
        tangent_now = tangent(self.compiled, data)[0]
        jt = jac @ tangent_now
        out = np.array(given, dtype=float)
        out[self._dep_dof] = 0.0
        out[self._dep_dof] = _solve(jt[:, self._dep_dof],
                                    -(constant + jt @ out))
        return out

    def basis(self, jt):
        """G: the dofs' motion per unit motion of the independent dofs, with
        J T G = 0. Its rows follow the dofs, its columns the independent
        dofs."""
        nv = self.model.nv
        g = np.zeros((nv, len(self.independent_dofs)))
        g[self.independent_dofs, np.arange(len(self.independent_dofs))] = 1.0
        g[self._dep_dof] = -_solve(jt[:, self._dep_dof],
                                   jt[:, self.independent_dofs])
        return g

    def _choose_dependent(self):
        compiled, model = self.compiled, self.model
        with compiled._scratch() as data:
            mujoco.mj_kinematics(model, data)
            mujoco.mj_comPos(model, data)
            _, jac = self.rows(data)
        actuated = {model.joint(int(model.actuator_trnid[i, 0])).name
                    for i in range(model.nu)}
        followers = {c.a for c in compiled.description.couples}
        scalar = [n for n in compiled.coordinates
                  if model.jnt_type[model.joint(n).id] in
                  (mujoco.mjtJoint.mjJNT_HINGE, mujoco.mjtJoint.mjJNT_SLIDE)]
        order = {n: i for i, n in enumerate(compiled.coordinates)}
        candidates = sorted(
            (n for n in scalar
             if np.any(jac[:, model.jnt_dofadr[model.joint(n).id]])),
            key=lambda n: (n in actuated, n not in followers, -order[n]))
        target, chosen = rank(jac), []
        for n in candidates:
            if len(chosen) == target:
                break
            trial = chosen + [n]
            cols = [model.jnt_dofadr[model.joint(c).id] for c in trial]
            if rank(jac[:, cols]) == len(trial):
                chosen = trial
        chosen.sort(key=order.get)
        self.dependent = tuple(chosen)
        self._dep_adr = [model.jnt_qposadr[model.joint(n).id] for n in chosen]
        self._dep_dof = [model.jnt_dofadr[model.joint(n).id] for n in chosen]
        self.independent_dofs = [i for i in range(model.nv)
                                 if i not in self._dep_dof]


def _solve(matrix, rhs):
    """The least-squares solution, truncated at `RANK_TOL`: no step along a
    direction the rows cannot see. At a singular posture an untruncated
    step divides the rounding in the gap by a vanishing singular value, and
    throws the solve off the singularity it was asked for."""
    return np.linalg.lstsq(matrix, rhs, rcond=RANK_TOL)[0]


def _directions(compiled, body_a, body_b):
    """The rows a loop between `body_a` and `body_b` keeps: the two in-plane
    directions when every moving joint around it turns about one direction
    and slides across it, all three base axes otherwise."""
    description = compiled.description
    moving = [j for j in _around(description, body_a, body_b)
              if j.name not in description.locks]
    hinges = [np.array(j.axis, dtype=float) for j in moving
              if j.kind == "hinge"]
    if any(j.kind == "free" for j in moving) or not hinges:
        return np.eye(3)
    normal = hinges[0] / np.linalg.norm(hinges[0])
    planar = all(np.linalg.norm(np.cross(h, normal)) < PARALLEL_TOL
                 for h in hinges) and all(
        abs(np.dot(np.array(j.axis, dtype=float), normal)) < PARALLEL_TOL
        for j in moving if j.kind == "slide")
    return null_space(normal[None, :]).T if planar else np.eye(3)


def _around(description, body_a, body_b):
    """The joints on the path from `body_a` to `body_b` (either may be the
    world): those on one's way to the world and not on the other's."""
    joint_into = {j.child: j for j in description.joints}

    def path(body):
        out = []
        while body != WORLD:
            j = joint_into[body]
            out.append(j)
            body = j.parent
        return out

    a, b = path(body_a), path(body_b)
    return [j for j in a if j not in b] + [j for j in b if j not in a]
