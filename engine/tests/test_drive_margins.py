"""The drive margins, searched.

Answer: each expected value is worked here, never read from the margins
module:
- the 2R arm's worst move is a brute-force sweep over direction and
  distance, each move traced and taken through `electrical` directly;
- the bus's worst bands follow from the energy relation: the least
  capacitance and the most efficient gearbox return the most to the bus;
- a hold's winding reaches the periodic state of a square-wave loss,
  ΔT = P·R_th·(1 − e^(−t_on/τ))/(1 − e^(−T/τ)), with α = 0 so P is fixed,
  and its RMS torque is τ·√(t_on/T);
- a hold's energy is its copper loss, R·i², over the driver's efficiency;
- an e-stop's worst trigger is a brute-force sweep over its fraction, each
  traced and charged directly.
"""

import math

import numpy as np
import pytest
from PIL import Image

import armature
from armature import Band, Budget, Direction, Interval, Space, search
from armature.drive import (Bus, Current, Drive, Driver, Duty, Energy,
                            Gearbox, Kt, Limits, Mission, Motor, Resistance,
                            Source, Thermal, after, charge, electrical, energy,
                            event, follow, hold, margins, move, review, trace)
from test_drive_bus import ALPHA, J_WHEEL, STOP, W0, returned
from test_drive_bus import driver as plain_driver
from test_drive_bus import flywheel as spinning
from test_drive_bus import motor as tiny_motor
from test_drive_mission import (MGL, SWING, pendulum, swing_q, swing_qd,
                                swing_qdd)
from test_fixture_2r_arm import PARAMS as ARM
from test_fixture_2r_arm import arm

SQ3 = math.sqrt(3)
KT = 0.05      # N·m/A in d-q, motor side
R = 0.2        # Ω per phase
I_PEAK = 5.0   # A_peak, the driver's
DQ = math.sqrt(3 / 2)  # d-q amperes per peak line ampere, in a wye
QUICK = Budget(global_points=32, polish_starts=2, polish_evals=40)


def motor(**extra):
    return Motor(kt=Kt(KT * SQ3, per="A_rms", side="motor"),
                 r=Resistance(R, between="phase", alpha=0.0), wiring="wye",
                 **extra)


def driver(**extra):
    return Driver(efficiency=0.95, i_peak=Current(I_PEAK, per="A_peak"),
                  max_voltage=60.0, undervoltage=10.0, **extra)


def on_a_bus(names, motors=None, eta=0.9, capacitance=1e-3, sinks=True,
             drivers=None, brake=None):
    return Drive(motors=motors or {a: motor() for a in names},
                 drivers=drivers or {a: driver() for a in names},
                 gearboxes={a: Gearbox(forward=eta) for a in names},
                 bus=Bus(actuators=tuple(names),
                         source=Source(v=24.0, sinks=sinks, p_max=500.0),
                         capacitance=capacitance, brake=brake))


def named(ms):
    return {m.name: m for m in ms}


# --- searched endpoints on the 2R arm ----------------------------------------
START = {"shoulder": 0.3, "elbow": 0.6}
LIMITS = Limits(v=3.0, a=20.0, j=400.0, along="path")
ARM_MOTORS = ("shoulder_motor", "elbow_motor")
CURRENT = "elbow_motor: driver peak current"


def searched(p):
    return Mission("searched", [move(START, direction=p.direction,
                                     distance=p.distance, limits=LIMITS)])


ELBOW_ONLY = Mission("elbow only", [move(
    START, end={"shoulder": START["shoulder"],
                "elbow": START["elbow"] + 1.0}, limits=LIMITS)])


@pytest.fixture(scope="module")
def arm_model():
    return armature.compile(arm, ARM)


@pytest.fixture(scope="module")
def arm_margins(arm_model):
    space = Space(direction=Direction("xy"), distance=Interval(0.2, 1.0))
    return named(margins(on_a_bus(ARM_MOTORS), [searched, ELBOW_ONLY],
                         space, model=arm_model, budget=QUICK))


@pytest.fixture(scope="module")
def arm_worst(arm_margins):
    return search(arm_margins[CURRENT])


