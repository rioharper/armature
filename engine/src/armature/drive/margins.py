"""The drive margins, searched (ADR 0005, ADR 0006).

`margins(drive, missions, over=space)` returns one ADR 0005 `Margin` per
check, each searched by `armature.search`:

- **per actuator**, every (τ, ω) sample inside the torque–speed envelope at
  the bus's lowest voltage, with the winding hot; the driver's peak current;
  the winding's temperature over the duty, or, where the motor publishes no
  `Thermal`, its RMS torque against its continuous rating; and the driver's
  RMS current against its continuous rating, where it gives one;
- **per bus**, its peak voltage against the lowest trip on it (each
  driver's `max_voltage`, the source's `overvoltage`, each of the bus's
  `ratings`), its row naming the part that binds; its minimum against
  the highest undervoltage trip; the brake resistor's pulse energy and its
  continuous power, where there is one; and the source's power.

A bus configuration with no source has no minimum-voltage or source-power
margin: its slack on each is +∞, and where no configuration has a source
neither is checked. Its hotel load still drains it, so its envelope reads
V_min no lower than each driver's undervoltage trip, below which the driver
is off.

`drive` is a `Drive`; or the project's `drive(p)`, called with `params`
and each drive band's value in, `Band(name, BANDS, of="drive")`; or a
mapping of names to either, the bus configurations, enumerated as the
`Choice` axis `"drive"`. `missions` is a sequence, or a mapping by name, of
missions as written (`Mission`s) and searched missions: callables
`mission(point) → Mission`, which build their moves from the point's axes,
a start from a `Coordinates` axis, a direction from a `Direction`, a
distance or an event's trigger fraction from an `Interval`. The missions
are the `Choice` axis `"mission"`.

What each margin searches:

- The **peak** margins (envelope, peak current, the bus's peak and minimum
  voltage, the brake's pulse, the source's power) search every axis of
  `over`, every mission, every bus configuration, and the bus's own bands,
  its capacitance and its source's voltage (with no source, the voltage it
  starts at), as the `Interval` axes `"capacitance"` and `"v_source"`.
- The **duty** margins (winding temperature or RMS torque, RMS current,
  the brake's power) run each mission as written, over its duty, searching
  only the bands and the bus configurations. A searched mission is never
  repeated over a duty: its worst move is a peak, not a session.

Every margin's slack at a point comes from one evaluation, shared: the
mission traced at `rate`, each actuator through the electrical model, and
the bus charged. The margins of one space read the same Sobol set, so the
evaluations are cached by point and each runs once. Where a motor has a
`Thermal`, the bus is charged twice: with every winding at its resistance's
T₀, which returns the most regeneration, for the peak voltage and the
brake; and with each winding at its `t_max`, which draws the most, for the
minimum voltage, the source's power, the flux brakes' heat and the
envelope, whose V_min it is. The envelope reads the winding hot too.

Each margin's `truth` re-runs its point at `confirm` (1 kHz) with each
event at half its timestep, and must agree within `agree` of the limit the
margin is checked against, a fraction.

A margin whose inputs are missing is UNCHECKED (`Margin.unchecked`): a
winding with neither a `Thermal` nor a continuous rating, or duty margins
with no mission as written. Its search returns a `Worst` naming them, and
fails.

`energy(...)` reports each written mission's energy, which no margin
checks. `review(margins)` plots each margin's worst case into `review/`.
"""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType

import numpy as np

from ..compiler import Compiled, compile
from ..search import (Band, Choice, Coordinates, Direction, Infeasible,
                      Interval, Margin, Point, Space, search)
from .bus import Drive, _v_source, charge
from .electrical import (_amps, _bound, _current_limit, _efficiencies, _hot,
                         _resolve, electrical)
from .event import Event
from .mission import CONFIRM_RATE, SEARCH_RATE, Mission, _actuators, trace
from .thermal import heat, repeat, rms_torque

TRUTH_AGREE = 0.01  # a margin's truth agrees within this fraction of its
                    # limit: the trip, the rating, the stall torque
RESERVED = ("mission", "drive", "capacitance", "v_source")
PEAK, DUTY = "peak", "duty"
WRITTEN = "a mission as written, with its duty"
KEPT_COMPILES = 8  # band values a setup keeps compiled; past it, it starts
                   # over, since a search moves on from a band value
KEPT_TRACES = 32   # written missions' traces, kept the same way


