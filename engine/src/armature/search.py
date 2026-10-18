"""The worst-case search: one search over a named space, for every margin
(ADR 0005).

A margin is slack, available minus required against a limit with its
derating already applied, written as `fn(point)` over a `Space` of named
axes. Slack ≥ 0 passes, or > 0 for a `strict` margin, and −∞ is a legal
value. `search(margin)` finds the worst, and a project declares margins rather than writing searches, so no
worst case is read at a posture, direction, sign or band value somebody
happened to pick.

The method is fixed, because each knob would be a way to under-search:

- `Choice` axes are enumerated, never searched, and the result keeps the
  worst of each combination.
- For each combination, the continuous axes are searched in their unit
  cube: a scrambled, seeded Sobol set, then every corner (an interval's
  ends, a direction's axis directions in both signs), then bounded Powell
  from the best few points.
- The result is the minimum over every point evaluated, the polish's
  included, so nothing it steps through is lost.

The polish is scipy's bounded Powell, with one change in its line search.
Bounded Brent finds a local minimum along the line, which may be worse
than the line's start, and scipy steps there anyway. The polish's line
search compares that minimum with the line's two ends, each on a face of
the cube, and steps to the least of the three only where it is below the
start. So no step ends worse than its start, and a worst on a face is
found from a start near it even when the line holds a deeper-looking basin
between. On the wheel leg's hold, scipy's line along A stepped from
A = 0.94 to a basin at A = −0.51 worse than its start and never came back,
reading 1.165 A_peak against the A = 1 face's 0.983 (#126).

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
point the map refuses is `Infeasible`, under the loop, joint, envelope or
`rest_on` contact that refused it.

A margin with a `truth` is confirmed where the search ends: `truth` is
evaluated at the worst point and at the pre-polish best, each the very
`Point` `fn` read there, and `Worst.truth` records both values and whether
they match `fn` within `agree`. A disagreement is recorded, never raised:
the search reports, and the caller's check fails on it.

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
from scipy.optimize import minimize_scalar
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
    reads the value by axis name, as `p.m2`.

    `of` says whose parameter it is: the `"mechanism"`'s, by default, which
    is compiled, or another's, such as `"drive"` for the drive data's
    (`armature.drive.margins` reads those), which the space leaves alone:
    neither checked against the mechanism nor compiled into it."""
    param: str
    of: str

    def __init__(self, param, bands, of="mechanism"):
        if param not in bands:
            raise ValueError(f"no band named {param!r}; the bands are "
                             f"{sorted(bands)}")
        try:
            lo, hi = (float(v) for v in bands[param])
        except (TypeError, ValueError):
            raise ValueError(f"band {param!r} is a (low, high) pair; got "
                             f"{bands[param]!r}") from None
        if not (isinstance(of, str) and of):
            raise TypeError(f"band {param!r}: of names whose parameter it is, "
                            f"such as 'mechanism' or 'drive'; got {of!r}")
        object.__setattr__(self, "param", param)
        object.__setattr__(self, "of", of)
        object.__setattr__(self, "lo", lo)
        object.__setattr__(self, "hi", hi)
        try:
            self.__post_init__()
        except ValueError as err:
            raise ValueError(f"band {param!r}: {err}") from None

    @property
    def compiled(self):
        """Whether the band is the mechanism's, compiled with the state."""
        return self.of == "mechanism"

    def __repr__(self):
        of = "" if self.compiled else f", of={self.of!r}"
        return f"Band({self.param!r}, ({self.lo!r}, {self.hi!r}){of})"


