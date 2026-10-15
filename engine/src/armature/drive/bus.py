"""The shared DC bus, charged by each actuator's bus power over a trace
(ADR 0006).

    C·dV/dt = Σ P_actuator/V − I_source − I_brake − I_flux − P_hotel/V

is integrated as the capacitor's energy, E = ½CV², which the same equation
times V makes dE/dt = Σ P − P_source − P_brake − P_flux − P_hotel, with
each actuator's P (W, positive drawing) from `electrical`'s `bus`. Between
the trace's samples each actuator's power is the straight line between
them, so a substep integrates it exactly; `heat` holds each sample instead,
but the bus's peak can fall inside a sample interval, and a held power
would move it.

Everything that holds the bus at a voltage is a **clamp**: at its level it
takes or gives whatever keeps V there, up to a capacity, and past that
capacity V moves on. The actuators' and the hotel load's power is drawn
unconditionally. Over a substep every rate is constant, and each clamp is
off, saturated or holding, so the substep is solved exactly: E moves at a
constant rate to the next level, stops there while that level's clamps can
take up the rest, and moves on at the reduced rate when they cannot. A
clamp crossed partway through a substep acts for the rest of it only. The
clamps are:

- **the source** at its voltage V_s, a point in its band `v`: it sources up
  to `p_max` to hold V up to V_s, and, only if `sinks`, takes up to `p_max`
  back to hold V down to V_s. A pack sinks; a PSU behind a diode does not,
  so with `sinks=False` its current is never negative and the bus above V_s
  floats on the capacitor. Inside its limits a sinking source holds V at
  V_s, inside its band; past `p_max` the bus sags below it or rises above
  it, which is what the minimum and peak report. Battery state of charge
  and sag beyond the band are left out (spec #83): the band is the range V_s
  takes, and #88 searches it. A bus with no source, such as a pack unmated,
  has no such clamp: it starts at its own `v0`, and the hotel load drains
  it all along.
- **the brake resistor**, an ideal chopper: above `threshold` it connects
  `r` across the bus, so it holds V at the threshold while V_th²/R covers
  what arrives, and past that V rises until V²/R does. Its capacity in a
  substep is V²/R at the substep's starting voltage, never below the
  threshold: the one first-order term, and why the substep is refined. A
  forward-Euler chopper overshoots by P·h/(C·V_th) instead, which is how
  ADR 0006's probe read 30.2 V where this model holds the threshold.
- **each flux brake**, a driver's: above its `onset` it drives d-axis
  current into its own winding, absorbing up to i_d²·R_φ(T) in the
  power-invariant d-q convention, i_d = `FluxBrake.i_d.dq(wiring)`, which is
  the spec's amplitude-invariant 1.5·I_d,peak²·R_φ. R_φ is at the winding
  temperature `charge` is given, by default the resistance's T₀, which on a
  hot winding reads both the capacity and the heat low, so give it. All of
  it is taken to heat the winding, and none is lost in the driver. Its heat,
  per actuator on the trace's own times, is `heat`'s `power=` input for
  that motor. It acts only while its driver is on, as `Trace.driven` says:
  an event that coasts or shorts the motor has switched it off.

Clamps at one level share what they take in proportion to their
capacities. A clamp below the source's voltage takes the source's own
power, and the source and brake rows report it. The bus starts at V_s, or
at `v0` for an event triggered partway through a mission. A draw no clamp
can meet empties the capacitor to 0 V, where it stays until power returns:
a minimum of 0 is a collapsed bus.

The substep starts at the trace's longest sample interval and is halved
until halving it again moves the peak V by less than `agree` (V, by default
`AGREE`); `Charged` reports the substep it ran at, so halving that one
moves the peak by less than `agree`. Within a substep each actuator's
power is its mean there, and the brake's capacity is V²/R at its start, so
both converge as it shrinks; on a brake carrying twice its threshold
capacity, the refined peak sits within 2·`agree` of the ODE's.

The bus's bands, its `capacitance` and its source's `v` (or, with no
source, its `v0`), are searched by #88 as `Interval(*band)` axes; `charge`
runs at one point in each, given as `capacitance=` and `v_source=`, or the
band's only value where it is one.
A bus configuration, such as Ibex's pack unmated, is a `Choice` between
`Drive`s.

Units are SI: V, F, W, J, Ω, s.
"""

import math
from dataclasses import dataclass
from functools import partial
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from ..state import _frozen
from .electrical import (Driver, DriveError, Gearbox, Motor, _kind, _number,
                         _positive, _resolve, electrical)

AGREE = 0.01       # V: halving the substep moves the peak by less than this
MAX_HALVINGS = 10  # the substep's refinement gives up past this many halvings
SOURCE, BRAKE = ("source",), ("brake",)
# the clamps' keys; a flux brake's is ("flux", actuator)
TRIPPED_SOURCE = "source"  # the source's name where `tripped` reports it