def slack_of(m, mission):
    """The elbow driver's peak-current slack (A_peak), worked from the
    trace and the electrical model directly."""
    t = trace(m, mission, 200.0)
    tau, omega, rotor = t.output("elbow_motor")
    e = electrical(tau, omega, ARM["N2"], motor(), Gearbox(forward=0.9),
                   driver(), rotor=rotor)
    return I_PEAK - float(np.max(np.abs(e.current))) / DQ


def test_the_searched_move_finds_a_direction_a_named_move_misses(
        arm_model, arm_worst):
    """The elbow's own move is the one a spec names; its worst is the
    shoulder's, whose acceleration couples into the elbow. The sweep runs
    72 directions by 5 distances; the search lands at or below its least,
    and within its grid's resolution of it."""
    sweep = min(
        (slack_of(arm_model, Mission("swept", [move(
            START, direction=(math.cos(a), math.sin(a)), distance=d,
            limits=LIMITS)])), a, d)
        for a in np.linspace(-math.pi, math.pi, 72, endpoint=False)
        for d in np.linspace(0.2, 1.0, 5))
    assert arm_worst.at["mission"] == "searched"
    assert arm_worst.value <= sweep[0] + 1e-9
    assert arm_worst.value == pytest.approx(sweep[0], abs=0.02 * I_PEAK)
    direction = arm_worst.at["direction"]
    assert abs(direction[1]) < 0.5  # mostly the shoulder, not the elbow
    case = {c.choices["mission"]: c.value for c in arm_worst.cases}
    assert case["elbow only"] == pytest.approx(
        slack_of(arm_model, ELBOW_ONLY), abs=1e-12)
    assert case["elbow only"] > arm_worst.value + 0.05 * I_PEAK


def test_the_worst_case_agrees_with_its_truth_at_1_kHz(arm_worst):
    assert arm_worst.truth.agrees
    assert arm_worst.truth.agree == pytest.approx(0.01 * I_PEAK)


def test_a_coarse_rate_shows_the_disagreement(arm_model):
    """At 5 Hz the samples straddle the move's peaks, so its truth at
    1 kHz reads more current than the search did."""
    ms = named(margins(on_a_bus(ARM_MOTORS), [ELBOW_ONLY],
                       model=arm_model, rate=5.0))
    worst = search(ms[CURRENT])
    assert not worst.truth.agrees
    assert worst.truth.value < worst.value - worst.truth.agree


def test_the_margins_name_every_check(arm_margins):
    assert list(arm_margins) == [
        "shoulder_motor: envelope at V_min",
        "shoulder_motor: driver peak current",
        "elbow_motor: envelope at V_min", "elbow_motor: driver peak current",
        "bus: peak V", "bus: minimum V", "bus: source power",
        "shoulder_motor: winding", "elbow_motor: winding"]
    peak = arm_margins["bus: peak V"].over
    assert set(peak.axes) == {"direction", "distance", "mission"}
    assert peak.axes["mission"].values == ("searched", "elbow only")
    assert arm_margins[CURRENT].unit == "A_peak"


# --- the bus's bands ---------------------------------------------------------
BUS_BANDS = {"eta": (0.8, 0.95)}
SWING_MISSION = Mission("swing", [follow(swing_q, 2.4, qd=swing_qd,
                                         qdd=swing_qdd)])


def swing_drive(p):
    """The pendulum's motor behind a gearbox of efficiency `eta` both ways,
    on 220 µF to 2.2 mF and a 24 V supply that cannot sink."""
    return on_a_bus(["motor"], eta=p["eta"], capacitance=(220e-6, 2.2e-3),
                    sinks=False,
                    drivers={"motor": Driver(
                        efficiency=0.95, i_peak=Current(40.0, per="A_peak"),
                        max_voltage=150.0, undervoltage=10.0)})


@pytest.fixture(scope="module")
def swing_margins():
    space = Space(eta=Band("eta", BUS_BANDS, of="drive"))
    return named(margins(swing_drive, [SWING_MISSION], space,
                         model=armature.compile(pendulum, SWING),
                         params={"eta": 0.9}, budget=QUICK))


def test_the_least_capacitance_and_the_most_efficient_gearbox_peak_the_bus(
        swing_margins):
    margin = swing_margins["bus: peak V"]
    assert set(margin.over.axes) == {"eta", "mission", "capacitance"}
    worst = search(margin)
    assert worst.at["capacitance"] == 220e-6
    assert worst.at["eta"] == 0.95
    assert worst.truth.agrees


