"""The drive data and the quasi-static electrical model (ADR 0006).

Every motor constant names its basis as a required keyword, for the
reason ADR 0006 gives; A_rms and A_peak share a dimension, so units cannot
catch a slip between them:

- `Kt(value, per="A_rms" | "A_peak", side="motor" | "output")`, in N·m per
  ampere of line current;
- `Ke(value, per="V_rms/krpm" | ..., between="line" | "phase", side=...)`;
- `Resistance(value, between="line" | "phase", at=25.0)`, and the motor's
  `wiring`, `"wye"` or `"delta"`;
- `Current(value, per="A_rms" | "A_peak")`, a line current.

"Phase" is the winding: line to neutral in a wye, line to line in a delta.
An output-side constant is the motor's times the gear ratio N, with no
efficiency in it. N itself is the engine `actuator`'s `gear`, said there
once, so every function here takes it.

Inside, everything is in the power-invariant d-q convention of Lee et al.
(arXiv:2310.00080), on the winding's quantities: a d-q magnitude is √3 times
the winding's RMS and √(3/2) times its peak, so electrical power is v·i and
copper loss R_φ·i², with no 3/2 anywhere. In it Kt and Ke are one number
(N·m/A = V·s/rad), which is the cross-check, and the bus reaches the winding
through the modulation constant, √(1/2) for wye and √(3/2) for delta.
Inductance and iron loss are left out.

`check(motor, n)` cross-checks Kt against Ke and against a published
`Curve`. `electrical(tau, omega, n, motor, ...)` takes arrays of one
actuator's output samples to current, voltage, copper loss and power, and
`envelope(motor, n, v_bus, ...)` gives the torque–speed envelope at a bus
voltage. Both run the check first.

Units are SI: N·m, rad/s, V, A, Ω, W. Temperatures are in °C.
"""

import math
from dataclasses import KW_ONLY, dataclass, field, replace

import numpy as np

SQ3 = math.sqrt(3)
RPM = 2 * math.pi / 60   # rad/s per rpm
K_MOD = {"wye": math.sqrt(1 / 2), "delta": math.sqrt(3 / 2)}
KT_KE = 0.02             # Kt and Ke, both given, agree within this fraction
COPPER = 234.5           # K: annealed copper's resistance extrapolates to
                         # zero at −234.5 °C, so α at T₀ is 1/(234.5 + T₀)

CURRENTS = ("A_rms", "A_peak")
VOLTAGES = ("V_rms", "V_peak")
SPEEDS = {"krpm": 1000 * RPM, "rpm": RPM, "(rad/s)": 1.0}
SIDES = ("motor", "output")
BETWEEN = ("line", "phase")
WIRINGS = tuple(K_MOD)


class DriveError(ValueError):
    """Drive data that cannot be used: Kt and Ke that disagree, a published
    curve the model does not reproduce, a limit the envelope needs and
    nobody gave."""


def _number(owner, name, value, low=0.0, inclusive=False):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise TypeError(f"{owner}'s {name} is a number; got {value!r}") \
            from None
    if not math.isfinite(value) or value < low or (
            value == low and not inclusive):
        bound = "≥" if inclusive else ">"
        raise ValueError(f"{owner}'s {name} is finite and {bound} {low:g}; "
                         f"got {value}")
    return value


def _positive(value, label):
    """`value` as a finite number > 0, or raise naming it by `label`."""
    value = float(value)
    if not (math.isfinite(value) and value > 0):
        raise ValueError(f"{label} is a positive number; got {value}")
    return value


def _efficiency(owner, name, value, inclusive=False):
    value = _number(owner, name, value, inclusive=inclusive)
    if value > 1:
        raise ValueError(f"{owner}'s {name} is at most 1; got {value}")
    return value


def _kind(owner, name, value, kind, optional=False):
    if not (isinstance(value, kind) or (optional and value is None)):
        raise TypeError(f"{owner}'s {name} is a {kind.__name__}; got "
                        f"{value!r}")


def _among(owner, name, value, allowed):
    if value not in allowed:
        raise ValueError(f"{owner}'s {name} is one of "
                         f"{', '.join(repr(a) for a in allowed)}; got "
                         f"{value!r}")