def _band(owner, name, value):
    """A (lo, hi) band of positive numbers, lo ≤ hi; a number is a band of
    one value."""
    if isinstance(value, (int, float)):
        value = (value, value)
    try:
        lo, hi = value
    except (TypeError, ValueError):
        raise TypeError(f"{owner}'s {name} is a (lo, hi) band or a number; "
                        f"got {value!r}") from None
    lo, hi = (_number(owner, f"{name} band's {end}", v)
              for end, v in (("low", lo), ("high", hi)))
    if lo > hi:
        raise ValueError(f"{owner}'s {name} band's low is above its high; "
                         f"got ({lo}, {hi})")
    return lo, hi


def _within(name, band, value):
    """`value`, a point in `band`, or the band's only value."""
    lo, hi = band
    if value is None:
        if lo != hi:
            raise ValueError(f"the bus's {name} is a band ({lo:g}, {hi:g}); "
                             f"charge runs at a point in it, so give "
                             f"{name}=")
        return lo
    value = _positive(value, f"charge's {name}")
    if not lo <= value <= hi:
        raise ValueError(f"charge's {name} lies in the bus's band ({lo:g}, "
                         f"{hi:g}); got {value:g}")
    return value


@dataclass(frozen=True, kw_only=True)
class Source:
    """The bus's source: its voltage `v`, a (lo, hi) band or a number (V);
    whether it `sinks`, as a pack does and a PSU behind a diode does not;
    `p_max` (W), the most it sources, or sinks; and an optional
    `overvoltage` (V), where it trips, one of the bus's trips."""
    v: tuple
    sinks: bool
    p_max: float
    overvoltage: float = None

    def __post_init__(self):
        object.__setattr__(self, "v", _band("a source", "v", self.v))
        if not isinstance(self.sinks, bool):
            raise TypeError(f"a source's sinks is True or False; got "
                            f"{self.sinks!r}")
        object.__setattr__(self, "p_max",
                           _number("a source", "p_max", self.p_max))
        if self.overvoltage is not None:
            trip = _number("a source", "overvoltage", self.overvoltage)
            if not trip > self.v[1]:
                raise ValueError(f"a source's overvoltage is above its v "
                                 f"band; got {trip:g} V over "
                                 f"{self.v[1]:g} V")
            object.__setattr__(self, "overvoltage", trip)


@dataclass(frozen=True, kw_only=True)
class BrakeResistor:
    """A brake resistor `r` (Ω), switched across the bus above `threshold`
    (V), rated for `energy` (J) in one pulse and `power` (W) continuous."""
    threshold: float
    r: float
    energy: float
    power: float

    def __post_init__(self):
        for name in ("threshold", "r", "energy", "power"):
            object.__setattr__(self, name, _number(
                "a brake resistor", name, getattr(self, name)))


@dataclass(frozen=True, kw_only=True)
class Bus:
    """The shared DC bus: the `actuators` on it, by name; its `source`, or
    None where nothing sources or sinks (a pack unmated), and then the
    voltage `v0` (V) it starts at, a (lo, hi) band or a number; its
    `capacitance` (F), a (lo, hi) band or a number; an optional `brake`
    resistor; a constant `hotel` load (W), drawn with or without a source;
    and the voltage `ratings` (V) of the parts on it that no driver
    carries, by name, such as `{"power board": 44.0}`, each one of the
    bus's trips. Flux braking is each driver's own, from its
    `Driver.flux_brake`."""
    actuators: tuple
    source: Source
    capacitance: tuple
    brake: BrakeResistor = None
    hotel: float = 0.0
    ratings: MappingProxyType = None
    v0: tuple = None

    def __post_init__(self):
        if isinstance(self.actuators, str) or not hasattr(
                self.actuators, "__iter__"):
            raise TypeError(f"a bus's actuators are a sequence of names; got "
                            f"{self.actuators!r}")
        actuators = tuple(self.actuators)
        if not actuators or not all(isinstance(a, str) for a in actuators):
            raise ValueError(f"a bus's actuators are one or more names; got "
                             f"{actuators!r}")
        if len(set(actuators)) != len(actuators):
            raise ValueError(f"a bus names each actuator once; got "
                             f"{actuators!r}")
        if TRIPPED_SOURCE in actuators:
            raise ValueError(f"a bus's actuators are never named "
                             f"{TRIPPED_SOURCE!r}, the name `tripped` gives "
                             f"its source; got {actuators!r}")
        object.__setattr__(self, "actuators", actuators)
        _kind("a bus", "source", self.source, Source, optional=True)
        if self.source is None:
            if self.v0 is None:
                raise ValueError("a bus with no source starts at a voltage; "
                                 "give v0=")
            object.__setattr__(self, "v0", _band("a bus", "v0", self.v0))
        elif self.v0 is not None:
            raise ValueError("a bus with a source starts at its source's v; "
                             "give v0= only with source=None")
        object.__setattr__(self, "capacitance",
                           _band("a bus", "capacitance", self.capacitance))
        _kind("a bus", "brake", self.brake, BrakeResistor, optional=True)
        object.__setattr__(self, "hotel", _number(
            "a bus", "hotel load", self.hotel, inclusive=True))
        ratings = self.ratings if self.ratings is not None else {}
        if not hasattr(ratings, "items") or not all(
                isinstance(k, str) and k for k in ratings):
            raise TypeError(f"a bus's ratings map each part's name to its "
                            f"voltage rating; got {self.ratings!r}")
        for name, value in ratings.items():
            rating = _number("a bus", f"rating {name!r}", value)
            if not rating > _v_source(self)[1]:
                raise ValueError(f"a bus's rating {name!r} lies above the "
                                 f"voltage it starts at; got {rating:g} V "
                                 f"over {_v_source(self)[1]:g} V")
        object.__setattr__(self, "ratings", MappingProxyType(
            {k: float(v) for k, v in ratings.items()}))


