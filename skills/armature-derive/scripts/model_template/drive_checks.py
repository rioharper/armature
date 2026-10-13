"""
drive_checks.py — self-tests for drive.py and missions.py.

The drive margins are the engine's, and `run_all.py` searches them; what is
checked here is that this project's data reaches them as meant, each against
an answer worked here from the datasheet's numbers and not read from the
engine:

- each motor's Kt and Ke, on the bases the datasheet states them in;
- tau1 and tau2, the description's torque limits, against what each
  winding's thermal data supports;
- each sample's bus power, from the direction power flows (the closed form
  every drive margin rests on);
- the bus's peak, the energy relation V = sqrt(V_s^2 + 2E/C) at the worst
  case's capacitance and supply, the PSU behind its diode taking nothing
  back;
- an event's truth, which must have re-run it at half its timestep;
- a winding with no thermal data, which must read UNCHECKED and fail.
"""

import contextlib
import io
import math

import numpy as np

import armature
from armature import Budget, search
from armature.drive import (SEARCH_RATE, Mission, check, electrical, event,
                            margins, trace)

from params import BANDS, DRIVE, PARAMS
from mechanism import mechanism, truth
from missions import (MISSIONS, PRESSING, REST, SHORTED, SPACE, STOP_STEP,
                      STOP_TIME, stopped)
from drive import DRIVE_MARGINS, MOTORS, drive
from run_all import margin_check, searched

RPM = 2 * math.pi / 60  # rad/s per rpm
MARGINS = {margin.name: margin for margin in DRIVE_MARGINS}
# The bus's peak, against the lowest trip on it: each driver's v_max, since
# the supply states no overvoltage trip of its own.
PEAK_V = MARGINS["bus: peak V"]


def by_hand(k):
    """Motor `k`'s constants from params.DRIVE, in the power-invariant d-q
    convention on its own shaft, worked from each one's basis:

    - Kt from Kv by the sinusoidal convention, (sqrt(3)/2)(60/2pi)/Kv per
      A_peak of line current, and a wye's peak line ampere is sqrt(3/2) d-q
      amperes;
    - Ke in V_rms/krpm line to line, which in a wye is already the d-q
      magnitude, over 1000 rpm in rad/s;
    - R line to line, which in a wye is two windings in series.

    Returns (kt [N m/A], ke [V s/rad], R_phase [ohm])."""
    kt = (math.sqrt(3) / 2) / (DRIVE[f"kv{k}"] * RPM) / math.sqrt(1.5)
    ke = DRIVE[f"ke{k}"] / (1000 * RPM)
    return kt, ke, DRIVE[f"r{k}"] / 2


def bus_power(tau, omega, k):
    """What a direct-drive motor `k` draws from the bus (W, negative where
    it returns power) at output torque `tau` and speed `omega`, its winding
    at 25 C: the winding's V i, which its driver divides by its efficiency
    when the motor draws and multiplies by it when the motor returns."""
    kt, ke, r = by_hand(k)
    current = np.asarray(tau) / kt
    power = (r * current + ke * np.asarray(omega)) * current
    eta = DRIVE["eta_driver"]
    return np.where(power >= 0, power / eta, power * eta)


def test_each_motors_constants_agree_on_their_bases(tol=1e-9):
    """The engine reads each constant on the basis drive.py names, and holds
    Kt to Ke within 2 %; this holds both to the hand reading. A Kt taken by
    the trapezoidal convention, 9.55/Kv, is 15 % off its Ke, and the engine
    refuses the drive when drive.py builds its margins, naming the gap."""
    d = drive(DRIVE)
    gear = {a.name: float(a.gear) for a in truth().description.actuators}
    for a, k in MOTORS.items():
        kt, ke, _ = by_hand(k)
        c = check(d.motors[a], gear[a])
        assert abs(c.kt - kt) < tol * kt and abs(c.ke - ke) < tol * ke, (
            f"{a}: the engine reads Kt {c.kt:.6g}, Ke {c.ke:.6g}; by hand "
            f"{kt:.6g}, {ke:.6g}")
        print(f"  [PASS] {a}: Kt {kt:.4f} N m/A and Ke {ke:.4f} V s/rad in "
              f"d-q, {100 * (c.ratio - 1):+.2f} % apart")


def test_the_torque_limits_are_within_each_windings_rating():
    """tau1 and tau2 are the description's torque limits, derated. Each
    must sit within the continuous torque its winding's thermal data
    supports, Kt sqrt((t_max - t_ambient) / (R_th R_phase(t_max))), the
    copper loss that holds the winding at its limit. A motor with no
    thermal data has no rating here; its winding margin is UNCHECKED."""
    d = drive(DRIVE)
    for actuator in truth().description.actuators:
        a, limit = actuator.name, float(actuator.torque_limit)
        th, k = d.motors[a].thermal, MOTORS[actuator.name]
        if th is None:
            print(f"  [PASS] {a}: no thermal data, so no rating to hold "
                  f"{limit:g} N m to; its winding margin reads UNCHECKED")
            continue
        kt, _, r = by_hand(k)
        hot = r * (1 + d.motors[a].r.alpha * (th.t_max - d.motors[a].r.at))
        rating = kt * math.sqrt((th.t_max - th.t_ambient) / (th.r_th * hot))
        assert limit <= rating, (
            f"{a}: its torque limit {limit:g} N m is above the "
            f"{rating:.3g} N m its winding holds continuously")
        print(f"  [PASS] {a}: limit {limit:g} N m, {100 * limit / rating:.0f}"
              f" % of the {rating:.3g} N m its winding holds")


