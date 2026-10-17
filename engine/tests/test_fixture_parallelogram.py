"""Fixture 4: a balanced parallelogram arm, CineWave-shaped.

The upper arm turns about O on J1. The forearm hangs from its far end P, and
its direction is set by a crank on J2, also at O, through a coupler that stays
parallel to the upper arm: O, P, Q and C are a parallelogram, and the forearm
turns with the crank. Every hinge is about z, and gravity is −y.

Answer: each body's COM moves with u(θ1), the upper arm's direction, or u(φ),
the crank's, so the total moment of mass is B1 u(θ1) + B2 u(φ), with

    B1 = m1 r1 + m4 r4 + m2 a,    B2 = m3 r3 + m4 c + m2 r2.

Counterweights that zero both give zero gravity torque at every posture; a
wrong one leaves τ1 = g B1 cos θ1 / N1 and τ2 = g B2 cos φ / N2, and a
stiffness K11 = −g B1 sin θ1. M is closed-form too: J11 = 2I + m1 r1² + m4 r4²
+ m2 a² + N1² J_m, coupled to J2 by (m2 a r2 + m4 r4 c) cos(θ1 − φ).

Traps: a wrong counterweight must fail the balance check, and at the
singularity, where the four links lie on one line, the solve must report its
lost rank rather than a number. Near it the motors' torques stay bounded while
the coupler pin's load, M_P / (c sin(φ − θ1)), does not: searched over the
working range it fails at the corner nearest θ1 = φ, and checked at home it
passes. The stop's regeneration, ½J11ω0² less the copper loss, lifts a bus
whose source cannot sink to √(V₀² + 2E/C), past its drivers' trip, where a
source that sinks holds it at V₀.
"""

import math
from dataclasses import replace

import numpy as np
import pytest

import armature
from armature import Coordinates, Margin, Space, joint, search
from armature.drive import (AGREE, CONFIRM_RATE, Mission, capacitance_needed,
                            charge, event, margins, trace)
from golden import parallelogram
from golden.answers import (PEAK_BUS_VOLTAGE, STOP_CAPACITANCE,
                            STOP_RETURNED, STOP_TURN, stop_returned)

# The description is the golden project's, its counterweights' COMs solved
# from the balance condition in its params.py.
PARAMS = parallelogram.PARAMS
arm = parallelogram.mechanism
WRONG = {**PARAMS, "m1": 2.5}  # the upper counterweight 0.5 kg light
SEED = 20261011