def _v_source(bus):
    """The band `charge`'s `v_source` is a point in: the source's `v`, or,
    on a bus with no source, its `v0`."""
    return bus.v0 if bus.source is None else bus.source.v


def _keyed(name, value, kind):
    if not hasattr(value, "items"):
        raise TypeError(f"a drive's {name} map each actuator's name to a "
                        f"{kind.__name__}; got {value!r}")
    for key, item in value.items():
        if not isinstance(item, kind):
            raise TypeError(f"a drive's {name}[{key!r}] is a "
                            f"{kind.__name__}; got {item!r}")
    return MappingProxyType(dict(value))


@dataclass(frozen=True, kw_only=True)
class Drive:
    """A project's drive data, `drive(p) → Drive`: the `motors`, `drivers`
    and `gearboxes`, each keyed by actuator name, and the `bus` they share.
    An actuator with no gearbox is a direct drive, so one geared in the
    compiled model needs one. Each actuator's `gear` and `rotor_inertia` are
    the compiled model's, never repeated here. One bus per model (ADR 0006):
    every motor is on it, and every actuator on it has a motor and a
    driver."""
    motors: MappingProxyType
    drivers: MappingProxyType
    bus: Bus
    gearboxes: MappingProxyType = None

    def __post_init__(self):
        object.__setattr__(self, "motors", _keyed("motors", self.motors,
                                                  Motor))
        object.__setattr__(self, "drivers", _keyed("drivers", self.drivers,
                                                   Driver))
        object.__setattr__(self, "gearboxes", _keyed(
            "gearboxes", self.gearboxes or {}, Gearbox))
        _kind("a drive", "bus", self.bus, Bus)
        on = set(self.bus.actuators)
        for name, keys in (("motors", self.motors), ("drivers", self.drivers),
                           ("gearboxes", self.gearboxes)):
            stray = sorted(set(keys) - on)
            if stray:
                raise ValueError(f"a drive's {name} name {stray}, which the "
                                 f"bus does not carry; one bus carries "
                                 f"every actuator")
        for name, keys in (("motor", self.motors), ("driver", self.drivers)):
            missing = [a for a in self.bus.actuators if a not in keys]
            if missing:
                raise ValueError(f"the bus carries {missing}, which have no "
                                 f"{name}")


@dataclass(frozen=True)
class Charged:
    """The bus over a trace, run at `capacitance` (F) and `v_source` (V),
    the voltage a bus with no source started at, with a `substep` (s),
    halving which moves the peak by less than the `agree` it was run with.

    `t` (s) is every substep's end, from the trace's start, and `v` (V) the
    bus there; `peak` and `minimum` are its extremes. `source` and `brake`
    are the power (W) each took or gave over the substep starting at each
    time, the last value never held: the source's positive sourcing and
    negative sinking, the brake's always ≥ 0.

    The brake's `brake_energy` (J) is over the whole trace, its
    `brake_pulse` (J) the most in one unbroken run of conduction, against
    its pulse rating, and `brake_peak` (W) its most at once. The source's
    `source_peak` (W) is the most it sourced, which stops at `p_max`, and
    `source_demand` (W) the most the bus drew from it, the actuators' net
    draw plus the hotel load, uncapped, so a source too small for the
    mission reads above its `p_max` and not only as sag; `sink_peak` (W) is
    the most it sank, and `source_energy` (J) the net energy it gave.

    `power` is each actuator's bus power (W, positive drawing) as the trace
    gives it, past a trip too, as is `source_demand`, and `flux` each flux
    brake's heat (W, zero where its driver has none or is off), both on the
    trace's own times, each value the mean over the interval it starts:
    `heat(trace.t, thermal, power=flux[a], ...)` takes it as it is.

    `tripped` gives the time (s) at which each driver, by its actuator's
    name, or the source, as `"source"`, tripped, latched from there; it is
    empty where nothing did. A trip inside a substep ends it there, so its
    time is one of `t`, and V there is the trip's level."""
    t: np.ndarray
    v: np.ndarray
    peak: float
    minimum: float
    source: np.ndarray
    brake: np.ndarray
    flux: MappingProxyType
    power: MappingProxyType
    brake_energy: float
    brake_pulse: float
    brake_peak: float
    source_peak: float
    source_demand: float
    sink_peak: float
    source_energy: float
    capacitance: float
    v_source: float
    substep: float
    agree: float
    tripped: MappingProxyType = MappingProxyType({})


