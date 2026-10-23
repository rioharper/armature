"""
drive_checks.py — self-tests for drive.py and missions.py.

The drive margins are the engine's, and `run_all.py` searches them; what is
checked here is that this project's data reaches them as meant, each held to
an answer worked here from the datasheet's numbers rather than read from the
engine, and that an UNCHECKED margin fails through `run_all.py`'s own
discovery unless DRIVE_EXEMPT argues it. Each check's teeth, a mutant it
must catch, are in test_drive_mutants.py.
"""

import contextlib
import io
import math
import types
from dataclasses import replace

import numpy as np

import armature
from armature import Budget, search
from armature.drive import (SEARCH_RATE, DriveError, Mission, check,
                            electrical, event, kt_from_kv, margins, trace)

from params import DRIVE, PARAMS, QD_LIMITS
from mechanism import BANDS, mechanism, truth
from missions import (PRESSING, REST, SHORTED, STOP_STEP, STOP_TIME,
                      stopped)
from drive import DRIVE_BANDS, DRIVE_MARGINS, MOTORS, drive, motor
from run_all import HERE, UNCHECKED_EXEMPT, checks_for, searched

DQ_PER_PEAK = math.sqrt(1.5)  # a wye's d-q amperes per peak line ampere
MARGINS = {margin.name: margin for margin in DRIVE_MARGINS}
# The bus's peak, against the lowest trip on it: each driver's v_max, since
# the source states no overvoltage trip of its own.
PEAK_V = MARGINS["bus: peak V"]
# Power is linear between a trace's samples, as the engine's bus reads it;
# the energy relation below integrates it at these points of each interval.
MIDPOINTS = (np.arange(20) + 0.5) / 20


def by_hand(k):
    """Motor `k`'s (Kt [N m/A], Ke [V s/rad], R_phase [ohm]) from
    params.DRIVE, in the power-invariant d-q convention on its own shaft:
    Kt = (sqrt(3)/2)/Kv per peak line ampere, Kv in rad/s per line-to-line
    peak volt, the sinusoidal reading; Ke in V_rms per rad/s line to line,
    which in a wye is the d-q magnitude; R line to line, two windings in
    series."""
    kt = (math.sqrt(3) / 2) / DRIVE[f"kv{k}"] / DQ_PER_PEAK
    return kt, DRIVE[f"ke{k}"], DRIVE[f"r{k}"] / 2


def bus_power(tau, omega, k):
    """What direct-drive motor `k` draws from the bus (W, negative where it
    returns power) at output torque `tau` and speed `omega`, its winding at
    25 C: the winding's V i, over the driver's efficiency when drawing and
    times it when returning."""
    kt, ke, r = by_hand(k)
    current = np.asarray(tau) / kt
    power = (r * current + ke * np.asarray(omega)) * current
    eta = DRIVE["eta_driver"]
    return np.where(power >= 0, power / eta, power * eta)


def _gear(a):
    return {x.name: float(x.gear) for x in truth().description.actuators}[a]


def test_each_motors_constants_agree_on_their_bases(tol=1e-9):
    """The engine reads each constant on the basis drive.py names, and holds
    Kt to Ke within 2 %; this holds both to the hand reading."""
    d = drive(DRIVE)
    for a, k in MOTORS.items():
        kt, ke, _ = by_hand(k)
        c = check(d.motors[a], _gear(a))
        assert abs(c.kt - kt) < tol * kt and abs(c.ke - ke) < tol * ke, (
            f"{a}: the engine reads Kt {c.kt:.6g}, Ke {c.ke:.6g}; by hand "
            f"{kt:.6g}, {ke:.6g}")
        print(f"  [PASS] {a}: Kt {kt:.4f} N m/A and Ke {ke:.4f} V s/rad in "
              f"d-q, {100 * (c.ratio - 1):+.2f} % apart")


def test_the_trapezoidal_reading_of_kv_is_refused():
    """9.55/Kv is the DC motor's Kt = Ke, block commutation's; on these
    sinusoidal windings it reads Kt 15 % above the datasheet's Ke, and the
    data must be refused, not used."""
    for a, k in MOTORS.items():
        wrong = replace(motor(DRIVE, k), kt=kt_from_kv(
            DRIVE[f"kv{k}"], per="(rad/s)/V", convention="trapezoidal"))
        try:
            check(wrong, _gear(a))
        except DriveError:
            continue
        raise AssertionError(f"{a}: Kt by 9.55/Kv passed against its Ke")
    print("  [PASS] Kt read by the trapezoidal 9.55/Kv is refused against "
          "each motor's Ke")