def postures(n, seed=SEED):
    """Upper-arm angle and crank coordinate, kept 0.3 rad or more from the
    singularity θ1 = φ."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        j1 = rng.uniform(-1.0, 1.0)
        out.append((j1, j1 + rng.uniform(-1.2, 1.2)))
    return out


def gravity_torque(p, j1, j2):
    """τ1, τ2 per motor, from the moment of mass B1 u(θ1) + B2 u(φ)."""
    b1 = p["m1"] * p["r1"] + p["m4"] * p["r4"] + p["m2"] * p["a"]
    b2 = p["m3"] * p["r3"] + p["m4"] * p["c"] + p["m2"] * p["r2"]
    phi = j2 + math.pi / 2
    return np.array([p["g"] * b1 * math.cos(j1) / p["N1"],
                     p["g"] * b2 * math.cos(phi) / p["N2"]])


def mass_matrix(p, j1, j2):
    """M over (J1, J2), rotors included. With φ held, the forearm translates
    and the coupler turns with θ1 about C; with θ1 held, the crank and the
    forearm turn with φ and the coupler translates. The forearm's COM at
    a u(θ1) + r2 u(φ) and the coupler's at c u(φ) + r4 u(θ1) couple the two
    by (m2 a r2 + m4 r4 c) cos(θ1 − φ)."""
    phi = j2 + math.pi / 2
    j11 = (2 * p["I"] + p["m1"] * p["r1"] ** 2 + p["m4"] * p["r4"] ** 2
           + p["m2"] * p["a"] ** 2 + p["N1"] ** 2 * p["J_m"])
    j22 = (2 * p["I"] + p["m3"] * p["r3"] ** 2 + p["m4"] * p["c"] ** 2
           + p["m2"] * p["r2"] ** 2 + p["N2"] ** 2 * p["J_m"])
    j12 = coupling(p) * math.cos(j1 - phi)
    return np.array([[j11, j12], [j12, j22]])


def coupling(p):
    """The coefficient of cos(θ1 − φ) in M12."""
    return p["m2"] * p["a"] * p["r2"] + p["m4"] * p["r4"] * p["c"]


def gravity_stiffness(p, j1, j2):
    """∂²V/∂q² over (J1, J2), V = g (B1 sin θ1 + B2 sin φ) the potential
    `gravity_torque` is the gradient of."""
    b1 = p["m1"] * p["r1"] + p["m4"] * p["r4"] + p["m2"] * p["a"]
    b2 = p["m3"] * p["r3"] + p["m4"] * p["c"] + p["m2"] * p["r2"]
    phi = j2 + math.pi / 2
    return np.diag([-p["g"] * b1 * math.sin(j1), -p["g"] * b2 * math.sin(phi)])


def assert_balanced(m, n=12):
    for j1, j2 in postures(n):
        inv = m.at(q={"J1": j1, "J2": j2}).inverse()
        assert abs(inv.torque["J1_motor"]) < 1e-10
        assert abs(inv.torque["J2_motor"]) < 1e-10


@pytest.fixture(scope="module")
def m():
    return armature.compile(arm, PARAMS)


def test_the_motors_drive_and_the_parallelogram_follows(m):
    assert m.independent == ("J1", "J2")
    assert m.dependent == ("elbow", "pin")


@pytest.mark.parametrize("j1, j2", postures(6))
def test_the_parallelogram_closes(m, j1, j2):
    s = m.at(q={"J1": j1, "J2": j2})
    # The forearm turns with the crank; the coupler stays with the upper arm.
    assert s.q["elbow"] == pytest.approx(j2 - j1, abs=1e-11)
    assert s.q["pin"] == pytest.approx(j1 - j2, abs=1e-11)
    assert s.pose("Q_fore").residual <= 1e-10


@pytest.mark.parametrize("short", [0.05, 0.013, 1e-3, 1e-6, 0.0])
def test_the_parallelogram_holds_its_branch_up_to_the_singularity(m, short):
    # At the singularity the antiparallelogram branch crosses this one, and
    # just short of it the two are close. The closure pins the dependent
    # angles only to (gap)/σ_min there, with σ_min shrinking as `short`, so
    # the tolerance scales with it: well inside the other branch, which lies
    # some 2 × short away.
    j1 = 0.3
    j2 = j1 - math.pi / 2 + short
    s = m.at(q={"J1": j1, "J2": j2})
    assert s.pose("Q_fore").residual <= 1e-10
    assert s.q["elbow"] == pytest.approx(j2 - j1, abs=1e-12 + 1e-2 * short)
    assert s.q["pin"] == pytest.approx(j1 - j2, abs=1e-12 + 1e-2 * short)


def test_a_closure_outside_a_joint_range_raises():
    def stiff_elbow(p):
        return [joint("elbow", "hinge", parent="upper", child="fore",
                      axis=(0, 0, 1), point=(p["a"], 0, 0), range=(-1.0, 1.0))
                if getattr(e, "name", None) == "elbow" else e for e in arm(p)]
    m = armature.compile(stiff_elbow, PARAMS)
    # elbow = J2 − J1 = 1.2, past its range of ±1.0, with the parallelogram
    # clear of its singularity at J2 − J1 = ±π/2.
    with pytest.raises(ValueError, match="joint 'elbow': closing the loops"):
        m.at(q={"J1": 0.0, "J2": 1.2})


def test_gravity_torque_is_zero_over_the_envelope(m):
    assert_balanced(m)


def test_a_wrong_counterweight_fails_the_balance():
    wrong = armature.compile(arm, WRONG)
    with pytest.raises(AssertionError):
        assert_balanced(wrong)


@pytest.mark.parametrize("j1, j2", postures(6))
def test_a_wrong_counterweight_reads_its_closed_form(j1, j2):
    inv = armature.compile(arm, WRONG).at(q={"J1": j1, "J2": j2}).inverse()
    got = [inv.torque["J1_motor"], inv.torque["J2_motor"]]
    assert got == pytest.approx(gravity_torque(WRONG, j1, j2), rel=1e-9,
                                abs=1e-12)


def test_the_singularity_reports_its_rank_loss(m):
    regular = m.at(q={"J1": 0.3, "J2": 0.0}).inverse()
    assert (regular.rank, regular.unknowns) == (4, 4)
    assert math.isfinite(regular.condition)
    # θ1 = φ: O, C, P and Q on one line, and the loop's rows lose a rank.
    s = m.at(q={"J1": 0.3, "J2": 0.3 - math.pi / 2})
    for loads in (None, {"tip": (0.0, -20.0, 0.0)}):
        inv = s.inverse(loads=loads)
        assert (inv.rank, inv.unknowns) == (3, 4)
        assert math.isinf(inv.condition)
        # The force along the line is anyone's: NaN, not a least-norm number.
        assert np.all(np.isnan(inv.constraint["parallelogram"]))
        # The flip into the antiparallelogram is free here, and the weights
        # push along it, balanced or not: these motors cannot hold it.
        assert inv.residual > 1.0
    # A milliradian away the solve has its rank, and its loop force is the
    # number the singularity would otherwise have printed.
    near = m.at(q={"J1": 0.3, "J2": 0.3 - math.pi / 2 + 1e-3}).inverse()
    assert near.rank == 4
    assert near.condition > 1e5
    assert np.linalg.norm(near.constraint["parallelogram"]) > 1e4


def test_released_with_the_motors_off_it_stays(m):
    """Balanced means neutral: let go anywhere, the arm stays there."""
    settled = m.at(q={"J1": 0.5, "J2": 0.1}).settle()
    assert settled.stable
    assert settled.residual <= 1e-6
    for name in m.coordinates:
        assert abs(settled.moved[name]) < 1e-6


def test_released_with_a_wrong_counterweight_it_falls():
    settled = armature.compile(arm, WRONG).at(q={"J1": 0.5, "J2": 0.1}).settle()
    assert abs(settled.moved["J1"]) > 0.1


# --- linearise ----------------------------------------------------------------
@pytest.mark.parametrize("j1, j2", postures(6))
def test_balanced_it_has_no_gravity_stiffness_anywhere(m, j1, j2):
    """K = ∂²V/∂q² = 0 at every posture, and M is the closed form, the
    rotors' N²J_m included."""
    lin = m.at(q={"J1": j1, "J2": j2}).linearise()
    assert lin.dofs == ("J1", "J2")
    assert lin.stiffness == pytest.approx(np.zeros((2, 2)), abs=1e-6)
    assert lin.mass == pytest.approx(mass_matrix(PARAMS, j1, j2), rel=1e-10)


