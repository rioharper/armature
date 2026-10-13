"""The winding's temperature over a duty: a single-node RC (ADR 0006).

    C·dT/dt = P − (T − T_a)/R_th

A trace is sampled at times `t`, each sample's value held until the next
(the last sample only ends the trace). Over each interval the power is
constant, so each step is the exact exponential, never an Euler step. With
the winding's copper loss R_φ(T)·i² in P, R_φ(T) = R₀(1 + α(T − T₀)) keeps
the equation linear in T, so the step stays exact with the resistance
feeding back; the time constant lengthens, and past R_th·R₀·α·i² ≥ 1 the
winding runs away.

`repeat` runs a trace once per period, idle at zero loss for the rest of
it, from ambient, until a cycle starts within 0.1 K of the periodic state
or the session ends. Each cycle is the same affine map of the temperature
it starts at, so the periodic state is that map's fixed point, exactly.
The test is on the distance to it, not on how far one cycle moves: a cycle
moves (1 − m) of that distance, with m the map's slope, so where the time
constant is long against the period a cycle moves under 0.1 K while the
winding is still well short. At τ = 3600 s, 60 s on in every 360 s, that
stops 0.95 K short of a 3.47 K periodic rise. Where a motor publishes no
`Thermal`, the check falls back to `rms_torque` over the period against
its continuous rating.

Temperatures are in °C, times in s, powers in W, currents in d-q A.
"""

import math
from dataclasses import dataclass

import numpy as np

from .electrical import Motor, Thermal, _phase, _positive

PERIODIC = 0.1  # K: a cycle starting this close to the periodic state is
                # the periodic state


@dataclass(frozen=True)
class Heated:
    """The winding's `temperature` (°C) at each time `t` (s) of a trace,
    and its `peak`."""
    t: np.ndarray
    temperature: np.ndarray
    peak: float


@dataclass(frozen=True)
class Repeated:
    """A duty run to its periodic state or its session's end: the `peak`
    temperature (°C) over every cycle; the last cycle's `t` and
    `temperature`, its times counted from the trace's start; the number of
    `cycles` run; and whether the last was `periodic`, starting within
    0.1 K of the periodic state, before the session ended."""
    t: np.ndarray
    temperature: np.ndarray
    peak: float
    cycles: int
    periodic: bool


def heat(t, thermal, power=0.0, current=None, motor=None, start=None):
    """The winding's temperature over a trace at times `t`: `power` (W) is
    any loss beyond copper, such as a flux brake's; `current` (d-q A, as
    `electrical` gives it) adds the copper loss R_φ(T)·i² of `motor`'s
    winding. It starts at `start` (°C), by default the ambient."""
    t, a, b = _affine(t, thermal, power, current, motor)
    start = thermal.t_ambient if start is None else float(start)
    temperature = a * start + b
    return Heated(t, temperature, float(temperature.max()))


def repeat(t, thermal, period, session, power=0.0, current=None,
           motor=None):
    """The trace at times `t` (as `heat` takes it) run once per `period`
    (s), idle at zero loss for the rest of each, from ambient, until a
    cycle starts within 0.1 K of the periodic state, or `session` (s) ends.
    A session ending partway through a cycle ends it there. The trace is
    integrated once, as an affine map, and each cycle reuses it."""
    period = _positive(period, "the period")
    session = _positive(session, "the session")
    t, a, b = _affine(t, thermal, power, current, motor)
    since = t - t[0]
    if since[-1] > period:
        raise ValueError(f"a trace of {since[-1]:g} s does not fit in a "
                         f"period of {period:g} s")
    ambient, tau = thermal.t_ambient, thermal.r_th * thermal.c_th
    # A whole cycle maps its start T to m·T + c. Below m = 1 its fixed point
    # is the periodic state; at or above it the winding runs away.
    rest = math.exp(-(period - since[-1]) / tau)
    m, c = a[-1] * rest, ambient + (b[-1] - ambient) * rest
    fixed = c / (1 - m) if m < 1 else math.inf
    start, peak, elapsed, cycles = ambient, ambient, 0.0, 0
    while True:
        span = min(period, session - elapsed)
        periodic = span == period and abs(start - fixed) < PERIODIC
        if span < since[-1]:
            # The session ends inside the trace: run it up to there.
            keep = since < span
            times = np.append(since[keep], span)
            temperature = heat(t[0] + times, thermal,
                               _cut(power, keep), _cut(current, keep),
                               motor, start).temperature
        else:
            times, temperature = since, a * start + b
        idle = span - times[-1]
        end = ambient + (temperature[-1] - ambient) * math.exp(-idle / tau)
        peak = max(peak, float(temperature.max()))
        cycles += 1
        elapsed += span
        if periodic or elapsed >= session:
            return Repeated(times, temperature, peak, cycles, periodic)
        start = end


