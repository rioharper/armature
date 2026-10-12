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

The limits come from `params.py` until Overhaul 02 replaces this sampler
with its search.
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
    """A draw the sampler did not keep: `q`, as drawn, keyed by
    independent coordinate, and `reason`, what refused it. That is the
    constraint `at()` could not close (`"loop 'pin'"`), the joint closing
    would put out of range (`"joint 'B'"`), or the contact `rest_on` could
    not bring to touch (`"contact 'tyre'"`)."""
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
    draw = _plan(compiled, dict(poses or {}), dict(within or {}),
                 dict(rest_on or {}))
    postures, rates = (np.random.default_rng(s)
                       for s in np.random.SeedSequence(seed).spawn(2))
    states, accels, rejected, drawn = [], [], [], 0
    while len(states) < n:
        if drawn >= MAX_DRAWS * max(n, 1):
            reasons = Counter(r.reason for r in rejected)
            raise ValueError(f"only {len(states)} of {drawn} draws closed "
                             f"(n = {n}, seed = {seed}): {_listed(reasons)}")
        drawn += 1
        values = draw(postures)
        qd = qdd = None
        if limits:
            qd, qdd = ({d: float(rates.uniform(-lim, lim))
                        for d, lim in limit.items()} for limit in limits)
        try:
            state = (_rest(compiled, values, rest_on) if rest_on
                     else compiled.at(q=values, qd=qd))
        except _Refused as refused:
            rejected.append(Rejected(MappingProxyType(values), refused.reason))
            continue
        except ClosureError as refused:
            rejected.append(Rejected(MappingProxyType(values),
                                     refused.constraint))
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


# --- the plan: how each independent coordinate is drawn ------------------------
def _plan(compiled, poses, within, rest_on):
    """A function drawing one posture from a generator, keyed by
    independent coordinate, after checking every argument against
    `compiled`."""
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
    steps = []  # each takes the generator and fills the posture
    for name in compiled.independent:
        joint, component = compiled._coordinate[name]
        if joint.kind != "free":
            lo, hi = within.get(name, tuple(float(v) for v in joint.range))
            steps.append(_uniform(name, lo, hi))
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

    def draw(rng):
        values = {}
        for step in steps:
            step(rng, values)
        return values
    return draw


def _drawable(compiled, name, label):
    if name not in compiled.coordinates:
        raise ValueError(f"{label}: no coordinate named {name!r}; this "
                         f"mechanism has {list(compiled.coordinates)}")
    if name in compiled.dependent:
        raise ValueError(f"{label}: {name!r} closes the loops "
                         f"{list(compiled.constraints)}, so it is solved, not "
                         f"drawn; name the independent coordinates "
                         f"{list(compiled.independent)}")


def _uniform(name, lo, hi):
    def step(rng, values):
        values[name] = float(rng.uniform(lo, hi))
    return step


class _Free:
    """An unlocked floating body's draw: a `Placement` from its envelope."""

    def __init__(self, name, envelope, up):
        self.name, self.envelope, self.up = name, envelope, up
        # two level directions, so a lean can point any way round up
        other = AXES[int(np.argmin(np.abs(up)))]
        self.level = np.cross(up, other) / np.linalg.norm(np.cross(up, other))
        self.across = np.cross(up, self.level)

    def __call__(self, rng, values):
        box, tilt, yaw = self.envelope
        position = np.array([rng.uniform(lo, hi) for lo, hi in box])
        # uniform over the cap: cos θ uniform between cos(tilt) and 1
        lean = math.acos(1.0 - rng.random() * (1.0 - math.cos(tilt)))
        azimuth = rng.uniform(0.0, 2 * math.pi)
        heading = rng.uniform(*yaw)
        about = math.cos(azimuth) * self.level + math.sin(azimuth) * self.across
        rotation = turn(about, lean) @ turn(self.up, heading)
        values[self.name] = (position, rotation)


class _Chain:
    """A rebuilt floating body's draw: each of its independent components,
    the slides from the box and the turns within ±tilt or the yaw bounds,
    redrawn until the whole pose lies inside the envelope."""

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

    def __call__(self, rng, values):
        for _ in range(POSE_TRIES):
            drawn = {c: float(rng.uniform(lo, hi))
                     for c, lo, hi in self.components}
            position = [drawn.get(c, self.held_position.get(c))
                        for c in "xyz"]
            rotation = floating_rotation(
                self.held_turns, {c: v for c, v in drawn.items()
                                  if c.startswith("r")})
            if self.envelope.contains(position, rotation, self.up):
                values.update({f"{self.owner}:{c}": v
                               for c, v in drawn.items()})
                return
        raise ValueError(f"the pose envelope of {self.owner!r} holds no pose "
                         f"its chain allows: {POSE_TRIES} draws all fell "
                         f"outside it (held: {self.held_position})")


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