@pytest.mark.parametrize("j1, j2", postures(6))
def test_a_wrong_counterweight_stiffens_j1_by_its_closed_form(j1, j2):
    """With the upper counterweight light, B1 ≠ 0 and K11 = −g B1 sin θ1;
    B2 is untouched, so J2 stays neutral."""
    lin = armature.compile(arm, WRONG).at(q={"J1": j1, "J2": j2}).linearise()
    expected = gravity_stiffness(WRONG, j1, j2)
    assert abs(expected[0, 0]) > 0.01 or abs(j1) < 0.02
    assert lin.stiffness == pytest.approx(expected, abs=1e-6)


# --- the singularity: the coupler pin's load, searched ------------------------
# The tip carries a 2 kg camera. Near θ1 = φ the motors' torques stay bounded,
# τ = JᵀF, but the coupler's pin load grows as 1/sin(φ − θ1). The working
# range is J1 within ±0.3 and the crank's angle φ within 1.0 to 2.0 rad, so
# J2 = φ − π/2; the pin is rated for PIN_RATING.
PAYLOAD = 20.0  # N, down, at the tip
CAMERA = {"tip": (0.0, -PAYLOAD, 0.0)}
PIN_RATING = 60.0  # N
WORKING = {"J1": (-0.3, 0.3), "J2": (1.0 - math.pi / 2, 2.0 - math.pi / 2)}


def unit(angle):
    return np.array([math.cos(angle), math.sin(angle), 0.0])


def pin_load(p, j1, j2, payload=PAYLOAD):
    """The force the crank exerts on the coupler at C, static, worked from
    the two links' balances. The coupler's moment about C fixes the part of
    its force at Q across the coupler, f⊥ = (r4/a) m4 g cos θ1; the
    forearm's moment about P, M_P = (b F − r2 m2 g) cos φ from the camera and
    its own weight, is all the coupler's at Q, lever c u(φ), so the part
    along the coupler is f = (M_P/c − f⊥ cos(θ1 − φ)) / sin(θ1 − φ): the
    M_P / (c sin(φ − θ1)) that grows without bound at the singularity. The
    pin then carries f u(θ1) + f⊥ n(θ1) back, less the coupler's weight."""
    phi, g = j2 + math.pi / 2, p["g"]
    across = p["r4"] / p["a"] * p["m4"] * g * math.cos(j1)
    moment = (p["b"] * payload - p["r2"] * p["m2"] * g) * math.cos(phi)
    along = (moment / p["c"] - across * math.cos(j1 - phi)) / math.sin(
        j1 - phi)
    at_q = along * unit(j1) + across * unit(j1 + math.pi / 2)
    return -at_q + np.array([0.0, p["m4"] * g, 0.0])