def margins(drive, missions, over=None, *, model=None, params=None,
            gear=None, rate=SEARCH_RATE, confirm=CONFIRM_RATE,
            agree=TRUTH_AGREE, budget=None):
    """The drive margins of `drive` over `missions`, searched over `over`:
    a tuple of `Margin`s, the peak margins first, then the duty margins.

    The missions run on the mechanism of `over`'s `Coordinates` axis, or,
    where it has none, on `model`, a compiled mechanism. `params` are the
    drive's parameters, which a callable `drive(p)` is called with. `gear`
    gives an actuation seam's actuators their ratio, as `charge` takes it.
    Missions are traced at `rate` (Hz) in the search and at `confirm` for
    the truth, which must agree within `agree` of each margin's limit.
    `budget` is each margin's search budget."""
    setup = _Setup(drive, missions, over, model, params, gear)
    rate = _rate(rate, "rate")
    confirm = _rate(confirm, "confirm")
    agree = float(agree)
    if not (math.isfinite(agree) and agree > 0):
        raise ValueError(f"margins' agree is a positive fraction of each "
                         f"margin's limit; got {agree}")
    out = []
    for kind, space in ((PEAK, setup.space(PEAK)), (DUTY, setup.space(DUTY))):
        evaluator = _Evaluator(setup, space, kind, rate, confirm)
        for check in setup.checks(kind):
            if check.missing:
                out.append(Margin(check.name, _never, check.unit,
                                  over=Space(), unchecked=check.missing))
                continue
            out.append(Margin(
                check.name, _Slack(evaluator, check, False), check.unit,
                over=space, truth=_Slack(evaluator, check, True),
                agree=agree * check.limit, budget=budget,
                against=check.against))
    return tuple(out)


def _never(point):
    raise AssertionError("an UNCHECKED margin is never evaluated")


def _rate(value, name):
    value = float(value)
    if not (math.isfinite(value) and value > 0):
        raise ValueError(f"margins' {name} is a positive rate in Hz; got "
                         f"{value}")
    return value


@dataclass(frozen=True)
class _Check:
    """One margin's identity: its `name`, `unit`, `kind` (peak or duty),
    what it reads (`what`), its `actuator` or None for the bus, the `limit`
    (in `unit`) its truth's tolerance is a fraction of, the plot that
    reviews it, the inputs it is `missing`, if any, and what its row says
    it is held `against`, if anything."""
    name: str
    unit: str
    kind: str
    what: str
    actuator: str
    limit: float
    plot: str
    missing: tuple = None
    against: str = None


@dataclass(frozen=True)
class Energy:
    """A written mission's energy (J) over one run, on bus configuration
    `drive` (None where there is one): what the `source` gave, net; what
    the actuators `regenerated` into the bus; what the `brake` resistor
    took; the windings' `copper` loss; and the flux brakes' heat, `flux`.
    `per_session` is the source's over the duty's session, its runs end to
    end, or None without a duty."""
    mission: str
    drive: str
    duration: float
    source: float
    regenerated: float
    brake: float
    copper: float
    flux: float
    per_session: float


def energy(drive, missions, over=None, *, model=None, params=None,
           gear=None, rate=SEARCH_RATE):
    """Each written mission's `Energy` on each bus configuration, at
    nominal: every band at its parameter's nominal, the bus's capacitance
    and source voltage at the middle of their bands. Reported, not
    checked."""
    setup = _Setup(drive, missions, over, model, params, gear)
    rate = _rate(rate, "rate")
    out = []
    for config in setup.configs:
        for name in setup.written:
            values = {"mission": name, "drive": config}
            run = setup.run(values, rate, nominal=True)
            regenerated = copper = 0.0
            for a in setup.actuators:
                e = run.loads[a]
                regenerated += _integral(run.trace.t, np.maximum(
                    -e.bus, 0.0))
                copper += _integral(run.trace.t, e.copper)
            c = run.charged
            flux = sum(_held(run.trace.t, h) for h in c.flux.values())
            duty = run.mission.duty
            out.append(Energy(
                name, config if setup.configured else None,
                run.trace.duration, c.source_energy, regenerated,
                c.brake_energy, copper, flux,
                None if duty is None
                else c.source_energy * duty.session / duty.period))
    return tuple(out)


def _integral(t, values):
    return float(np.trapezoid(values, t))


def _held(t, values):
    """The integral of `values` each held over the interval it starts."""
    return float(np.sum(np.asarray(values)[:-1] * np.diff(t)))