class Coordinates(_Axis):
    """A mechanism's independent coordinates, as a ready `State` at rest:
    `Coordinates(mechanism, params, within=None, poses=None,
    rest_on=None)`, with `within`, `poses` and `rest_on` as
    `armature.sample` takes them. Name the axis `state` and `fn` reads
    `p.state`.

    Each point is mapped by the sampler's `unit_cube`: every hinge and
    slide over its joint range or `within`, every loop closed, every
    floating body inside its pose envelope, and each contact `rest_on`
    names brought to touch by solving its coordinate, which is then no
    axis: `rest_on={"tyre": "y"}` stands a torso on its wheel at every
    point. Its corners are the corners of those ranges. A point the map
    refuses, a loop that cannot close, a pose outside the envelope or a
    contact it cannot bring to touch, raises `Infeasible` with the map's
    reason, such as `"loop 'pin'"` or `"contact 'tyre'"`. In a `Worst`'s
    `at` the state is written as its independent coordinates, by name, a
    solved one among them.

    The mechanism compiles once at `params`, when the space is made, which
    fixes the axes: a space's dimension is known before it is searched.
    Where the space has a `Band`, each point compiles again with its band
    values (1–3 ms), and a band that would change the axes raises. The
    nominal compile and the last are kept, so a space without a band, or a
    run of points with the same band values, compiles once. Like the
    compiled model, it is for one thread at a time."""

    def __init__(self, mechanism, params, within=None, poses=None,
                 rest_on=None):
        self.mechanism, self.params = mechanism, MappingProxyType(dict(params))
        self.within = MappingProxyType(dict(within or {}))
        self.poses = MappingProxyType(dict(poses or {}))
        self.rest_on = MappingProxyType(dict(rest_on or {}))
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
                         poses=self.poses, within=self.within,
                         rest_on=self.rest_on)
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
        twice = sorted(p for (_, p), k in Counter(
            (b.of, b.param) for b in bands).items() if k > 1)
        if twice:
            raise ValueError(f"the bands {twice} appear twice; a parameter "
                             f"takes one value at a point")
        self.axes = MappingProxyType(dict(axes))
        if mechanisms:
            coordinates = axes[mechanisms[0]]
            for band in bands:
                if band.compiled:
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
    over the space `over`; slack ≥ 0 passes, or slack > 0 where `strict`,
    for a limit that reaching is itself the failure, such as a trip that
    latches at its level. The derating and its reason sit
    in `fn`'s docstring. `truth(point)`, when set, re-evaluates a point in
    the truth model, and `agree` is the absolute tolerance in `unit` it must
    match `fn` within; it is required with `truth`. The search evaluates
    `truth` at its worst point and its pre-polish best (`Worst.truth`).
    `budget` defaults to `Budget()`.

    A margin whose inputs are missing is `unchecked`: a tuple naming each
    missing input. It is never evaluated, and its search returns a `Worst`
    marked UNCHECKED, which fails.

    `against`, optional, names the limit for the row, where the name alone
    does not: "power board (44 V)"."""
    name: str
    fn: object
    unit: str
    over: Space
    truth: object = None
    agree: float = None
    budget: Budget = None
    unchecked: tuple = None
    against: str = None
    strict: bool = False

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
        if self.unchecked is not None:
            missing = self.unchecked
            if isinstance(missing, str) or not missing or not all(
                    isinstance(m, str) and m for m in missing):
                raise TypeError(f"margin {self.name!r}: unchecked names each "
                                f"missing input, a tuple of strings; got "
                                f"{missing!r}")
            object.__setattr__(self, "unchecked", tuple(missing))
        if self.against is not None and not isinstance(self.against, str):
            raise TypeError(f"margin {self.name!r}: against names the "
                            f"limit, a string; got {self.against!r}")
        if self.budget is None:
            object.__setattr__(self, "budget", Budget())
        elif not isinstance(self.budget, Budget):
            raise TypeError(f"margin {self.name!r}: budget is a Budget; got "
                            f"{self.budget!r}")


class Confirmed(NamedTuple):
    """A margin's `truth` at the search's worst point (`value`) and at its
    pre-polish best (`pre_polish`), in the margin's unit. `gap` is the
    larger distance from `fn` at those points, nan where `truth` read nan,
    and `agrees` is `gap ≤ agree`."""
    value: float
    pre_polish: float
    gap: float
    agree: float
    agrees: bool


class Case(NamedTuple):
    """The worst of one `Choice` combination: `choices` maps each choice
    axis to its value, and `value` is the worst slack, at `at`."""
    choices: dict
    value: float
    at: dict


@dataclass(frozen=True)
class Worst:
    """A margin's worst case. `value` is the least slack found, in `unit`,
    at `at` (each axis's value by name), and `passes` is `value ≥ 0`, or
    `value > 0` for a strict margin.
    `cases` holds the worst of each `Choice` combination. `n` counts every
    evaluation, `seed` seeds the Sobol set, and `method` says what was
    spent. `pre_polish` is the least slack before the polish, at
    `pre_polish_at`, so a reviewer sees whether the polish moved it.
    `rejected` counts the `Infeasible` points by reason, and `coverage` is
    the fraction of the global set's feasible points that pass, pooled over
    every combination; a `Case` carries none. `truth`
    is the `Confirmed` record of the margin's truth at `at` and at
    `pre_polish_at`, or None for a margin without one. Print it for the
    one-line row a note cites.

    An UNCHECKED margin's worst names its missing inputs in `unchecked`; its
    value is nan, it fails, and nothing was evaluated. `against` is the
    margin's, printed after the value."""
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
    truth: Confirmed = None
    unchecked: tuple = None
    against: str = None

    def __str__(self):
        if self.unchecked:
            return (f"{self.margin}: UNCHECKED, FAILS; missing "
                    + ", ".join(self.unchecked))
        held = f" against {self.against}" if self.against else ""
        text = (f"{self.margin}: {self.value:.7g} {self.unit}{held} at "
                f"{_written(self.at)}, "
                f"{'passes' if self.passes else 'FAILS'}; pre-polish "
                f"{self.pre_polish:.7g}; coverage {self.coverage:.1%}; "
                f"n = {self.n}, seed = {self.seed}; {self.method}")
        if self.rejected:
            text += (f"; {sum(self.rejected.values())} rejected ("
                     + ", ".join(f"{r}: {k}" for r, k in self.rejected.items())
                     + ")")
        if self.truth is not None:
            t = self.truth
            text += (f"; truth {t.value:.7g} at the worst, {t.pre_polish:.7g} "
                     f"at the pre-polish best, "
                     + (f"agrees within {t.agree:g}" if t.agrees else
                        f"DISAGREES by {t.gap:.3g} beyond {t.agree:g}"))
        return text


def search(margin, seed=DEFAULT_SEED):
    """The worst case of `margin` over its space, from `seed`.

    Enumerates the `Choice` combinations. For each, evaluates a scrambled
    Sobol set of `budget.global_points` and every corner of the continuous
    axes, then polishes with bounded Powell from the best
    `budget.polish_starts` points, each start capped at
    `budget.polish_evals`. Returns a `Worst`, the minimum over every point
    evaluated. A −∞ ends its combination's polish, since nothing is worse.

    Where the margin has a `truth`, evaluates it at the worst point and at
    the pre-polish best, the `Point`s `fn` read there, and records the
    result in `Worst.truth`; those evaluations are not counted in `n`.

    An UNCHECKED margin is not evaluated: its `Worst` names what is
    missing, and fails.

    Raises when `fn` returns nan, naming the point, when a combination has
    no point `fn` could evaluate, giving the reasons, and when `truth`
    raises `Infeasible` at a point `fn` evaluated.
    """
    if not isinstance(margin, Margin):
        raise TypeError(f"search takes a Margin; got {margin!r}")
    if margin.unchecked:
        return Worst(margin.name, margin.unit, math.nan, {}, False, (),
                     "UNCHECKED: nothing evaluated", 0, seed, math.nan, {},
                     MappingProxyType({}), 0.0, None, margin.unchecked,
                     margin.against)
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
    cases, found, pre = [], [], None
    for combination in itertools.product(*choices.values()):
        fixed = dict(zip(choices, combination))
        best, before = run.combination(fixed, cube, corners, starts, cap)
        cases.append(Case(fixed, best[0], best[1]))
        found.append(best)
        if pre is None or before[0] < pre[0]:
            pre = before
    first = min(range(len(cases)), key=lambda i: cases[i].value)
    worst, point = cases[first], found[first][2]
    method = (f"Sobol {len(cube)} (scrambled) + {len(corners)} corners + "
              f"Powell from {starts} (at most {cap} evaluations each)"
              if dims else "every combination evaluated once")
    if len(cases) > 1:
        method += f", for each of {len(cases)} combinations"
    return Worst(margin.name, margin.unit, worst.value, worst.at,
                 _passes(margin, worst.value), tuple(cases), method, run.n,
                 seed, pre[0], pre[1], MappingProxyType(dict(run.rejected)),
                 run.covered / run.counted if run.counted else 0.0,
                 _confirm(margin, (worst.value, worst.at, point), pre),
                 against=margin.against)


def _passes(margin, slack):
    return slack > 0 if margin.strict else slack >= 0


def _confirm(margin, worst, pre):
    """`margin.truth` at the worst and the pre-polish best, each a
    (value, at, point) triple, as a `Confirmed`; None without a truth. The
    same point is evaluated once."""
    if margin.truth is None:
        return None
    read = {}
    for value, at, point in (worst, pre):
        if id(point) in read:
            continue
        try:
            read[id(point)] = float(margin.truth(point))
        except Infeasible as refused:
            raise ValueError(f"margin {margin.name!r}: its truth cannot "
                             f"evaluate {_written(at)}, where fn read "
                             f"{value:.7g}: {refused.reason}") from None
    truth = read[id(worst[2])], read[id(pre[2])]
    gaps = [abs(t - v) for t, v in zip(truth, (worst[0], pre[0]))]
    gap = math.nan if any(math.isnan(g) for g in gaps) else max(gaps)
    agree = float(margin.agree)
    return Confirmed(*truth, gap, agree, gap <= agree)


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
                if isinstance(a, Band) and a.compiled})
        return values

    def evaluate(self, fixed, u):
        """`fn` at unit coordinates `u`: its slack, or None where it raised
        `Infeasible`; with the point as a plain dict, and the `Point` `fn`
        read."""
        self.n += 1
        try:
            values = self.point(fixed, u)
            at = {n: self.space.axes[n].plain(v) for n, v in values.items()}
            point = Point(values)
            slack = float(self.margin.fn(point))
        except Infeasible as refused:
            self.rejected[refused.reason] += 1
            return None, None, None
        if math.isnan(slack):
            raise ValueError(f"margin {self.margin.name!r} is nan at "
                             f"{_written(at)}: a point it cannot evaluate "
                             f"raises Infeasible(reason)")
        return slack, at, point

    def combination(self, fixed, cube, corners, starts, cap):
        """The least slack of one combination, and the least before the
        polish, each as (value, at, point)."""
        best = None
        ranked = []   # (slack, order, u) of every feasible point so far
        seen = {}

        def visit(u, glob=False):
            nonlocal best
            key = u.tobytes()
            if key in seen:
                return seen[key]
            slack, at, point = self.evaluate(fixed, u)
            seen[key] = slack
            if glob and slack is not None:
                self.counted += 1
                self.covered += _passes(self.margin, slack)
            if slack is not None:
                ranked.append((slack, len(ranked), u))
                if best is None or slack < best[0]:
                    best = (slack, at, point)
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
                _powell(objective, u)
            except _Spent:
                pass
            except _Found:
                break
        return best, before