@dataclass(frozen=True)
class Current:
    """A line current, `per="A_rms"` or `per="A_peak"`."""
    value: float
    _: KW_ONLY
    per: str

    def __post_init__(self):
        object.__setattr__(self, "value",
                           _number("a current", "value", self.value))
        _among("a current", "per", self.per, CURRENTS)

    def dq(self, wiring):
        """The current as a d-q magnitude in the winding (A)."""
        return self.value * _amps(self.per, wiring)


@dataclass(frozen=True)
class Kt:
    """The torque constant in N·m per ampere of line current, `per="A_rms"`
    or `"A_peak"`, on the motor's shaft or the actuator's output (`side`)."""
    value: float
    _: KW_ONLY
    per: str
    side: str

    def __post_init__(self):
        object.__setattr__(self, "value", _number("Kt", "value", self.value))
        _among("Kt", "per", self.per, CURRENTS)
        _among("Kt", "side", self.side, SIDES)


@dataclass(frozen=True)
class Ke:
    """The back-EMF constant: `per` is volts, `V_rms` or `V_peak`, over a
    speed, `krpm`, `rpm` or `(rad/s)`, such as `"V_rms/krpm"`; `between` is
    `"line"` (line to line) or `"phase"` (the winding); `side` is the motor's
    shaft or the actuator's output."""
    value: float
    _: KW_ONLY
    per: str
    between: str
    side: str

    def __post_init__(self):
        object.__setattr__(self, "value", _number("Ke", "value", self.value))
        _among("Ke", "per", self.per,
               tuple(f"{v}/{s}" for v in VOLTAGES for s in SPEEDS))
        _among("Ke", "between", self.between, BETWEEN)
        _among("Ke", "side", self.side, SIDES)


@dataclass(frozen=True)
class Resistance:
    """Winding resistance in Ω, measured `between="line"` (terminal to
    terminal) or per `"phase"` (one winding), at `at` °C. `alpha` (1/K) is
    its temperature coefficient there; it defaults to copper's."""
    value: float
    _: KW_ONLY
    between: str
    at: float = 25.0
    alpha: float = None

    def __post_init__(self):
        object.__setattr__(self, "value",
                           _number("a resistance", "value", self.value))
        _among("a resistance", "between", self.between, BETWEEN)
        at = float(self.at)
        object.__setattr__(self, "at", at)
        alpha = 1 / (COPPER + at) if self.alpha is None else self.alpha
        object.__setattr__(self, "alpha", _number(
            "a resistance", "alpha", alpha, inclusive=True))


@dataclass(frozen=True)
class Thermal:
    """A winding's single-node thermal RC, where published: `r_th` (K/W)
    from winding to ambient, `c_th` (J/K), the winding's limit `t_max` (°C)
    and the ambient `t_ambient` (°C). Its time constant is r_th·c_th."""
    r_th: float
    c_th: float
    t_max: float
    t_ambient: float

    def __post_init__(self):
        for name in ("r_th", "c_th"):
            object.__setattr__(self, name,
                               _number("a thermal RC", name,
                                       getattr(self, name)))
        for name in ("t_max", "t_ambient"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"a thermal RC's {name} is finite; got "
                                 f"{value}")
            object.__setattr__(self, name, value)
        if not self.t_ambient < self.t_max:
            raise ValueError(f"a thermal RC's t_ambient is below its t_max; "
                             f"got {self.t_ambient} and {self.t_max}")


@dataclass(frozen=True, kw_only=True)
class Curve:
    """A published torque–speed curve: `torque` (N·m) at each `speed`
    (rad/s), measured at bus `voltage` (V), on the motor's shaft or the
    actuator's output (`side`). `agree` is the torque gap (N·m) the model's
    envelope may leave at any point before the drive data fails."""
    speed: tuple
    torque: tuple
    voltage: float
    side: str
    agree: float

    def __post_init__(self):
        speed = tuple(float(w) for w in self.speed)
        torque = tuple(float(t) for t in self.torque)
        if len(speed) != len(torque) or not speed:
            raise ValueError(f"a curve has one torque per speed; got "
                             f"{len(speed)} speeds and {len(torque)} torques")
        if min(speed) < 0 or min(torque) < 0:
            raise ValueError("a curve's speeds and torques are magnitudes, "
                             "≥ 0")
        object.__setattr__(self, "speed", speed)
        object.__setattr__(self, "torque", torque)
        object.__setattr__(self, "voltage",
                           _number("a curve", "voltage", self.voltage))
        _among("a curve", "side", self.side, SIDES)
        object.__setattr__(self, "agree",
                           _number("a curve", "agree", self.agree))