def charge(trace, drive, *, capacitance=None, v_source=None, v0=None,
           agree=AGREE, substep=None, temperature=None, gear=None):
    """The bus of `drive` over `trace`, at `capacitance` (F) and `v_source`
    (V), each a point in its band, or the band's only value where it is
    one: a `Charged`. The bus starts at `v0` (V), by default `v_source`,
    which on a bus with no source is a point in its `v0` band.

    Each actuator's load comes from `trace.output(a)` and its bus power from
    `electrical`, its winding at `temperature[a]` (°C, a number or one per
    sample; by default its resistance's T₀). `gear` gives the ratio of an
    actuation seam's actuator, which has none in the compiled model.

    Each driver, and the source, trips where the bus first reaches its
    level on the trace's prescribed samples, latched for the rest of the
    trace; inside an event, where the event tripped it (`Run.tripped`).

    Without a `substep` (s), it is refined from the trace's longest sample
    interval, halving until halving again moves the peak by less than
    `agree` (V); given, the bus runs at that substep alone."""
    if not isinstance(drive, Drive):
        raise TypeError(f"charge takes a Drive; got {drive!r}")
    bus = drive.bus
    c = _within("capacitance", bus.capacitance, capacitance)
    v_s = _within("v_source", _v_source(bus), v_source)
    v0 = v_s if v0 is None else _positive(v0, "charge's v0")
    agree = _positive(agree, "charge's agree")
    t = np.asarray(trace.t, dtype=float)
    stray = sorted(set(getattr(trace, "torque", {})) - set(bus.actuators))
    if stray:
        raise ValueError(f"the trace drives {stray}, which have no drive "
                         f"data; give each a motor and driver on the bus")
    power, flux, coasts = {}, [], {}
    temperature = dict(temperature or {})
    gear = dict(gear or {})
    driven = getattr(trace, "driven", None) or {}
    for a in bus.actuators:
        n = gear.get(a)
        tau, omega, rotor = trace.output(a, n)
        n = trace.gear[a] if n is None else n
        box = drive.gearboxes.get(a)
        if box is None and n != 1:
            raise ValueError(f"{a!r} has a gear of {n:g} but no gearbox; "
                             f"give gearboxes={{{a!r}: Gearbox(forward=...)}}")
        motor, driver = drive.motors[a], drive.drivers[a]
        e = electrical(tau, omega, n, motor, box, driver,
                       temperature.get(a), rotor=rotor)
        power[a] = e.bus
        coasts[a] = _Coast(driver.max_voltage, e, _resolve(motor, n, box),
                           driver.efficiency)
        if driver.flux_brake is not None:
            capacity = _flux_capacity(driver, motor, e.resistance)
            if a in driven:  # a coasting or shorted driver's bridge is off
                capacity = np.where(driven[a], capacity, 0.0)
            flux.append((a, driver.flux_brake.onset, capacity))
    total = sum(power.values())
    run = partial(_run, t, total, flux, bus, c, v_s, v0,
                  _trips(trace, t, bus, coasts))
    if substep is not None:
        result = run(_positive(substep, "charge's substep"))
    else:
        h = float(np.max(np.diff(t)))
        result = run(h)
        for _ in range(MAX_HALVINGS):
            finer = run(h / 2)
            if abs(finer.peak - result.peak) < agree:
                break
            h, result = h / 2, finer
        else:
            moved = abs(finer.peak - result.peak)
            raise DriveError(
                f"the bus's peak still moved {moved:.3g} V on halving the "
                f"substep to {h / 2:.3g} s, after {MAX_HALVINGS} halvings; "
                f"agree is {agree:g} V")
        substep = h
    heat = {a: np.zeros(t.shape) for a in bus.actuators}
    for a, energy in result.flux.items():
        heat[a][:-1] = np.divide(energy, np.diff(t), out=np.zeros(len(energy)),
                                 where=np.diff(t) > 0)
    steps = np.diff(result.t)
    sourced, braked = result.source, result.brake
    taken = braked[:-1] * steps  # J, the brake's in each substep
    return Charged(
        _frozen(result.t), _frozen(result.v), result.peak,
        float(np.min(result.v)), _frozen(sourced), _frozen(braked),
        MappingProxyType({a: _frozen(h) for a, h in heat.items()}),
        MappingProxyType({a: _frozen(p) for a, p in power.items()}),
        float(np.sum(taken)), _largest_run(taken), float(np.max(braked)),
        float(max(0.0, np.max(sourced))),
        float(max(0.0, np.max(total + bus.hotel))),
        float(max(0.0, -np.min(sourced))),
        float(np.sum(sourced[:-1] * steps)), c, v_s, float(substep), agree,
        MappingProxyType(result.tripped))