class _Setup:
    """What every margin reads, checked once: the bus configurations, the
    missions, the mechanism, the bands and the spaces."""

    def __init__(self, drive, missions, over, model, params, gear):
        if over is None:
            over = Space()
        if not isinstance(over, Space):
            raise TypeError(f"margins search over a Space; got {over!r}")
        reserved = sorted(set(over.axes) & set(RESERVED))
        if reserved:
            raise ValueError(f"the axes {reserved} are the margins' own; "
                             f"name yours otherwise")
        self.axes = dict(over.axes)
        self.params = MappingProxyType(dict(params or {}))
        self.gear = MappingProxyType(dict(gear or {}))
        self._mechanism(over, model)
        self._bands()
        self._configs(drive)
        self._missions(missions)
        self._compiles = {}
        self._traces = {}

    # --- what the margins run on ---------------------------------------------
    def _mechanism(self, over, model):
        found = [n for n, a in over.axes.items() if isinstance(a, Coordinates)]
        self.coordinates = found[0] if found else None
        if found:
            axis = over.axes[found[0]]
            self.mechanism, self.mechanism_params = axis.mechanism, axis.params
            self.model = model if model is not None else \
                axis._cube({}).compiled
        elif model is not None:
            if not isinstance(model, Compiled):
                raise TypeError(f"margins' model is a compiled mechanism, "
                                f"armature.compile(...); got {model!r}")
            self.model = model
            self.mechanism, self.mechanism_params = model._source or (
                None, MappingProxyType({}))
        else:
            raise TypeError("margins trace the missions on a mechanism: give "
                            "over a Coordinates axis, or model=compile(...)")
        if not isinstance(self.model, Compiled):
            raise TypeError(f"margins' model is a compiled mechanism; got "
                            f"{self.model!r}")

    def _bands(self):
        self.mechanism_bands, self.drive_bands = {}, {}
        for name, axis in self.axes.items():
            if not isinstance(axis, Band):
                continue
            if axis.of == "mechanism":
                owner, known = self.mechanism_bands, self.mechanism_params
            elif axis.of == "drive":
                owner, known = self.drive_bands, self.params
            else:
                raise ValueError(f"band {axis.param!r} is of {axis.of!r}; the "
                                 f"drive margins read bands of 'mechanism' "
                                 f"and of 'drive'")
            if axis.param not in known:
                raise ValueError(f"band {axis.param!r} names no parameter of "
                                 f"the {axis.of}; its parameters are "
                                 f"{sorted(known)}")
            nominal = known[axis.param]
            if not axis.lo <= nominal <= axis.hi:
                raise ValueError(f"band {axis.param!r}: its nominal "
                                 f"{nominal!r} lies outside the band "
                                 f"({axis.lo!r}, {axis.hi!r})")
            owner[name] = axis

    def _configs(self, drive):
        self.configured = isinstance(drive, Mapping)
        configs = dict(drive) if self.configured else {None: drive}
        if not configs:
            raise ValueError("margins take at least one bus configuration")
        for name, d in configs.items():
            if not (isinstance(d, Drive) or callable(d)):
                raise TypeError(f"a bus configuration is a Drive or a "
                                f"callable drive(p); got {d!r}"
                                + (f" for {name!r}" if name else ""))
            if callable(d) and not isinstance(d, Drive) and not self.params:
                raise TypeError("a callable drive(p) is called with the "
                                "drive's parameters; give params=")
        if self.drive_bands and all(isinstance(d, Drive)
                                    for d in configs.values()):
            raise ValueError(f"the drive bands {sorted(self.drive_bands)} "
                             f"are read by a callable drive(p), and every "
                             f"bus configuration is a fixed Drive")
        self.configs = configs
        self.nominal = {n: self._drive(n, {}) for n in configs}
        self.first = next(iter(self.nominal.values()))
        self.braked = any(d.bus.brake is not None
                          for d in self.nominal.values())
        self.actuators = self.first.bus.actuators
        for n, d in self.nominal.items():
            if set(d.bus.actuators) != set(self.actuators):
                raise ValueError(f"bus configuration {n!r} carries "
                                 f"{list(d.bus.actuators)}, where "
                                 f"{list(self.actuators)} are carried by "
                                 f"another; the configurations share their "
                                 f"actuators")
        self.capacitance = _union(d.bus.capacitance
                                  for d in self.nominal.values())
        self.v_source = _union(_v_source(d.bus)
                               for d in self.nominal.values())
        self.sourced = [d for d in self.nominal.values()
                        if d.bus.source is not None]
        self.compiled_gear = {a: g for a, (_, g, _)
                              in _actuators(self.model).items()}

    def _drive(self, config, values):
        d = self.configs[config]
        if not isinstance(d, Drive):
            d = d({**self.params, **values})
            if not isinstance(d, Drive):
                raise TypeError(f"drive(p) returns a Drive; got {d!r}")
        return d

    def _missions(self, missions):
        if isinstance(missions, Mission) or callable(missions):
            missions = [missions]
        if isinstance(missions, Mapping):
            named = dict(missions)
        else:
            named = {}
            for m in missions:
                name = m.name if isinstance(m, Mission) else getattr(
                    m, "__name__", None)
                if not isinstance(name, str) or name == "<lambda>":
                    raise TypeError(f"a searched mission is a named function "
                                    f"of the point, or give the missions as "
                                    f"a mapping by name; got {m!r}")
                if name in named:
                    raise ValueError(f"two missions are named {name!r}")
                named[name] = m
        if not named:
            raise ValueError("margins take at least one mission")
        for name, m in named.items():
            if not (isinstance(m, Mission) or callable(m)):
                raise TypeError(f"mission {name!r} is a Mission or a callable "
                                f"mission(point); got {m!r}")
        self.missions = named
        self.written = tuple(n for n, m in named.items()
                             if isinstance(m, Mission))

    def gear_of(self, a):
        if a in self.gear:
            return float(self.gear[a])
        if a in self.compiled_gear:
            return self.compiled_gear[a]
        raise KeyError(f"{a!r} has no gear in the compiled model; give its "
                       f"ratio, margins(..., gear={{{a!r}: n}})")

    # --- the spaces ----------------------------------------------------------
    def space(self, kind):
        if kind == PEAK:
            axes = dict(self.axes)
            names = tuple(self.missions)
        else:
            axes = {n: a for n, a in self.axes.items() if isinstance(a, Band)}
            names = self.written
        if names:
            axes["mission"] = Choice(names)
        if self.configured:
            axes["drive"] = Choice(tuple(self.configs))
        for name, band in (("capacitance", self.capacitance),
                           ("v_source", self.v_source)):
            if band[0] < band[1]:
                axes[name] = Interval(*band)
        return Space(**axes)

    # --- the checks ----------------------------------------------------------
    def checks(self, kind):
        first = self.first
        out = []
        if kind == PEAK:
            for a in self.actuators:
                motor, driver = first.motors[a], first.drivers[a]
                n = self.gear_of(a)
                box = first.gearboxes.get(a)
                c = _resolve(motor, n, box)
                stall = (c.kt * _current_limit(c, motor, driver) * n
                         * _efficiencies(box)[0])
                out.append(_Check(f"{a}: envelope at V_min", "N·m", PEAK,
                                  "envelope", a, stall, "torque-speed"))
                out.append(_Check(f"{a}: driver peak current",
                                  driver.i_peak.per, PEAK, "peak current", a,
                                  driver.i_peak.value, "torque-speed"))
            out.append(_Check("bus: peak V", "V", PEAK, "peak V", None,
                              _trip(first), "bus",
                              against=_against(self.nominal)))
            if self.sourced:
                held = self.sourced[0]
                out.append(_Check("bus: minimum V", "V", PEAK, "minimum V",
                                  None, _undervoltage(held)
                                  or held.bus.source.v[0], "bus"))
            if self.braked:
                brake = _first_brake(self.nominal)
                out.append(_Check("bus: brake pulse energy", "J", PEAK,
                                  "brake pulse", None, brake.energy, "bus"))
            if self.sourced:
                out.append(_Check("bus: source power", "W", PEAK,
                                  "source power", None,
                                  self.sourced[0].bus.source.p_max, "bus"))
            return out
        missing = None if self.written else (WRITTEN,)
        for a in self.actuators:
            out.append(self._winding(a, missing))
            if any(d.drivers[a].i_continuous is not None
                   for d in self.nominal.values()):
                rating = next(d.drivers[a].i_continuous
                              for d in self.nominal.values()
                              if d.drivers[a].i_continuous is not None)
                out.append(_Check(f"{a}: driver RMS current", rating.per,
                                  DUTY, "RMS current", a, rating.value,
                                  "torque-speed", missing))
        if self.braked:
            out.append(_Check("bus: brake power", "W", DUTY, "brake power",
                              None, _first_brake(self.nominal).power, "bus",
                              missing))
        return out

    def _winding(self, a, missing):
        """The winding's check: its temperature where every configuration's
        motor has a `Thermal`, its RMS torque where none has one and each
        gives a continuous rating, and UNCHECKED where a motor has
        neither."""
        kinds = set()
        for d in self.nominal.values():
            motor = d.motors[a]
            kinds.add("thermal" if motor.thermal is not None else
                      "rms" if motor.i_continuous is not None else None)
        if len(kinds) > 1:
            raise ValueError(f"the bus configurations give {a!r}'s motor "
                             f"different thermal data; give each the same")
        kind = kinds.pop()
        first = self.first
        motor = first.motors[a]
        if kind is None:
            return _Check(f"{a}: winding", "K", DUTY, "winding", a, 1.0,
                          "winding", (f"motors[{a!r}].thermal",
                                      f"motors[{a!r}].i_continuous"))
        if kind == "thermal":
            th = motor.thermal
            return _Check(f"{a}: winding temperature", "K", DUTY,
                          "temperature", a, th.t_max - th.t_ambient,
                          "winding", missing)
        c = _resolve(motor, self.gear_of(a), first.gearboxes.get(a))
        return _Check(f"{a}: RMS torque", "N·m", DUTY, "RMS torque", a,
                      c.kt * c.i_continuous, "torque-speed", missing)

    # --- one evaluation ------------------------------------------------------
    def run(self, values, rate, confirm=False, nominal=False):
        """The mission at a point's `values`, traced at `rate`, through the
        electrical model and the bus: a `_Ran`."""
        mechanism = {} if nominal else {
            b.param: float(values[n]) for n, b in self.mechanism_bands.items()}
        drive_values = {} if nominal else {
            b.param: float(values[n]) for n, b in self.drive_bands.items()}
        if self.coordinates is not None and values.get(
                self.coordinates) is not None:
            m = values[self.coordinates].compiled
        else:
            m = self._compiled(mechanism)
        config = values.get("drive") if self.configured else None
        d = self._drive(config, drive_values)
        if set(d.bus.actuators) != set(self.actuators):
            raise ValueError(f"drive(p) carries {list(d.bus.actuators)} at "
                             f"{drive_values}; at nominal it carries "
                             f"{list(self.actuators)}")
        if nominal:
            cap = sum(d.bus.capacitance) / 2
            v_s = sum(_v_source(d.bus)) / 2
        else:
            cap = _clip(values.get("capacitance"), d.bus.capacitance)
            v_s = _clip(values.get("v_source"), _v_source(d.bus))
        name = values["mission"]
        mission = self.missions[name]
        if not isinstance(mission, Mission):
            mission = mission(Point(values))
            if not isinstance(mission, Mission):
                raise TypeError(f"mission {name!r} returns a Mission; got "
                                f"{mission!r}")
        if confirm:
            mission = _halved(mission)
        t = self._trace(name, m, mission, rate, d, cap, v_s, mechanism,
                        confirm)
        loads, r_hot, hot = {}, {}, {}
        for a in self.actuators:
            n = self.gear_of(a)
            tau, omega, rotor = t.output(a, n)
            motor, driver = d.motors[a], d.drivers[a]
            box = d.gearboxes.get(a)
            if box is None and n != 1:
                raise ValueError(f"{a!r} has a gear of {n:g} but no gearbox; "
                                 f"give gearboxes={{{a!r}: "
                                 f"Gearbox(forward=...)}}")
            loads[a] = electrical(tau, omega, n, motor, box, driver,
                                  rotor=rotor)
            if motor.thermal is not None:
                hot[a] = motor.thermal.t_max
            r_hot[a] = float(_hot(_resolve(motor, n, box), hot.get(a)))
        gear = {a: self.gear_of(a) for a in self.actuators}
        charged = charge(t, d, capacitance=cap, v_source=v_s, gear=gear)
        sagged = charged if not hot else charge(
            t, d, capacitance=cap, v_source=v_s, gear=gear, temperature=hot)
        return _Ran(values, m, d, mission, t, loads, r_hot, charged, sagged)

    def _compiled(self, bands):
        key = tuple(sorted(bands.items()))
        if not any(v != self.mechanism_params[p] for p, v in bands.items()):
            return self.model
        if key not in self._compiles:
            if len(self._compiles) > KEPT_COMPILES:
                self._compiles.clear()
            self._compiles[key] = compile(
                self.mechanism, {**self.mechanism_params, **bands})
        return self._compiles[key]

    def _trace(self, name, m, mission, rate, d, cap, v_s, mechanism,
               confirm):
        """The mission traced; a written mission without events depends on
        nothing but the mechanism's bands, so its trace is kept."""
        events = any(isinstance(s, Event) for s in mission.segments)
        if events:
            return trace(m, mission, rate, drive=d, capacitance=cap,
                         v_source=v_s)
        if name not in self.written:
            return trace(m, mission, rate)
        key = (name, rate, tuple(sorted(mechanism.items())), confirm)
        if key not in self._traces:
            if len(self._traces) > KEPT_TRACES:
                self._traces.clear()
            self._traces[key] = trace(m, mission, rate)
        return self._traces[key]

    def slack(self, check, ran):
        """`check`'s slack on the evaluation `ran`."""
        what, a, d, c = check.what, check.actuator, ran.drive, ran.charged
        if a is not None:
            motor, driver = d.motors[a], d.drivers[a]
            e = ran.loads[a]
            wiring = motor.wiring
        if what == "envelope":
            return self._envelope(a, ran)[0]
        if what == "peak current":
            per = check.unit
            limit = driver.i_peak.dq(wiring)
            return (limit - float(np.max(np.abs(e.current)))) / _amps(
                per, wiring)
        if what == "peak V":
            return _trip(d) - c.peak
        if what in ("minimum V", "source power") and d.bus.source is None:
            return math.inf
        if what == "minimum V":
            return ran.sagged.minimum - _undervoltage(d)
        if what == "brake pulse":
            return math.inf if d.bus.brake is None else (
                d.bus.brake.energy - c.brake_pulse)
        if what == "source power":
            return d.bus.source.p_max - ran.sagged.source_demand
        t = ran.trace.t
        duty = ran.mission.duty
        period = duty.period if duty is not None else ran.trace.duration
        if what == "temperature":
            return motor.thermal.t_max - self.heated(a, ran).peak
        if what == "RMS torque":
            k = _resolve(motor, self.gear_of(a), d.gearboxes.get(a))
            return k.kt * k.i_continuous - rms_torque(t, e.tau, period)
        if what == "RMS current":
            rating = driver.i_continuous
            if rating is None:
                return math.inf
            rms = rms_torque(t, e.current, period)  # a held trace's RMS
            return (rating.dq(wiring) - rms) / _amps(check.unit, wiring)
        if what == "brake power":
            return math.inf if d.bus.brake is None else (
                d.bus.brake.power - c.brake_energy / period)
        raise AssertionError(what)

    def heated(self, a, ran):
        """`a`'s winding over the mission's duty, repeated to its periodic
        state or its session's end, or run once without a duty."""
        motor = ran.drive.motors[a]
        t, duty = ran.trace.t, ran.mission.duty
        flux, current = ran.sagged.flux[a], ran.loads[a].current
        if duty is None:
            return heat(t, motor.thermal, power=flux, current=current,
                        motor=motor)
        return repeat(t, motor.thermal, duty.period, duty.session,
                      power=flux, current=current, motor=motor)

    def _envelope(self, a, ran):
        """`a`'s envelope slack (N·m at the output, the envelope's own scale
        Kt·N·η) and its `Envelope` at V_min with the winding hot, on a bus
        with no source no lower than the driver's undervoltage trip. Each
        sample's d-q current must lie within the current limit and within
        the voltage limit |R·i + E| ≤ k_mod·V_min; its slack is the nearer
        of the two bounds."""
        d = ran.drive
        motor, driver = d.motors[a], d.drivers[a]
        n, box = self.gear_of(a), d.gearboxes.get(a)
        c = _resolve(motor, n, box)
        e, r = ran.loads[a], ran.r_hot[a]
        v_min = ran.v_min
        if d.bus.source is None:  # drained below its trip, the driver is off
            v_min = max(v_min, driver.undervoltage)
        i_max = _current_limit(c, motor, driver)
        v_max = c.k_mod * v_min
        back = c.ke * e.omega
        hi = np.minimum(i_max, (v_max - back) / r)
        lo = np.maximum(-i_max, (-v_max - back) / r)
        within = np.minimum(e.current - lo, hi - e.current)
        scale = c.kt * n * _efficiencies(box)[0]
        return (scale * float(np.min(within)),
                _bound(c, n, v_min, _efficiencies(box)[0], i_max, r)
                if v_min > 0 else None)


