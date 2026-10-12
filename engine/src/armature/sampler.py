"""The seeded sampler: states drawn uniformly over a mechanism's independent
coordinates, with every loop closed and every floating body inside a
declared pose envelope.

One sampler, so "over the envelope" is the same set of states in every
check that asks for it. Random, never named: home, outstretched and a
workspace corner are the mechanism's symmetry planes, where a wrong
assumption is invisible, and fixture 3's skid, reached only away from
α = 0, is the trap that pins it. Seeded, so a reviewer re-running a check
gets the states it was written from; every result prints n and the seed.

- A hinge or slide is drawn uniformly over its joint range, or a narrower
  `within` box, such as the intended workspace. Only the independent
  coordinates are drawn. `at()` solves the dependent ones, so every loop
  closes, and a draw it cannot close is counted under the constraint that
  refused it, never kept.
- A floating body is drawn from its `PoseEnvelope`. Its point is uniform in
  the box. Its up axis is uniform over the cap of directions within the tilt
  bound of gravity's up, and its yaw about up is uniform within the yaw
  bounds. A variant's rebuilt chain draws its slides from the box, its turns
  about level axes within ±tilt and about the upright within the yaw
  bounds, and keeps a draw only if the whole pose is inside the envelope.
- Contact takes no part in `at()`, so `rest_on` names, for each contact, a
  coordinate solved so that contact just touches: a torso's height, for a
  wheel on the floor.
- `sample_states` adds rates and accelerations, uniform within ± the limits
  it is given, both signs, so a dynamics claim is not checked at rest.

The core is a map, `unit_cube`: a point in [0, 1]^d to a state, or to a
rejection naming what refused it, the same state every time for the same
point. `sample` feeds it uniform draws from its seed. The sampler stays for
the truth checks, and Overhaul 02's search drives the same map with its own
points, so "over the envelope" is one set of states for both. The limits
come from `params.py`.
"""

import math
from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

import mujoco
import numpy as np

from .assembly import ClosureError
from .contact import TOUCH
from .contact import clearance as _clearance
from .rotations import AXES, floating_rotation, turn

DEFAULT_SAMPLES = 24  # small enough that a milestone's checks stay seconds,
    # large enough that a state off every symmetry plane is certain
DEFAULT_SEED = 20260915
MAX_DRAWS = 100       # per state asked for: past this many draws the sampler
                      # stops and reports what refused them
POSE_TRIES = 1000     # draws of a rebuilt chain's turns before its envelope
                      # is judged to hold no pose the chain allows
PLACE_TOL = 1e-10     # m: how near touching `rest_on` brings each contact,
                      # well inside `TOUCH`
PLACE_STEPS = 20
PLACE_EPS = 1e-7      # m or rad: rest_on's difference step
LEVEL_TOL = 1e-9      # how far a turn's axis may lean and still count as
                      # level or upright
ENVELOPE_TOL = 1e-12  # rad: the rounding a drawn pose may carry past its
                      # envelope's bounds
METHOD = ("uniform over the independent coordinates' ranges, loops closed "
          "by at()")


class PoseEnvelope(NamedTuple):
    """Where a floating body may be drawn. Its point lies inside `box`,
    three (low, high) pairs along the base axes (m). Its `tilt` (rad) is
    the most its home-up axis may lean from gravity's up. Its yaw lies
    within `yaw`, a (low, high) pair (rad); the yaw is the turn about up
    that is left once the tilt is taken out (a swing-twist split), zero at
    home. Make one with `pose_envelope`."""
    box: tuple
    tilt: float
    yaw: tuple

    def contains(self, position, rotation, up):
        """Whether the pose (`position`, `rotation`) lies inside, with tilt
        and yaw measured from `up`."""
        tilt, yaw = tilt_yaw(rotation, up)
        return (all(lo <= x <= hi for x, (lo, hi) in zip(position, self.box))
                and tilt <= self.tilt + ENVELOPE_TOL
                and self.yaw[0] - ENVELOPE_TOL <= yaw
                <= self.yaw[1] + ENVELOPE_TOL)