@dataclass(frozen=True, kw_only=True)
class Motor:
    """A motor's data, each constant with its basis. One of `kt` and `ke` is
    needed; given both, they must agree within 2 % (`check`). `i_peak` and
    `i_continuous` are its current ratings, `curve` an optional published
    torque–speed curve, and `thermal` its winding's RC, where published."""
    r: Resistance
    wiring: str
    kt: Kt = None
    ke: Ke = None
    i_peak: Current = None
    i_continuous: Current = None
    curve: Curve = None
    thermal: Thermal = None

    def __post_init__(self):
        _among("a motor", "wiring", self.wiring, WIRINGS)
        if self.kt is None and self.ke is None:
            raise TypeError("a motor needs kt=Kt(...) or ke=Ke(...), or both")
        _kind("a motor", "r", self.r, Resistance)
        for name, kind in (("kt", Kt), ("ke", Ke), ("i_peak", Current),
                           ("i_continuous", Current), ("curve", Curve),
                           ("thermal", Thermal)):
            _kind("a motor", name, getattr(self, name), kind, optional=True)


@dataclass(frozen=True, kw_only=True)
class Gearbox:
    """A gearbox's efficiency `forward`, motor driving load, and `backward`,
    load driving motor. Backward defaults to forward; a self-locking gear
    states `backward=0`. The ratio N is the engine `actuator`'s `gear`, said
    there once, and passed to each function here."""
    forward: float
    backward: float = None

    def __post_init__(self):
        forward = _efficiency("a gearbox", "forward efficiency", self.forward)
        backward = forward if self.backward is None else _efficiency(
            "a gearbox", "backward efficiency", self.backward, inclusive=True)
        object.__setattr__(self, "forward", forward)
        object.__setattr__(self, "backward", backward)


@dataclass(frozen=True, kw_only=True)
class FluxBrake:
    """A driver's flux brake: above `onset` volts on the bus, it drives
    `i_d` of d-axis current into the winding, whose heat is the motor's."""
    onset: float
    i_d: Current

    def __post_init__(self):
        object.__setattr__(self, "onset",
                           _number("a flux brake", "onset", self.onset))
        _kind("a flux brake", "i_d", self.i_d, Current)


@dataclass(frozen=True, kw_only=True)
class Driver:
    """A motor driver: its `efficiency`, constant, dividing the power it
    draws from the bus and multiplying what it returns; its `i_peak` and
    optional `i_continuous` line currents; the bus voltages at which it
    trips, `max_voltage` and `undervoltage`; and an optional `flux_brake`."""
    efficiency: float
    i_peak: Current
    max_voltage: float
    undervoltage: float
    i_continuous: Current = None
    flux_brake: FluxBrake = None

    def __post_init__(self):
        object.__setattr__(self, "efficiency", _efficiency(
            "a driver", "efficiency", self.efficiency))
        for name in ("max_voltage", "undervoltage"):
            object.__setattr__(self, name, _number(
                "a driver", name, getattr(self, name), inclusive=True))
        if not self.undervoltage < self.max_voltage:
            raise ValueError(f"a driver's undervoltage trip is below its "
                             f"max_voltage; got {self.undervoltage} and "
                             f"{self.max_voltage}")
        _kind("a driver", "i_peak", self.i_peak, Current)
        _kind("a driver", "i_continuous", self.i_continuous, Current,
              optional=True)
        _kind("a driver", "flux_brake", self.flux_brake, FluxBrake,
              optional=True)
        if (self.flux_brake is not None
                and not self.flux_brake.onset < self.max_voltage):
            raise ValueError(f"a driver's flux brake's onset lies under its "
                             f"max_voltage, where the driver trips and its "
                             f"flux brake stops; got {self.flux_brake.onset:g}"
                             f" V against {self.max_voltage:g} V")