@dataclass(frozen=True)
class _Ran:
    """One evaluation: the point's `values`, the compiled model `m`, the
    `drive`, the `mission` as run, its `trace`, each actuator's electrical
    model (`loads`; its current is the same at any winding temperature) and
    its winding's resistance hot (`r_hot`, Ω), and the bus charged with
    every winding at T₀ (`charged`) and with each at its `t_max`
    (`sagged`), one run where no motor has a `Thermal`."""
    values: dict
    m: object
    drive: Drive
    mission: Mission
    trace: object
    loads: dict
    r_hot: dict
    charged: object
    sagged: object

    @property
    def v_min(self):
        """The bus's lowest voltage, with the windings hot (V)."""
        return max(self.sagged.minimum, 0.0)


class _Evaluator:
    """The evaluations of one space, cached by point, so the margins
    searched over it share each one: the slack of every check at a point,
    or the `Infeasible` it raised."""

    def __init__(self, setup, space, kind, rate, confirm):
        self.setup, self.space, self.kind = setup, space, kind
        self.rate, self.confirm = rate, confirm
        self.checks = [c for c in setup.checks(kind) if not c.missing]
        self._slacks = {}

    def slacks(self, point, confirm):
        key = (confirm, _key(self.space, point))
        if key not in self._slacks:
            try:
                ran = self.ran(point, confirm)
            except Infeasible as refused:
                self._slacks[key] = refused
            else:
                self._slacks[key] = {
                    check.name: float(self.setup.slack(check, ran))
                    for check in self.checks}
        found = self._slacks[key]
        if isinstance(found, Infeasible):
            raise Infeasible(found.reason)
        return found

    def ran(self, point, confirm):
        values = {n: point[n] for n in point}
        return self.setup.run(values, self.confirm if confirm else self.rate,
                              confirm)

    def point(self, at):
        """The `Point` a `Worst`'s `at` was read from."""
        values = {}
        bands = {b.param: float(at[n]) for n, b
                 in self.setup.mechanism_bands.items() if n in at}
        for name, axis in self.space.axes.items():
            plain = at[name]
            if isinstance(axis, Coordinates):
                m = axis._cube(bands).compiled
                values[name] = m.at(q=dict(plain))
            elif isinstance(axis, Direction):
                vector = np.array(plain, dtype=float)
                vector.flags.writeable = False
                values[name] = vector
            elif isinstance(axis, Interval):
                values[name] = float(plain)
            else:
                values[name] = plain
        return Point(values)