def pose_envelope(*, box, tilt, yaw):
    """A floating body's pose envelope: `box`, the point's (low, high) along
    x, y and z in the base frame (m); `tilt`, the largest lean of its
    home-up axis from gravity's up, 0 to π (rad); `yaw`, the (low, high)
    turn about up, within ±π (rad). A body free to turn any way is
    `tilt=math.pi, yaw=(-math.pi, math.pi)`."""
    try:
        box = tuple((float(lo), float(hi)) for lo, hi in box)
    except (TypeError, ValueError):
        box = ()
    if len(box) != 3:
        raise ValueError(f"a pose envelope's box is three (low, high) pairs, "
                         f"along x, y and z; got {box!r}")
    for axis, (lo, hi) in zip("xyz", box):
        if lo > hi:
            raise ValueError(f"the box's {axis} has its low above its high: "
                             f"({lo}, {hi})")
    tilt = float(tilt)
    if not 0.0 <= tilt <= math.pi:
        raise ValueError(f"tilt bounds a lean from up, 0 to π rad; got {tilt}")
    lo, hi = (float(v) for v in yaw)
    if not -math.pi <= lo <= hi <= math.pi:
        raise ValueError(f"yaw is a (low, high) pair within ±π rad, low "
                         f"first; got ({lo}, {hi})")
    return PoseEnvelope(box, tilt, (lo, hi))


def tilt_yaw(rotation, up):
    """The tilt and the yaw (rad) of `rotation` from unit `up`: the angle
    the turned up axis leans from up, and the turn about up left once that
    lean is taken out (the twist of a swing-twist split), in [−π, π]."""
    rotation = np.asarray(rotation, dtype=float)
    leaned = rotation @ up
    tilt = math.atan2(np.linalg.norm(np.cross(up, leaned)), up @ leaned)
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, np.ascontiguousarray(rotation).ravel())
    yaw = math.remainder(2 * math.atan2(quat[1:] @ up, quat[0]), 2 * math.pi)
    return tilt, yaw


class Rejected(NamedTuple):
    """A draw the sampler did not keep, or a point the map refused: `q`, as
    drawn, keyed by independent coordinate (less any `rest_on` solves), and
    `reason`, what refused it. That is the constraint `at()` could not
    close (`"loop 'pin'"`), the joint closing would put out of range
    (`"joint 'B'"`), the contact `rest_on` could not bring to touch
    (`"contact 'tyre'"`), or the envelope a rebuilt chain's pose fell
    outside (`"pose envelope 'base'"`)."""
    q: MappingProxyType
    reason: str


@dataclass(frozen=True, eq=False)
class Samples:
    """`n` states drawn from `seed`, in the order drawn.

    `qdd`, from `sample_states`, holds each state's accelerations keyed by
    independent dof, as `inverse` takes them; from `sample` it is None and
    the states are at rest. `drawn` counts every draw, and `rejected` holds
    each one not kept, with its reason. `clearance` gives, for each
    contact, its clearance at each state (m, negative where its shapes
    interpenetrate). `residual` is the largest closure gap over the states
    (m). Print it to get n and the seed beside the result it backs.
    """
    states: tuple
    qdd: tuple
    n: int
    seed: int
    drawn: int
    rejected: tuple
    clearance: MappingProxyType
    residual: float
    method: str

    def __len__(self):
        return len(self.states)

    def __iter__(self):
        return iter(self.states)

    @property
    def reasons(self):
        """How many draws each reason refused."""
        return MappingProxyType(dict(Counter(r.reason for r in self.rejected)))

    def reached(self, contact):
        """The states at which `contact` touches or interpenetrates: its
        clearance is within `TOUCH`."""
        if contact not in self.clearance:
            raise KeyError(f"no contact named {contact!r}; this mechanism has "
                           f"{list(self.clearance)}")
        return tuple(s for s, gap in zip(self.states, self.clearance[contact])
                     if gap <= TOUCH)

    def __str__(self):
        text = (f"{len(self.states)} states (n = {self.n}, seed = "
                f"{self.seed}), {self.method}")
        if self.rejected:
            text += (f"; {len(self.rejected)} of {self.drawn} draws refused "
                     f"({_listed(self.reasons)})")
        else:
            text += f"; all {self.drawn} draws kept"
        if self.clearance:
            text += "; contacts reached: " + ", ".join(
                f"{c}: {len(self.reached(c))} of {len(self.states)}"
                for c in self.clearance)
        return text


