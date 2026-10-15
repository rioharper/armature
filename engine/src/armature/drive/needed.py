"""The capacitance a bus needs (#93): for each searched worst case of the
bus's peak V, the least capacitance that holds it under the lowest trip, at
which nothing trips (#96). Reported, never checked.

Where nothing takes power off the bus below the trip (no sinking source, no
brake resistor or flux brake switching in under it) and no event runs, the
capacitor alone takes the net return, so the peak is √(V₀² + 2E/C) and
inverts in closed form, C = 2E/(V_trip² − V₀²). E is the most net energy
the bus gathers above where it started: what the actuators return, less
what they and the hotel load draw, with a source's floor refilling any sag
below V₀. One `charge` at that C confirms the peak lands on the trip. A
source too small to hold its floor, a bus with no source emptied before its
peak, a sink below the trip and an event, whose motion depends on the bus,
each bisect C instead, on `charge` at each C tried holding its peak under
the trip with nothing tripped: a driver that trips latches, and the bus can
stop there, at its trip, so the peak alone would hold at any C.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace

import numpy as np

from ..search import Margin, search
from .bus import charge
from .electrical import DriveError
from .event import Event
from .margins import _lowest, _Slack

TOLERANCE = 1e-3  # the bisection's width, a fraction of C
MAX_STEPS = 40    # halvings or doublings of C that bracket it


@dataclass(frozen=True)
class Needed:
    """The least `capacitance` (F) that holds one searched worst case of
    the bus's peak V under its lowest `trip` (V), named `against`, with
    nothing tripped, for `mission` on bus configuration `drive` (None where
    there is one), at the case's point `at`, every axis but the capacitance
    read there.
    `exact` where the closed form gave it; otherwise it was bisected, and
    lies within the tolerance above the least. 0 F where the bus never
    rises above where it starts, or where its clamps hold it under the trip
    at any capacitance tried. The brake resistor's `brake_energy` over the
    mission and its `brake_pulse` (J) are at that capacitance, None
    without one."""
    mission: str
    drive: str
    capacitance: float
    trip: float
    against: str
    exact: bool
    brake_energy: float
    brake_pulse: float
    at: dict


def capacitance_needed(margins, worsts=None, *, tolerance=TOLERANCE):
    """The `Needed` capacitance of each searched worst case of the bus's
    peak V, one per mission and bus configuration, from `margins`, the
    drive margins `armature.drive.margins` returns, at its truth's
    resolution. `worsts` are the margins' `Worst`s, a sequence or a mapping
    by name, as `review` takes them; the peak-V margin's is searched where
    none is given. `tolerance` is the bisection's width, a fraction of C.

    Raises where no capacitance up to 2⁴⁰ times the case's own holds."""
    peak = [m for m in margins if isinstance(m, Margin)
            and isinstance(m.fn, _Slack) and m.fn.check.what == "peak V"]
    if not peak:
        raise ValueError("capacitance_needed reads the bus's peak-V margin; "
                         "give it the margins armature.drive.margins "
                         "returns")
    tolerance = float(tolerance)
    if not (math.isfinite(tolerance) and tolerance > 0):
        raise ValueError(f"capacitance_needed's tolerance is a positive "
                         f"fraction of C; got {tolerance}")
    if isinstance(worsts, Mapping):
        found = dict(worsts)
    else:
        found = {w.margin: w for w in worsts or ()}
    out = []
    for margin in peak:
        worst = found.get(margin.name) or search(margin)
        out += [_needed(margin.fn.evaluator, case, tolerance)
                for case in worst.cases]
    return tuple(out)


def _needed(evaluator, case, tolerance):
    """The `Needed` of one worst `case`."""
    setup = evaluator.setup
    point = evaluator.point(case.at)
    values = {n: point[n] for n in point}
    ran = evaluator.ran(point, True)
    d, v0 = ran.drive, ran.charged.v_source
    trip, parts = _lowest(d)
    gear = {a: setup.gear_of(a) for a in setup.actuators}
    events = any(isinstance(s, Event) for s in ran.mission.segments)

    def charged(c):
        if events:  # the event's motion depends on the bus
            return setup.run(values, evaluator.confirm, True,
                             capacitance=c).charged
        return charge(ran.trace, replace(d, bus=replace(
            d.bus, capacitance=c)), capacitance=c, v_source=v0, gear=gear)

    exact, at = False, None
    if not events and not _sinks_below(d, trip):
        c = _closed_form(ran, v0, trip)
        if c == 0.0:
            exact = True
        else:
            at = charged(c)
            exact = abs(at.peak - trip) < at.agree
    if not exact:
        c = _bisected(charged, ran.charged.capacitance, trip, tolerance)
        at = charged(c) if c > 0 else None
    braked = d.bus.brake is not None and at is not None
    return Needed(
        values["mission"], values.get("drive"), c, trip,
        f"{', '.join(parts)} ({trip:g} V)", exact,
        at.brake_energy if braked else None,
        at.brake_pulse if braked else None,
        {n: v for n, v in case.at.items() if n != "capacitance"})


def _sinks_below(d, trip):
    """Whether anything on the bus of `d` takes power off it below `trip`
    (V)."""
    bus = d.bus
    if bus.source is not None and bus.source.sinks:
        return True
    if bus.brake is not None and bus.brake.threshold < trip:
        return True
    return any(d.drivers[a].flux_brake is not None
               and d.drivers[a].flux_brake.onset < trip
               for a in bus.actuators)


def _closed_form(ran, v0, trip):
    """C = 2E/(V_trip² − V₀²) (F), E the most net energy the bus of `ran`
    gathers above `v0` (J): each actuator's bus power the straight line
    between samples, as `charge` takes it, so the energy is exact at each
    sample and at each turn between; a source's floor refills a sag."""
    t = np.asarray(ran.trace.t, dtype=float)
    q = -(sum(ran.charged.power.values()) + ran.drive.bus.hotel)  # W in
    floor = ran.drive.bus.source is not None
    gathered = low = most = 0.0
    for k in range(len(t) - 1):
        dt, q0, q1 = t[k + 1] - t[k], float(q[k]), float(q[k + 1])
        if dt <= 0:
            continue
        points = [gathered + (q0 + q1) * dt / 2]
        if q0 * q1 < 0:  # it turns inside, where q crosses zero
            points.insert(0, gathered + q0 * q0 * dt / (2 * (q0 - q1)))
        for e in points:
            if floor:
                low = min(low, e)
            most = max(most, e - low)
        gathered = points[-1]
    return float(2 * most / (trip ** 2 - v0 ** 2)) if most > 0 else 0.0


def _bisected(charged, c0, trip, tolerance):
    """The least C (F) whose `charged(C)` holds its peak under `trip` (V)
    with nothing tripped, bracketed from `c0` and bisected in ratio to
    within `tolerance`; the end that holds."""
    def holds(c):
        at = charged(c)
        return at.peak <= trip and not at.tripped

    lo = hi = c0
    if holds(c0):
        for _ in range(MAX_STEPS):
            lo = hi / 2
            if not holds(lo):
                break
            hi = lo
        else:
            return 0.0
    else:
        for _ in range(MAX_STEPS):
            lo, hi = hi, hi * 2
            if holds(hi):
                break
        else:
            raise DriveError(f"no capacitance up to {hi:.3g} F holds the "
                             f"bus's peak under {trip:g} V")
    while hi / lo > 1 + tolerance:
        mid = math.sqrt(lo * hi)
        if holds(mid):
            hi = mid
        else:
            lo = mid
    return hi