def test_truth_bus_power_follows_the_flow_of_power(tol=1e-9):
    """Every sample of the press, through the engine's electrical model,
    against `bus_power`: the driver's efficiency divides what the motor
    draws and multiplies what it returns. Applied the other way round, a
    regenerating arm returns more than its motors made. Both directions
    must occur, or the check has read one of them only."""
    t, d = trace(truth(), PRESSING, SEARCH_RATE), drive(DRIVE)
    flows = {"draws": 0, "returns": 0}
    for a, k in MOTORS.items():
        tau, omega, rotor = t.output(a)
        engine = electrical(tau, omega, t.gear[a], d.motors[a],
                            d.gearboxes.get(a), d.drivers[a], rotor=rotor).bus
        hand = bus_power(tau, omega, k)
        gap = float(np.max(np.abs(engine - hand)))
        assert gap < tol * float(np.max(np.abs(hand))), (
            f"{a}: the engine's bus power is {gap:.3g} W from the hand's")
        flows["draws"] += int(np.sum(hand > 0))
        flows["returns"] += int(np.sum(hand < 0))
    assert all(flows.values()), f"the press samples one direction only: {flows}"
    print(f"  [PASS] bus power by direction matches the hand model over "
          f"{flows['draws']} drawing and {flows['returns']} returning samples")


def test_truth_the_bus_peak_is_the_energy_relation(tol=0.05):
    """The bus's searched worst, at the least capacitance and the highest
    supply, against V = sqrt(V_s^2 + 2E/C): E is the most energy the
    capacitance holds above V_s, the motors' and the hotel load's net
    return accumulated from `bus_power`, emptied back to V_s whenever they
    draw, since the PSU sources what holds V_s and sinks nothing. A bus
    charged at a capacitance the band does not reach misses it."""
    worst = searched(PEAK_V)
    at = worst.at
    c, v_s = at.get("capacitance"), at.get("v_source")
    assert c == BANDS["c_bus"][0] and v_s == BANDS["v_bus"][1], (
        f"the bus peaks at C = {c}, V_s = {v_s}; regeneration lifts the "
        f"least capacitance on the highest supply furthest")
    m = armature.compile(mechanism, {**PARAMS, **{k: at[k] for k in BANDS
                                                  if k in PARAMS}})
    mission = (PRESSING if at["mission"] == PRESSING.name
               else stopped(at["end"], at["fraction"]))
    t = trace(m, mission, SEARCH_RATE, drive=drive(DRIVE), capacitance=c,
              v_source=v_s)
    drawn = DRIVE["hotel"] + sum(bus_power(*t.output(a)[:2], k)
                                 for a, k in MOTORS.items())
    stored = most = 0.0
    for t0, t1, p0, p1 in zip(t.t[:-1], t.t[1:], drawn[:-1], drawn[1:]):
        for f in np.linspace(0.0, 1.0, 21)[1:]:  # linear between samples
            stored = max(0.0, stored - (p0 + (p1 - p0) * (f - 0.025))
                         * (t1 - t0) / 20)
            most = max(most, stored)
    peak = math.sqrt(v_s ** 2 + 2 * most / c)
    found = DRIVE["v_max"] - worst.value
    assert abs(peak - found) < tol, (
        f"the bus peaks at {found:.4f} V; {most:.4g} J on {c * 1e3:g} mF from "
        f"{v_s:g} V reaches {peak:.4f} V")
    print(f"  [PASS] the bus peak {found:.3f} V is {most:.3g} J on "
          f"{c * 1e3:g} mF from {v_s:g} V, within {tol} V")


def test_truth_an_event_is_confirmed_at_half_its_timestep():
    """Each drive margin's truth is a resolution check: its worst case
    re-run at 1 kHz, every event at half its timestep. An event alone, the
    arm shorted at speed, is sampled at its own timestep, and the shoulder
    driver's RMS current is integrated over those samples, so a truth that
    did not halve the step would read the search's value back exactly."""
    at_speed = Mission("stopped at speed", [event(
        truth().at(q=REST, qd={"shoulder": 3.0, "elbow": -4.0}), SHORTED,
        STOP_TIME, timestep=STOP_STEP)])
    found = {m.name: m for m in margins(
        drive, [at_speed], model=truth(), params=DRIVE,
        budget=Budget(global_points=4, polish_starts=0))}
    worst = search(found["shoulder_motor: driver RMS current"])
    assert worst.truth.agrees, f"the event has not converged: {worst}"
    assert worst.truth.value != worst.value, (
        "the truth read the search's own value back: it never re-ran the "
        "event at half its timestep")
    print(f"  [PASS] the shorted stop's truth, at half its timestep, moves "
          f"its RMS current by {abs(worst.truth.value - worst.value):.2g} "
          f"A_rms, within {worst.truth.agree:g}")


def test_a_winding_without_thermal_data_is_unchecked_and_fails():
    """The teeth of UNCHECKED: drop the shoulder's thermal data and its
    winding margin cannot be computed, so run_all's check fails it, and
    passes it only with a reason in DRIVE_EXEMPT."""
    bare = {k: v for k, v in DRIVE.items() if k not in ("rth1", "cth1")}
    winding = {m.name: m for m in margins(drive, MISSIONS, SPACE,
                                          params=bare)}["shoulder_motor: winding"]
    assert winding.unchecked, f"{winding.name} is checked without its data"
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            margin_check(winding)()
        except AssertionError:
            margin_check(winding, "a reason, argued")()
        else:
            raise AssertionError("an UNCHECKED margin passed with no exemption")
    print(f"  [PASS] with no thermal data, {winding.name!r} reads UNCHECKED "
          f"(missing {', '.join(winding.unchecked)}) and fails unless exempt")
