"""The worst-case search: one search over a named space, for every margin
(ADR 0005).

A margin is slack, available minus required against a limit with its
derating already applied, written as `fn(point)` over a `Space` of named
axes. Slack ≥ 0 passes, and −∞ is a legal value. `search(margin)` finds the
worst, and a project declares margins rather than writing searches, so no
worst case is read at a posture, direction, sign or band value somebody
happened to pick.

The method is fixed, because each knob would be a way to under-search:

- `Choice` axes are enumerated, never searched, and the result keeps the
  worst of each combination.
- For each combination, the continuous axes are searched in their unit
  cube: a scrambled, seeded Sobol set, then every corner (an interval's
  ends, a direction's axis directions in both signs), then bounded Powell
  from the best few points.
- The result is the minimum over every point evaluated. The polish does not
  always improve on its start: at a kink, its line search closes in on the
  optimum without landing on it and ends worse, so its own answer is never
  the result.

The polish's bounds reach `REACH` past the unit cube, and a point beyond it
is evaluated at the nearest face, so a line search lands exactly on a face
rather than within its tolerance of one. Bounded at the cube itself, Powell
stalls once a coordinate reaches a face: every direction mixing that
coordinate in is cut to nothing, and on the 2R arm's golden it stopped 1e-4
short after 2,000 evaluations.

A point `fn` cannot evaluate, such as a loop that cannot close or a settle
that does not come to rest, raises `Infeasible(reason)`. It is counted
under its reason, never reported as the worst, and ranks last during the
polish. A design failing there, a cable going slack or a contact lifting,
is a number, never an `Infeasible`. A `nan` is an error naming the point.

Two axes touch the mechanism. A `Band` is a parameter's tolerance band, and
`Coordinates` its independent coordinates as a ready `State`, compiled
with the point's band values and placed by the sampler's map, so the
search and the sampler mean one set of states by "over the envelope". A
point the map refuses is `Infeasible`, under the loop, joint or envelope
that refused it.

Probed on 2026-10-11, pure sampling never landed on either golden worst
case even at 10⁴ points; this method matched both closed forms in about
650 evaluations.
"""

import itertools
import math
from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

import numpy as np
from scipy.optimize import minimize
from scipy.stats import qmc

from .compiler import compile
from .sampler import Rejected, unit_cube
from .state import Placement

DEFAULT_SEED = 20261011
SOBOL_PER_DIM = 64    # global points per continuous dimension, before
                      # rounding up to a power of two
POLISH_STARTS = 3
POLISH_PER_DIM = 100  # evaluations per Powell start per continuous dimension
POLISH_XTOL = 1e-6    # in the unit cube: each line search's bracket
POLISH_FTOL = 1e-10   # relative: a start stops on its evaluation cap, or once
                      # an iteration gains less than this
REACH = 0.05          # how far past each face of the unit cube the polish
                      # may step; it evaluates there at the face
SNAP = 1e-15          # a direction's component this small is zero, so an
                      # axis direction reads exactly
PLANES = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}