def sample(compiled, n=DEFAULT_SAMPLES, seed=DEFAULT_SEED, *, poses=None,
           within=None, rest_on=None):
    """`n` states of `compiled`, at rest, drawn reproducibly from `seed`.

    Each independent hinge or slide is drawn uniformly over its joint range,
    or over `within[name]`, a (low, high) inside it. Each floating body is
    drawn from `poses[joint]`, a `pose_envelope`; a floating body without
    one is refused, since a free joint has no range. `at()` closes every
    loop, and a draw it cannot close is counted in `rejected`. `rest_on`
    maps a contact to an independent hinge or slide that is solved, not
    drawn, so that contact just touches at every state: `{"tyre": "y"}`
    lifts a torso until its wheel meets the floor.

    Returns a `Samples`. Raises when fewer than one draw in `MAX_DRAWS`
    yields a state, naming what refused them.
    """
    return _sample(compiled, n, seed, poses, within, rest_on, None)


def sample_states(compiled, n=DEFAULT_SAMPLES, seed=DEFAULT_SEED, *,
                  qd_limits, qdd_limits, poses=None, within=None,
                  rest_on=None):
    """`n` states with rates and accelerations: `sample`'s postures, from
    the same seed, with each independent dof's rate drawn uniformly within
    ±`qd_limits[dof]` and its acceleration within ±`qdd_limits[dof]`.

    Both limits are keyed by dof (a floating body's `f:x` … `f:rz`), and
    each must name every independent dof and nothing else. On a closed
    chain the dependent rates are solved so the loops stay closed, and the
    accelerations, in `Samples.qdd`, are keyed by the independent dofs, as
    `inverse` takes them. A contact's rates are not solved, so `rest_on`
    is refused here: it places postures only.
    """
    if rest_on:
        raise ValueError("rest_on places postures only: the rates a "
                         "resting contact allows are not solved, so a "
                         "sampled rate would lift it or drive it in")
    limits = (_limits(compiled, qd_limits, "qd_limits"),
              _limits(compiled, qdd_limits, "qdd_limits"))
    return _sample(compiled, n, seed, poses, within, None, limits)


def _sample(compiled, n, seed, poses, within, rest_on, limits):
    n = int(n)
    cube = unit_cube(compiled, poses=poses, within=within, rest_on=rest_on)
    postures, rates = (np.random.default_rng(s)
                       for s in np.random.SeedSequence(seed).spawn(2))
    states, accels, rejected, drawn = [], [], [], 0
    while len(states) < n:
        if drawn >= MAX_DRAWS * max(n, 1):
            reasons = Counter(r.reason for r in rejected)
            raise ValueError(f"only {len(states)} of {drawn} draws closed "
                             f"(n = {n}, seed = {seed}): {_listed(reasons)}")
        drawn += 1
        point = cube._draw(postures)
        qd = qdd = None
        if limits:
            qd, qdd = ({d: float(rates.uniform(-lim, lim))
                        for d, lim in limit.items()} for limit in limits)
        state = cube._state(point, qd)
        if isinstance(state, Rejected):
            rejected.append(state)
            continue
        states.append(state)
        if limits:
            accels.append(MappingProxyType(qdd))
    gaps, residual = _measured(compiled, states)
    return Samples(tuple(states), tuple(accels) if limits else None, n,
                   seed, drawn, tuple(rejected), gaps, residual, METHOD)