def test_the_torque_limits_are_within_each_windings_rating():
    """tau1 and tau2, the description's derated torque limits, within the
    continuous torque each winding's thermal data supports: Kt times the
    current whose copper loss R_phase(t_max) i^2 holds the winding at t_max,
    (t_max - t_ambient) / R_th. A motor with no thermal data has no rating
    here, and its winding margin reads UNCHECKED."""
    d = drive(DRIVE)
    for actuator in truth().description.actuators:
        a, limit = actuator.name, float(actuator.torque_limit)
        th = d.motors[a].thermal
        if th is None:
            print(f"  [PASS] {a}: no thermal data, so no rating to hold "
                  f"{limit:g} N m to; its winding margin reads UNCHECKED")
            continue
        kt, _, r = by_hand(MOTORS[a])
        hot = r * (1 + d.motors[a].r.alpha * (th.t_max - d.motors[a].r.at))
        rating = kt * math.sqrt((th.t_max - th.t_ambient) / (th.r_th * hot))
        assert limit <= rating, (
            f"{a}: its torque limit {limit:g} N m is above the "
            f"{rating:.3g} N m its winding holds continuously")
        print(f"  [PASS] {a}: limit {limit:g} N m, {100 * limit / rating:.0f}"
              f" % of the {rating:.3g} N m its winding holds")


def test_the_torque_limits_are_within_each_drivers_peak():
    """tau1 and tau2 within what each driver's peak current makes on its
    motor's shaft, Kt times the peak line current in d-q: a limit the driver
    cannot reach is one the truth model's settle would hold and the machine
    would not."""
    for actuator in truth().description.actuators:
        a, limit = actuator.name, float(actuator.torque_limit)
        kt, _, _ = by_hand(MOTORS[a])
        peak = kt * DRIVE["i_peak"] * DQ_PER_PEAK
        assert limit <= peak, (f"{a}: its torque limit {limit:g} N m is above "
                               f"the {peak:.3g} N m its driver's peak makes")
        print(f"  [PASS] {a}: limit {limit:g} N m, {100 * limit / peak:.0f} % "
              f"of the {peak:.3g} N m its driver's peak current makes")


def test_truth_bus_power_follows_the_flow_of_power(tol=1e-9):
    """Every sample of the press, through the engine's electrical model,
    against `bus_power`. Both directions must occur, or the check has read
    one of them only."""
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


def bus_peak_by_energy(margin, tol=0.05):
    """Hold `margin`, a bus peak-V margin, to V = sqrt(V_s^2 + 2E/C) at its
    searched worst, which must sit at the least capacitance on the highest
    source. E is the most the capacitance holds above V_s: the motors' and
    the hotel load's net return, emptied back to V_s whenever they draw,
    since the PSU sources what holds V_s and sinks nothing. Returns the
    (peak, E, C, V_s) it read."""
    worst = searched(margin)
    at = worst.at
    c, v_s = at.get("c_bus"), at.get("v_bus")
    assert c == DRIVE_BANDS["c_bus"].lo and v_s == DRIVE_BANDS["v_bus"].hi, (
        f"the bus peaks at C = {c}, V_s = {v_s}; regeneration lifts the "
        f"least capacitance on the highest source furthest")
    m = armature.compile(mechanism, {**PARAMS, **{k: at[k] for k in BANDS
                                                  if k in at}})
    mission = (PRESSING if at["mission"] == PRESSING.name
               else stopped(at["end"], at["fraction"]))
    t = trace(m, mission, SEARCH_RATE, capacitance=c, v_source=v_s,
              drive=drive({**DRIVE, "c_bus": c, "v_bus": v_s}))
    drawn = DRIVE["hotel"] + sum(bus_power(*t.output(a)[:2], k)
                                 for a, k in MOTORS.items())
    stored = most = 0.0
    for t0, t1, p0, p1 in zip(t.t[:-1], t.t[1:], drawn[:-1], drawn[1:]):
        for f in MIDPOINTS:
            stored = max(0.0, stored - (p0 + (p1 - p0) * f) * (t1 - t0)
                         / len(MIDPOINTS))
            most = max(most, stored)
    peak = math.sqrt(v_s ** 2 + 2 * most / c)
    found = DRIVE["v_max"] - worst.value
    assert abs(peak - found) < tol, (
        f"the bus peaks at {found:.4f} V; {most:.4g} J on {c * 1e3:g} mF from "
        f"{v_s:g} V reaches {peak:.4f} V")
    return found, most, c, v_s