@dataclass(frozen=True)
class Electrical:
    """The electrical model at each (τ_out, ω_out) sample, as arrays: the
    rotor's torque `tau` (N·m) and speed `omega` (rad/s); the q-axis
    `current` (A) and `voltage` (V), signed, in d-q; the winding's
    `resistance` R_φ(T) (Ω) and `copper` loss (W); the electrical `power` into the motor (W, negative
    when it generates); and `bus`, that power seen from the bus through the
    driver (W), None without a driver."""
    tau: np.ndarray
    omega: np.ndarray
    current: np.ndarray
    voltage: np.ndarray
    resistance: np.ndarray
    copper: np.ndarray
    power: np.ndarray
    bus: np.ndarray = None


def electrical(tau, omega, n, motor, gearbox=None, driver=None,
               temperature=None, rotor=0.0):
    """The quasi-static electrical model at per-actuator output samples
    `tau` (N·m) and `omega` (rad/s), through a gear of ratio `n`. `tau` is
    the load across the gear; `rotor` (N·m, motor side) is the rotor's own
    inertia torque J_m·ω̇_m, which turns on the motor's side of the gear, so
    no efficiency touches it. `Trace.output` gives all three.

    The load's share of the rotor's torque follows the sign of τ·ω, the
    load's alone. Motoring (τ·ω ≥ 0, so a hold counts as motoring) it is
    τ/(N·η); back-driven it is τ·η_b/N. No gearbox is a direct drive, with
    η = 1. Then τ_m is that plus `rotor`, i = τ_m/Kt and V = R_φ(T)·i +
    Ke·ω_m in d-q, with R_φ(T) = R₀(1 + α(T − T₀)) at the winding
    `temperature` (°C, a scalar or one per sample; by default the
    resistance's own T₀). Electrical power is V·i; the bus sees it over the
    driver's efficiency when drawing and times it when returning.

    The motor's data is checked first, as `check` does it."""
    n = _number("electrical", "the gear ratio n", n)
    c = _resolve(motor, n, gearbox)
    tau, omega, rotor = np.broadcast_arrays(
        np.asarray(tau, dtype=float), np.asarray(omega, dtype=float),
        np.asarray(rotor, dtype=float))
    return _electrical(c, n, gearbox, driver, tau, omega, rotor,
                       np.broadcast_to(_hot(c, temperature), tau.shape))


def _electrical(c, n, gearbox, driver, tau, omega, rotor, resistance):
    """`electrical` on resolved constants `c`, at the winding's
    `resistance`: the model itself, which an event's simulation steps
    sample by sample."""
    forward, backward = _efficiencies(gearbox)
    tau_m = np.where(tau * omega >= 0, tau / (n * forward),
                     tau * backward / n) + rotor
    omega_m = omega * n
    current = tau_m / c.kt
    voltage = resistance * current + c.ke * omega_m
    power = voltage * current
    bus = None
    if driver is not None:
        eta = driver.efficiency
        bus = np.where(power >= 0, power / eta, power * eta)
    return Electrical(tau_m, omega_m, current, voltage, resistance,
                      resistance * current ** 2, power, bus)


@dataclass(frozen=True)
class Envelope:
    """The torque–speed envelope at bus voltage `v_bus`, on the output side:
    `no_load_speed` (rad/s), `stall_torque` (N·m), and `torque(omega)`, the
    most torque the actuator delivers motoring at output speed |omega|."""
    v_bus: float
    no_load_speed: float
    stall_torque: float
    kt: float = field(repr=False)
    ke: float = field(repr=False)
    r: float = field(repr=False)
    i_max: float = field(repr=False)
    v_max: float = field(repr=False)
    n: float = field(repr=False)
    eta: float = field(repr=False)

    def torque(self, omega):
        omega_m = np.abs(np.asarray(omega, dtype=float)) * self.n
        current = np.clip((self.v_max - self.ke * omega_m) / self.r, 0.0,
                          self.i_max)
        return self.kt * current * self.n * self.eta


