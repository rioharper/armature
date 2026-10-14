"""Events: uncommanded motion, forward-simulated, with the bus stepped
alongside.

Answer: each expected value is worked here from the drive data's numbers
and the mechanics, never from the event module:
- a flywheel on a shorted motor decays as exp(−c·t/J), c = N²·Kt·Ke/(R_φ·η_b)
  in d-q, J its inertia with the rotor's N²J_m;
- a coasting pendulum keeps ½J q̇² + m g l_c (1 − cos q), to first order in
  the timestep, semi-implicit Euler's;
- `after(move, fraction)` starts where ruckig, called here directly, puts
  the move at that fraction;
- a flux-braking flywheel regenerates (E − R_φ·i_max)·i_max, raising the
  bus by ½C(V² − V₀²) to the onset, where the flux brake takes it;
- fixture 3, held by its motors at the torques `inverse` gives, presses
  its wheel on the floor with the weight of everything the wheel carries;
- fixture 2's platform on four shorted winches, stopped partway through a
  move, loses exactly the energy the shorts dissipate, its rotors'
  ½J_m·ω_m² counted, and each winch turns at its cable's rate, worked here
  from the anchors.
"""

import math

import numpy as np
import pytest
from ruckig import InputParameter, Ruckig, Synchronization, Trajectory

import armature
from armature import actuator, body, gravity, joint, lock
from armature.drive import (AGREE, Bus, Current, Drive, Driver, FluxBrake,
                            Gearbox, Kt, Limits, Mission, Motor, Resistance,
                            Simulated, Source, after, charge, electrical,
                            event, follow, hold, move, trace)
from armature.elements import Cable
from test_drive_mission import (AMPLITUDE, J_TOTAL, MGL, SWING, pendulum)
from test_fixture_cable_platform import ANCHORS, ATTACH, G, HOME
from test_fixture_cable_platform import params as hung_at
from test_fixture_cable_platform import platform
from test_fixture_wheel_leg import CARRIED
from test_fixture_wheel_leg import PARAMS as WHEEL_LEG
from test_fixture_wheel_leg import wheel_leg

SQ3 = math.sqrt(3)
KT = 0.1  # N·m/A in d-q, as 0.1·√3 N·m/A_rms reads in a wye; Ke the same
V_S = 24.0


def motor(r, kt=KT):
    return Motor(kt=Kt(kt * SQ3, per="A_rms", side="motor"),
                 r=Resistance(r, between="phase"), wiring="wye")


def drive(names, r, i_peak=100.0, flux=None, gearboxes=None,
          capacitance=1e-3, kt=KT):
    """Every actuator in `names` on one motor and driver, through a lossless
    gearbox unless `gearboxes` gives one, on a 24 V supply behind a
    diode."""
    if gearboxes is None:
        gearboxes = {a: Gearbox(forward=1.0) for a in names}
    return Drive(
        motors={a: motor(r, kt) for a in names},
        drivers={a: Driver(efficiency=1.0,
                           i_peak=Current(i_peak / math.sqrt(3 / 2),
                                          per="A_peak"),  # i_peak in d-q
                           max_voltage=200.0, undervoltage=5.0,
                           flux_brake=flux) for a in names},
        gearboxes=gearboxes,
        bus=Bus(actuators=tuple(names),
                source=Source(v=V_S, sinks=False, p_max=1e3),
                capacitance=capacitance))


def flywheel(p):
    return [body("wheel", mass=1.0, com=(0, 0, 0),
                 inertia=np.diag([p["J"]] * 3)),
            joint("spin", "hinge", parent="world", child="wheel",
                  axis=(0, 0, 1), point=(0, 0, 0), range=(-1e4, 1e4)),
            actuator("motor", joint="spin", gear=p["N"],
                     rotor_inertia=p["Jm"]),
            gravity((0, 0, 0))]


def spun(m, w0):
    return m.at(qd={"spin": w0})


# --- a shorted flywheel -------------------------------------------------------
@pytest.mark.parametrize("n, jm, backward", [(1.0, 0.0, None),
                                             (5.0, 1e-4, 0.8)])
