"""Contacts: which are touching, their explicit rows, and what they carry.

A contact touches where MuJoCo's collision finds its pair within `TOUCH`. Each
point it finds becomes rows in the explicit solve: the force on the moving
body at that point, along the directions its joints let it move in (a planar
chain's two in-plane axes, a chain of slides its axes' span, all three base
axes otherwise; only the normal on a frictionless contact), with the Jacobian
from `mj_jac` at the point. Points whose rows coincide, as a planar wheel's
two rims do, are one constraint and are merged, so a lost rank means the same
on a wheel as on a pin. A contact's force is reported as its total over its
points, with the friction-cone margin μN − |F_t|: positive where Coulomb
friction holds it, negative where it would slip. A point is MuJoCo's own,
midway through the overlap, so the explicit solve and the simulation push at
the same place: on a compliant tyre sunk δ, r − δ/2 from the hub.

Settle reads the solver's own contact forces instead, at rest, where the
noslip solver has made them exact; the queries that solve never do. The
linearisation's roots come from the one-step map at two contact stiffnesses,
and `split` keeps those that hold between them.
"""

import math
from typing import NamedTuple

import mujoco
import numpy as np

from .assembly import _directions
from .elements import WORLD

TOUCH = 1e-8      # m: a contact this close counts as touching. It is the
    # pair's margin, so MuJoCo reports it; MuJoCo 3.15 ignores a pair's gap,
    # so its solver also pushes from here, and a resting rigid contact sits
    # within 10 nm of touching rather than sunk in, a compliant one 10 nm
    # shallower than its load over its stiffness
ROW_TOL = 1e-12   # rows this close, relative to their size, are one constraint
ZERO_ROOT = 1e-3  # s⁻¹: a root this small is a neutral direction, not a mode
MOVE_TOL = 1e-2   # a root that moves more than this, relative, between the
                  # two contact stiffnesses is the solver's, not the mechanism's
RESOLVED = 0.5    # |s|·dt: a root faster than this is beyond what the
                  # timestep resolves, and is the integrator's or the noslip
                  # solver's


class ContactForce(NamedTuple):
    """What a touching contact carries: the `normal` force (N, pushing the
    shapes apart when positive), the `friction` force (a 3-vector in the base
    frame, along the surface), the cone `margin` μN − |friction| (N; negative
    where it would slip), the `penetration` (m) of its deepest point, and
    `point`, the mean of its contact points. All on the contact's body."""
    normal: float
    friction: np.ndarray
    margin: float
    penetration: float
    point: np.ndarray


class Point(NamedTuple):
    contact: str
    position: np.ndarray
    normal: np.ndarray       # into the moving body
    directions: np.ndarray   # the rows' directions, k × 3
    penetration: float


def touching(compiled, data):
    """Each touching contact's merged points, in the description's order,
    and their rows' Jacobian (rows × MuJoCo's rates). `data`'s collision and
    kinematics must be current."""
    model = compiled.model
    points, blocks = [], []
    for c in compiled.description.contacts:
        found = _found(model, data, c.name)
        if not found:
            continue
        body = model.body(c.body).id
        frictionless = float(c.mu) == 0.0
        plane = _reach(compiled, c.body)
        merged = []  # [rows, positions, normal, directions, penetration]
        for i in found:
            normal = _into(model, data, i, c.name) * data.contact.frame[i][:3]
            directions = normal[None, :] if frictionless else plane
            position = data.contact.pos[i].copy()
            jac = np.zeros((3, model.nv))
            mujoco.mj_jac(model, data, jac, None, position, body)
            rows = directions @ jac
            depth = max(0.0, -float(data.contact.dist[i]))
            for m in merged:
                scale = max(1.0, float(np.max(np.abs(rows), initial=0.0)))
                if (m[0].shape == rows.shape
                        and np.max(np.abs(m[0] - rows)) <= ROW_TOL * scale):
                    m[1].append(position)
                    m[4] = max(m[4], depth)
                    break
            else:
                merged.append([rows, [position], normal, directions, depth])
        for rows, positions, normal, directions, depth in merged:
            points.append(Point(c.name, np.mean(positions, axis=0), normal,
                                directions, depth))
            blocks.append(rows)
    jac = np.vstack(blocks) if blocks else np.zeros((0, model.nv))
    return points, jac


def forces(compiled, points, multipliers):
    """Each touching contact's `ContactForce` from its points' least-norm
    `multipliers`: the total over its points, which is what the solve can
    tell even where it cannot tell the split."""
    mu = {c.name: float(c.mu) for c in compiled.description.contacts}
    totals, row = {}, 0
    for p in points:
        k = len(p.directions)
        force, at, depth, normal = totals.get(
            p.contact, (np.zeros(3), [], 0.0, p.normal))
        totals[p.contact] = (force + p.directions.T @ multipliers[row:row + k],
                             at + [p.position], max(depth, p.penetration),
                             normal)
        row += k
    return {name: _record(f, n, mu[name], depth, np.mean(at, axis=0))
            for name, (f, at, depth, n) in totals.items()}


def selectors(points, offset, size):
    """Per touching contact, the matrix (3 × `size`) that sums its points'
    forces out of the unknowns, whose contact rows start at `offset`."""
    out, row = {}, offset
    for p in points:
        k = len(p.directions)
        g = out.setdefault(p.contact, np.zeros((3, size)))
        g[:, row:row + k] = p.directions.T
        row += k
    return out


