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
  takes, and #88 searches it.
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

The bus's bands, its `capacitance` and its source's `v`, are searched by
#88 as `Interval(*band)` axes; `charge` runs at one point in each, given as
`capacitance=` and `v_source=`, or the band's only value where it is one.
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
                         _positive, electrical)

AGREE = 0.01       # V: halving the substep moves the peak by less than this
MAX_HALVINGS = 10  # the substep's refinement gives up past this many halvings
SOURCE, BRAKE = ("source",), ("brake",)
# the clamps' keys; a flux brake's is ("flux", actuator)


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
    """The shared DC bus: the `actuators` on it, by name; its `source`; its
    `capacitance` (F), a (lo, hi) band or a number; an optional `brake`
    resistor; a constant `hotel` load (W); and the voltage `ratings` (V) of
    the parts on it that no driver carries, by name, such as `{"power
    board": 44.0}`, each one of the bus's trips. Flux braking is each
    driver's own, from its `Driver.flux_brake`."""
    actuators: tuple
    source: Source
    capacitance: tuple
    brake: BrakeResistor = None
    hotel: float = 0.0
    ratings: MappingProxyType = None

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
        object.__setattr__(self, "actuators", actuators)
        _kind("a bus", "source", self.source, Source)
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
            if not rating > self.source.v[1]:
                raise ValueError(f"a bus's rating {name!r} lies above its "
                                 f"source's v band; got {rating:g} V over "
                                 f"{self.source.v[1]:g} V")
        object.__setattr__(self, "ratings", MappingProxyType(
            {k: float(v) for k, v in ratings.items()}))


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
    """The bus over a trace, run at `capacitance` (F) and `v_source` (V)
    with a `substep` (s), halving which moves the peak by less than the
    `agree` it was run with.

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

    `power` is each actuator's bus power (W, positive drawing) and `flux`
    each flux brake's heat (W, zero where its driver has none), both on the
    trace's own times, each value the mean over the interval it starts:
    `heat(trace.t, thermal, power=flux[a], ...)` takes it as it is."""
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


def charge(trace, drive, *, capacitance=None, v_source=None, v0=None,
           agree=AGREE, substep=None, temperature=None, gear=None):
    """The bus of `drive` over `trace`, at `capacitance` (F) and `v_source`
    (V), each a point in its band, or the band's only value where it is
    one: a `Charged`. The bus starts at `v0` (V), by default `v_source`.

    Each actuator's load comes from `trace.output(a)` and its bus power from
    `electrical`, its winding at `temperature[a]` (°C, a number or one per
    sample; by default its resistance's T₀). `gear` gives the ratio of an
    actuation seam's actuator, which has none in the compiled model.

    Without a `substep` (s), it is refined from the trace's longest sample
    interval, halving until halving again moves the peak by less than
    `agree` (V); given, the bus runs at that substep alone."""
    if not isinstance(drive, Drive):
        raise TypeError(f"charge takes a Drive; got {drive!r}")
    bus = drive.bus
    c = _within("capacitance", bus.capacitance, capacitance)
    v_s = _within("v_source", bus.source.v, v_source)
    v0 = v_s if v0 is None else _positive(v0, "charge's v0")
    agree = _positive(agree, "charge's agree")
    t = np.asarray(trace.t, dtype=float)
    stray = sorted(set(getattr(trace, "torque", {})) - set(bus.actuators))
    if stray:
        raise ValueError(f"the trace drives {stray}, which have no drive "
                         f"data; give each a motor and driver on the bus")
    power, flux = {}, []
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
        if driver.flux_brake is not None:
            capacity = _flux_capacity(driver, motor, e.resistance)
            if a in driven:  # a coasting or shorted driver's bridge is off
                capacity = np.where(driven[a], capacity, 0.0)
            flux.append((a, driver.flux_brake.onset, capacity))
    total = sum(power.values())
    run = partial(_run, t, total, flux, bus, c, v_s, v0)
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
        float(np.sum(sourced[:-1] * steps)), c, v_s, float(substep), agree)


def _largest_run(energies):
    """The most energy in one unbroken run of nonzero entries."""
    best = run = 0.0
    for e in energies:
        run = run + e if e > 0 else 0.0
        best = max(best, run)
    return float(best)