def test_a_shorted_flywheel_decays_as_its_damping_from_the_constants(
        n, jm, backward):
    """c = N²·Kt·Ke/(R_φ·η_b): the gearbox back-driven adds its friction to
    the short's. R_φ is set so J/c = 1 s, where the implicit step reads
    exp(−t) to t·dt/2 = 5e-5 at 1 s."""
    j = 0.01 + n ** 2 * jm  # the wheel and the rotor through the gear
    eta = 1.0 if backward is None else backward
    r = n ** 2 * KT * KT / (j * eta)  # Ω per phase, so c = J
    c = n ** 2 * KT * KT / (r * eta)
    w0 = 20.0
    m = armature.compile(flywheel, {"J": 0.01, "N": n, "Jm": jm})
    boxes = None if backward is None else {
        "motor": Gearbox(forward=0.9, backward=backward)}
    t = trace(m, Mission("short", [event(spun(m, w0), {"motor": "short"},
                                         1.0)]), 1000.0,
              drive=drive(["motor"], r, gearboxes=boxes))

    expected = n * w0 * np.exp(-c * t.t / j)  # motor side
    np.testing.assert_allclose(t.speed["motor"], expected, rtol=1e-4, atol=0)
    simulated, = t.events
    assert isinstance(simulated, Simulated)
    assert simulated.run.timestep == 1e-4 and simulated.half.timestep == 5e-5
    assert len(simulated.half.trace.t) == 2 * len(t.t) - 1
    np.testing.assert_allclose(simulated.half.trace.speed["motor"],
                               n * w0 * np.exp(-c * simulated.half.trace.t
                                               / j), rtol=5e-5, atol=0)
    # halving the step moves the run by less than the 1e-4 it is held to
    moved = simulated.moved
    assert moved.speed["motor"] < 1e-4 * n * w0
    assert moved.torque["motor"] < 1e-4 * np.max(np.abs(t.torque["motor"]))
    assert moved.v < AGREE
    assert not t.driven["motor"].any()  # a short's driver is off


def test_a_short_puts_nothing_on_the_bus():
    """Its winding voltage, read back through the electrical model, is
    zero: all its power is the winding's heat, ½Jω₀² in all over ten time
    constants, J/c = 0.1 s, less the implicit step's c·dt/J = 1e-3."""
    r, w0 = 0.1, 20.0
    m = armature.compile(flywheel, {"J": 0.01, "N": 1.0, "Jm": 0.0})
    d = drive(["motor"], r)
    t = trace(m, Mission("short", [event(spun(m, w0), {"motor": "short"},
                                         1.0)]), 1000.0, drive=d)
    tau, omega, rotor = t.output("motor")
    e = electrical(tau, omega, 1.0, d.motors["motor"], rotor=rotor)
    assert np.max(np.abs(e.voltage)) < 1e-12 * KT * w0
    heat = np.trapezoid(e.copper, t.t)
    assert heat == pytest.approx(0.5 * 0.01 * w0 ** 2, rel=2e-3)
    assert np.all(t.events[0].run.v == V_S)


# --- a coasting pendulum ------------------------------------------------------
def energy(t):
    q, qd = t.q["pivot"], t.qd["pivot"]
    return 0.5 * J_TOTAL * qd ** 2 + MGL * (1 - np.cos(q))


