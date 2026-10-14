"""The shared DC bus: its source, capacitance, brake resistor and flux
brakes, charged by each actuator's bus power over a trace.

Answer: each expected value is worked here, by hand or with numpy, from the
mechanics and the drive data, never from the bus module:
- a flywheel stopped at constant deceleration returns ½Jω₀² less its copper
  loss, so a capacitor with no sink reads V = √(V₀² + 2E/C) (Ibex eq. 60);
- a brake that clamps takes the pulse's excess over ½C(V_th² − V₀²);
- a weight lowered at constant speed regenerates a constant power, worked
  from τ = m·g, the gearbox's backward efficiency and the copper loss;
- a flux brake's capacity is the spec's amplitude-invariant 1.5·I_d²·R_φ,
  I_d per A_peak;
- the probe's geared swing reads the energy relation on its largest run of
  net returned energy, integrated with numpy from `electrical`'s bus powers.
"""

import math

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

import armature
from armature import actuator, body, gravity, joint
from armature.drive import (CONFIRM_RATE, BrakeResistor, Bus, Current, Drive,
                            Driver, FluxBrake, Gearbox, Kt, Mission, Motor,
                            Resistance, Source, Thermal, charge, electrical,
                            follow, heat, trace)
from test_drive_mission import (SWING, pendulum, swing_q, swing_qd,
                                swing_qdd)

SQ3 = math.sqrt(3)
KT = 0.1        # N·m/A in d-q, as Kt 0.1·√3 N·m/A_rms reads in a wye
R_TINY = 1e-6   # Ω per phase: a motor that loses next to nothing


def motor(r=R_TINY, **overrides):
    kwargs = dict(kt=Kt(KT * SQ3, per="A_rms", side="motor"),
                  r=Resistance(r, between="phase"), wiring="wye")
    kwargs.update(overrides)
    return Motor(**kwargs)


def driver(**overrides):
    kwargs = dict(efficiency=1.0, i_peak=Current(100.0, per="A_peak"),
                  max_voltage=200.0, undervoltage=10.0)
    kwargs.update(overrides)
    return Driver(**kwargs)


# --- a flywheel stopped at constant deceleration ------------------------------
J_WHEEL = 0.01            # kg·m², about its axis; direct drive, no rotor
W0, STOP = 100.0, 1.0     # rad/s, s
ALPHA = W0 / STOP         # rad/s²


def flywheel(p):
    return [body("wheel", mass=1.0, com=(0, 0, 0),
                 inertia=np.diag([p["J"]] * 3)),
            joint("spin", "hinge", parent="world", child="wheel",
                  axis=(0, 0, 1), point=(0, 0, 0), range=(-1e3, 1e3)),
            actuator("motor", joint="spin"),
            gravity((0, 0, 0))]


@pytest.fixture(scope="module")
def stop():
    """The flywheel from W0 to rest in STOP seconds."""
    m = armature.compile(flywheel, {"J": J_WHEEL})
    return trace(m, Mission("stop", [follow(
        lambda t: {"spin": W0 * t - 0.5 * ALPHA * t * t}, STOP,
        qd=lambda t: {"spin": W0 - ALPHA * t},
        qdd=lambda t: {"spin": -ALPHA})]), CONFIRM_RATE)


def returned(t, r=R_TINY):
    """The energy (J) the stop has returned to the bus by time `t`: the
    kinetic energy given up, ½J(ω₀² − ω²), less the copper loss R_φ·i²·t at
    the constant current i = J·α/Kt."""
    omega = W0 - ALPHA * np.asarray(t)
    return (0.5 * J_WHEEL * (W0 ** 2 - omega ** 2)
            - r * (J_WHEEL * ALPHA / KT) ** 2 * np.asarray(t))


def one(source, capacitance, **bus):
    """A drive of the one direct-drive motor on a bus."""
    return Drive(motors={"motor": motor()}, drivers={"motor": driver()},
                 bus=Bus(actuators=("motor",), source=source,
                         capacitance=capacitance, **bus))