def envelope(motor, n, v_bus, gearbox=None, driver=None, temperature=None):
    """The torque–speed envelope at bus voltage `v_bus`, through a gear of
    ratio `n`, motoring. In d-q the winding's current is bounded by the
    lower of the motor's and the driver's `i_peak`, and its voltage
    R_φ(T)·i + Ke·ω_m by k_mod·V_bus, so no-load speed is k_mod·V_bus/Ke
    and stall is the current limit. The gearbox's forward efficiency
    applies; R_φ is at `temperature` (°C), by default the resistance's T₀.
    No field weakening: i_d = 0."""
    n = _number("envelope", "the gear ratio n", n)
    v_bus = _number("envelope", "v_bus", v_bus)
    c = _resolve(motor, n, gearbox)
    limit = _current_limit(c, motor, driver)
    if limit is None:
        raise DriveError("the envelope needs a current limit: the motor's "
                         "i_peak or the driver's i_peak")
    return _bound(c, n, v_bus, _efficiencies(gearbox)[0], limit,
                  float(_hot(c, temperature)))


def _current_limit(c, motor, driver):
    """The winding's current limit (d-q A): the lower of the motor's
    `i_peak` and the driver's, None where neither is given."""
    limits = [c.i_peak] + ([] if driver is None
                           else [driver.i_peak.dq(motor.wiring)])
    limits = [i for i in limits if i is not None]
    return min(limits) if limits else None


def kt_from_kv(kv, *, convention):
    """Kt from a velocity constant `kv` in rpm/V, on the motor's shaft, per
    A_peak. Kv is rpm per volt of line-to-line peak back-EMF, which is also
    no-load rpm per bus volt under space-vector modulation. The convention is
    a choice, because the two in use are 15 % apart:

    - `"sinusoidal"`: Kt = (√3/2)·(60/2π)/Kv, the 8.27/Kv of a sinusoidally
      commutated motor, and the one the model's own physics implies;
    - `"trapezoidal"`: Kt = (60/2π)/Kv, the 9.55/Kv of the DC-motor relation
      Kt = Ke, which holds for block commutation only.
    """
    kv = _number("kt_from_kv", "kv", kv)
    scale = {"sinusoidal": SQ3 / 2, "trapezoidal": 1.0}
    _among("kt_from_kv", "convention", convention, tuple(scale))
    return Kt(scale[convention] / (kv * RPM), per="A_peak", side="motor")


@dataclass(frozen=True)
class Checked:
    """A motor's constants on the motor's shaft in the power-invariant d-q
    convention: `kt` (N·m/A) and `ke` (V·s/rad), and `ratio`, kt/ke, which
    is None where only one was given. `curve` is the largest torque gap
    (N·m) between the model's envelope and the published curve, or None."""
    kt: float
    ke: float
    ratio: float
    curve: float = None


def check(motor, n, gearbox=None):
    """Check a motor's data at gear ratio `n`, and return its constants.
    Raises `DriveError` where Kt and Ke, both given, are more than 2 %
    apart, or where the motor's envelope at a published curve's voltage
    (its own `i_peak`, the gearbox's forward efficiency for an output-side
    curve, R_φ at T₀) misses the curve by more than the curve's `agree`.

    Ibex's RobStride 02 is the worked example. Ke 9.6 V_rms/krpm line to line
    is 9.6 / (1000·2π/60) = 0.091673 V·s/rad, and a wye's line-to-line RMS
    voltage is its d-q magnitude, so that is Ke in d-q. Kt 1.22 N·m/A_rms at
    the output of a 7.75:1 gear is 0.15742 N·m/A_rms at the rotor, and a
    line ampere RMS is √3 d-q amperes, so Kt in d-q is 0.15742/√3 = 0.090886.
    They are 0.86 % apart. Read as per A_peak instead, the same Kt is 40 %
    off."""
    n = _number("check", "the gear ratio n", n)
    c = _resolve(motor, n, gearbox)
    return Checked(c.kt, c.ke, c.ratio, c.curve)


@dataclass(frozen=True)
class _Resolved:
    """A motor's data in d-q on the motor's shaft: kt, ke, the winding's
    resistance r at temperature at with coefficient alpha, and the current
    ratings, None where not given."""
    kt: float
    ke: float
    ratio: float
    r: float
    at: float
    alpha: float
    k_mod: float
    i_peak: float
    i_continuous: float
    curve: float = None