def test_a_coasting_pendulum_keeps_its_energy_to_first_order():
    """Released from 1 rad, its back-EMF peaks near 2.2 V, under k_mod·V_s =
    17 V, so no current flows: semi-implicit Euler keeps the energy within
    O(dt), with no drift, and halving dt halves the error."""
    m = armature.compile(pendulum, SWING)
    t = trace(m, Mission("coast", [event({"pivot": AMPLITUDE},
                                         {"motor": "coast"}, 2.0)]),
              1000.0, drive=drive(["motor"], 1.0, kt=0.01))
    assert np.all(t.torque["motor"] == 0.0)
    simulated = t.events[0]
    errors = []
    for run in (simulated.run, simulated.half):
        e = energy(run.trace)
        errors.append(np.max(np.abs(e - e[0])) / e[0])
    assert errors[0] < 1e-3
    assert errors[0] / errors[1] == pytest.approx(2.0, rel=0.1)
    # the swing still turns at the height it started from: no drift
    assert np.max(t.q["pivot"][len(t.t) // 2:]) == pytest.approx(
        AMPLITUDE, abs=1e-3)


# --- after(move, fraction) ----------------------------------------------------
def test_an_estop_partway_through_a_move_inherits_its_rates():
    """The move from 0 to 1.2 rad, planned here by ruckig itself; the event
    starts at 0.4 of it, in its posture and at its rate. The move's own
    samples stop there too, its last at the event's first time, where the
    torque jumps from the move's to the short's."""
    limits = dict(v=2.0, a=8.0, j=80.0)
    inp = InputParameter(1)
    inp.current_position, inp.target_position = [0.0], [1.2]
    inp.max_velocity, inp.max_acceleration, inp.max_jerk = (
        [limits["v"]], [limits["a"]], [limits["j"]])
    inp.synchronization = Synchronization.Phase
    planned = Trajectory(1)
    Ruckig(1).calculate(inp, planned)
    at = 0.4 * planned.duration
    (q,), (qd,), _ = planned.at_time(at)
    assert qd > 1.0

    m = armature.compile(pendulum, SWING)
    lift = move({"pivot": 0.0}, end={"pivot": 1.2},
                limits=Limits(**limits, along="coordinate"))
    t = trace(m, Mission("e-stop", [lift, event(after(lift, 0.4),
                                                {"motor": "short"}, 0.2)]),
              1000.0, drive=drive(["motor"], 0.5, kt=0.01))
    first = int(np.argmax(t.segment == 1))
    assert t.t[first] == pytest.approx(at, abs=1e-12)
    assert t.t[first - 1] == t.t[first] and t.segment[first - 1] == 0
    assert np.all(t.t[:first - 1] < at)
    assert t.q["pivot"][first - 1] == pytest.approx(q, abs=1e-12)
    assert t.torque["motor"][first - 1] != t.torque["motor"][first]
    assert t.q["pivot"][first] == pytest.approx(q, abs=1e-12)
    assert t.qd["pivot"][first] == pytest.approx(qd, abs=1e-12)
    assert t.speed["motor"][first] == pytest.approx(SWING["N"] * qd,
                                                    abs=1e-9)
    assert t.spans[0] == (0.0, pytest.approx(at, abs=1e-12))
    assert t.t[-1] == pytest.approx(at + 0.2, abs=1e-12)

    # a hold after the event starts at its end, sampled on both sides
    then = trace(m, Mission("e-stop, held", [
        lift, event(after(lift, 0.4), {"motor": "short"}, 0.2),
        hold(None, 0.1)]), 1000.0, drive=drive(["motor"], 0.5, kt=0.01))
    ended = int(np.argmax(then.segment == 2))
    assert then.t[ended] == then.t[ended - 1] == pytest.approx(at + 0.2)
    assert then.segment[ended - 1] == 1
    assert then.q["pivot"][ended] == then.q["pivot"][ended - 1]

    # the same event first in its own mission runs the move on its own
    alone = trace(m, Mission("e-stop alone", [event(after(lift, 0.4),
                                                    {"motor": "short"},
                                                    0.2)]),
                  1000.0, drive=drive(["motor"], 0.5, kt=0.01))
    assert alone.qd["pivot"][0] == pytest.approx(qd, abs=1e-12)


def test_an_event_after_a_followed_q_starts_at_its_closed_form():
    def q(t):
        return {"pivot": 0.5 * math.sin(3.0 * t)}

    def qd(t):
        return {"pivot": 1.5 * math.cos(3.0 * t)}

    m = armature.compile(pendulum, SWING)
    swing = follow(q, 1.0, qd=qd, qdd=lambda t: {
        "pivot": -4.5 * math.sin(3.0 * t)})
    t = trace(m, Mission("stop", [swing, event(after(swing, 0.25),
                                               {"motor": "coast"}, 0.1)]),
              200.0, drive=drive(["motor"], 1.0, kt=0.01))
    first = int(np.argmax(t.segment == 1))
    assert t.q["pivot"][first] == pytest.approx(q(0.25)["pivot"], abs=1e-12)
    assert t.qd["pivot"][first] == pytest.approx(qd(0.25)["pivot"],
                                                 abs=1e-12)


# --- the bus, continued -------------------------------------------------------
def test_an_event_starts_on_the_bus_the_mission_left():
    """A flywheel slowed from 100 to 50 rad/s at 100 rad/s² returns ½J(100²
    − 50²) = 37.5 J less R_φ·i²·t = 0.5 J of copper loss at i = J·α/Kt =
    10 A, into 0.1 F behind a diode: √(24² + 2·37.0/0.1) = 36.28 V when the
    event takes over. Its coasting motor's 5 V of back-EMF is under
    k_mod·V, so the bus holds there."""
    m = armature.compile(flywheel, {"J": 0.01, "N": 1.0, "Jm": 0.0})
    slow = follow(lambda t: {"spin": 100 * t - 50 * t * t}, 0.5,
                  qd=lambda t: {"spin": 100 - 100 * t},
                  qdd=lambda t: {"spin": -100.0})
    t = trace(m, Mission("slow, then coast", [
        slow, event(after(slow, 1.0), {"motor": "coast"}, 0.05)]), 1000.0,
        drive=drive(["motor"], 0.01, capacitance=0.1))
    returned = 0.5 * 0.01 * (100 ** 2 - 50 ** 2) - 0.01 * 10 ** 2 * 0.5
    v = t.events[0].run.v
    assert v[0] == pytest.approx(math.sqrt(V_S ** 2 + 2 * returned / 0.1),
                                 abs=AGREE)
    assert np.all(v == v[0])


def test_a_torque_profile_drives_its_joint_through_the_gear():
    """τ_m = 2t N·m through N = 2 on a 0.01 kg·m² wheel and a 1e-4 kg·m²
    rotor, from rest: J = 0.01 + 4e-4, so ω = N·t²/J at the joint, to first
    order in the step."""
    m = armature.compile(flywheel, {"J": 0.01, "N": 2.0, "Jm": 1e-4})
    t = trace(m, Mission("spin up", [event(m.at(), {"motor": lambda s: 2 * s},
                                           0.5)]), 1000.0,
              drive=drive(["motor"], 1.0))
    np.testing.assert_allclose(t.torque["motor"], 2 * t.t, rtol=0,
                               atol=1e-12)
    j = 0.01 + 2.0 ** 2 * 1e-4
    lag = 2.0 * 2 * 0.5 / j * 1e-4  # one step at the largest ω̇ = N·τ/J
    np.testing.assert_allclose(t.qd["spin"], 2.0 * t.t ** 2 / j, rtol=0,
                               atol=lag)
    assert t.driven["motor"].all()


# --- flux braking -------------------------------------------------------------
R_FLUX, I_MAX, W0 = 0.1, 10.0, 150.0  # Ω per phase, d-q A, rad/s
ONSET, I_D = 30.0, 40.0               # V, d-q A: 160 W of capacity


def test_a_flux_brake_event_raises_the_bus_to_its_onset_and_holds_it():
    """At 150 rad/s the short's current, E/R = 150 A, passes the driver's
    10 A, so the driver brakes at 10 A and the rest of the back-EMF drives
    (E − R_φ·i_max)·i_max = 140 W into the bus. It rises from 24 V to the
    30 V onset in ½C(30² − 24²)/140 W = 1.16 ms, and the flux brake's 160 W
    holds it there while the wheel slows at Kt·i_max/J = 100 rad/s²."""
    m = armature.compile(flywheel, {"J": 0.01, "N": 1.0, "Jm": 0.0})
    flux = FluxBrake(onset=ONSET, i_d=Current(I_D / math.sqrt(3 / 2),
                                              per="A_peak"))
    d = drive(["motor"], R_FLUX, i_peak=I_MAX, flux=flux)
    t = trace(m, Mission("brake", [event(spun(m, W0),
                                         {"motor": "flux_brake"}, 0.5)]),
              1000.0, drive=d)
    run = t.events[0].run
    v, times = run.v, run.trace.t

    regen = (KT * W0 - R_FLUX * I_MAX) * I_MAX
    rise = 0.5 * 1e-3 * (ONSET ** 2 - V_S ** 2) / regen
    reached = times[int(np.argmax(v >= ONSET - AGREE))]
    assert reached == pytest.approx(rise, rel=0.05)
    assert np.all(np.diff(v[times < rise]) > 0)
    held = times > 2 * rise
    assert np.all(np.abs(v[held] - ONSET) < AGREE)
    # braking at the driver's limit: Kt·i_max, and ω falls at 100 rad/s²
    np.testing.assert_allclose(np.abs(t.torque["motor"]), KT * I_MAX,
                               rtol=1e-12)
    np.testing.assert_allclose(t.speed["motor"], W0 - 100.0 * t.t,
                               rtol=0, atol=1e-6)
    assert t.driven["motor"].all()

    # `charge` over the trace reads the same bus, its flux brake taking the
    # regen from the onset on
    charged = charge(t, d)
    assert charged.peak == pytest.approx(ONSET, abs=AGREE)
    returned = (KT * t.speed["motor"] - R_FLUX * I_MAX) * I_MAX
    late = t.t[:-1] > 2 * rise
    np.testing.assert_allclose(charged.flux["motor"][:-1][late],
                               returned[:-1][late], rtol=0.01)


def test_a_coasting_motor_regenerates_through_its_diodes_past_the_bus():
    """At 300 rad/s the back-EMF, 30 V, is past k_mod·V_s = 17.0 V, so the
    diodes conduct (E − k_mod·V)/R_φ against the motion. Its driver is off,
    so its flux brake cannot hold the bus, which rises past the onset until
    E falls to k_mod·V."""
    m = armature.compile(flywheel, {"J": 0.01, "N": 1.0, "Jm": 0.0})
    flux = FluxBrake(onset=ONSET, i_d=Current(I_D / math.sqrt(3 / 2),
                                              per="A_peak"))
    d = drive(["motor"], 1.0, flux=flux)
    t = trace(m, Mission("coast", [event(spun(m, 300.0),
                                         {"motor": "coast"}, 0.2)]),
              1000.0, drive=d)
    v = t.events[0].run.v
    k_mod = math.sqrt(1 / 2)
    current = (KT * t.speed["motor"][0] - k_mod * V_S) / 1.0
    assert t.torque["motor"][0] == pytest.approx(-KT * current, rel=1e-12)
    assert v[-1] > ONSET + 1.0
    assert not t.driven["motor"].any()
    assert np.all(charge(t, d).flux["motor"] == 0.0)
    # the back-EMF settles towards k_mod·V, past which the diodes conduct
    assert KT * t.speed["motor"][-1] == pytest.approx(k_mod * v[-1],
                                                      rel=0.05)


# --- contact ------------------------------------------------------------------
def test_an_event_with_a_resting_contact_reports_it():
    """Fixture 3 held at home by its motors at the torques `inverse` gives,
    as torque profiles: the wheel carries the weight of everything but the
    rail cart, at every sample."""
    m = armature.compile(wheel_leg, WHEEL_LEG)
    home = m.at()
    held = home.inverse().torque
    names = list(m.actuators)
    weight = sum(WHEEL_LEG[k] for k in CARRIED) * WHEEL_LEG["g"]
    t = trace(m, Mission("held", [event(home, held, 0.05)]), 1000.0,
              drive=drive(names, 1.0, gearboxes={
                  a: Gearbox(forward=0.9) for a in names}))
    contacts = t.events[0].run.contacts
    assert len(contacts) == len(t.t)
    assert all("tyre" in c for c in contacts)
    normal = np.array([c["tyre"].normal for c in contacts])
    np.testing.assert_allclose(normal[10:], weight, rtol=1e-3)
    assert np.max(np.abs(t.qd["x"])) < 1e-3


# --- a cable robot, through its transmission -----------------------------------
WINCHES = ("w1", "w2", "w3", "w4")
SLIDES = ("hang:x", "hang:y", "hang:z")
N_W, R_W, J_W = 5.0, 0.03, 5.6e-5  # belt ratio, drum radius (m), rotor
                                   # inertia (kg·m²): Plumb's winches
K_W = N_W / R_W                    # motor rad/s per m/s of cable
KT_W, R_W_PHI = 0.03, 1.0          # N·m/A and Ω in d-q: a short's 25 N·s/m
                                   # on each cable


def unhung(p):
    """Fixture 2's platform with its cables taken off, for winches to carry
    through a seam."""
    return [e for e in platform(p) if not isinstance(e, Cable)]


LEVEL_ON_WINCHES = armature.reduce(
    unhung, *(lock(f"hang:{c}", 0.0, assumption="A5")
              for c in ("rx", "ry", "rz")), name="level, on winches")


def cables(point):
    """Each cable's unit vector from its attachment toward its anchor, and
    its length."""
    span = ANCHORS - (np.asarray(point) + ATTACH)
    length = np.linalg.norm(span, axis=1)
    return span / length[:, None], length


def winch_rates(state):
    """The cables' unit vectors, the platform's velocity, and each winch's
    ω̇_m at q̈ = 0, K(l̇² − |v|²)/l."""
    point = np.array([state.q[s] for s in SLIDES])
    v = np.array([state.qd[s] for s in SLIDES])
    u, length = cables(point)
    pay = -u @ v  # each cable's l̇
    return u, v, K_W * (pay ** 2 - v @ v) / length


def winches(state, *, t, p):
    """ω_m = K·u·v: a winch turns positive reeling in."""
    u, _, bias = winch_rates(state)
    return {w: (dict(zip(SLIDES, K_W * u[i])), bias[i], J_W)
            for i, w in enumerate(WINCHES)}


def least_tensions(state, qdd, loads, *, t, p):
    """The least-norm tensions that carry the platform, as each winch's
    motor torque with its rotor's own J_m·ω̇_m."""
    u, v, bias = winch_rates(state)
    a = np.array([qdd[s] for s in SLIDES])
    pull = np.linalg.pinv(u.T) @ (p["m"] * (a + (0.0, 0.0, G)))
    out = {}
    for i, w in enumerate(WINCHES):
        rotor = J_W * (K_W * u[i] @ a + bias[i])
        out[w] = (pull[i] / K_W + rotor, K_W * u[i] @ v, rotor)
    return out


def on_winches(p):
    m = armature.compile(LEVEL_ON_WINCHES, p)
    start = dict(zip(SLIDES, HOME))
    across = move(start, end={**start, "hang:x": 2.8, "hang:z": 1.5},
                  limits=Limits(v=1.0, a=3.0, j=30.0, along="path"))
    return m, across


def test_an_estop_stops_a_cable_robot_on_its_shorted_winches():
    """A move across the room, its winches shorted halfway: the platform's
    energy, ½m|v|² + m·g·z and each rotor's ½J_m·ω_m², falls by what the
    shorts dissipate, ∫Σ c·ω_m² with c = Kt·Ke/R_φ, to first order in the
    step. Each winch turns at K·u·v and brakes at −c·ω_m, at the platform's
    own samples; a short puts nothing on the bus."""
    p = hung_at(HOME, 2.0)
    m, across = on_winches(p)
    assert m.coordinates == SLIDES and not m.actuators
    stop = event(after(across, 0.5), {w: "short" for w in WINCHES}, 0.3)
    t = trace(m, Mission("e-stop", [across, stop], actuation=least_tensions,
                         transmission=winches), 1000.0,
              drive=drive(WINCHES, R_W_PHI, kt=KT_W),
              gear={w: N_W for w in WINCHES})
    simulated, = t.events
    c = KT_W * KT_W / R_W_PHI
    first = simulated.run.trace
    assert np.linalg.norm([first.qd[s][0] for s in SLIDES]) > 0.5

    gaps = []
    for run in (simulated.run, simulated.half):
        tr = run.trace
        point = np.stack([tr.q[s] for s in SLIDES], axis=1)
        v = np.stack([tr.qd[s] for s in SLIDES], axis=1)
        for i, w in enumerate(WINCHES):
            u = np.array([cables(x)[0][i] for x in point])
            np.testing.assert_allclose(tr.speed[w],
                                       K_W * np.sum(u * v, axis=1),
                                       rtol=1e-12, atol=1e-9)
            np.testing.assert_allclose(tr.torque[w], -c * tr.speed[w],
                                       rtol=1e-12, atol=1e-12)
        assert np.all(run.v == V_S)
        rotors = sum(0.5 * J_W * tr.speed[w] ** 2 for w in WINCHES)
        e = (0.5 * p["m"] * np.sum(v * v, axis=1)
             + p["m"] * G * tr.q["hang:z"] + rotors)
        dissipated = np.trapezoid(sum(c * tr.speed[w] ** 2
                                      for w in WINCHES), tr.t)
        gaps.append(abs(e[0] - e[-1] - dissipated) / dissipated)
    assert gaps[0] < 5e-4  # 1.5e-2 without the rotors' ω̇ at q̈ = 0, 0.15
                           # without their inertia
    assert gaps[1] == pytest.approx(gaps[0] / 2, rel=0.1)  # first order


# --- what an event needs ------------------------------------------------------
def test_an_event_names_what_it_is_missing():
    m = armature.compile(pendulum, SWING)
    d = drive(["motor"], 1.0)
    with pytest.raises(TypeError, match="drive"):
        trace(m, Mission("x", [event({}, {"motor": "coast"}, 0.1)]), 1e3)
    with pytest.raises(KeyError, match="motor"):
        trace(m, Mission("x", [event({}, {}, 0.1)]), 1e3, drive=d)
    with pytest.raises(ValueError, match="flux brake"):
        trace(m, Mission("x", [event({}, {"motor": "flux_brake"}, 0.1)]),
              1e3, drive=d)
    with pytest.raises(ValueError, match="mode"):
        event({}, {"motor": "brake"}, 0.1)
    with pytest.raises(ValueError, match="self-locking"):
        trace(m, Mission("x", [event({}, {"motor": "short"}, 0.1)]), 1e3,
              drive=drive(["motor"], 1.0, gearboxes={
                  "motor": Gearbox(forward=0.5, backward=0.0)}))
    first = hold({"pivot": 0.2}, 0.1)
    other = hold({"pivot": 0.2}, 0.1)
    with pytest.raises(ValueError, match="just before"):
        trace(m, Mission("x", [first, other, event(after(first, 0.5),
                                                   {"motor": "coast"},
                                                   0.1)]), 1e3, drive=d)
    with pytest.raises(ValueError, match="pivot"):
        trace(m, Mission("x", [first, event({"pivot": 0.5},
                                            {"motor": "coast"}, 0.1)]),
              1e3, drive=d)
    with pytest.raises(ValueError, match="fraction"):
        after(first, 1.5)


def test_an_event_under_a_seam_names_what_it_is_missing():
    p = hung_at(HOME, 2.0)
    m, across = on_winches(p)
    stop = event(after(across, 0.5), {w: "short" for w in WINCHES}, 0.1)
    d = drive(WINCHES, R_W_PHI, kt=KT_W)
    gear = {w: N_W for w in WINCHES}
    with pytest.raises(ValueError, match="transmission="):
        trace(m, Mission("x", [across, stop], actuation=least_tensions),
              1e3, drive=d, gear=gear)
    with pytest.raises(KeyError, match="gear"):
        trace(m, Mission("x", [across, stop], actuation=least_tensions,
                         transmission=winches), 1e3, drive=d)
    with pytest.raises(ValueError, match="actuation="):
        Mission("x", [across], transmission=winches)
    with pytest.raises(KeyError, match="hang:rx"):
        trace(m, Mission("x", [across, stop], actuation=least_tensions,
                         transmission=lambda state, *, t, p: {
                             w: ({"hang:rx": 1.0}, 0.0, 0.0)
                             for w in WINCHES}), 1e3, drive=d, gear=gear)
    floating = armature.compile(unhung, p)
    with pytest.raises(ValueError, match="open chain"):
        trace(floating, Mission("x", [event(floating.at(), {
            w: "short" for w in WINCHES}, 0.1)], actuation=least_tensions,
            transmission=winches), 1e3, drive=d, gear=gear)