class _Coast(NamedTuple):
    """A driver as `charge` trips it: its `level` (V), its actuator's
    `electrical` model on the trace's samples, its resolved constants `c`,
    and its `efficiency`."""
    level: float
    e: object
    c: object
    efficiency: float


class _Trips(NamedTuple):
    """What may trip on a bus over a trace: each trip's `levels` (V), by
    actuator or `TRIPPED_SOURCE`; each driver's `_Coast`; whether each of
    the trace's intervals is `prescribed`, outside every event; and the
    trips the events `recorded`, at their times in the trace (s)."""
    levels: dict
    drivers: dict
    prescribed: np.ndarray
    recorded: dict


def _trips(trace, t, bus, coasts):
    """The `_Trips` of `bus` over `trace`, sampled at `t`, each driver's
    from `coasts`."""
    levels = {a: d.level for a, d in coasts.items()}
    if bus.source is not None and bus.source.overvoltage is not None:
        levels[TRIPPED_SOURCE] = bus.source.overvoltage
    prescribed, recorded = np.ones(len(t) - 1, dtype=bool), {}
    events = getattr(trace, "events", ()) or ()
    if events:
        segment = np.asarray(trace.segment)[:-1]
        prescribed = ~np.isin(segment, [s.segment for s in events])
        for s in events:
            begun = trace.spans[s.segment][0]
            for key, when in s.run.tripped.items():
                recorded[key] = min(recorded.get(key, math.inf),
                                    begun + when)
    return _Trips(levels, coasts, prescribed, recorded)


def _largest_run(energies):
    """The most energy in one unbroken run of nonzero entries, each run
    summed in order."""
    on = np.concatenate(([False], np.asarray(energies) > 0, [False]))
    edges = np.flatnonzero(on[1:] != on[:-1]).reshape(-1, 2)
    return float(max((np.add.accumulate(energies[a:b])[-1]
                      for a, b in edges), default=0.0))


class _Run(NamedTuple):
    """One run of the bus: substep ends `t` and voltages `v`, the source's
    and brake's power over each substep (W), each flux brake's energy (J)
    over each of the trace's intervals, and the time (s) each driver or the
    source tripped."""
    t: np.ndarray
    v: np.ndarray
    source: np.ndarray
    brake: np.ndarray
    flux: dict
    tripped: dict

    @property
    def peak(self):
        return float(np.max(self.v))


class _Clamp(NamedTuple):
    """A clamp: the voltage `level` it holds, its `key`, and whether it is a
    `floor`, giving power to hold V up, or a ceiling, taking it to hold V
    down."""
    level: float
    key: tuple
    floor: bool


class _Substeps(NamedTuple):
    """The substeps of a run, end to end: each one's sample `interval` k,
    its index `j` among the `m` that interval splits into, its `step` (s)
    and its `end` (s)."""
    interval: np.ndarray
    j: np.ndarray
    m: np.ndarray
    step: np.ndarray
    end: np.ndarray


def _substeps(t, h):
    """Each interval of the sample times `t` split into the fewest equal
    substeps no longer than `h`; an interval of no length has none."""
    span = np.diff(t)
    kept = np.flatnonzero(span != 0)
    m = np.maximum(1, np.ceil(span[kept] / h - 1e-9)).astype(int)
    j = np.arange(int(np.sum(m))) - np.repeat(np.cumsum(m) - m, m)
    k, count = np.repeat(kept, m), np.repeat(m, m)
    step = np.repeat(span[kept] / m, m)
    end = np.where(j == count - 1, t[k + 1], t[k] + (j + 1) * step)
    return _Substeps(k, j, count, step, end)