# --- the energy relation ------------------------------------------------------
def test_a_pulse_into_a_capacitor_with_no_sink_reads_the_energy_relation(
        stop):
    """The source cannot sink, so the returned energy lands on the
    capacitor alone: V = √(V₀² + 2E/C) at every substep, and at the end."""
    v0, c = 24.0, 0.01
    charged = charge(stop, one(Source(v=v0, sinks=False, p_max=500.0), c))
    expected = np.sqrt(v0 ** 2 + 2 * returned(charged.t) / c)
    np.testing.assert_allclose(charged.v, expected, rtol=1e-12)
    end = math.sqrt(v0 ** 2 + 2 * (0.5 * J_WHEEL * W0 ** 2
                                   - R_TINY * (J_WHEEL * ALPHA / KT) ** 2
                                   * STOP) / c)
    assert charged.peak == pytest.approx(end, rel=1e-12)
    assert charged.minimum == v0
    assert charged.t[0] == 0.0 and charged.t[-1] == STOP


def test_a_bus_may_start_away_from_its_source(stop):
    """An event triggered partway through a mission starts from the bus as
    it then is: from 30 V over a 24 V source that cannot sink, the stop's
    return lands on the capacitor from 30 V."""
    v0, c = 30.0, 0.01
    charged = charge(stop, one(Source(v=24.0, sinks=False, p_max=500.0), c),
                     v0=v0)
    np.testing.assert_allclose(
        charged.v, np.sqrt(v0 ** 2 + 2 * returned(charged.t) / c),
        rtol=1e-12)
    for name in ("t", "v", "source", "brake"):
        assert not getattr(charged, name).flags.writeable
    assert not charged.flux["motor"].flags.writeable
    with pytest.raises(ValueError, match="v0"):
        charge(stop, one(Source(v=24.0, sinks=False, p_max=1.0), c), v0=-1.0)


def test_a_brake_clamps_at_its_threshold_and_takes_the_excess(stop):
    """On 10 mF from 24 V the stop would reach 102.8 V. A 48 V brake of 8 Ω
    takes 48²/8 = 288 W at its threshold, above the stop's peak return of
    J·α·ω₀ = 100 W, so it holds the bus at 48 V, and it takes the pulse's
    excess over the capacitor's ½C(48² − 24²) = 8.64 J."""
    v0, c, threshold = 24.0, 0.01, 48.0
    assert threshold ** 2 / 8.0 > J_WHEEL * ALPHA * W0
    charged = charge(stop, one(Source(v=v0, sinks=False, p_max=500.0), c,
                               brake=BrakeResistor(threshold=threshold, r=8.0,
                                                   energy=100.0, power=50.0)))
    assert charged.peak == pytest.approx(threshold, abs=1e-9)
    excess = returned(STOP) - 0.5 * c * (threshold ** 2 - v0 ** 2)
    assert excess == pytest.approx(41.36, abs=1e-3)
    assert charged.brake_energy == pytest.approx(excess, rel=1e-9)
    assert charged.brake_pulse == charged.brake_energy  # one pulse
    # below the threshold the brake is open, and the bus is the capacitor's
    below = charged.v < threshold - 1e-9
    assert np.all(charged.brake[:-1][below[:-1] & below[1:]] == 0.0)
    np.testing.assert_allclose(
        charged.v[below], np.sqrt(v0 ** 2 + 2 * returned(charged.t[below])
                                  / c), rtol=1e-12)
    assert charged.brake_peak <= J_WHEEL * ALPHA * W0


class Pulses:
    """A stand-in for a trace, as `charge` reads one: the direct-drive
    motor returns P = τ·ω through 1 N·m at −P rad/s over [0, 1] s and
    [2, 3] s, and carries nothing between, at 1 kHz."""
    P = 50.0

    def __init__(self):
        self.t = np.arange(3001) / 1000.0
        on = (self.t <= 1.0) | (self.t >= 2.0)
        self._tau = np.where(on, 1.0, 0.0)
        self._omega = np.where(on, -self.P, 0.0)
        self.torque = {"motor": self._tau}
        self.gear = {"motor": 1.0}

    def output(self, actuator, n=None):
        return self._tau, self._omega, np.zeros(self.t.shape)