def clearance(state, contact):
    """How far apart `contact`'s two shapes are at `state` (m), negative
    where they interpenetrate. A contact touches within `TOUCH`."""
    names = [c.name for c in state.compiled.description.contacts]
    if contact not in names:
        raise KeyError(f"no contact named {contact!r}; this mechanism has "
                       f"{names}")
    return _clearance(state.compiled.model, state._data(), contact)


# --- the map: a point in the unit cube to a state -----------------------------
class UnitCube:
    """The map from a point in the unit cube to a state of `compiled`: what
    `sample` feeds from its seed, and the search drives with its own
    points. Make one with `unit_cube`.

    `axes` names the cube's `d` axes, in the order a point lists them, 0 at
    each one's low end and 1 at its high:
    - an independent hinge or slide, by its coordinate name, over its joint
      range or `within`;
    - a floating body, as `name:x`, `name:y` and `name:z` across its box,
      then `name:tilt`, the share of the cap of up directions within its
      tilt bound (0 upright, 1 the full lean, so equal steps cover equal
      areas of the cap), `name:azimuth`, which way round up it leans, and
      `name:yaw`, within its yaw bounds;
    - a rebuilt chain, by its free components' coordinate names, each over
      the box or within ±tilt or the yaw bounds. Those bounds can hold
      poses the envelope does not (two tilts at once lean further than
      either), and such a point is rejected, naming the envelope. It is
      never redrawn: the map draws nothing of its own, so a search reads
      the miss as outside the space.
    A coordinate `rest_on` solves is not an axis.
    """

    def __init__(self, compiled, steps, rest_on):
        self.compiled, self._steps, self._rest_on = compiled, steps, rest_on
        self.axes = tuple(axis for step in steps for axis in step.axes)

    @property
    def d(self):
        """How many axes the cube has."""
        return len(self.axes)

    def map(self, points):
        """The state at each of `points`, an (n, d) array with every value
        in [0, 1], in order: a `State` at rest, or a `Rejected` naming the
        loop, joint, contact or pose envelope that refused the point. The
        same point gives the same state every time."""
        points = np.asarray(points, dtype=float)
        if points.ndim != 2 or points.shape[1] != self.d:
            raise ValueError(f"points are an (n, {self.d}) array, one row per "
                             f"point along the {self.d} axes "
                             f"{list(self.axes)}; got shape {points.shape}")
        outside = ~((0.0 <= points) & (points <= 1.0))  # NaN is outside too
        if outside.any():
            row = int(np.argwhere(outside)[0][0])
            raise ValueError(f"a point lies in the unit cube, every value in "
                             f"[0, 1]; point {row} is "
                             f"{points[row].tolist()}")
        return tuple(self._state(point) for point in points.tolist())

    def _state(self, point, qd=None):
        """The state at `point`, a list of d floats, with rates `qd`, or the
        `Rejected` that refused it."""
        values, start, outside = {}, 0, None
        for step in self._steps:
            outside = (step.place(point[start:start + len(step.axes)], values)
                       or outside)
            start += len(step.axes)
        if outside:
            return Rejected(MappingProxyType(values), outside)
        try:
            if self._rest_on:
                return _rest(self.compiled, values, self._rest_on)
            return self.compiled.at(q=values, qd=qd)
        except _Refused as refused:
            return Rejected(MappingProxyType(values), refused.reason)
        except ClosureError as refused:
            return Rejected(MappingProxyType(values), refused.constraint)

    def _draw(self, rng):
        """A point drawn uniformly from `rng`, number for number as the
        sampler has always drawn it: a coordinate `rest_on` solves still
        spends its draw, and a rebuilt chain is redrawn until its pose lies
        inside the envelope."""
        point = []
        for step in self._steps:
            point += step.draw(rng)
        return point