class _Slack:
    """A drive margin's `fn` (or, confirming, its `truth`): its check's
    slack at a point, from the evaluation its space shares."""

    def __init__(self, evaluator, check, confirm):
        self.evaluator, self.check, self.confirm = evaluator, check, confirm

    def __call__(self, point):
        return self.evaluator.slacks(point, self.confirm)[self.check.name]

    def __repr__(self):
        return (f"<{'truth' if self.confirm else 'slack'} of "
                f"{self.check.name!r}>")


def _key(space, point):
    return tuple((n, _hashable(space.axes[n].plain(point[n])))
                 for n in space.axes)


def _hashable(value):
    if isinstance(value, Mapping):
        return tuple((k, _hashable(v)) for k, v in sorted(value.items()))
    if isinstance(value, (tuple, list, np.ndarray)):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, (np.floating, float)):
        return float(value)
    return value


def _union(bands):
    bands = list(bands)
    return (min(lo for lo, _ in bands), max(hi for _, hi in bands))


def _clip(value, band):
    """A point's bus value in one configuration's `band`: its nearest end
    where the configurations' union reaches past it; the band's low end
    where the space has no such axis, its value being the only one."""
    lo, hi = band
    if value is None:
        return lo
    return min(max(float(value), lo), hi)


def _undervoltage(d):
    """The highest undervoltage trip on the bus of `d`."""
    return max(d.drivers[a].undervoltage for a in d.bus.actuators)