def from_solver(compiled, data):
    """Each touching contact's `ContactForce` from MuJoCo's own solution,
    read at rest by settle, where the noslip solver has made it exact."""
    model = compiled.model
    out = {}
    for c in compiled.description.contacts:
        total, at, depth, normal = np.zeros(3), [], 0.0, None
        for i in _found(model, data, c.name):
            local = np.zeros(6)
            mujoco.mj_contactForce(model, data, i, local)
            frame = data.contact.frame[i].reshape(3, 3)
            sign = _into(model, data, i, c.name)
            total += sign * (frame.T @ local[:3])  # on geom 2; ours may be 1
            at.append(data.contact.pos[i].copy())
            depth = max(depth, -float(data.contact.dist[i]))
            normal = sign * frame[0]
        if at:
            out[c.name] = _record(total, normal, float(c.mu), depth,
                                  np.mean(at, axis=0))
    return out


def _record(force, normal, mu, depth, point):
    n = float(force @ normal)
    friction = force - n * normal
    return ContactForce(n, _frozen(friction),
                        float(mu * n - np.linalg.norm(friction)), float(depth),
                        _frozen(point))


def _reach(compiled, body):
    """The directions `body`'s points can move in, by the joints between it
    and the world: a planar chain's plane, a chain of slides alone the span
    of their axes, and all three otherwise. A force across them is carried
    by the joints, which the solve has no rows for, so it is not asked."""
    joint_into = {j.child: j for j in compiled.description.joints}
    slides, at = [], body
    while at != WORLD:
        j = joint_into[at]
        if j.kind == "hinge" or j.kind == "free":
            return _directions(compiled, body, WORLD)
        if j.name not in compiled.description.locks:
            slides.append(np.array(j.axis, dtype=float))
        at = j.parent
    if not slides:
        return np.zeros((0, 3))
    _, s, vt = np.linalg.svd(np.array(slides))
    return vt[:int(np.sum(s > 1e-9 * s[0]))]


def _into(model, data, i, name):
    """+1 where contact `i`'s normal points into contact `name`'s moving
    shape, −1 where it points out. MuJoCo orders a pair's geoms by type, not
    as the pair wrote them: a plane always comes first, but a sphere comes
    before the box it rests on."""
    return 1.0 if int(data.contact.geom[i][1]) == model.geom(name).id else -1.0


def _found(model, data, name):
    """The indices of `data.contact` entries for contact `name`'s pair
    within `TOUCH`."""
    pair = {model.geom(f"{name}:against").id, model.geom(name).id}
    return [i for i in range(data.ncon)
            if set(int(g) for g in data.contact.geom[i]) == pair
            and data.contact.dist[i] <= TOUCH]


def roots(model, data, eps):
    """The continuous-time roots of `data`'s one-step map, linearised by
    `mjd_transitionFD` (central differences).

    Each eigenvalue λ of the map is turned back into s by inverting the
    semi-implicit Euler step the compiler pins: an undamped mode of root s
    steps with (λ − 1)²/λ = (s dt)², so s = (λ − 1)/(dt √λ), exactly. ln(λ)/dt
    would read a 112 rad/s mode 5e-4 high at dt = 1 ms."""
    n = 2 * model.nv + model.na
    a = np.zeros((n, n))
    mujoco.mjd_transitionFD(model, data, eps, True, a, None, None, None)
    lam = np.linalg.eigvals(a).astype(complex)
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (lam - 1) / (model.opt.timestep * np.sqrt(lam))
    s[~np.isfinite(s)] = -math.inf  # λ = 0: gone within the step
    return s


def split(first, second, timestep):
    """The roots of `first` that hold between the two contact stiffnesses,
    and the rest as (root at the first, its match at the second) pairs.
    Matching is one-to-one, nearest first. A root that moves, or that the
    timestep cannot resolve, is the solver's."""
    from scipy.optimize import linear_sum_assignment
    cost = np.abs(first[:, None] - second[None, :])
    cost[~np.isfinite(cost)] = 1e300
    rows, cols = linear_sum_assignment(cost)
    match = dict(zip(rows, cols))
    kept, gone = [], []
    for i, s in enumerate(first):
        t = second[match[i]]
        finite = np.isfinite(s) and np.isfinite(t)
        neutral = finite and max(abs(s), abs(t)) < ZERO_ROOT  # both zero
        holds = finite and abs(s) * timestep <= RESOLVED and (
            neutral or abs(s - t) <= MOVE_TOL * max(abs(s), abs(t)))
        (kept if holds else gone).append((s, t))
    return (np.array([s for s, _ in kept], dtype=complex),
            np.array(gone, dtype=complex).reshape(-1, 2))


def frequencies(kept):
    """The signed mode frequencies (Hz) of the kept roots, ascending: one
    per oscillating pair, |s|/2π, and one per diverging real root, negative.
    Neutral (zero) and decaying real roots are not modes; they stay in the
    roots."""
    out = []
    for s in kept:
        if abs(s.imag) > ZERO_ROOT:
            if s.imag > 0:
                out.append(abs(s) / (2 * math.pi))
        elif s.real > ZERO_ROOT:
            out.append(-s.real / (2 * math.pi))
    return np.sort(np.array(out, dtype=float))


def _frozen(array):
    array = np.array(array, dtype=float)
    array.flags.writeable = False
    return array