# --- the lowest trip on the bus ----------------------------------------------
STOPPED = Mission("stop", [follow(
    lambda t: {"spin": W0 * t - 0.5 * ALPHA * t * t}, STOP,
    qd=lambda t: {"spin": W0 - ALPHA * t}, qdd=lambda t: {"spin": -ALPHA})])
C_STOP = 0.2  # F: the stop's 50 J lifts 24 V to 32.8 V


def stopping(**bus):
    """The flywheel's one motor, on 200 V drivers, a 24 V source that cannot
    sink, and C_STOP."""
    kwargs = dict(source=Source(v=24.0, sinks=False, p_max=500.0),
                  capacitance=C_STOP)
    kwargs.update(bus)
    return Drive(motors={"motor": tiny_motor()},
                 drivers={"motor": plain_driver()},
                 bus=Bus(actuators=("motor",), **kwargs))


@pytest.fixture(scope="module")
def free_wheel():
    return armature.compile(spinning, {"J": J_WHEEL})


def test_a_rating_no_driver_carries_is_the_lowest_trip(free_wheel):
    """A 40 V power board under the 200 V drivers: the stop lands on the
    capacitor alone, so the peak is √(V₀² + 2E/C) and the board takes the
    slack, which the row names."""
    ms = named(margins(stopping(ratings={"power board": 40.0,
                                         "capacitor bank": 63.0}),
                       [STOPPED], model=free_wheel))
    worst = search(ms["bus: peak V"])
    peak = math.sqrt(24.0 ** 2 + 2 * returned(STOP) / C_STOP)
    assert worst.value == pytest.approx(40.0 - peak, rel=1e-9)
    assert str(worst).startswith(
        f"bus: peak V: {worst.value:.7g} V against power board (40 V) at ")


def test_each_bus_configuration_names_its_own_lowest_trip(free_wheel):
    ms = named(margins({"boarded": stopping(ratings={"power board": 40.0}),
                        "bare": stopping(source=Source(
                            v=24.0, sinks=False, p_max=500.0,
                            overvoltage=150.0))},
                       [STOPPED], model=free_wheel))
    worst = search(ms["bus: peak V"])
    assert worst.at["drive"] == "boarded"
    assert ("against power board (40 V) on boarded, the source's "
            "overvoltage (150 V) on bare at ") in str(worst)


def test_a_drive_band_names_a_drive_parameter():
    with pytest.raises(ValueError, match=r"band 'eta'.*names no parameter.*"
                                         r"drive.*\['eff'\]"):
        margins(swing_drive, [SWING_MISSION],
                Space(eta=Band("eta", BUS_BANDS, of="drive")),
                model=armature.compile(pendulum, SWING),
                params={"eff": 0.9})


# --- the duty: winding temperature, RMS torque -------------------------------
THERMAL = Thermal(r_th=2.0, c_th=20.0, t_max=80.0, t_ambient=25.0)
ON, PERIOD = 20.0, 60.0


def held(name, q):
    return Mission(name, [hold({"pivot": q}, ON)],
                   duty=Duty(period=PERIOD, session=3600.0))


def hold_current(q, eta=0.9):
    """The winding's d-q current holding the pendulum at `q`: the output
    torque m g l_c sin q through the gearbox motoring."""
    return MGL * math.sin(q) / (SWING["N"] * eta * KT)


def periodic_peak(power):
    tau = THERMAL.r_th * THERMAL.c_th
    return THERMAL.t_ambient + power * THERMAL.r_th * (
        -math.expm1(-ON / tau)) / (-math.expm1(-PERIOD / tau))


def pendulum_margins(motors, missions=None):
    def wave(p):
        return Mission("wave", [move({"pivot": 0.0}, direction=(1.0,),
                                     distance=p.reach,
                                     limits=Limits(v=2, a=10, j=100,
                                                   along="coordinate"))])
    missions = missions if missions is not None else [
        held("light", 0.3), held("heavy", 1.0), wave]
    return named(margins(on_a_bus(["motor"], motors={"motor": motors}),
                         missions, Space(reach=Interval(0.5, 1.5)),
                         model=armature.compile(pendulum, SWING),
                         budget=QUICK))