def _trip(d):
    """The lowest overvoltage trip on the bus of `d` (V)."""
    return _lowest(d)[0]


def _lowest(d):
    """The lowest overvoltage trip on the bus of `d` and what binds there:
    (V, its parts, named), every driver there named as one."""
    drivers = {f"{a}'s driver": d.drivers[a].max_voltage
               for a in d.bus.actuators}
    trips = dict(d.bus.ratings)
    source = d.bus.source
    if source is not None and source.overvoltage is not None:
        trips["the source's overvoltage"] = source.overvoltage
    low = min([*drivers.values(), *trips.values()])
    parts = [n for n, v in trips.items() if v == low]
    tied = [n for n, v in drivers.items() if v == low]
    if len(tied) == len(drivers) > 1:
        tied = ["every driver"]
    return low, parts + tied


def _against(nominal):
    """What the peak V is held under, the lowest trip at nominal, named for
    its row: once where every bus configuration shares it, each named
    otherwise."""
    named = {c: "{} ({:g} V)".format(", ".join(parts), low)
             for c, (low, parts) in ((c, _lowest(d))
                                     for c, d in nominal.items())}
    if len(set(named.values())) == 1:
        return next(iter(named.values()))
    return ", ".join(f"{text} on {c}" for c, text in named.items())