def _powell(f, x):
    """Powell's method from `x` within the polish's reach, as scipy's
    bounded Powell runs it, but each line search through `_line`, so no
    step ends worse than its start. Stops once an iteration gains less
    than `POLISH_FTOL`, relative; `f` raises to stop it sooner."""
    directions = np.eye(len(x))
    fx = f(x)
    while True:
        start, f_start = x, fx
        biggest, gain = 0, 0.0
        for i, direction in enumerate(directions):
            before = fx
            x, fx, _ = _line(f, x, direction, fx)
            if before - fx > gain:
                biggest, gain = i, before - fx
        if 2.0 * (f_start - fx) <= POLISH_FTOL * (
                abs(f_start) + abs(fx)) + 1e-20:
            return
        # Powell's extrapolation: a new direction, x − start, replaces the
        # one that gained most, where that keeps the set from collapsing
        direction = x - start
        _, reach = _segment(x, direction)
        f_far = f(x + min(reach, 1.0) * direction)
        if f_start > f_far:
            t = (2.0 * (f_start + f_far - 2.0 * fx) * (f_start - fx - gain) ** 2
                 - gain * (f_start - f_far) ** 2)
            if t < 0.0:
                x, fx, step = _line(f, x, direction, fx)
                if np.any(step):
                    directions[biggest] = directions[-1]
                    directions[-1] = step


def _line(f, x, direction, fx):
    """The least of `f` along `x + α·direction` within the polish's reach,
    from `x`, where `f` reads `fx`: bounded Brent's local minimum, or either
    end of the line, each on a face of the cube, whichever is least. The
    start stands unless one is lower than it, so a step never ends worse
    than its start. Returns the point, its value and the step taken."""
    if not np.any(direction):
        return x, fx, direction
    low, high = _segment(x, direction)
    along = minimize_scalar(lambda a: f(x + a * direction),
                            bounds=(low, high), method="bounded",
                            options={"xatol": POLISH_XTOL})
    best, value = 0.0, fx
    for a, fa in ((along.x, along.fun), (low, f(x + low * direction)),
                  (high, f(x + high * direction))):
        if fa < value:
            best, value = a, fa
    step = best * direction
    return x + step, value, step


def _segment(x, direction):
    """The steps (low, high) that keep `x + α·direction` within the
    polish's reach, `REACH` past each face of the unit cube."""
    moving = direction != 0.0
    ends = (np.array([[-REACH], [1.0 + REACH]]) - x[moving]) / direction[
        moving]
    low, high = np.sort(ends, axis=0)
    return float(low.max()), float(high.min())


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