def rms_torque(t, tau, period=None):
    """The RMS of a torque trace (N·m) at times `t`, each sample held until
    the next, over `period` (s) with zero torque for the rest of it; by
    default the period is the trace. It is the thermal check's fallback,
    against the continuous rating, where no `Thermal` is published."""
    t = _times(t)
    tau = np.broadcast_to(np.asarray(tau, dtype=float), t.shape)
    duration = t[-1] - t[0]
    period = duration if period is None else float(period)
    if not period >= duration or not period > 0:
        raise ValueError(f"the period is positive and at least the trace's "
                         f"{duration:g} s; got {period:g}")
    return math.sqrt(float(np.sum(tau[:-1] ** 2 * np.diff(t))) / period)


def _affine(t, thermal, power, current, motor):
    """The trace's temperatures as T_k = a_k·T_0 + b_k (°C)."""
    if not isinstance(thermal, Thermal):
        raise TypeError(f"expected a Thermal; got {thermal!r}")
    t = _times(t)
    power = np.broadcast_to(np.asarray(power, dtype=float), t.shape)
    # Over each interval C·dT/dt = q − g·T, with g the net conductance to
    # ambient (W/K) once copper's rise with temperature is taken out.
    g = np.full(t.shape, 1 / thermal.r_th)
    q = power + thermal.t_ambient / thermal.r_th
    if current is not None:
        if not isinstance(motor, Motor):
            raise TypeError(f"a current heats a winding, so heat needs its "
                            f"motor=; got {motor!r}")
        squared = np.broadcast_to(np.asarray(current, dtype=float),
                                  t.shape) ** 2
        r0, alpha = _phase(motor), motor.r.alpha
        g = g - r0 * alpha * squared
        q = q + r0 * (1 - alpha * motor.r.at) * squared
    step = np.diff(t) / thermal.c_th
    x = -g[:-1] * step
    decay = np.exp(x)
    # (e^x − 1)/x, which is 1 at x = 0, so g = 0 drives T at q/C.
    safe = np.where(x == 0, 1.0, x)
    gain = np.where(x == 0, 1.0, np.expm1(x) / safe) * step
    drive = q[:-1] * gain
    a = np.concatenate(([1.0], np.cumprod(decay)))
    b = np.zeros(t.shape)
    for k in range(len(decay)):
        b[k + 1] = decay[k] * b[k] + drive[k]
    return t, a, b


def _cut(values, keep):
    """A per-sample input cut to the samples kept, plus one more to end the
    trace, whose value is never held."""
    if values is None:
        return None
    values = np.broadcast_to(np.asarray(values, dtype=float), keep.shape)
    return np.append(values[keep], 0.0)


def _times(t):
    t = np.asarray(t, dtype=float)
    if t.ndim != 1 or t.size < 2:
        raise ValueError(f"a trace has at least two times; got {t!r}")
    if not np.all(np.isfinite(t)) or np.any(np.diff(t) < 0):
        raise ValueError("a trace's times are finite and do not decrease")
    return t