def unit_cube(compiled, *, poses=None, within=None, rest_on=None):
    """The `UnitCube` mapping a point in [0, 1]^d to a state of `compiled`,
    with `poses`, `within` and `rest_on` as `sample` takes them and checked
    as it checks them. `axes` gives the order of a point's values, and `d`
    their number."""
    poses, within, rest_on = (dict(poses or {}), dict(within or {}),
                              dict(rest_on or {}))
    description = compiled.description
    floating = {j.name: j for j in description.joints if j.kind == "free"}
    scalar = {n: compiled._coordinate[n][0] for n in compiled.coordinates
              if compiled._coordinate[n][0].kind != "free"}
    contacts = {c.name for c in description.contacts}

    for name, box in within.items():
        _drawable(compiled, name, "within")
        if name not in scalar:
            raise ValueError(f"within: {name!r} belongs to a floating body; "
                             f"it is drawn from its pose envelope")
        lo, hi = (float(v) for v in box)
        if lo > hi:
            raise ValueError(f"within: {name!r} has its low above its high: "
                             f"({lo}, {hi})")
        joint_lo, joint_hi = (float(v) for v in scalar[name].range)
        if lo < joint_lo or hi > joint_hi:
            raise ValueError(f"within: ({lo}, {hi}) lies outside {name}'s "
                             f"range ({joint_lo}, {joint_hi})")
        within[name] = (lo, hi)
    solved = set()
    for contact, name in rest_on.items():
        if contact not in contacts:
            raise ValueError(f"rest_on: no contact named {contact!r}; this "
                             f"mechanism has {sorted(contacts)}")
        _drawable(compiled, name, "rest_on")
        if compiled._coordinate[name][1] is None and name not in scalar:
            raise ValueError(f"rest_on: {name!r} is a floating body's "
                             f"placement; name a hinge or a slide")
        if name in within or name in solved:
            raise ValueError(f"rest_on: {name!r} is drawn or solved twice")
        solved.add(name)
    unknown = sorted(set(poses) - set(floating))
    if unknown:
        raise ValueError(f"poses: no floating body's joint named {unknown}; "
                         f"this mechanism has {sorted(floating)}")

    gravity = np.array(description.gravity, dtype=float)
    up = -gravity / np.linalg.norm(gravity) if gravity.any() else None
    steps = []  # each spans its axes and fills its part of the posture
    for name in compiled.independent:
        joint, component = compiled._coordinate[name]
        if joint.kind != "free":
            lo, hi = within.get(name, tuple(float(v) for v in joint.range))
            steps.append(_Solved() if name in solved
                         else _Uniform(name, lo, hi))
        elif component is None or not any(s.owner == joint.name for s in steps
                                          if isinstance(s, _Chain)):
            envelope = poses.get(joint.name)
            if envelope is None:
                raise ValueError(
                    f"{joint.name!r} is a floating body: give its pose "
                    f"envelope, poses={{{joint.name!r}: pose_envelope(box=..."
                    f", tilt=..., yaw=...)}}")
            if up is None:
                raise ValueError(f"{joint.name!r}: a pose envelope's tilt and "
                                 f"yaw are measured from gravity's up, and "
                                 f"this mechanism has no gravity")
            steps.append(_Free(name, envelope, up) if component is None
                         else _Chain(compiled, joint, envelope, up))
    return UnitCube(compiled, tuple(steps), rest_on)


def _drawable(compiled, name, label):
    if name not in compiled.coordinates:
        raise ValueError(f"{label}: no coordinate named {name!r}; this "
                         f"mechanism has {list(compiled.coordinates)}")
    if name in compiled.dependent:
        raise ValueError(f"{label}: {name!r} closes the loops "
                         f"{list(compiled.constraints)}, so it is solved, not "
                         f"drawn; name the independent coordinates "
                         f"{list(compiled.independent)}")


# Each step spans `axes`, places its part of a posture from its slice of a
# point (returning the envelope its pose falls outside, if any), and draws
# that slice from a generator as the sampler always has.
def _between(lo, hi, u):
    """lo + (hi − lo)·u, as NumPy's `uniform` computes it, so a seeded draw
    lands where it always did; never past hi, so the cube's corner 1 is the
    range's end."""
    return min(hi, lo + (hi - lo) * u)