def payload_torque(p, j1, j2, payload=PAYLOAD):
    """τ = JᵀF / N per motor, by virtual work: the tip a u(θ1) − b u(φ)
    lifted against the camera's weight."""
    phi = j2 + math.pi / 2
    return np.array([payload * p["a"] * math.cos(j1) / p["N1"],
                     -payload * p["b"] * math.cos(phi) / p["N2"]])


def pin_slack(state):
    """The pin's rating less its load under the camera (N)."""
    return PIN_RATING - float(np.linalg.norm(
        state.wrench("coupler", loads=CAMERA).force))


def pin_margin(within):
    return Margin("coupler pin", lambda p: pin_slack(p.state), "N",
                  over=Space(state=Coordinates(arm, PARAMS, within=within)))


def test_the_pin_load_is_its_closed_form(m):
    for j1, j2 in postures(6):
        s = m.at(q={"J1": j1, "J2": j2})
        assert s.wrench("coupler", loads=CAMERA).force == pytest.approx(
            pin_load(PARAMS, j1, j2), rel=1e-9, abs=1e-9)


def test_the_searched_pin_margin_is_worst_nearest_the_singularity(m):
    """Over the working range the closed form is worst at the corner nearest
    θ1 = φ, J1 = 0.3 and φ = 1.0, where φ − θ1 = 0.7 rad; a dense grid of it
    says so. There the motors' torques are the virtual work's, the balanced
    arm's gravity_torque plus JᵀF, inside aF/N1 and bF/N2, and the crank's
    moment about O, N2 τ2 = c u(φ) × F_C plus its own weight's, ties the
    wrench to them."""
    (lo1, hi1), (lo2, hi2) = WORKING["J1"], WORKING["J2"]
    grid = max((np.linalg.norm(pin_load(PARAMS, a, b)), a, b)
               for a in np.linspace(lo1, hi1, 61)
               for b in np.linspace(lo2, hi2, 61))
    assert (grid[1], grid[2]) == (hi1, lo2)
    corner = {"J1": hi1, "J2": lo2}
    answer = PIN_RATING - np.linalg.norm(pin_load(PARAMS, hi1, lo2))
    assert answer == pytest.approx(-28.02, abs=0.01)

    worst = search(pin_margin(WORKING))
    print(worst)
    assert not worst.passes
    assert worst.value == pytest.approx(answer, rel=1e-9)
    assert worst.at["state"] == pytest.approx(corner, abs=1e-12)

    s = m.at(q=corner)
    inv = s.inverse(loads=CAMERA)
    torque = np.array([inv.torque["J1_motor"], inv.torque["J2_motor"]])
    expected = (gravity_torque(PARAMS, hi1, lo2)
                + payload_torque(PARAMS, hi1, lo2))
    assert torque == pytest.approx(expected, rel=1e-9, abs=1e-12)
    assert abs(torque[0]) <= PARAMS["a"] * PAYLOAD / PARAMS["N1"]
    assert abs(torque[1]) <= PARAMS["b"] * PAYLOAD / PARAMS["N2"]
    phi = lo2 + math.pi / 2
    f_c = s.wrench("coupler", loads=CAMERA).force
    crank = (PARAMS["c"] * np.cross(unit(phi), f_c)[2]
             + PARAMS["r3"] * PARAMS["m3"] * PARAMS["g"] * math.cos(phi))
    assert PARAMS["N2"] * torque[1] == pytest.approx(crank, rel=1e-9)


def test_the_pin_margin_checked_at_home_passes(m):
    """The trap: at home, φ − θ1 = π/2, the forearm hangs plumb, the camera
    has no moment about P, and the pin carries its share of the coupler's
    weight alone, (1 − r4/a) m4 g, Q the rest."""
    home = m.at(q={"J1": 0.0, "J2": 0.0})
    share = (1 - PARAMS["r4"] / PARAMS["a"]) * PARAMS["m4"] * PARAMS["g"]
    assert pin_slack(home) == pytest.approx(PIN_RATING - share, rel=1e-12)
    assert pin_slack(home) > 0
    at_home = search(pin_margin({"J1": (0.0, 0.0), "J2": (0.0, 0.0)}))
    assert at_home.passes