def test_a_brake_pulse_is_one_run_of_conduction():
    """A brake at the source's own 24 V, which cannot sink, takes each
    return as it comes, so it conducts twice. Each pulse is the return over
    [0, 1] s plus half a millisecond's ramp, P·1.0005 less copper; the
    energy is both."""
    copper = R_TINY * (1.0 / KT) ** 2  # W, at 10 A while it carries
    pulse = (Pulses.P - copper) * 1.0005
    drive = one(Source(v=24.0, sinks=False, p_max=500.0), 0.01,
                brake=BrakeResistor(threshold=24.0, r=1.0, energy=100.0,
                                    power=50.0))
    charged = charge(Pulses(), drive)
    assert charged.brake_pulse == pytest.approx(pulse, rel=1e-9)
    assert charged.brake_energy == pytest.approx(2 * pulse, rel=1e-9)


# --- the source ---------------------------------------------------------------
@pytest.fixture(scope="module")
def start():
    """The flywheel from rest to W0 in STOP seconds, drawing."""
    m = armature.compile(flywheel, {"J": J_WHEEL})
    return trace(m, Mission("start", [follow(
        lambda t: {"spin": 0.5 * ALPHA * t * t}, STOP,
        qd=lambda t: {"spin": ALPHA * t},
        qdd=lambda t: {"spin": ALPHA})]), CONFIRM_RATE)


COPPER = R_TINY * (J_WHEEL * ALPHA / KT) ** 2  # W, all along either
RATE = J_WHEEL * ALPHA ** 2   # W/s: the mechanical power's slope, J·α·α


def test_a_source_that_cannot_sink_never_takes_current_back(start, stop):
    """Starting, the source supplies the draw, J·α²·t plus copper, and
    holds 24 V; stopping, it takes nothing back, so the bus rises by the
    energy relation from 24 V."""
    v0, c = 24.0, 0.01
    drive = one(Source(v=v0, sinks=False, p_max=500.0), c)
    drawing, returning = charge(start, drive), charge(stop, drive)
    np.testing.assert_allclose(drawing.v, v0, rtol=1e-12)
    np.testing.assert_allclose(  # each substep's mean draw
        drawing.source[:-1],
        RATE * (drawing.t[:-1] + drawing.t[1:]) / 2 + COPPER, rtol=1e-9)
    assert drawing.source_energy == pytest.approx(
        0.5 * J_WHEEL * W0 ** 2 + COPPER * STOP, rel=1e-9)
    assert np.all(returning.source == 0.0)
    assert returning.source_energy == 0.0
    np.testing.assert_allclose(
        returning.v, np.sqrt(v0 ** 2 + 2 * returned(returning.t) / c),
        rtol=1e-12)


def test_a_source_that_sinks_holds_the_bus_inside_its_band(stop):
    """A pack in a 22–26 V band, run at 25 V and able to sink 500 W, takes
    the stop's return of at most 100 W: the bus never leaves 25 V, and the
    pack takes all the stop returns."""
    c = 0.01
    drive = one(Source(v=(22.0, 26.0), sinks=True, p_max=500.0), c)
    charged = charge(stop, drive, v_source=25.0)
    assert np.all((22.0 <= charged.v) & (charged.v <= 26.0))
    np.testing.assert_allclose(charged.v, 25.0, rtol=1e-12)
    assert np.all(charged.source[:-1] < 0)
    assert charged.source_energy == pytest.approx(-returned(STOP), rel=1e-9)


def test_a_sinking_source_past_its_limit_lets_the_bus_rise(stop):
    """Sinking at most 40 W, the source leaves the capacitor the stop's
    return beyond 40 W. P(t) = J·α·ω₀ − J·α²·t − copper is over 40 W until
    t* = (60 W − copper)/(J·α²), and ∫(P − 40) to there, ½(60 −
    copper)²/(J·α²), is the peak's energy. From t* to the end the source
    drains ∫(40 − P) = ½(40 + copper)²/(J·α²) of it back."""
    v0, c, sink = 24.0, 0.01, 40.0
    charged = charge(stop, one(Source(v=v0, sinks=True, p_max=sink), c))
    over = J_WHEEL * ALPHA * W0 - sink - COPPER   # W, at t = 0
    rise = 0.5 * over ** 2 / RATE
    drained = 0.5 * (sink + COPPER) ** 2 / RATE
    assert (rise, drained) == pytest.approx((18.0, 8.0), abs=1e-3)
    assert charged.peak == pytest.approx(
        math.sqrt(v0 ** 2 + 2 * rise / c), rel=1e-9)
    assert charged.v[-1] == pytest.approx(
        math.sqrt(v0 ** 2 + 2 * (rise - drained) / c), rel=1e-9)
    assert np.min(charged.source) == pytest.approx(-sink, rel=1e-12)
    assert charged.sink_peak == pytest.approx(sink, rel=1e-12)