class _Uniform:
    """An independent hinge or slide, over (lo, hi)."""

    def __init__(self, name, lo, hi):
        self.axes, self.lo, self.hi = (name,), lo, hi

    def draw(self, rng):
        return [rng.random()]

    def place(self, u, values):
        values[self.axes[0]] = _between(self.lo, self.hi, u[0])


class _Solved:
    """A hinge or slide `rest_on` solves: no axis. Its draw is still spent,
    and thrown away, so the draws after it fall where they always did."""
    axes = ()

    def draw(self, rng):
        rng.random()
        return []

    def place(self, u, values):
        pass


class _Free:
    """An unlocked floating body: a `Placement` from its envelope."""

    def __init__(self, name, envelope, up):
        self.name, self.envelope, self.up = name, envelope, up
        self.axes = tuple(f"{name}:{a}" for a in ("x", "y", "z", "tilt",
                                                  "azimuth", "yaw"))
        # two level directions, so a lean can point any way round up
        other = AXES[int(np.argmin(np.abs(up)))]
        self.level = np.cross(up, other) / np.linalg.norm(np.cross(up, other))
        self.across = np.cross(up, self.level)

    def draw(self, rng):
        return [rng.random() for _ in self.axes]

    def place(self, u, values):
        box, tilt, yaw = self.envelope
        position = np.array([_between(lo, hi, v) for (lo, hi), v
                             in zip(box, u)])
        # uniform over the cap: cos θ uniform between cos(tilt) and 1
        lean = math.acos(1.0 - u[3] * (1.0 - math.cos(tilt)))
        azimuth = _between(0.0, 2 * math.pi, u[4])
        heading = _between(*yaw, u[5])
        about = math.cos(azimuth) * self.level + math.sin(azimuth) * self.across
        rotation = turn(about, lean) @ turn(self.up, heading)
        values[self.name] = (position, rotation)


class _Chain:
    """A rebuilt floating body: each of its independent components, the
    slides from the box and the turns within ±tilt or the yaw bounds. A
    pose outside the envelope is refused by the map, and redrawn by the
    seeded draw."""

    def __init__(self, compiled, joint, envelope, up):
        self.owner, self.envelope, self.up = joint.name, envelope, up
        locks = compiled.description.locks
        held = {c: float(locks[f"{joint.name}:{c}"].at)
                for c in ("x", "y", "z", "rx", "ry", "rz")
                if f"{joint.name}:{c}" in locks}
        self.held_position = held
        self.held_turns = {c: v for c, v in held.items() if c.startswith("r")}
        free = [c for c in ("x", "y", "z", "rx", "ry", "rz")
                if c not in held]
        solved = [c for c in free if f"{joint.name}:{c}" in compiled.dependent]
        if solved:
            raise ValueError(f"{joint.name!r}: {solved} of this floating body "
                             f"are solved by a closure; sampling such a body "
                             f"is not supported yet")
        facing = floating_rotation(self.held_turns, {})
        self.components = []  # (component, low, high)
        for c in free:
            if not c.startswith("r"):
                self.components.append((c, *envelope.box["xyz".index(c)]))
                continue
            axis = facing @ AXES[("rx", "ry", "rz").index(c)]
            if abs(axis @ up) < LEVEL_TOL:
                self.components.append((c, -envelope.tilt, envelope.tilt))
            elif np.linalg.norm(np.cross(axis, up)) < LEVEL_TOL:
                lo, hi = envelope.yaw if axis @ up > 0 else (-envelope.yaw[1],
                                                             -envelope.yaw[0])
                self.components.append((c, lo, hi))
            else:
                raise ValueError(
                    f"'{joint.name}:{c}' turns about {axis.round(6).tolist()}, "
                    f"neither level nor upright, so neither the tilt nor the "
                    f"yaw bounds it")
        self.axes = tuple(f"{self.owner}:{c}" for c, _, _ in self.components)

    def draw(self, rng):
        for _ in range(POSE_TRIES):
            u = [rng.random() for _ in self.components]
            if self._inside(self._components(u)):
                return u
        raise ValueError(f"the pose envelope of {self.owner!r} holds no pose "
                         f"its chain allows: {POSE_TRIES} draws all fell "
                         f"outside it (held: {self.held_position})")

    def place(self, u, values):
        drawn = self._components(u)
        values.update({f"{self.owner}:{c}": v for c, v in drawn.items()})
        return None if self._inside(drawn) else f"pose envelope {self.owner!r}"

    def _components(self, u):
        return {c: _between(lo, hi, v)
                for (c, lo, hi), v in zip(self.components, u)}

    def _inside(self, drawn):
        position = [drawn.get(c, self.held_position.get(c)) for c in "xyz"]
        rotation = floating_rotation(
            self.held_turns, {c: v for c, v in drawn.items()
                              if c.startswith("r")})
        return self.envelope.contains(position, rotation, self.up)