class Infeasible(Exception):
    """Raised by a margin's `fn` at a point outside the space: a loop that
    cannot close, a settle that does not come to rest, a pose outside the
    envelope. `reason` says which, and the search counts it under that."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = str(reason)


class _Axis:
    """A named axis of a `Space`. A continuous axis takes `dims` coordinates
    of the search's unit cube: `value(u)` maps them to what `fn` reads,
    `corners()` lists the unit coordinates the search always evaluates, and
    `plain(value)` writes a value into a `Worst`'s `at`. A `Choice` takes
    none and is enumerated instead."""
    dims = 0

    def corners(self):
        raise NotImplementedError

    def value(self, u):
        raise NotImplementedError

    def plain(self, value):
        return value


@dataclass(frozen=True)
class Interval(_Axis):
    """A continuous value in [lo, hi] that does not change the model. Its
    corners are its ends."""
    lo: float
    hi: float
    dims = 1

    def __post_init__(self):
        lo, hi = float(self.lo), float(self.hi)
        if not (math.isfinite(lo) and math.isfinite(hi)):
            raise ValueError(f"an interval's ends are finite; got ({lo}, {hi})")
        if not lo < hi:
            raise ValueError(f"an interval has its low below its high; got "
                             f"({lo}, {hi})")
        object.__setattr__(self, "lo", lo)
        object.__setattr__(self, "hi", hi)

    def corners(self):
        return ((0.0,), (1.0,))

    def value(self, u):
        if u[0] == 1.0:
            return self.hi
        return self.lo + u[0] * (self.hi - self.lo)


@dataclass(frozen=True)
class Choice(_Axis):
    """Discrete values (load cases, signs, leg laws), enumerated and never
    searched. The result keeps the worst of each combination."""
    values: tuple

    def __post_init__(self):
        if isinstance(self.values, (str, bytes)) or not hasattr(
                self.values, "__iter__"):
            raise TypeError(f"a choice takes a sequence of values; got "
                            f"{self.values!r}")
        values = tuple(self.values)
        if not values:
            raise ValueError("a choice takes at least one value")
        object.__setattr__(self, "values", values)


@dataclass(frozen=True)
class Direction(_Axis):
    """A unit vector in the base frame, as a read-only array: in the `"xy"`,
    `"xz"` or `"yz"` plane, searched as one angle, or anywhere on the
    `"sphere"`, searched as two (an azimuth, and a height uniform in
    [−1, 1], so the global set is uniform over the sphere's area). Its
    corners are the axis directions it can point along, in both signs: four
    for a plane, six for the sphere."""
    kind: str

    def __post_init__(self):
        if self.kind not in (*PLANES, "sphere"):
            raise ValueError(f"a direction lies in 'xy', 'xz', 'yz' or "
                             f"'sphere'; got {self.kind!r}")

    @property
    def dims(self):
        return 2 if self.kind == "sphere" else 1

    def corners(self):
        if self.kind == "sphere":
            return ((0.5, 0.0), (0.5, 1.0), (0.0, 0.5), (0.25, 0.5),
                    (0.5, 0.5), (0.75, 0.5))
        return ((0.0,), (0.25,), (0.5,), (0.75,))

    def value(self, u):
        turn = math.pi * (2 * u[0] - 1)
        vector = np.zeros(3)
        if self.kind == "sphere":
            height = 2 * u[1] - 1
            across = math.sqrt(max(0.0, 1 - height * height))
            vector[:] = (across * math.cos(turn), across * math.sin(turn),
                         height)
        else:
            vector[list(PLANES[self.kind])] = math.cos(turn), math.sin(turn)
        vector[np.abs(vector) < SNAP] = 0.0
        vector.flags.writeable = False
        return vector

    def plain(self, value):
        return tuple(float(c) for c in value)


@dataclass(frozen=True, init=False, repr=False)
class Band(Interval):
    """A parameter's tolerance band: `Band("m2", BANDS)` spans
    `BANDS["m2"]`, a (low, high) pair, and its corners are both ends. The
    mapping is an argument, so the engine reads no project file; the
    template passes `params.BANDS`. In a space with `Coordinates`, each
    band's value overrides its parameter before the state is compiled, and
    the space checks, before anything compiles, that the parameter is one
    of the mechanism's and that its nominal lies within its band. `fn`
    reads the value by axis name, as `p.m2`."""
    param: str

    def __init__(self, param, bands):
        if param not in bands:
            raise ValueError(f"no band named {param!r}; the bands are "
                             f"{sorted(bands)}")
        try:
            lo, hi = (float(v) for v in bands[param])
        except (TypeError, ValueError):
            raise ValueError(f"band {param!r} is a (low, high) pair; got "
                             f"{bands[param]!r}") from None
        object.__setattr__(self, "param", param)
        object.__setattr__(self, "lo", lo)
        object.__setattr__(self, "hi", hi)
        try:
            self.__post_init__()
        except ValueError as err:
            raise ValueError(f"band {param!r}: {err}") from None

    def __repr__(self):
        return f"Band({self.param!r}, ({self.lo!r}, {self.hi!r}))"


class Coordinates(_Axis):
    """A mechanism's independent coordinates, as a ready `State` at rest:
    `Coordinates(mechanism, params, within=None, poses=None)`, with
    `within` and `poses` as `armature.sample` takes them. Name the axis
    `state` and `fn` reads `p.state`.

    Each point is mapped by the sampler's `unit_cube`: every hinge and
    slide over its joint range or `within`, every loop closed, every
    floating body inside its pose envelope. Its corners are the corners of
    those ranges. A point the map refuses, a loop that cannot close or a
    pose outside the envelope, raises `Infeasible` with the map's reason,
    such as `"loop 'pin'"`. In a `Worst`'s `at` the state is written as its
    independent coordinates, by name.

    The mechanism compiles once at `params`, when the space is made, which
    fixes the axes: a space's dimension is known before it is searched.
    Where the space has a `Band`, each point compiles again with its band
    values (1–3 ms), and a band that would change the axes raises. The
    nominal compile and the last are kept, so a space without a band, or a
    run of points with the same band values, compiles once. Like the
    compiled model, it is for one thread at a time."""

    def __init__(self, mechanism, params, within=None, poses=None):
        self.mechanism, self.params = mechanism, MappingProxyType(dict(params))
        self.within = MappingProxyType(dict(within or {}))
        self.poses = MappingProxyType(dict(poses or {}))
        self._nominal = self._last = None  # each a (band values, UnitCube)

    @property
    def dims(self):
        return self._cube({}).d

    def corners(self):
        return tuple(itertools.product((0.0, 1.0), repeat=self.dims))

    def value(self, u, bands=None):
        """The state at unit coordinates `u`, compiled with `bands`, each
        parameter's value by name; raises `Infeasible` where the map refuses
        the point."""
        state = self._cube(bands or {}).map([u])[0]
        if isinstance(state, Rejected):
            raise Infeasible(state.reason)
        return state

    def plain(self, value):
        return {n: _plain(value.q[n]) for n in value.compiled.independent}

    def _check(self, band):
        """Raises unless `band` names one of `params`, with its nominal
        within the band."""
        if band.param not in self.params:
            raise ValueError(f"band {band.param!r} names no parameter of "
                             f"this mechanism; its parameters are "
                             f"{sorted(self.params)}")
        nominal = self.params[band.param]
        if not band.lo <= nominal <= band.hi:
            raise ValueError(f"band {band.param!r}: its nominal {nominal!r} "
                             f"lies outside the band ({band.lo!r}, "
                             f"{band.hi!r})")

    def _cube(self, bands):
        """The map at `bands`, compiled, or kept from the last call there;
        a band at its nominal value is no change."""
        bands = {p: v for p, v in bands.items() if v != self.params[p]}
        key = tuple(sorted(bands.items()))
        for kept in (self._last, self._nominal):
            if kept is not None and kept[0] == key:
                return kept[1]
        cube = unit_cube(compile(self.mechanism, {**self.params, **bands}),
                         poses=self.poses, within=self.within)
        if self._nominal is None and not key:
            self._nominal = (key, cube)
            return cube
        axes = self._cube({}).axes
        if cube.axes != axes:
            raise ValueError(f"the band values {dict(bands)} change the "
                             f"mechanism's coordinates from {list(axes)} to "
                             f"{list(cube.axes)}; a band may change numbers, "
                             f"not the coordinates searched")
        self._last = (key, cube)
        return cube

    def __repr__(self):
        name = getattr(self.mechanism, "__name__", None) or repr(
            self.mechanism)
        return f"Coordinates({name})"


def _plain(value):
    if isinstance(value, Placement):
        return (tuple(float(c) for c in value.position),
                tuple(tuple(float(c) for c in row) for row in value.rotation))
    return float(value)


class Space:
    """The named axes a margin is searched over, in the order given:
    `Space(q1=Interval(-math.pi, math.pi), load=Direction("xy"),
    case=Choice(LOAD_CASES))`.

    A space holds at most one `Coordinates`, and each band once. Every
    `Band` is checked against the `Coordinates`' parameters before the
    mechanism compiles, and then the mechanism compiles at nominal, so a
    bad band, `within` or envelope raises here rather than mid-search."""

    def __init__(self, **axes):
        for name, axis in axes.items():
            if not isinstance(axis, _Axis):
                raise TypeError(f"{name!r} is not an axis: a space takes "
                                f"Interval, Choice, Direction, Band and "
                                f"Coordinates; got {axis!r}")
            if name.startswith("_"):
                raise ValueError(f"an axis name may not start with an "
                                 f"underscore; got {name!r}")
        mechanisms = [n for n, a in axes.items() if isinstance(a, Coordinates)]
        if len(mechanisms) > 1:
            raise ValueError(f"a space holds one Coordinates, which every "
                             f"band compiles into; got {mechanisms}")
        bands = [a for a in axes.values() if isinstance(a, Band)]
        twice = sorted(p for p, k in Counter(b.param for b in bands).items()
                       if k > 1)
        if twice:
            raise ValueError(f"the bands {twice} appear twice; a parameter "
                             f"takes one value at a point")
        self.axes = MappingProxyType(dict(axes))
        if mechanisms:
            coordinates = axes[mechanisms[0]]
            for band in bands:
                coordinates._check(band)
            coordinates.dims  # compiles at nominal, fixing the axes

    @property
    def dims(self):
        """The continuous dimensions: the unit cube the search works in."""
        return sum(a.dims for a in self.axes.values())

    def __repr__(self):
        return "Space(" + ", ".join(f"{n}={a!r}"
                                    for n, a in self.axes.items()) + ")"


class Point:
    """One point of a space, as a margin's `fn` receives it: each axis's
    value by name, `p.q1` or `p["q1"]`, a band's as its value and
    `Coordinates`' as a ready `State`, `p.state`. The search's flat vector
    never reaches `fn`."""
    __slots__ = ("_values",)

    def __init__(self, values):
        object.__setattr__(self, "_values", MappingProxyType(dict(values)))

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(f"no axis named {name!r}; this space has "
                                 f"{list(self._values)}") from None

    def __getitem__(self, name):
        return self._values[name]

    def __setattr__(self, name, value):
        raise AttributeError("a point is read-only")

    def __iter__(self):
        return iter(self._values)

    def __repr__(self):
        return "Point(" + ", ".join(f"{n}={v!r}" for n, v
                                    in self._values.items()) + ")"


@dataclass(frozen=True)
class Budget:
    """What a search spends per `Choice` combination. `global_points` is
    the Sobol set's size, rounded up to a power of two so the set keeps its
    balance (default 64 per continuous dimension); `polish_starts` the
    number of best points Powell starts from (default 3); `polish_evals`
    the evaluations each start may spend (default 100 per continuous
    dimension)."""
    global_points: int = None
    polish_starts: int = POLISH_STARTS
    polish_evals: int = None

    def __post_init__(self):
        for name in ("global_points", "polish_starts", "polish_evals"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or int(value) != value or value < (
                    0 if name == "polish_starts" else 1):
                raise ValueError(f"{name} is a count, at least "
                                 f"{0 if name == 'polish_starts' else 1}; "
                                 f"got {value!r}")
            object.__setattr__(self, name, int(value))


@dataclass(frozen=True)
class Margin:
    """A margin: `fn(point)` is slack against the derated limit, in `unit`,
    over the space `over`; slack ≥ 0 passes. The derating and its reason sit
    in `fn`'s docstring. `truth(point)`, when set, re-evaluates a point in
    the truth model, and `agree` is the absolute tolerance in `unit` it must
    match `fn` within; it is required with `truth`. `budget` defaults to
    `Budget()`."""
    name: str
    fn: object
    unit: str
    over: Space
    truth: object = None
    agree: float = None
    budget: Budget = None

    def __post_init__(self):
        if not callable(self.fn):
            raise TypeError(f"margin {self.name!r}: fn is a callable taking "
                            f"a point; got {self.fn!r}")
        if not isinstance(self.over, Space):
            raise TypeError(f"margin {self.name!r} is searched over a Space; "
                            f"got {self.over!r}")
        if self.truth is not None:
            if not callable(self.truth):
                raise TypeError(f"margin {self.name!r}: truth is a callable "
                                f"taking a point; got {self.truth!r}")
            if self.agree is None or not float(self.agree) > 0:
                raise ValueError(f"margin {self.name!r} has a truth, so it "
                                 f"needs agree=, the tolerance in "
                                 f"{self.unit} it must match within")
        if self.budget is None:
            object.__setattr__(self, "budget", Budget())
        elif not isinstance(self.budget, Budget):
            raise TypeError(f"margin {self.name!r}: budget is a Budget; got "
                            f"{self.budget!r}")


class Case(NamedTuple):
    """The worst of one `Choice` combination: `choices` maps each choice
    axis to its value, and `value` is the worst slack, at `at`."""
    choices: dict
    value: float
    at: dict


@dataclass(frozen=True)
class Worst:
    """A margin's worst case. `value` is the least slack found, in `unit`,
    at `at` (each axis's value by name), and `passes` is `value ≥ 0`.
    `cases` holds the worst of each `Choice` combination. `n` counts every
    evaluation, `seed` seeds the Sobol set, and `method` says what was
    spent. `pre_polish` is the least slack before the polish, at
    `pre_polish_at`, so a reviewer sees whether the polish moved it.
    `rejected` counts the `Infeasible` points by reason, and `coverage` is
    the fraction of the global set's feasible points that pass. Print it
    for the one-line row a note cites."""
    margin: str
    unit: str
    value: float
    at: dict
    passes: bool
    cases: tuple
    method: str
    n: int
    seed: int
    pre_polish: float
    pre_polish_at: dict
    rejected: MappingProxyType
    coverage: float

    def __str__(self):
        text = (f"{self.margin}: {self.value:.7g} {self.unit} at "
                f"{_written(self.at)}, "
                f"{'passes' if self.passes else 'FAILS'}; pre-polish "
                f"{self.pre_polish:.7g}; coverage {self.coverage:.1%}; "
                f"n = {self.n}, seed = {self.seed}; {self.method}")
        if self.rejected:
            text += (f"; {sum(self.rejected.values())} rejected ("
                     + ", ".join(f"{r}: {k}" for r, k in self.rejected.items())
                     + ")")
        return text


def search(margin, seed=DEFAULT_SEED):
    """The worst case of `margin` over its space, from `seed`.

    Enumerates the `Choice` combinations. For each, evaluates a scrambled
    Sobol set of `budget.global_points` and every corner of the continuous
    axes, then polishes with bounded Powell from the best
    `budget.polish_starts` points, each start capped at
    `budget.polish_evals`. Returns a `Worst`, the minimum over every point
    evaluated. A −∞ ends its combination's polish, since nothing is worse.

    Raises when `fn` returns nan, naming the point, and when a combination
    has no point `fn` could evaluate, giving the reasons.
    """
    if not isinstance(margin, Margin):
        raise TypeError(f"search takes a Margin; got {margin!r}")
    space, budget = margin.over, margin.budget
    dims = space.dims
    run = _Run(margin, space)
    if dims:
        size = _power_of_two(budget.global_points or SOBOL_PER_DIM * dims)
        cube = qmc.Sobol(dims, scramble=True, seed=seed).random(size)
        corners = np.array([sum(c, ()) for c in itertools.product(
            *(a.corners() for a in space.axes.values() if a.dims))])
        cap = budget.polish_evals or POLISH_PER_DIM * dims
        starts = budget.polish_starts
    else:
        cube, corners, cap, starts = np.zeros((1, 0)), np.zeros((0, 0)), 0, 0
    choices = {n: a.values for n, a in space.axes.items()
               if isinstance(a, Choice)}
    cases, pre = [], None
    for combination in itertools.product(*choices.values()):
        fixed = dict(zip(choices, combination))
        best, before = run.combination(fixed, cube, corners, starts, cap)
        cases.append(Case(fixed, best[0], best[1]))
        if pre is None or before[0] < pre[0]:
            pre = before
    worst = min(cases, key=lambda c: c.value)
    method = (f"Sobol {len(cube)} (scrambled) + {len(corners)} corners + "
              f"Powell from {starts} (at most {cap} evaluations each)"
              if dims else "every combination evaluated once")
    if len(cases) > 1:
        method += f", for each of {len(cases)} combinations"
    return Worst(margin.name, margin.unit, worst.value, worst.at,
                 worst.value >= 0, tuple(cases), method, run.n, seed, pre[0],
                 pre[1], MappingProxyType(dict(run.rejected)),
                 run.covered / run.counted if run.counted else 0.0)


class _Found(Exception):
    """−∞: nothing is worse, so the polish stops."""


class _Spent(Exception):
    """A polish start has spent its evaluations."""


class _Run:
    """The evaluations of one search: every point, its tally, and each
    combination's least slack."""

    def __init__(self, margin, space):
        self.margin, self.space = margin, space
        self.n, self.rejected = 0, Counter()
        self.covered = self.counted = 0

    def point(self, fixed, u):
        """Each axis's value at unit coordinates `u`, the `Coordinates`'
        state last, compiled with the point's band values. Raises
        `Infeasible` where the map refuses the point."""
        values, mechanism, i = {}, None, 0
        for name, axis in self.space.axes.items():
            if isinstance(axis, Choice):
                values[name] = fixed[name]
                continue
            unit = tuple(float(x) for x in u[i:i + axis.dims])
            i += axis.dims
            if isinstance(axis, Coordinates):
                values[name], mechanism = None, (name, axis, unit)
            else:
                values[name] = axis.value(unit)
        if mechanism:
            name, axis, unit = mechanism
            values[name] = axis.value(unit, {
                a.param: values[n] for n, a in self.space.axes.items()
                if isinstance(a, Band)})
        return values

    def evaluate(self, fixed, u):
        """`fn` at unit coordinates `u`: its slack, or None where it raised
        `Infeasible`; with the point as a plain dict."""
        self.n += 1
        try:
            values = self.point(fixed, u)
            at = {n: self.space.axes[n].plain(v) for n, v in values.items()}
            slack = float(self.margin.fn(Point(values)))
        except Infeasible as refused:
            self.rejected[refused.reason] += 1
            return None, None
        if math.isnan(slack):
            raise ValueError(f"margin {self.margin.name!r} is nan at "
                             f"{_written(at)}: a point it cannot evaluate "
                             f"raises Infeasible(reason)")
        return slack, at

    def combination(self, fixed, cube, corners, starts, cap):
        """The least slack of one combination, and the least before the
        polish, each as (value, at)."""
        best = None
        ranked = []   # (slack, order, u) of every feasible point so far
        seen = {}

        def visit(u, glob=False):
            nonlocal best
            key = u.tobytes()
            if key in seen:
                return seen[key]
            slack, at = self.evaluate(fixed, u)
            seen[key] = slack
            if glob and slack is not None:
                self.counted += 1
                self.covered += slack >= 0
            if slack is not None:
                ranked.append((slack, len(ranked), u))
                if best is None or slack < best[0]:
                    best = (slack, at)
            return slack

        for u in cube:
            visit(u, glob=True)
        for u in corners:
            visit(np.array(u, dtype=float))
        if best is None:
            raise ValueError(
                f"margin {self.margin.name!r} has no point it could evaluate"
                + (f" at {_written(fixed)}" if fixed else "") + ": "
                + ", ".join(f"{r}: {k}" for r, k in self.rejected.items()))
        before = best
        if not math.isfinite(best[0]) or not starts:
            return best, before
        top = max(s for s, _, _ in ranked if math.isfinite(s))
        last = top + 1.0 + abs(top)   # what an infeasible point reads to
                                      # the polish: worse than every point
        spent = 0

        def objective(u):
            nonlocal spent
            u = np.clip(u, 0.0, 1.0)
            if u.tobytes() not in seen:
                if spent >= cap:
                    raise _Spent
                spent += 1
            slack = visit(u)
            if slack == -math.inf:
                raise _Found
            return slack if slack is not None and math.isfinite(slack) \
                else last

        for slack, _, u in sorted(ranked, key=lambda r: r[:2])[:starts]:
            spent = 0
            try:
                minimize(objective, u, method="Powell",
                         bounds=[(-REACH, 1.0 + REACH)] * len(u),
                         options={"xtol": POLISH_XTOL, "ftol": POLISH_FTOL,
                                  "maxfev": cap})
            except _Spent:
                pass
            except _Found:
                break
        return best, before


def _power_of_two(n):
    return 1 << max(0, math.ceil(math.log2(n)))


def _written(at):
    return ", ".join(f"{n} = {_number(v)}" for n, v in at.items())


def _number(v):
    if isinstance(v, dict):
        return "(" + _written(v) + ")"
    if isinstance(v, tuple):
        return "(" + ", ".join(_number(c) for c in v) + ")"
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)