def test_a_source_past_its_limit_lets_the_bus_sag(start):
    """Sourcing at most 60 W, the source leaves the capacitor the start's
    draw beyond it. P(t) = J·α²·t + copper passes 60 W at t* = (60 −
    copper)/(J·α²), and ∫(P − 60) from there to the end is ½(J·α²·STOP +
    copper − 60)²/(J·α²), so on 100 mF the bus sags to √(24² − 2E/C)."""
    v0, c, limit = 24.0, 0.1, 60.0
    charged = charge(start, one(Source(v=v0, sinks=False, p_max=limit), c))
    deficit = 0.5 * (RATE * STOP + COPPER - limit) ** 2 / RATE
    assert deficit == pytest.approx(8.0, abs=1e-3)
    assert charged.minimum == pytest.approx(
        math.sqrt(v0 ** 2 - 2 * deficit / c), rel=1e-9)
    assert charged.v[-1] == charged.minimum
    assert charged.source_peak == pytest.approx(limit, rel=1e-12)
    # asked of it, past what it could give: the draw at the end
    assert charged.source_demand == pytest.approx(RATE * STOP + COPPER,
                                                  rel=1e-12)
    assert charged.sink_peak == 0.0


def test_a_hotel_load_draws_from_the_bus_all_along(stop):
    """A 10 W hotel load takes 10 W·t of the stop's return, which falls
    below 10 W at t = 0.9 s, J·α·(ω₀ − α·t) = 10, so the bus peaks there:
    on 10 mF, √(24² + 2(E(0.9) − 9 J)/C)."""
    v0, c, hotel = 24.0, 0.01, 10.0
    charged = charge(stop, one(Source(v=v0, sinks=False, p_max=500.0), c,
                               hotel=hotel))
    turn = (W0 - hotel / (J_WHEEL * ALPHA)) / ALPHA - COPPER / RATE
    assert turn == pytest.approx(0.9, abs=1e-5)
    assert charged.peak == pytest.approx(
        math.sqrt(v0 ** 2 + 2 * (returned(turn) - hotel * turn) / c),
        rel=1e-9)
    np.testing.assert_allclose(
        charged.v, np.sqrt(v0 ** 2 + 2 * (returned(charged.t)
                                          - hotel * charged.t) / c),
        rtol=1e-12)


# --- flux braking -------------------------------------------------------------
LIFT = {"m": 2.0, "N": 200.0}  # kg; rad of rotor per metre of slide
G, ETA_GEAR, ETA_DRIVER = 9.81, 0.9, 0.95
R_HOIST = 0.5                  # Ω per phase
I_D = 2.0                      # A_peak of d-axis current
ONSET = 30.0                   # V
LOWER = 2.0                    # s


def lift(p):
    return [body("weight", mass=p["m"], com=(0, 0, 0),
                 inertia=np.diag([1e-4] * 3)),
            joint("z", "slide", parent="world", child="weight",
                  axis=(0, 0, 1), point=(0, 0, 0), range=(-10.0, 10.0)),
            actuator("hoist", joint="z", gear=p["N"]),
            gravity((0, 0, -G))]


def lowered(speed):
    """The weight lowered at `speed` (m/s) for LOWER seconds."""
    m = armature.compile(lift, LIFT)
    return trace(m, Mission("lower", [follow(
        lambda t: {"z": -speed * t}, LOWER, qd=lambda t: {"z": -speed},
        qdd=lambda t: {"z": 0.0})]), CONFIRM_RATE)


def regen(speed):
    """The bus power (W, negative returning) of lowering at `speed`: the
    load m·g back-drives the gear, so the rotor's torque is m·g·η_b/N and
    its current that over Kt; the winding's power is R_φ·i² + Ke·ω_m·i with
    ω_m = −N·v, and the driver passes η_d of it back."""
    i = LIFT["m"] * G * ETA_GEAR / LIFT["N"] / KT
    winding = R_HOIST * i ** 2 - KT * LIFT["N"] * speed * i
    return winding * ETA_DRIVER