# --- resting contacts, and what the states measure ----------------------------
class _Refused(Exception):
    def __init__(self, reason):
        self.reason = reason


def _rest(compiled, values, rest_on):
    """The state at `values` with each `rest_on` coordinate solved, by
    Newton on the clearances, so each contact just touches."""
    contacts, names = list(rest_on), list(rest_on.values())
    reason = ", ".join(f"contact {c!r}" for c in contacts)
    x = np.array([compiled.home(n) for n in names], dtype=float)

    def at(guess):
        try:
            return compiled.at(q=values | dict(zip(names, map(float, guess))))
        except ClosureError:
            raise
        except ValueError:  # the solve has left a joint's range
            raise _Refused(reason) from None

    for _ in range(PLACE_STEPS):
        state = at(x)
        gap = _gaps(state, contacts)
        if np.max(np.abs(gap)) <= PLACE_TOL:
            return state
        slope = np.empty((len(contacts), len(names)))
        for j in range(len(names)):
            nudged = x.copy()
            nudged[j] += PLACE_EPS
            slope[:, j] = (_gaps(at(nudged), contacts) - gap) / PLACE_EPS
        x = x - np.linalg.lstsq(slope, gap, rcond=None)[0]
    raise _Refused(reason)


def _gaps(state, contacts):
    data = state._data()
    return np.array([_clearance(state.compiled.model, data, c)
                     for c in contacts])


def _measured(compiled, states):
    """Each contact's clearance at each state, and the largest closure gap
    over them."""
    contacts = [c.name for c in compiled.description.contacts]
    gaps, residual = {c: [] for c in contacts}, 0.0
    for s in states:
        data = s._data()
        for c in contacts:
            gaps[c].append(_clearance(compiled.model, data, c))
        if compiled.closure:
            gap, _ = compiled.closure.rows(data)
            residual = max(residual, float(np.max(np.abs(gap), initial=0.0)))
    return (MappingProxyType({c: tuple(v) for c, v in gaps.items()}),
            residual)


def _limits(compiled, limits, label):
    """`limits` checked against the independent dofs, in dof order."""
    limits = dict(limits)
    independent = [d for d in compiled.dofs if d not in compiled.dependent]
    unknown = sorted(set(limits) - set(compiled.dofs))
    if unknown:
        raise ValueError(f"{label}: no dof named {unknown}; this mechanism "
                         f"has {list(compiled.dofs)}")
    solved = sorted(set(limits) & set(compiled.dependent))
    if solved:
        raise ValueError(f"{label}: {solved} closing the loops "
                         f"{list(compiled.constraints)} are solved, not drawn; "
                         f"limit the independent dofs {independent}")
    missing = [d for d in independent if d not in limits]
    if missing:
        raise ValueError(f"{label}: no limit for {missing}; a dof left out "
                         f"would be sampled at rest only")
    negative = {d: v for d, v in limits.items() if float(v) < 0}
    if negative:
        raise ValueError(f"{label}: {negative} are negative; a limit is a "
                         f"magnitude, drawn in both signs")
    return {d: float(limits[d]) for d in independent}


def _listed(counts):
    return ", ".join(f"{reason}: {count}" for reason, count in counts.items())