def test_truth_the_bus_peak_is_the_energy_relation(tol=0.05):
    found, energy, c, v_s = bus_peak_by_energy(PEAK_V, tol)
    print(f"  [PASS] the bus peak {found:.3f} V is {energy:.3g} J on "
          f"{c * 1e3:g} mF from {v_s:g} V, within {tol} V")


def test_truth_an_event_is_confirmed_at_half_its_timestep():
    """Each drive margin's check is a resolution check, every event re-run
    at half its timestep. An event alone, the arm shorted at full speed, is
    sampled at its own timestep and the shoulder driver's RMS current
    integrated over those samples, so a check that did not halve the step
    would read the search's value back exactly."""
    at_speed = Mission("stopped at speed", [event(
        truth().at(q=REST, qd=QD_LIMITS), SHORTED, STOP_TIME,
        timestep=STOP_STEP)])
    found = {m.name: m for m in margins(
        drive, [at_speed], model=truth(), params=DRIVE,
        budget=Budget(global_points=4, polish_starts=0))}
    worst = search(found["shoulder_motor: driver RMS current"])
    assert worst.check.agrees, f"the event has not converged: {worst}"
    assert worst.check.value != worst.value, (
        "the check read the search's own value back: it never re-ran the "
        "event at half its timestep")
    print(f"  [PASS] the shorted stop's check, at half its timestep, moves "
          f"its RMS current by {abs(worst.check.value - worst.value):.2g} "
          f"A_rms, within {worst.check.agree:g}")


def _discovered(exempt=None, params=None):
    """run_all's checks for a module declaring the press's drive margins on
    `params`, and DRIVE_EXEMPT = `exempt` where it is given."""
    module = types.ModuleType("unchecked_drive")
    module.__file__ = str(HERE / "unchecked_drive.py")  # has no checks file
    module.DRIVE_MARGINS = margins(drive, [PRESSING], model=truth(),
                                   params=params or DRIVE)
    if exempt is not None:
        setattr(module, UNCHECKED_EXEMPT, exempt)
    return checks_for(module)


def _fails(checks, match):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            for check in checks:
                check()
        except AssertionError as failure:
            assert match in str(failure), f"failed otherwise: {failure}"
            return out.getvalue()
    raise AssertionError(f"passed, where it must fail with {match!r}")


def test_an_unchecked_winding_fails_through_discovery_unless_exempt():
    """Drop both windings' thermal data and run_all's discovery fails the
    press's winding margins as UNCHECKED, saying FAILS; exempt them in
    DRIVE_EXEMPT and the same discovery passes, printing each exemption as
    the data it lacks and its reason, and never FAILS, which beside
    [EXEMPT] reads as a contradiction."""
    bare = {k: v for k, v in DRIVE.items() if not k.startswith(("rth", "cth"))}
    _fails(_discovered(params=bare), "UNCHECKED, FAILS; missing ")
    why = "no datasheet thermal data yet; the bench run measures it"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        for check in _discovered({f"{a}: winding": why for a in MOTORS},
                                 bare):
            check()
    for a in MOTORS:
        assert (f"[EXEMPT] {a}: winding: UNCHECKED (missing "
                in out.getvalue()), out.getvalue()
    assert out.getvalue().count(f") because {why}") == len(MOTORS)
    assert "FAILS" not in out.getvalue(), out.getvalue()
    print("  [PASS] an UNCHECKED winding fails through run_all's discovery, "
          "and passes, printed with what it lacks and its reason, once "
          "DRIVE_EXEMPT argues it")


def test_drive_exempt_refuses_what_it_cannot_argue():
    """An exemption naming no margin, one for a margin that has its data,
    and one with no reason each fail the module's DRIVE_EXEMPT check."""
    bare = {k: v for k, v in DRIVE.items() if k not in ("rth1", "cth1")}
    for exempt, params, match in (
            ({"no such margin": "a reason"}, DRIVE, "no margins here"),
            ({"bus: peak V": "a reason"}, DRIVE, "have their data"),
            ({"shoulder_motor: winding": "  "}, bare, "no reason")):
        _fails(_discovered(exempt, params)[-1:], match)
    print(f"  [PASS] {UNCHECKED_EXEMPT} refuses an unknown name, a checked "
          f"margin and an empty reason")