def hoist(c=0.01, brake=None):
    flux = FluxBrake(onset=ONSET, i_d=Current(I_D, per="A_peak"))
    return Drive(motors={"hoist": motor(r=R_HOIST)},
                 drivers={"hoist": driver(efficiency=ETA_DRIVER,
                                          flux_brake=flux)},
                 gearboxes={"hoist": Gearbox(forward=ETA_GEAR)},
                 bus=Bus(actuators=("hoist",), source=Source(
                     v=24.0, sinks=False, p_max=100.0), capacitance=c,
                     brake=brake))


CAPACITY = 1.5 * I_D ** 2 * R_HOIST  # W: the spec's 1.5·I_d²·R_φ, I_d peak


def test_a_flux_brake_absorbs_its_capacity_above_onset_and_heats_its_motor():
    """Lowering at 0.5 m/s returns 8.0 W, more than the flux brake's
    1.5·2²·0.5 = 3 W. The bus rises from 24 V on the capacitor alone until
    the onset, at t₁ = ½C(30² − 24²)/P; from there the flux brake takes its
    3 W and the rest raises the bus, V² = 30² + 2(P − 3 W)(t − t₁)/C. Its
    3 W is the motor's thermal input: from ambient, the winding reaches
    T_a + 3·R_th·(1 − e^(−(t − t₁)/(R_th·C_th)))."""
    c = 0.01
    t = lowered(0.5)
    returning = -regen(0.5)
    assert CAPACITY == 3.0 and returning == pytest.approx(8.0, abs=0.05)
    charged = charge(t, hoist(c))
    t1 = 0.5 * c * (ONSET ** 2 - 24.0 ** 2) / returning
    after = charged.t >= t1
    np.testing.assert_allclose(
        charged.v[after],
        np.sqrt(ONSET ** 2 + 2 * (returning - CAPACITY)
                * (charged.t[after] - t1) / c), rtol=1e-9)
    np.testing.assert_allclose(
        charged.v[~after],
        np.sqrt(24.0 ** 2 + 2 * returning * charged.t[~after] / c),
        rtol=1e-9)
    flux = charged.flux["hoist"]
    assert flux.shape == t.t.shape and flux[-1] == 0.0
    np.testing.assert_allclose(flux[:-1][t.t[:-1] >= t1], CAPACITY,
                               rtol=1e-9)
    assert np.all(flux[t.t < t1 - 1e-3] == 0.0)

    thermal = Thermal(r_th=2.0, c_th=5.0, t_max=120.0, t_ambient=25.0)
    hot = heat(t.t, thermal, power=flux)
    tau = thermal.r_th * thermal.c_th
    late = t.t >= t1
    expected = 25.0 + CAPACITY * thermal.r_th * (
        1 - np.exp(-(t.t[late] - t1) / tau))
    # the interval holding t₁ heats for part of it: at most 3 W·1 ms/C_th
    np.testing.assert_allclose(hot.temperature[late], expected, rtol=0,
                               atol=CAPACITY * 1e-3 / thermal.c_th)


def test_a_flux_brake_within_its_capacity_holds_the_bus_at_its_onset():
    """Lowering at 0.15 m/s returns 2.1 W, under the flux brake's 3 W: past
    the onset it takes all of it, and the bus stays at 30 V."""
    t = lowered(0.15)
    returning = -regen(0.15)
    assert 0 < returning < CAPACITY
    charged = charge(t, hoist(c=1e-3))
    assert charged.peak == pytest.approx(ONSET, rel=1e-12)
    t1 = 0.5 * 1e-3 * (ONSET ** 2 - 24.0 ** 2) / returning
    late = t.t[:-1] >= t1
    np.testing.assert_allclose(charged.flux["hoist"][:-1][late], returning,
                               rtol=1e-9)


# --- the probe case -----------------------------------------------------------
PROBE = 2.4       # s, as long as the probe's swing
TRIP = 44.0       # V, the driver's max_voltage