def test_a_thermal_margin_takes_the_hotter_mission_as_written():
    ms = pendulum_margins(motor(thermal=THERMAL))
    margin = ms["motor: winding temperature"]
    # Only the missions as written, and only bands: never the searched wave
    assert set(margin.over.axes) == {"mission"}
    assert margin.over.axes["mission"].values == ("light", "heavy")
    worst = search(margin)
    assert worst.at == {"mission": "heavy"}
    hot = periodic_peak(R * hold_current(1.0) ** 2)
    assert worst.value == pytest.approx(THERMAL.t_max - hot, abs=0.12)
    assert worst.value >= THERMAL.t_max - hot  # from below, as it repeats
    light = {c.choices["mission"]: c.value for c in worst.cases}["light"]
    assert light == pytest.approx(
        THERMAL.t_max - periodic_peak(R * hold_current(0.3) ** 2), abs=0.12)
    assert worst.truth.agrees


def test_the_rms_fallback_reads_the_duty_against_the_continuous_rating():
    rating = Current(2.0, per="A_rms")
    ms = pendulum_margins(motor(i_continuous=rating))
    worst = search(ms["motor: RMS torque"])
    assert worst.at == {"mission": "heavy"}
    torque = KT * hold_current(1.0)
    assert worst.value == pytest.approx(
        KT * 2.0 * SQ3 - torque * math.sqrt(ON / PERIOD), rel=1e-9)


def test_a_mechanism_band_is_compiled_into_the_duty():
    """The bob's mass band: the heavier bob holds more torque, so the RMS
    margin is worst at the band's high end, its torque in proportion."""
    rating = Current(2.0, per="A_rms")
    space = Space(m=Band("m", {"m": (SWING["m"], 1.5 * SWING["m"])}))
    ms = named(margins(on_a_bus(["motor"], motors={
        "motor": motor(i_continuous=rating)}), [held("heavy", 1.0)], space,
        model=armature.compile(pendulum, SWING), budget=QUICK))
    worst = search(ms["motor: RMS torque"])
    assert worst.at["m"] == 1.5 * SWING["m"]
    torque = 1.5 * KT * hold_current(1.0)
    assert worst.value == pytest.approx(
        KT * 2.0 * SQ3 - torque * math.sqrt(ON / PERIOD), rel=1e-9)


def test_the_source_is_sized_with_the_windings_hot():
    """Copper's R rises by (t_max − T₀)/(234.5 + T₀) at t_max, and a hold
    draws R·i²/η from the source; the hot draw is the one checked."""
    hot = Motor(kt=Kt(KT * SQ3, per="A_rms", side="motor"),
                r=Resistance(R, between="phase"), wiring="wye",
                thermal=THERMAL)
    ms = pendulum_margins(hot, missions=[held("heavy", 1.0)])
    worst = search(ms["bus: source power"])
    r_hot = R * (1 + (THERMAL.t_max - 25.0) / (234.5 + 25.0))
    assert worst.value == pytest.approx(
        500.0 - r_hot * hold_current(1.0) ** 2 / 0.95, rel=1e-9)


def test_missing_thermal_data_is_unchecked_naming_both():
    ms = pendulum_margins(motor())
    margin = ms["motor: winding"]
    assert margin.unchecked == ("motors['motor'].thermal",
                                "motors['motor'].i_continuous")
    worst = search(margin)
    assert not worst.passes and worst.unchecked == margin.unchecked
    assert "UNCHECKED" in str(worst)


def test_duty_margins_without_a_mission_as_written_are_unchecked():
    def wave(p):
        return held("wave", p.reach)
    ms = pendulum_margins(motor(thermal=THERMAL), missions=[wave])
    assert ms["motor: winding temperature"].unchecked == (
        "a mission as written, with its duty",)


# --- energy, reported --------------------------------------------------------
def test_a_holds_energy_is_its_copper_loss_through_the_driver():
    m = armature.compile(pendulum, SWING)
    report, = energy(on_a_bus(["motor"]), [held("heavy", 1.0)], model=m)
    assert isinstance(report, Energy)
    copper = R * hold_current(1.0) ** 2 * ON
    assert report.copper == pytest.approx(copper, rel=1e-9)
    assert report.source == pytest.approx(copper / 0.95, rel=1e-9)
    assert report.regenerated == 0 and report.brake == 0
    assert report.per_session == pytest.approx(report.source * 60, rel=1e-12)