def _run(t, power, flux, bus, c, v_s, v0, trips, h):
    """The bus over sample times `t` with the actuators' total bus `power`
    (W) at each, at substep `h`, from `v0`, its source at `v_s`, each of
    `trips` latching where the bus reaches it.

    Where the bus floats clear of every level, or is held at one, its
    substeps are taken together (`_together`), with the same arithmetic as
    `_substep`'s, so the run is the same to the bit. A substep that reaches
    a level or leaves one, that floats above a conducting brake, whose
    capacity moves with V, or in which a tripped driver's diodes conduct, is
    solved alone by `_substep`. A trip is a level with no clamp, where
    `_substep` stops on the trace's prescribed samples: the driver or source
    latches there, the rest of the substep runs at the new rate, and the
    trip's time is a substep's end."""
    half_c = 0.5 * c
    brake = bus.brake
    onsets = [(a, onset) for a, onset, _ in flux]
    pending = dict(trips.levels)  # V: each trip not yet reached
    levels = _levels(bus, c, v_s, onsets, pending.values())
    stops = frozenset(0.5 * c * level ** 2 for level in pending.values())
    first = min(stops, default=math.inf)  # J: the lowest trip's
    grid = _substeps(t, h)
    k, n = grid.interval, len(grid.interval)
    p0, p1 = power[k], power[k + 1]
    rate = -(p0 + (p1 - p0) * (grid.j + 0.5) / grid.m + bus.hotel)
    # W: each clamp's capacity at each substep; the brake's is set as it
    # runs, from V
    caps = {("flux", a): np.asarray(values, dtype=float)[k]
            for a, _, values in flux}
    if bus.source is not None:
        caps[SOURCE] = np.full(n, bus.source.p_max)
    # J: what each clamp took from the bus over each substep, a floor's
    # negative
    flows = {key: np.zeros(n) for key in (SOURCE, BRAKE, *caps)}
    energy = np.empty(n)
    step = grid.step.copy()  # a substep a trip splits keeps its last piece

    prescribed = trips.prescribed[k]
    begins = np.concatenate((t[:1], grid.end[:-1]))  # s: each substep's start
    # each substep at which an event's trip latches, and where the trace
    # turns prescribed, where a level an event's bus passed latches
    recorded = {}
    for key, when in trips.recorded.items():
        at = int(np.searchsorted(begins, when))
        if at < n:
            recorded.setdefault(at, []).append((key, when))
    turns = np.flatnonzero(prescribed[1:] & ~prescribed[:-1]) + 1
    breaks = np.unique(np.concatenate((turns, list(recorded)))).astype(int)
    tripped, diodes, pieces = {}, [], []
    diode = None  # J: in each substep, the energy under which a tripped
                  # driver's diodes conduct

    def latch(keys, i, when):
        """Trip each of `keys` at `when` (s), from substep `i` on: the
        source neither sources nor sinks, and a driver's flux brake is off,
        and, where the trace is prescribed, its actuator draws nothing and
        returns what its diodes conduct."""
        nonlocal diode, stops, first
        for key in keys:
            tripped[key] = when
            pending.pop(key, None)
            if key == TRIPPED_SOURCE:
                if SOURCE in caps:
                    caps[SOURCE][i:] = 0.0
                continue
            if ("flux", key) in caps:
                caps[("flux", key)][i:] = 0.0
            d = trips.drivers[key]
            fraction = (grid.j[i:] + 0.5) / grid.m[i:]
            ki = k[i:]
            emf = d.c.ke * d.e.omega
            emf = np.where(prescribed[i:], np.abs(
                emf[ki] + (emf[ki + 1] - emf[ki]) * fraction), 0.0)
            r = d.e.resistance[ki] + (d.e.resistance[ki + 1]
                                      - d.e.resistance[ki]) * fraction
            k_mod = d.c.k_mod
            diodes.append((i, k_mod, d.efficiency, emf, r))
            under = np.zeros(n)
            under[i:] = half_c * (emf / k_mod) ** 2
            diode = under if diode is None else np.maximum(diode, under)
        on = [a for a in trips.drivers if a not in tripped]
        drawn = (sum(trips.drivers[a].e.bus for a in on) if on
                 else np.zeros(len(t)))
        q0, q1 = drawn[k[i:]], drawn[k[i:] + 1]
        rate[i:] = np.where(prescribed[i:], -(
            q0 + (q1 - q0) * (grid.j[i:] + 0.5) / grid.m[i:] + bus.hotel),
            rate[i:])
        levels[:] = _levels(bus, c, v_s, onsets, pending.values())
        stops = frozenset(0.5 * c * level ** 2 for level in pending.values())
        first = min(stops, default=math.inf)

    def returned(i, v):
        """What the tripped drivers' diodes return (W) over substep `i` from
        bus voltage `v`: η·k_mod·V·(|E| − k_mod·V)/R_φ where |E| passes
        k_mod·V, held at the substep's starting V, the first-order term the
        substep's halving refines, as the brake's V²/R is."""
        return sum(eta * k_mod * v * max(0.0, emf[i - at] - k_mod * v)
                   / r[i - at] for at, k_mod, eta, emf, r in diodes
                   if i >= at)

    def reached(e):
        return [key for key, level in pending.items()
                if 0.5 * c * level ** 2 <= e]

    e, v, i = half_c * v0 ** 2, v0, 0
    window, wait = WINDOW, 0
    while i < n:
        if i in recorded:  # an event tripped them
            for key, when in recorded[i]:
                latch([key], i, when)
        if e >= first and prescribed[i]:
            latch(reached(e), i, float(begins[i]))
        taken = 0
        if i > 0 and wait == 0:  # the first runs from v0 itself, alone
            later = np.searchsorted(breaks, i, side="right")
            hi = min(n, i + window,
                     int(breaks[later]) if later < len(breaks) else n)
            taken = _together(e, v, i, hi, levels, rate, step, caps, brake,
                              energy, flows, diode)
            window = 2 * window if i + taken == hi else WINDOW
            wait = 0 if taken >= SPARSE else WAIT
        if taken:
            i += taken
            e = float(energy[i - 1])
        else:
            left, done = float(step[i]), 0.0
            while True:
                cap = {key: float(values[i]) for key, values in caps.items()}
                if brake is not None:
                    cap[BRAKE] = _brake_capacity(brake, v)
                into = float(rate[i]) + (returned(i, v) if diodes else 0.0)
                e, flowed, rest = _substep(e, into, left, levels, cap,
                                           stops if prescribed[i] else ())
                if not rest:
                    break
                done += left - rest  # a trip: the substep's piece before it
                when = float(begins[i]) + done
                pieces.append((i, left - rest, e, flowed, when))
                latch(reached(e), i, when)
                left, v = rest, math.sqrt(e / half_c)
            energy[i], step[i] = e, left
            for key, flow in flowed.items():
                flows[key][i] = flow
            i += 1
            wait = max(0, wait - 1)
        v = math.sqrt(e / half_c)

    ends = grid.end
    if pieces:  # each piece before a trip goes in ahead of its substep
        at = [i for i, *_ in pieces]
        ends = np.insert(ends, at, [when for *_, when in pieces])
        step = np.insert(step, at, [piece[1] for piece in pieces])
        energy = np.insert(energy, at, [piece[2] for piece in pieces])
        k = np.insert(k, at, k[at])
        flows = {key: np.insert(values, at, [piece[3].get(key, 0.0)
                                             for piece in pieces])
                 for key, values in flows.items()}
    heat = {}
    for a, _, _ in flux:
        heat[a] = np.zeros(len(t) - 1)
        np.add.at(heat[a], k, flows[("flux", a)])  # in substep order
    return _Run(np.concatenate(([float(t[0])], ends)),
                np.concatenate(([v0], np.sqrt(energy / half_c))),
                np.append(-flows[SOURCE] / step, 0.0),
                np.append(flows[BRAKE] / step, 0.0), heat, tripped)