# --- the stop: regeneration into a source that cannot sink -------------------
# The golden project's stop brakes J1 from its top speed at constant
# deceleration with φ held, on its drive: a PSU behind a diode, which cannot
# sink, so what the stop returns lands on the drivers' capacitance alone.
# The answers are worked from the closed-form M, never from the engine.
STOPPING = parallelogram.missions
DRIVE = parallelogram.params.DRIVE
RATE = STOPPING.SLEW_SPEED / STOPPING.STOP_TIME  # J1's deceleration, rad/s²
PHI = STOPPING.HELD + math.pi / 2
V0, C_BUS, TRIP = DRIVE["v_bus"], DRIVE["c_bus"], DRIVE["v_max"]


def stopped(t):
    """J1's angle and rate at `t` into the stop."""
    t = np.asarray(t, dtype=float)
    return (STOPPING.START + STOPPING.SLEW_SPEED * t - 0.5 * RATE * t * t,
            STOPPING.SLEW_SPEED - RATE * t)


def stop_torques(t):
    """Each motor's torque along the stop: J1's J11 θ̈1 / N1, constant; J2's
    holding φ against the coupling, (M12 θ̈1 + ∂M12/∂θ1 θ̇1²) / N2, which
    does no work, φ̇ = 0."""
    theta, omega = stopped(t)
    k = coupling(PARAMS)
    j11 = mass_matrix(PARAMS, 0.0, 0.0)[0, 0]
    tau1 = np.full_like(theta, -j11 * RATE / PARAMS["N1"])
    tau2 = k * (np.cos(theta - PHI) * -RATE
                - np.sin(theta - PHI) * omega ** 2) / PARAMS["N2"]
    return tau1, tau2


def driven(**changes):
    """The golden drive with each of its drivers changed by `changes`."""
    d = parallelogram.drive.drive()
    return replace(d, drivers={a: replace(x, **changes)
                               for a, x in d.drivers.items()})


def sinking():
    """The golden drive on a source that sinks, as a pack does."""
    d = parallelogram.drive.drive()
    return replace(d, bus=replace(d.bus, source=replace(d.bus.source,
                                                        sinks=True)))


def named(ms):
    return {margin.name: margin for margin in ms}


@pytest.fixture(scope="module")
def stop(m):
    return trace(m, STOPPING.STOP, CONFIRM_RATE)


def test_the_stops_torques_are_the_closed_form(stop):
    tau1, tau2 = stop_torques(stop.t)
    assert stop.torque["J1_motor"] == pytest.approx(tau1, rel=1e-9)
    assert stop.torque["J2_motor"] == pytest.approx(tau2, rel=1e-7,
                                                    abs=1e-12)
    assert np.max(np.abs(tau2)) > 0.01  # J2 holds against the coupling
    theta, omega = stopped(stop.t)
    assert stop.q["J1"] == pytest.approx(theta, abs=1e-12)
    assert stop.speed["J1_motor"] == pytest.approx(PARAMS["N1"] * omega,
                                                   abs=1e-9)
    assert stop.q["J2"] == pytest.approx(np.full_like(theta, STOPPING.HELD))


def test_the_stop_lifts_the_bus_by_the_energy_relation(stop):
    """With its drivers' trip lifted out of the way, the stop's return lands
    on the capacitor alone: V = √(V₀² + 2E/C) at every sample up to where
    J1's return falls to the copper loss, and its peak is the answer's.
    That peak is past the drivers' 44 V."""
    charged = charge(stop, driven(max_voltage=200.0))
    rising = stop.t <= STOP_TURN
    expected = [math.sqrt(V0 ** 2 + 2 * float(stop_returned(t)) / C_BUS)
                for t in stop.t[rising]]
    sampled = np.interp(stop.t[rising], charged.t, charged.v)
    assert sampled == pytest.approx(expected, rel=1e-6)
    # charge's substep is refined until halving it moves the peak by AGREE
    assert charged.peak == pytest.approx(PEAK_BUS_VOLTAGE.value, abs=AGREE)
    assert charged.minimum == V0
    assert charged.peak > TRIP