# --- an event's trigger, searched --------------------------------------------
def flywheel(p):
    return [armature.body("wheel", mass=1.0, com=(0, 0, 0),
                          inertia=np.diag([p["J"]] * 3)),
            armature.joint("spin", "hinge", parent="world", child="wheel",
                           axis=(0, 0, 1), point=(0, 0, 0),
                           range=(-1e4, 1e4)),
            armature.actuator("motor", joint="spin", gear=1.0,
                              rotor_inertia=0.0),
            armature.gravity((0, 0, 0))]


SPIN = move({"spin": 0.0}, end={"spin": 20.0},
            limits=Limits(v=1e3, a=40.0, j=400.0, along="coordinate"))


def estop_at(fraction):
    """An e-stop partway through a spin, braking at a constant torque for
    20 ms."""
    return Mission("e-stop", [SPIN, event(after(SPIN, fraction),
                                          {"motor": -0.2}, 0.02,
                                          timestep=1e-3)])


def test_an_e_stops_trigger_is_searched():
    """The bus cannot sink, and 100 µF charges fast: as the spin's braking
    torque ramps in at speed, it returns more than its copper burns, and an
    e-stop there adds to it, so the worst trigger lies past the middle. The
    sweep runs 51 triggers, each traced and charged directly; the search
    lands at or below its least, near its place."""
    def estop(p):
        return estop_at(p.fraction)

    d = on_a_bus(["motor"], eta=1.0, capacitance=1e-4, sinks=False)
    m = armature.compile(flywheel, {"J": 0.01})
    ms = named(margins({"plain": d}, [estop],
                       Space(fraction=Interval(0.0, 1.0)), model=m,
                       budget=Budget(global_points=16, polish_starts=1,
                                     polish_evals=20)))
    worst = search(ms["bus: peak V"])
    sweep = min((60.0 - charge(trace(m, estop_at(f), 200.0, drive=d,
                                     capacitance=1e-4, v_source=24.0),
                               d).peak, f)
                for f in np.linspace(0.0, 1.0, 51))
    assert worst.value <= sweep[0] + 0.01  # charge's own agree
    assert worst.at["fraction"] == pytest.approx(sweep[1], abs=0.03)
    assert worst.at["fraction"] > 0.5
    assert worst.at["drive"] == "plain"
    assert worst.truth.agrees  # at half the event's timestep


# --- the review --------------------------------------------------------------
def test_a_move_starts_from_the_coordinates_axis(tmp_path):
    """Each point's move starts at the point's state; the review rebuilds
    that state from the worst case's coordinates."""
    starts = []

    def reach(p):
        starts.append((p.state.q["shoulder"], p.state.q["elbow"]))
        return Mission("reach", [move(p.state, direction=(1.0, 0.0),
                                      distance=0.5, limits=LIMITS)])

    within = {"shoulder": (0.0, 0.5), "elbow": (0.5, 1.0)}
    space = Space(state=armature.Coordinates(arm, ARM, within=within))
    ms = named(margins(on_a_bus(ARM_MOTORS), [reach], space,
                       budget=Budget(global_points=8, polish_starts=0)))
    worst = search(ms[CURRENT])
    assert {(s, e) for s, e in starts} >= {(0.0, 0.5), (0.5, 1.0)}
    assert set(worst.at["state"]) == {"shoulder", "elbow"}
    reviewed, = review([ms[CURRENT]], tmp_path, worsts=[worst])
    assert reviewed.path.is_file()



def test_the_review_writes_each_worst_case_with_its_panels(tmp_path):
    ms = pendulum_margins(motor(thermal=THERMAL))
    chosen = [ms[n] for n in ("motor: envelope at V_min", "bus: peak V",
                              "motor: winding temperature")]
    reviewed = review(chosen + [pendulum_margins(motor())["motor: winding"]],
                      tmp_path / "review")
    assert [r.margin for r in reviewed] == [m.name for m in chosen]
    expected = [["motor: (τ, ω) samples over the envelope at V_min"],
                ["bus: V(t) against its trips", "bus: source and brake power"],
                ["motor: T(t) against the winding limit"]]
    for r, panels in zip(reviewed, expected):
        assert r.path.is_file() and r.path.parent == tmp_path / "review"
        with Image.open(r.path) as png:
            assert png.format == "PNG"
            written = png.text["Panels"].split("; ")
        assert list(r.panels) == written
        assert [w[:len(p)] for w, p in zip(written, panels)] == panels