@pytest.fixture(scope="module")
def swing():
    """The geared pendulum's swing (N = 50) of test_drive_mission, 1 rad at
    1 Hz, run for 2.4 s."""
    m = armature.compile(pendulum, SWING)
    return trace(m, Mission("swing", [follow(swing_q, PROBE, qd=swing_qd,
                                             qdd=swing_qdd)]), CONFIRM_RATE)


def probe(brake=None):
    """A small wye motor, Kt = Ke = 0.05 in d-q and R_φ = 0.2 Ω, behind a
    90 % gearbox and a 95 % driver that trips at 44 V, on a 24 V supply
    that cannot sink and 220 µF."""
    return Drive(motors={"motor": motor(r=0.2, kt=Kt(0.05 * SQ3, per="A_rms",
                                                     side="motor"))},
                 drivers={"motor": driver(efficiency=0.95,
                                          max_voltage=TRIP)},
                 gearboxes={"motor": Gearbox(forward=0.9)},
                 bus=Bus(actuators=("motor",), source=Source(
                     v=24.0, sinks=False, p_max=500.0), capacitance=220e-6,
                     brake=brake))


def test_the_probes_swing_on_220_uF_runs_far_above_any_trip(swing):
    """With no brake, each run of returned energy lands on the capacitor,
    and each draw comes off it until the bus is back at 24 V, where the
    supply takes over. So the capacitor's energy above ½C·24² is the
    returned energy's running integral S(t), reflected at zero: S(t) −
    min(0, min S up to t). Integrated with numpy from `electrical`'s bus
    powers, its largest value is the peak by the energy relation. The probe
    reached 222 V with its own motor, whose constants were not kept."""
    tau, omega, rotor = swing.output("motor")
    power = electrical(tau, omega, SWING["N"], probe().motors["motor"],
                       Gearbox(forward=0.9), probe().drivers["motor"],
                       rotor=rotor).bus
    returned_ = np.concatenate(([0.0], np.cumsum(
        -(power[1:] + power[:-1]) / 2 * np.diff(swing.t))))
    above = returned_ - np.minimum(0.0, np.minimum.accumulate(returned_))
    expected = math.sqrt(24.0 ** 2 + 2 * np.max(above) / 220e-6)

    charged = charge(swing, probe())
    assert charged.peak == pytest.approx(expected, rel=1e-4)
    assert charged.peak > 2 * TRIP
    assert charged.minimum == pytest.approx(24.0, rel=1e-12)
    np.testing.assert_array_equal(charged.power["motor"], power)


def test_the_probes_swing_with_a_30_V_8_ohm_brake_stays_at_30_V(swing):
    """The brake takes 30²/8 = 112.5 W at its threshold, and the swing never
    returns more than a twentieth of that, so the brake holds the bus at
    its threshold: the probe's 30.2 V was its forward-Euler chopper's
    overshoot of P·h/(C·V_th) at 0.05 ms."""
    brake = BrakeResistor(threshold=30.0, r=8.0, energy=10.0, power=5.0)
    charged = charge(swing, probe(brake))
    assert -np.min(charged.power["motor"]) < 30.0 ** 2 / 8.0 / 20
    assert charged.peak == pytest.approx(30.0, abs=1e-9)
    assert charged.peak < TRIP
    assert 0 < charged.brake_peak < 30.0 ** 2 / 8.0 / 20


# --- the substep --------------------------------------------------------------
OVERLOADED = BrakeResistor(threshold=48.0, r=48.0 ** 2 / 50.0, energy=100.0,
                           power=50.0)  # 50 W at its threshold


def overloaded_peak(c=0.01, v0=24.0):
    """The stop's peak against a brake that takes 50 W at 48 V, by scipy:
    P(t) = J·α·(ω₀ − α·t) − copper fills the capacitor from ½C·24² until
    ½C·48², and then dE/dt = P(t) − V²/R = P(t) − 2E/(R·C), until the brake
    catches up and the bus falls back."""
    def returning(t):
        return J_WHEEL * ALPHA * (W0 - ALPHA * t) - COPPER

    reach = brentq(lambda t: returned(t) - 0.5 * c * (48.0 ** 2 - v0 ** 2),
                   0.0, STOP)
    solved = solve_ivp(
        lambda t, e: [returning(t) - 2 * e[0] / (OVERLOADED.r * c)],
        (reach, STOP), [0.5 * c * 48.0 ** 2], rtol=1e-12, atol=1e-12,
        dense_output=True)
    times = np.linspace(reach, STOP, 200001)
    return float(np.sqrt(2 * np.max(solved.sol(times)[0]) / c))