def _resolve(motor, n, gearbox=None):
    if not isinstance(motor, Motor):
        raise TypeError(f"expected a Motor; got {motor!r}")
    kt = ke = ratio = None
    if motor.kt is not None:
        kt = motor.kt.value / _amps(motor.kt.per, motor.wiring)
        if motor.kt.side == "output":
            kt /= n
    if motor.ke is not None:
        volts, speed = motor.ke.per.split("/", 1)
        ke = (motor.ke.value * _volts(volts, motor.ke.between, motor.wiring)
              / SPEEDS[speed])
        if motor.ke.side == "output":
            ke /= n
    if kt is not None and ke is not None:
        ratio = kt / ke
        if abs(ratio - 1) > KT_KE:
            raise DriveError(
                f"Kt and Ke disagree: in d-q on the motor's shaft Kt reads "
                f"{kt:.5g} N·m/A and Ke {ke:.5g} V·s/rad, "
                f"{100 * (ratio - 1):+.1f} % apart, beyond "
                f"{100 * KT_KE:g} %. Check each one's basis (A_rms or "
                f"A_peak, line or phase, motor or output side at N = {n:g})")
    kt = ke if kt is None else kt
    ke = kt if ke is None else ke
    i_peak, i_cont = (None if c is None else c.dq(motor.wiring)
                      for c in (motor.i_peak, motor.i_continuous))
    c = _Resolved(kt, ke, ratio, _phase(motor), motor.r.at, motor.r.alpha,
                  K_MOD[motor.wiring], i_peak, i_cont)
    if motor.curve is None:
        return c
    return replace(c, curve=_against(motor.curve, c, n, gearbox))


def _against(curve, c, n, gearbox):
    """The largest torque gap (N·m) between a published curve and the
    motor's envelope at its voltage; raises beyond the curve's `agree`."""
    if c.i_peak is None:
        raise DriveError("a published curve is checked against the motor's "
                         "envelope, which needs the motor's i_peak")
    if curve.side == "motor":
        n, eta = 1.0, 1.0
    else:
        eta = _efficiencies(gearbox)[0]
    model = _bound(c, n, curve.voltage, eta, c.i_peak, c.r).torque(
        curve.speed)
    gaps = np.abs(model - np.asarray(curve.torque))
    worst = int(np.argmax(gaps))
    if gaps[worst] > curve.agree:
        raise DriveError(
            f"the published torque–speed curve at {curve.voltage:g} V "
            f"({curve.side} side) reads {curve.torque[worst]:.4g} N·m at "
            f"{curve.speed[worst]:.4g} rad/s, where the model gives "
            f"{model[worst]:.4g} N·m: {gaps[worst]:.3g} N·m apart, beyond "
            f"the curve's agree of {curve.agree:g} N·m. Check Kt, Ke, R and "
            f"i_peak, each with its basis")
    return float(gaps[worst])


def _bound(c, n, v_bus, eta, i_max, r):
    """The envelope of resolved constants `c` at `v_bus`."""
    v_max = c.k_mod * v_bus
    return Envelope(v_bus, v_max / (c.ke * n),
                    c.kt * min(i_max, v_max / r) * n * eta,
                    c.kt, c.ke, r, i_max, v_max, n, eta)


def _efficiencies(gearbox):
    """The gearbox's (forward, backward) efficiency; a direct drive's is 1."""
    return (1.0, 1.0) if gearbox is None else (gearbox.forward,
                                               gearbox.backward)


def _phase(motor):
    """The winding's resistance R_φ at its T₀ (Ω). Terminal to terminal, a
    wye reads two windings in series, 2·R_φ, and a delta one winding across
    the other two, 2·R_φ/3."""
    r = motor.r.value
    if motor.r.between == "line":
        r *= 0.5 if motor.wiring == "wye" else 1.5
    return r


def _hot(c, temperature):
    """R_φ(T) = R₀(1 + α(T − T₀)), at T₀ where `temperature` is None."""
    if temperature is None:
        return c.r
    return c.r * (1 + c.alpha * (np.asarray(temperature, dtype=float) - c.at))


def _amps(per, wiring):
    """The winding's d-q current per ampere of line current on `per`."""
    phase = 1.0 if wiring == "wye" else 1 / SQ3
    return phase * _dq(per)


def _volts(per, between, wiring):
    """The winding's d-q voltage per volt on `per`, `between` line or
    phase."""
    phase = 1 / SQ3 if between == "line" and wiring == "wye" else 1.0
    return phase * _dq(per)


def _dq(per):
    """A d-q magnitude per unit of the winding's RMS or peak."""
    return SQ3 if per.endswith("rms") else math.sqrt(3 / 2)