def _first_brake(nominal):
    return next(d.bus.brake for d in nominal.values()
                if d.bus.brake is not None)


def _halved(mission):
    """`mission` with each event at half its timestep."""
    if not any(isinstance(s, Event) for s in mission.segments):
        return mission
    return replace(mission, segments=tuple(
        replace(s, timestep=s.timestep / 2) if isinstance(s, Event) else s
        for s in mission.segments))


# --- the review --------------------------------------------------------------
@dataclass(frozen=True)
class Reviewed:
    """A margin's review plot: the `margin`'s name, the PNG's `path`, and
    the titles of its `panels`, also written into the PNG as its `Panels`
    text."""
    margin: str
    path: Path
    panels: tuple


def review(margins, directory="review", worsts=None):
    """Plot each drive margin's worst case at its truth's resolution into
    `directory`, one PNG per margin, and return a `Reviewed` for each:

    - an actuator's envelope, current and RMS-torque margins: its (τ, ω)
      samples over its envelope at V_min, the winding hot;
    - the bus's margins: V(t) against its trip lines, and the source's and
      brake's power;
    - a winding temperature margin: T(t) over the last cycle against the
      winding's limit.

    `worsts` are the margins' `Worst`s, a sequence or a mapping by name; a
    margin without one is searched. An UNCHECKED margin has no worst case
    and is not plotted. matplotlib, a development dependency, draws them."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("the drive review is drawn by matplotlib: "
                          "`uv add --dev matplotlib`") from None
    if isinstance(worsts, Mapping):
        found = dict(worsts)
    else:
        found = {w.margin: w for w in worsts or ()}
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    out = []
    for margin in margins:
        if not isinstance(margin, Margin):
            raise TypeError(f"review takes the drive margins; got {margin!r}")
        if margin.unchecked:
            continue
        if not isinstance(margin.fn, _Slack):
            raise TypeError(f"margin {margin.name!r} is not a drive margin; "
                            f"review plots those of armature.drive.margins")
        worst = found.get(margin.name) or search(margin)
        if worst.unchecked:
            continue
        evaluator, check = margin.fn.evaluator, margin.fn.check
        ran = evaluator.ran(evaluator.point(worst.at), True)
        draw = {"torque-speed": _torque_speed, "bus": _bus,
                "winding": _winding}[check.plot]
        panels = draw(plt, evaluator.setup, check, ran, worst)
        path = directory / f"{_slug(margin.name)}.png"
        figure = plt.gcf()
        figure.suptitle(str(worst).split(";")[0], fontsize=9)
        figure.tight_layout()
        figure.savefig(path, dpi=110,
                       metadata={"Title": margin.name,
                                 "Panels": "; ".join(panels)})
        plt.close(figure)
        out.append(Reviewed(margin.name, path, tuple(panels)))
    return tuple(out)


def _slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()


def _torque_speed(plt, setup, check, ran, worst):
    a = check.actuator
    figure, axis = plt.subplots(figsize=(6.4, 4.8))
    tau, omega, _ = ran.trace.output(a, setup.gear_of(a))
    _, bound = setup._envelope(a, ran)
    if bound is not None:
        speeds = np.linspace(-bound.no_load_speed, bound.no_load_speed, 401)
        limit = bound.torque(speeds)
        axis.plot(speeds, limit, color="black", lw=1,
                  label=f"envelope at V_min = {bound.v_bus:.4g} V, "
                        f"winding hot")
        axis.plot(speeds, -limit, color="black", lw=1)
    axis.scatter(omega, tau, s=4, color="tab:blue", label="samples")
    axis.axhline(0, color="grey", lw=0.5)
    axis.axvline(0, color="grey", lw=0.5)
    axis.set_xlabel("ω at the output (rad/s)")
    axis.set_ylabel("τ at the output (N·m)")
    title = f"{a}: (τ, ω) samples over the envelope at V_min"
    axis.set_title(title, fontsize=9)
    axis.legend(fontsize=7)
    return [title]


def _bus(plt, setup, check, ran, worst):
    d, c = ran.drive, ran.charged
    figure, (volts, power) = plt.subplots(2, 1, figsize=(6.4, 6.4),
                                          sharex=True)
    volts.plot(c.t, c.v, color="tab:blue", lw=1, label="V(t), windings at T₀")
    if ran.sagged is not c:
        volts.plot(ran.sagged.t, ran.sagged.v, color="tab:purple", lw=1,
                   label="V(t), windings hot")
    trip, parts = _lowest(d)
    volts.axhline(trip, color="tab:red", lw=1,
                  label=f"lowest trip: {', '.join(parts)}")
    volts.axhline(_undervoltage(d), color="tab:red", ls="--", lw=1,
                  label="undervoltage trip")
    if d.bus.brake is not None:
        volts.axhline(d.bus.brake.threshold, color="tab:orange", ls=":",
                      lw=1, label="brake threshold")
    onsets = sorted({d.drivers[a].flux_brake.onset for a in d.bus.actuators
                     if d.drivers[a].flux_brake is not None})
    for k, onset in enumerate(onsets):
        volts.axhline(onset, color="tab:green", ls=":", lw=1,
                      label="flux-brake onset" if k == 0 else None)
    volts.axhline(c.v_source, color="grey", lw=0.5,
                  label="start" if d.bus.source is None else "source")
    volts.set_ylabel("V")
    first = "bus: V(t) against its trips"
    volts.set_title(first, fontsize=9)
    volts.legend(fontsize=7)
    power.step(c.t, c.source, where="post", lw=1, label="source")
    power.step(c.t, c.brake, where="post", lw=1, label="brake")
    if d.bus.source is not None:
        power.axhline(d.bus.source.p_max, color="tab:red", lw=1,
                      label="source p_max")
    power.set_xlabel("t (s)")
    power.set_ylabel("W")
    second = "bus: source and brake power"
    power.set_title(second, fontsize=9)
    power.legend(fontsize=7)
    return [first, second]


def _winding(plt, setup, check, ran, worst):
    a = check.actuator
    thermal = ran.drive.motors[a].thermal
    heated = setup.heated(a, ran)
    figure, axis = plt.subplots(figsize=(6.4, 4.8))
    t = getattr(heated, "t", ran.trace.t)
    axis.plot(t, heated.temperature, color="tab:blue", lw=1, label="T(t)")
    axis.axhline(thermal.t_max, color="tab:red", lw=1, label="t_max")
    axis.axhline(thermal.t_ambient, color="grey", lw=0.5, label="ambient")
    cycles = getattr(heated, "cycles", 1)
    axis.set_xlabel("t into the cycle (s)")
    axis.set_ylabel("°C")
    title = (f"{a}: T(t) against the winding limit, cycle {cycles}, peak "
             f"{heated.peak:.4g} °C")
    axis.set_title(title, fontsize=9)
    axis.legend(fontsize=7)
    return [title]