WINDOW = 64  # substeps `_run` first tries to take together; doubled while
             # it takes them all
SPARSE, WAIT = 8, 16  # where fewer than SPARSE are taken together, the next
                      # WAIT substeps are solved alone first


def _together(e, v, lo, hi, levels, rate, step, caps, brake, energy, flows,
              diode=None):
    """Substeps `lo` to `hi` from energy `e` (J) at voltage `v`, as many as
    `_substep` takes without solving a crossing: while the bus floats
    between two levels and ends each substep clear of them, or while it is
    held at one by its clamps, and while no tripped driver's diodes
    conduct, which they do in a substep starting under its `diode` energy
    (J). Writes their energies and flows into `energy` and `flows`, each by
    `_substep`'s own arithmetic in its order, and returns how many it took,
    0 where the first needs solving alone."""
    at = next((i for i, (level, _, _) in enumerate(levels) if level == e),
              None)
    below = sum(1 for level, _, _ in levels if level < e) - 1
    above = below + 1 + (at is not None)
    gives = [f for _, fs, _ in levels[above:] for f in fs]
    takes = [c for _, _, cs in levels[:below + 1] for c in cs]
    if at is None and BRAKE in takes:
        return 0  # the brake conducts, at V²/R from each substep's V
    span = step[lo:hi]
    cap = {key: values[lo:hi] for key, values in caps.items()}
    if brake is not None:  # held, V is the same at every substep
        cap[BRAKE] = np.full(hi - lo, _brake_capacity(brake, v))
    net = rate[lo:hi] + _sum(cap[f] for f in gives) - _sum(
        cap[c] for c in takes)
    if at is None:
        ends = np.add.accumulate(np.concatenate(([e], net * span)))[1:]
        top = levels[above][0] if above < len(levels) else math.inf
        bottom = levels[below][0] if below >= 0 else 0.0
        clear = TOUCH * max([e, *(level for level, _, _ in levels)])
        near = (((net > 0) & (ends >= top - clear))
                | ((net < 0) & (ends <= bottom + clear)))
        if diode is not None:
            near |= np.concatenate(([e], ends[:-1])) < diode[lo:hi]
        taken = int(np.argmax(near)) if near.any() else len(net)
    else:
        _, floors, ceilings = levels[at]
        up = net - _sum(cap[key] for key in ceilings)
        down = net + _sum(cap[key] for key in floors)
        held = (up <= 0) & (0 <= down)
        if diode is not None:
            held &= e >= diode[lo:hi]
        taken = int(np.argmin(held)) if not held.all() else len(net)
        ends = np.full(taken, e)
    if not taken:
        return 0
    out = slice(lo, lo + taken)
    energy[out] = ends[:taken]
    span = span[:taken]
    for key in gives:
        flows[key][out] = 0.0 - cap[key][:taken] * span
    for key in takes:
        flows[key][out] = 0.0 + cap[key][:taken] * span
    if at is not None:  # what the level's clamps took up, shared
        net, amount = net[:taken], net[:taken] * span
        for keys, sharing in ((ceilings, net > 0), (floors, net < 0)):
            total = _sum(cap[key][:taken] for key in keys)
            for key in keys:
                with np.errstate(divide="ignore", invalid="ignore"):
                    part = np.where(total > 0,
                                    amount * cap[key][:taken] / total, 0.0)
                flows[key][out] = np.where(sharing, 0.0 + part,
                                           flows[key][out])
    return taken


TOUCH = 1e-9  # a substep ending within this fraction of a level's energy
              # is solved alone, where it may cross it