def test_an_overloaded_brake_lets_the_bus_rise_as_its_ode(stop):
    """The stop returns up to 100 W, twice the brake's 50 W at 48 V, so the
    bus rises past the threshold until V²/R catches up. The brake's
    capacity is taken at each substep's starting V, the bus's one
    first-order term, so refined until halving moves the peak by less than
    agree, its error is under twice agree."""
    expected = overloaded_peak()
    assert expected > 48.5
    charged = charge(stop, one(Source(v=24.0, sinks=False, p_max=500.0),
                               0.01, brake=OVERLOADED), agree=1e-4)
    assert charged.peak == pytest.approx(expected, abs=2e-4)


def test_halving_the_reported_substep_moves_the_peak_by_less_than_agree(
        stop):
    """Refined to agree within 0.1 mV, halving the substep it reports moves
    the overloaded brake's peak by less than that; that substep run alone is
    the same bus; and the trace's own 1 ms interval was not enough."""
    drive = one(Source(v=24.0, sinks=False, p_max=500.0), 0.01,
                brake=OVERLOADED)
    charged = charge(stop, drive, agree=1e-4)
    assert charged.agree == 1e-4
    halved = charge(stop, drive, substep=charged.substep / 2)
    assert abs(halved.peak - charged.peak) < 1e-4
    assert charge(stop, drive, substep=charged.substep).peak == charged.peak
    coarse = charge(stop, drive, substep=1e-3)
    assert abs(charge(stop, drive, substep=5e-4).peak - coarse.peak) >= 1e-4
    assert charged.substep < 1e-3


# --- bands and points ---------------------------------------------------------
def test_a_band_runs_at_the_point_it_is_given(stop):
    """#88 searches a band as an `Interval(*band)` axis and runs the bus at
    the point it reads: on 4.7–10 mF, the low end gives the higher peak, by
    the energy relation."""
    drive = one(Source(v=(22.0, 26.0), sinks=False, p_max=500.0),
                (4.7e-3, 10e-3))
    low = charge(stop, drive, capacitance=4.7e-3, v_source=26.0)
    assert low.capacitance == 4.7e-3 and low.v_source == 26.0
    assert low.peak == pytest.approx(
        math.sqrt(26.0 ** 2 + 2 * returned(STOP) / 4.7e-3), rel=1e-12)
    with pytest.raises(ValueError, match="capacitance="):
        charge(stop, drive, v_source=26.0)
    with pytest.raises(ValueError, match="v_source="):
        charge(stop, drive, capacitance=4.7e-3)
    with pytest.raises(ValueError, match=r"capacitance.*\(0\.0047, 0\.01\)"):
        charge(stop, drive, capacitance=1e-3, v_source=26.0)


# --- a bus with no source -----------------------------------------------------
def test_a_bus_with_no_source_floats_from_where_it_starts(stop):
    """Nothing sources or sinks, so the stop's return lands on the
    capacitor from v0 and the hotel load drains it all along:
    V = √(V₀² + 2(E − P·t)/C)."""
    v0, c, hotel = 30.0, 0.01, 20.0
    charged = charge(stop, one(None, c, v0=v0, hotel=hotel))
    np.testing.assert_allclose(
        charged.v,
        np.sqrt(v0 ** 2 + 2 * (returned(charged.t) - hotel * charged.t) / c),
        rtol=1e-12)
    assert not np.any(charged.source) and charged.source_energy == 0
    assert charged.v_source == v0


def test_a_bus_with_no_source_starts_at_a_point_in_its_band(stop):
    charged = charge(stop, one(None, 0.01, v0=(26.0, 30.0)), v_source=28.0)
    assert charged.v[0] == 28.0
    with pytest.raises(ValueError, match="v_source="):
        charge(stop, one(None, 0.01, v0=(26.0, 30.0)))