def test_the_stop_trips_a_source_that_cannot_sink_and_not_one_that_can(
        m, stop):
    """The trap: the same stop on the golden PSU drives the bus to its
    drivers' 44 V and trips them, so the peak-V margin fails; on a source
    that sinks, as a pack does, the bus never leaves V₀, and it passes by
    the 20 V between them."""
    tripped = charge(stop, parallelogram.drive.drive())
    assert set(tripped.tripped) == set(parallelogram.drive.MOTORS)
    held = charge(stop, sinking())
    assert not held.tripped
    assert held.peak == pytest.approx(V0, abs=1e-12)

    ms = named(margins({"PSU": parallelogram.drive.drive(),
                        "sinking": sinking()}, STOPPING.MISSIONS, model=m))
    worst = search(ms["bus: peak V"])
    print(worst)
    cases = {c.choices["drive"]: c.value for c in worst.cases}
    assert worst.at["drive"] == "PSU" and not worst.passes
    assert cases["PSU"] <= 0
    assert cases["sinking"] == pytest.approx(TRIP - V0, abs=1e-9)
    assert worst.truth.agrees


def test_the_stop_forward_simulated_holds_phi_and_lifts_the_bus(m):
    """The same stop as an event: each motor commanded the closed form's
    torque, open loop, from the stop's first state. J1 brakes at RATE, φ
    stays put, so the closed-form coupling is the engine's, and the bus the
    event steps reads √(V₀² + 2E/C), to first order in the step."""
    start = m.at(q={"J1": STOPPING.START, "J2": STOPPING.HELD},
                 qd={"J1": STOPPING.SLEW_SPEED, "J2": 0.0})

    def simulated(hold=1.0):
        """The stop as an event, J2's torque `hold` times the closed
        form's."""
        modes = {"J1_motor": lambda s: float(stop_torques([s])[0][0]),
                 "J2_motor": lambda s: hold * float(stop_torques([s])[1][0])}
        t = trace(m, Mission("stop, simulated", [event(
            start, modes, STOPPING.STOP_TIME, timestep=2e-4)]),
            CONFIRM_RATE, drive=driven(max_voltage=200.0))
        return t.events[0]

    stopped_here = simulated()
    drift, gaps = [], []
    for run in (stopped_here.run, stopped_here.half):
        tr = run.trace
        assert tr.qd["J1"] == pytest.approx(stopped(tr.t)[1], abs=1e-5)
        drift.append(np.max(np.abs(tr.q["J2"] - STOPPING.HELD)))
        rising = tr.t <= STOP_TURN
        expected = np.array([
            math.sqrt(V0 ** 2 + 2 * float(stop_returned(s)) / C_BUS)
            for s in tr.t[rising][::10]])
        gaps.append(np.max(np.abs(run.v[rising][::10] - expected)))
    print(drift, gaps)
    assert drift[0] < 2e-5 and gaps[0] < 0.05
    assert drift[1] == pytest.approx(drift[0] / 2, rel=0.1)  # first order
    assert gaps[1] == pytest.approx(gaps[0] / 2, rel=0.1)
    # J2 holding against m2 a r2 alone, the coupler's m4 r4 c left out, lets
    # φ go 3 mrad, two hundred times as far
    alone = PARAMS["m2"] * PARAMS["a"] * PARAMS["r2"] / coupling(PARAMS)
    let_go = np.max(np.abs(simulated(alone).run.trace.q["J2"]))
    assert let_go > 100 * drift[0]


def test_the_capacitance_the_stop_needs_is_the_closed_form(m):
    """Nothing sinks below the trip on the PSU, so C = 2E/(V_trip² − V₀²)
    exactly, E the most the stop returns; on the sinking source the bus
    never rises, and needs nothing."""
    found = capacitance_needed(margins(
        {"PSU": parallelogram.drive.drive(), "sinking": sinking()},
        STOPPING.MISSIONS, model=m))
    needed = {n.drive: n for n in found}
    assert needed["PSU"].exact and needed["PSU"].trip == TRIP
    assert needed["PSU"].capacitance == pytest.approx(STOP_CAPACITANCE,
                                                      rel=1e-6)
    assert STOP_CAPACITANCE == pytest.approx(
        2 * STOP_RETURNED / (TRIP ** 2 - V0 ** 2), rel=1e-12)
    assert needed["PSU"].capacitance > C_BUS
    assert needed["sinking"].capacitance == 0.0