def _sum(terms):
    """Python's `sum` of floats, elementwise over arrays: since 3.12 it
    compensates (Neumaier's), so where three or more clamps are summed a
    plain `+` would differ from `_substep`'s in the last bit. Of fewer,
    the plain sum is the same."""
    terms = list(terms)
    if len(terms) <= 2:
        return sum(terms)
    total, carry = 0.0, 0.0
    for x in terms:
        t = total + x
        carry = carry + np.where(np.abs(total) >= np.abs(x),
                                 (total - t) + x, (x - t) + total)
        total = t
    return np.where((carry != 0) & np.isfinite(carry), total + carry, total)


def _flux_capacity(driver, motor, resistance):
    """What `driver`'s flux brake absorbs (W) at the winding's R_φ:
    i_d²·R_φ in d-q."""
    return driver.flux_brake.i_d.dq(motor.wiring) ** 2 * resistance


def _brake_capacity(brake, v):
    """What the brake resistor takes (W) over a substep starting at bus
    voltage `v`: V²/R, at its threshold where V is below it."""
    return max(v, brake.threshold) ** 2 / brake.r


def _levels(bus, c, v_s, flux, trips=()):
    """The clamps of `bus` at capacitance `c`, its source at `v_s`, with a
    flux brake at each (actuator, onset) in `flux`, grouped by level: each
    level's energy ½CV², its floors' keys and its ceilings' keys, lowest
    first, as `_substep` takes them. Each of `trips` (V) is a level too,
    with no clamp of its own unless one shares it."""
    clamps = []
    if bus.source is not None:
        clamps.append(_Clamp(v_s, SOURCE, True))
        if bus.source.sinks:
            clamps.append(_Clamp(v_s, SOURCE, False))
    if bus.brake is not None:
        clamps.append(_Clamp(bus.brake.threshold, BRAKE, False))
    clamps += [_Clamp(onset, ("flux", a), False) for a, onset in flux]
    return [(0.5 * c * level ** 2,
             [k.key for k in clamps if k.level == level and k.floor],
             [k.key for k in clamps if k.level == level and not k.floor])
            for level in sorted({k.level for k in clamps} | set(trips))]


def _substep(e, rate, step, levels, cap, stops=()):
    """The capacitor's energy `e` (J) after `step` (s) of a constant `rate`
    (W) into it, with the clamps at `levels` acting exactly: between levels
    every clamp is off or saturated, so e moves at a constant rate; at a
    level, its clamps hold e there if their capacity covers the rest, and
    otherwise it moves on. The net rate never rises with e, so e moves one
    way only and crosses each level at most once. Returns e, the energy
    each clamp took from the bus (J), a floor's negative, and the time left
    (s): 0, unless e rose to one of the levels in `stops`, where it stops
    before that level's clamps act."""
    flows = {}
    left = step

    def saturated(dt, below, above):
        """Every floor above e gives its capacity, and every ceiling below e
        takes its, for `dt`."""
        for i, (_, floors, ceilings) in enumerate(levels):
            if i >= above:
                for key in floors:
                    flows[key] = flows.get(key, 0.0) - cap[key] * dt
            if i <= below:
                for key in ceilings:
                    flows[key] = flows.get(key, 0.0) + cap[key] * dt

    def share(keys, amount):
        total = sum(cap[key] for key in keys)
        for key in keys:
            part = amount * cap[key] / total if total > 0 else 0.0
            flows[key] = flows.get(key, 0.0) + part

    while left > 0:
        at = next((i for i, (level, _, _) in enumerate(levels)
                   if level == e), None)
        below = sum(1 for level, _, _ in levels if level < e) - 1
        above = below + 1 + (at is not None)  # the first level above e
        net = (rate
               + sum(cap[f] for _, fs, _ in levels[above:] for f in fs)
               - sum(cap[c] for _, _, cs in levels[:below + 1] for c in cs))
        if at is not None:
            _, floors, ceilings = levels[at]
            up = net - sum(cap[key] for key in ceilings)
            down = net + sum(cap[key] for key in floors)
            if up <= 0 <= down:  # held: the level's clamps take up the rest
                saturated(left, below, above)
                if net > 0:
                    share(ceilings, net * left)
                elif net < 0:
                    share(floors, net * left)
                return e, flows, 0.0
            if up > 0:
                net, below = up, at
            else:
                net, above = down, at
        if net > 0 and above < len(levels):
            target = levels[above][0]
        elif net < 0:
            target = levels[below][0] if below >= 0 else 0.0
        else:
            target = None
        dt = left if target is None else (target - e) / net
        if dt >= left:
            saturated(left, below, above)
            return max(e + net * left, 0.0), flows, 0.0
        saturated(dt, below, above)
        e, left = target, left - dt
        if net > 0 and e in stops:  # a trip, which ends the substep here
            return e, flows, left
        if e == 0.0 and below < 0:  # the bus has collapsed
            saturated(left, below, above)
            return 0.0, flows, 0.0
    return e, flows, 0.0