def test_a_hotel_load_drains_a_bus_with_no_source_to_nothing(stop):
    """200 W outdraws the stop's return, 100 W at most, from the start: the
    bus empties and stays empty."""
    charged = charge(stop, one(None, 0.01, v0=30.0, hotel=200.0))
    assert charged.minimum == 0.0 and charged.v[-1] == 0.0


# --- the data, each error naming its field ------------------------------------
@pytest.mark.parametrize("make, words", [
    (lambda: Source(v=24.0, sinks="yes", p_max=1.0), "sinks"),
    (lambda: Source(v=(26.0, 22.0), sinks=True, p_max=1.0),
     r"v band's low is above its high"),
    (lambda: Source(v=24.0, sinks=True, p_max=0.0), "p_max"),
    (lambda: BrakeResistor(threshold=30.0, r=-8.0, energy=1.0, power=1.0),
     "r"),
    (lambda: Bus(actuators=("motor",), source=Source(
        v=24.0, sinks=True, p_max=1.0), capacitance=(-1.0, 1.0)),
     "capacitance"),
    (lambda: Bus(actuators=("motor", "motor"), source=Source(
        v=24.0, sinks=True, p_max=1.0), capacitance=1e-3), "once"),
    (lambda: Bus(actuators=("motor",), source=Source(
        v=24.0, sinks=True, p_max=1.0), capacitance=1e-3, hotel=-1.0),
     "hotel"),
    (lambda: Source(v=(22.0, 30.0), sinks=False, p_max=1.0,
                    overvoltage=30.0), "overvoltage"),
    (lambda: Bus(actuators=("motor",), source=Source(
        v=(22.0, 30.0), sinks=True, p_max=1.0), capacitance=1e-3,
        ratings={"power board": 30.0}), r"rating 'power board'.*above"),
    (lambda: Bus(actuators=("motor",), source=Source(
        v=24.0, sinks=True, p_max=1.0), capacitance=1e-3, ratings=44.0),
     "ratings"),
    (lambda: Bus(actuators=("motor",), source=None, capacitance=1e-3),
     r"no source.*v0"),
    (lambda: Bus(actuators=("motor",), source=Source(
        v=24.0, sinks=True, p_max=1.0), capacitance=1e-3, v0=24.0),
     r"source.*v0"),
    (lambda: Bus(actuators=("motor",), source=None, v0=(26.0, 33.6),
                 capacitance=1e-3, ratings={"power board": 33.6}),
     r"rating 'power board'.*above"),
    (lambda: Drive(motors={"motor": motor(), "spare": motor()},
                   drivers={"motor": driver()},
                   bus=Bus(actuators=("motor",), source=Source(
                       v=24.0, sinks=False, p_max=1.0), capacitance=1e-3)),
     "spare"),
    (lambda: Drive(motors={"motor": motor()}, drivers={},
                   bus=Bus(actuators=("motor",), source=Source(
                       v=24.0, sinks=False, p_max=1.0), capacitance=1e-3)),
     "no driver"),
    (lambda: Drive(motors={"motor": motor()}, drivers={"motor": driver()},
                   gearboxes={"motor": 0.9},
                   bus=Bus(actuators=("motor",), source=Source(
                       v=24.0, sinks=False, p_max=1.0), capacitance=1e-3)),
     "gearboxes"),
])
def test_drive_data_that_cannot_be_used_raises_naming_it(make, words):
    with pytest.raises((TypeError, ValueError), match=words):
        make()


def test_a_geared_actuator_without_a_gearbox_raises_naming_it(swing):
    drive = Drive(motors={"motor": motor()}, drivers={"motor": driver()},
                  bus=Bus(actuators=("motor",), source=Source(
                      v=24.0, sinks=False, p_max=100.0), capacitance=1e-3))
    with pytest.raises(ValueError, match="'motor' has a gear of 50"):
        charge(swing, drive)


def test_an_actuator_the_drive_does_not_carry_raises_naming_it(stop):
    drive = Drive(motors={"other": motor()}, drivers={"other": driver()},
                  bus=Bus(actuators=("other",), source=Source(
                      v=24.0, sinks=False, p_max=100.0), capacitance=1e-3))
    with pytest.raises(ValueError, match=r"\['motor'\]"):
        charge(stop, drive)