class _Run(NamedTuple):
    """One run of the bus: substep ends `t` and voltages `v`, the source's
    and brake's power over each substep (W), and each flux brake's energy
    (J) over each of the trace's intervals."""
    t: np.ndarray
    v: np.ndarray
    source: np.ndarray
    brake: np.ndarray
    flux: dict

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


def _run(t, power, flux, bus, c, v_s, v0, h):
    """The bus over sample times `t` with the actuators' total bus `power`
    (W) at each, at substep `h`, from `v0`, its source at `v_s`."""
    half_c = 0.5 * c
    brake = bus.brake
    levels = _levels(bus, c, v_s, [(a, onset) for a, onset, _ in flux])
    flux_capacity = {("flux", a): values for a, _, values in flux}
    heat = {a: np.zeros(len(t) - 1) for a, _, _ in flux}

    energy, v = half_c * v0 ** 2, v0
    times, volts, sourced, braked = [float(t[0])], [v0], [], []
    cap = {SOURCE: bus.source.p_max}  # W: each clamp's capacity this substep
    for k in range(len(t) - 1):
        span = float(t[k + 1] - t[k])
        if span == 0:
            continue
        m = max(1, math.ceil(span / h - 1e-9))
        step = span / m
        p0, p1 = float(power[k]), float(power[k + 1])
        for key, values in flux_capacity.items():
            cap[key] = float(values[k])
        for j in range(m):
            if brake is not None:
                cap[BRAKE] = _brake_capacity(brake, v)
            drawn = p0 + (p1 - p0) * (j + 0.5) / m + bus.hotel
            energy, flows = _substep(energy, -drawn, step, levels, cap)
            v = math.sqrt(energy / half_c)
            times.append(float(t[k + 1]) if j == m - 1
                         else float(t[k]) + (j + 1) * step)
            volts.append(v)
            sourced.append(-flows.get(SOURCE, 0.0) / step)
            braked.append(flows.get(BRAKE, 0.0) / step)
            for a in heat:
                heat[a][k] += flows.get(("flux", a), 0.0)
    return _Run(np.array(times), np.array(volts), np.append(sourced, 0.0),
                np.append(braked, 0.0), heat)


def _flux_capacity(driver, motor, resistance):
    """What `driver`'s flux brake absorbs (W) at the winding's R_φ:
    i_d²·R_φ in d-q."""
    return driver.flux_brake.i_d.dq(motor.wiring) ** 2 * resistance


def _brake_capacity(brake, v):
    """What the brake resistor takes (W) over a substep starting at bus
    voltage `v`: V²/R, at its threshold where V is below it."""
    return max(v, brake.threshold) ** 2 / brake.r


def _levels(bus, c, v_s, flux):
    """The clamps of `bus` at capacitance `c`, its source at `v_s`, with a
    flux brake at each (actuator, onset) in `flux`, grouped by level: each
    level's energy ½CV², its floors' keys and its ceilings' keys, lowest
    first, as `_substep` takes them."""
    clamps = [_Clamp(v_s, SOURCE, True)]
    if bus.source.sinks:
        clamps.append(_Clamp(v_s, SOURCE, False))
    if bus.brake is not None:
        clamps.append(_Clamp(bus.brake.threshold, BRAKE, False))
    clamps += [_Clamp(onset, ("flux", a), False) for a, onset in flux]
    return [(0.5 * c * level ** 2,
             [k.key for k in clamps if k.level == level and k.floor],
             [k.key for k in clamps if k.level == level and not k.floor])
            for level in sorted({k.level for k in clamps})]


def _substep(e, rate, step, levels, cap):
    """The capacitor's energy `e` (J) after `step` (s) of a constant `rate`
    (W) into it, with the clamps at `levels` acting exactly: between levels
    every clamp is off or saturated, so e moves at a constant rate; at a
    level, its clamps hold e there if their capacity covers the rest, and
    otherwise it moves on. The net rate never rises with e, so e moves one
    way only and crosses each level at most once. Returns e and the energy
    each clamp took from the bus (J), a floor's negative."""
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
                return e, flows
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
            return max(e + net * left, 0.0), flows
        saturated(dt, below, above)
        e, left = target, left - dt
        if e == 0.0 and below < 0:  # the bus has collapsed
            saturated(left, below, above)
            return 0.0, flows
    return e, flows
