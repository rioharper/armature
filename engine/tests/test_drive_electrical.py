"""The drive's electrical model, against closed forms and published numbers.

Answer: each expected value is a datasheet number, a hand-worked literal, or
a closed form that does not depend on the conventions the module chooses:
no-load speed is where the line-to-line peak back-EMF meets the bus, and
three-phase copper loss is 1.5·R_LL·I_rms² whatever the wiring.
"""

import math

import numpy as np
import pytest

from armature.drive import (Current, Curve, Driver, DriveError, Gearbox, Ke, Kt,
                            Motor, Resistance, check, electrical, envelope,
                            kt_from_kv)

SQ3 = math.sqrt(3)


def motor(**overrides):
    """A wye motor whose constants read 0.1 in Lee's power-invariant d-q
    convention: Kt 0.1·√3 N·m/A_rms and Ke 0.1 V_rms·s/rad line to line
    both give 0.1, with R_φ = 0.5 Ω and a 20 A d-q (20/√3 A_rms) limit."""
    kwargs = dict(kt=Kt(0.1 * SQ3, per="A_rms", side="motor"),
                  ke=Ke(0.1, per="V_rms/(rad/s)", between="line",
                        side="motor"),
                  r=Resistance(0.5, between="phase"), wiring="wye",
                  i_peak=Current(20 / SQ3, per="A_rms"))
    kwargs.update(overrides)
    return Motor(**kwargs)


# --- bases --------------------------------------------------------------------
@pytest.mark.parametrize("make, keyword", [
    (lambda: Kt(1.22, side="output"), "per"),
    (lambda: Kt(1.22, per="A_rms"), "side"),
    (lambda: Ke(9.6, between="line", side="motor"), "per"),
    (lambda: Ke(9.6, per="V_rms/krpm", side="motor"), "between"),
    (lambda: Ke(9.6, per="V_rms/krpm", between="line"), "side"),
    (lambda: Resistance(0.55), "between"),
    (lambda: Current(40.0), "per"),
    (lambda: Motor(kt=Kt(1.22, per="A_rms", side="output"),
                   r=Resistance(0.55, between="line")), "wiring"),
])
def test_omitting_a_basis_keyword_raises_naming_it(make, keyword):
    with pytest.raises(TypeError, match=f"'{keyword}'"):
        make()


@pytest.mark.parametrize("make, word", [
    (lambda: Kt(1.22, per="A", side="output"), "A_rms"),
    (lambda: Kt(1.22, per="A_rms", side="rotor"), "output"),
    (lambda: Ke(9.6, per="V/krpm", between="line", side="motor"), "V_rms"),
    (lambda: Resistance(0.55, between="terminal"), "line"),
    (lambda: motor(wiring="star"), "delta"),
    (lambda: motor(kt=1.22), "Kt"),
    (lambda: motor(kt=None, ke=None), "kt"),
])
def test_a_basis_outside_its_vocabulary_raises_listing_it(make, word):
    with pytest.raises((TypeError, ValueError), match=word):
        make()


# --- Kt against Ke --------------------------------------------------------------
IBEX_N = 7.75


def ibex():
    """Ibex's RobStride 02, as its spec states it: Ke 9.6 V_rms/krpm line to
    line at the rotor, Kt 1.22 N·m/A_rms at the output of a 7.75:1 gear."""
    return Motor(kt=Kt(1.22, per="A_rms", side="output"),
                 ke=Ke(9.6, per="V_rms/krpm", between="line", side="motor"),
                 r=Resistance(0.55, between="line"), wiring="wye")


def test_ibex_kt_and_ke_agree_under_the_sinusoidal_convention():
    # 1.22 / 7.75 / √3 = 0.090886 N·m/A and 9.6 / (1000 · 2π/60) = 0.091673
    # V·s/rad: 0.86 % apart.
    checked = check(ibex(), IBEX_N)
    assert checked.kt == pytest.approx(0.0908856, rel=1e-5)
    assert checked.ke == pytest.approx(0.0916732, rel=1e-5)
    assert checked.ratio == pytest.approx(0.99141, abs=1e-4)


def test_ibex_at_the_wrong_gear_ratio_fails_the_cross_check():
    with pytest.raises(DriveError, match="Kt"):
        check(ibex(), 9.0)


def test_kt_from_kv_gives_each_published_relation():
    # mjbots mj5208, Kv 304 rpm/V: 8.27/Kv sinusoidal, 9.55/Kv as Kt = Ke.
    sine = kt_from_kv(304, convention="sinusoidal")
    trap = kt_from_kv(304, convention="trapezoidal")
    assert sine.value == pytest.approx(8.27 / 304, rel=1e-3)
    assert trap.value == pytest.approx(9.55 / 304, rel=1e-3)
    assert (sine.per, sine.side) == (trap.per, trap.side) == ("A_peak",
                                                              "motor")
    with pytest.raises(TypeError, match="convention"):
        kt_from_kv(304)
    with pytest.raises(ValueError, match="sinusoidal"):
        kt_from_kv(304, convention="dc")


def test_plumb_mj5208_at_9_55_over_kv_fails_against_its_datasheet_ke():
    """Plumb took Kt = 9.55/Kv; the datasheet's 8.27/Kv is Kv read as rpm
    per volt of line-to-line peak back-EMF, so Ke is 1000/Kv V_peak/krpm."""
    ke = Ke(1000 / 304, per="V_peak/krpm", between="line", side="motor")
    datasheet = Motor(kt=kt_from_kv(304, convention="sinusoidal"), ke=ke,
                      r=Resistance(0.1, between="line"), wiring="wye")
    assert check(datasheet, 1.0).ratio == pytest.approx(1.0, abs=1e-3)
    plumb = Motor(kt=kt_from_kv(304, convention="trapezoidal"), ke=ke,
                  r=Resistance(0.1, between="line"), wiring="wye")
    with pytest.raises(DriveError, match="2 %"):
        check(plumb, 1.0)


# --- the electrical model -------------------------------------------------------
GEAR = Gearbox(forward=0.8, backward=0.6)
DRIVER = Driver(efficiency=0.9, i_peak=Current(40, per="A_peak"),
                max_voltage=60.0, undervoltage=20.0)


def test_gearbox_backward_defaults_to_forward_and_may_be_zero():
    assert Gearbox(forward=0.9).backward == 0.9
    assert Gearbox(forward=0.9, backward=0.0).backward == 0.0
    with pytest.raises(ValueError, match="forward"):
        Gearbox(forward=0.0)


def test_motoring_draws_tau_omega_over_eta_and_back_driving_returns_eta_b():
    """At N = 10, 2 N·m at ±3 rad/s is 6 W at the output, and R_φ = 0.2 Ω.
    Motoring, the rotor gives 2/(10·0.8) = 0.25 N·m, 2.5 A d-q and 1.25 W of
    copper: it draws 6/0.8 + 1.25 = 8.75 W, at 0.5 + 0.1·30 = 3.5 V.
    Back-driven, the rotor sees 2·0.6/10 = 0.12 N·m, 1.2 A and 0.288 W, and
    returns 0.6·6 − 0.288 = 3.312 W. The driver divides what is drawn by
    0.9 and multiplies what is returned by it."""
    m = motor(r=Resistance(0.2, between="phase"))
    out = electrical([2.0, 2.0], [3.0, -3.0], 10, m, gearbox=GEAR,
                     driver=DRIVER)
    assert np.allclose(out.tau, [0.25, 0.12])
    assert np.allclose(out.omega, [30.0, -30.0])
    assert np.allclose(out.current, [2.5, 1.2])
    assert np.allclose(out.copper, [1.25, 0.288])
    assert np.allclose(out.voltage, [3.5, -2.76])
    assert np.allclose(out.power, [6 / 0.8 + 1.25, -0.6 * 6 + 0.288])
    assert np.allclose(out.bus, [8.75 / 0.9, -3.312 * 0.9])


def test_the_rotors_own_torque_is_added_after_the_gearbox():
    """The rotor's inertia turns on the motor's side of the gear, so no
    efficiency touches it, and the branch is read from the load alone. At
    N = 10, 2 N·m of load at +3 rad/s motors: 2/(10·0.8) = 0.25 N·m, plus
    0.4 N·m of rotor, is 0.65. At −3 rad/s it is back-driven, though the
    rotor's −0.5 N·m makes the total τ·ω positive: 2·0.6/10 = 0.12 N·m,
    less 0.5, is −0.38."""
    m = motor(r=Resistance(0.2, between="phase"))
    out = electrical([2.0, 2.0], [3.0, -3.0], 10, m, gearbox=GEAR,
                     rotor=[0.4, -0.5])
    assert np.allclose(out.tau, [0.65, -0.38])
    assert np.allclose(out.current, [6.5, -3.8])


def test_direct_drive_without_a_driver_has_no_bus_power():
    out = electrical(1.0, 10.0, 1, motor())
    assert out.tau == pytest.approx(1.0)
    assert out.power == pytest.approx(1.0 * 10.0 + 0.5 * 10.0 ** 2)
    assert out.bus is None


@pytest.mark.parametrize("wiring", ["wye", "delta"])
def test_copper_loss_is_one_and_a_half_r_line_i_rms_squared_either_wiring(
        wiring):
    """Measured at the terminals, a three-phase winding loses 1.5·R_LL·I²
    at I_rms line current whether it is wound wye or delta: 0.3 Ω at 10 A
    is 45 W."""
    m = Motor(kt=Kt(0.05, per="A_rms", side="motor"),
              r=Resistance(0.3, between="line"), wiring=wiring)
    assert electrical(0.5, 0.0, 1, m).copper == pytest.approx(45.0)


def test_per_phase_resistance_in_delta_is_the_winding():
    """A delta's winding carries I/√3: 3·R_φ·(10/√3)² = 0.3 · 100 = 30 W."""
    m = Motor(kt=Kt(0.05, per="A_rms", side="motor"),
              r=Resistance(0.3, between="phase"), wiring="delta")
    assert electrical(0.5, 0.0, 1, m).copper == pytest.approx(30.0)


def test_resistance_rises_with_copper_coefficient():
    """Copper's α at 20 °C is 1/254.5 per K, so 100 K hotter is ×1.3929."""
    m = motor(r=Resistance(0.2, between="phase", at=20.0))
    hot = electrical(0.25, 0.0, 1, m, temperature=120.0)
    assert hot.resistance == pytest.approx(0.2 * (1 + 100 / 254.5))
    assert hot.copper == pytest.approx(0.2 * 1.39293 * 2.5 ** 2, rel=1e-5)
    stated = motor(r=Resistance(0.2, between="phase", at=20.0, alpha=0.004))
    assert electrical(0.25, 0.0, 1, stated,
                      temperature=70.0).resistance == pytest.approx(0.24)


# --- the torque-speed envelope --------------------------------------------------
@pytest.mark.parametrize("wiring", ["wye", "delta"])
def test_no_load_speed_is_where_line_peak_back_emf_meets_the_bus(wiring):
    """Space-vector modulation puts at most V_bus line to line, peak, so
    no-load speed is V_bus over Ke line-to-line peak, whatever the wiring:
    48 / (0.1·√2) = 339.41 rad/s. That is k_mod·V/Ke in d-q: √(1/2)·48/0.1
    wound wye, √(3/2)·48/(0.1·√3) wound delta."""
    env = envelope(motor(wiring=wiring), 1, 48.0)
    assert env.no_load_speed == pytest.approx(48 / (0.1 * math.sqrt(2)))
    assert env.no_load_speed == pytest.approx(339.411, abs=1e-3)
    assert env.torque(env.no_load_speed) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("wiring", ["wye", "delta"])
def test_stall_is_the_current_limit(wiring):
    """Kt 0.1·√3 N·m/A_rms at 20/√3 A_rms is 2 N·m; through 10:1 at 0.8 it
    is 16 N·m, with no-load at a tenth of the rotor's speed."""
    env = envelope(motor(wiring=wiring), 10, 48.0, gearbox=GEAR)
    assert env.stall_torque == pytest.approx(16.0)
    assert env.torque(0.0) == pytest.approx(16.0)
    assert env.no_load_speed == pytest.approx(33.9411, abs=1e-4)


def test_stall_is_the_lower_of_the_motor_and_driver_limits():
    """A 10 A_peak driver is below the motor's 20/√3 A_rms (16.3 A_peak):
    0.1·√3 · 10/√2 = 1.2247 N·m."""
    driver = Driver(efficiency=0.9, i_peak=Current(10, per="A_peak"),
                    max_voltage=60.0, undervoltage=20.0)
    env = envelope(motor(), 1, 48.0, driver=driver)
    assert env.stall_torque == pytest.approx(0.1 * SQ3 * 10 / math.sqrt(2))


# --- a published torque-speed curve ---------------------------------------------
# At 24·√2 V the wye's d-q limit is 24 V. Stall is 0.1 · 20 = 2 N·m; the
# current limit meets the voltage limit where 24 − 0.5·20 = 0.1·ω, at 140
# rad/s; at 190 rad/s (24 − 19)/0.5 = 10 A gives 1 N·m; no-load is 240 rad/s.
SPEED = (0.0, 70.0, 140.0, 190.0, 240.0)
TORQUE = (2.0, 2.0, 2.0, 1.0, 0.0)
VOLTS = 24 * math.sqrt(2)


def test_a_curve_made_from_the_constants_passes():
    published = Curve(speed=SPEED, torque=TORQUE, voltage=VOLTS, side="motor",
                      agree=0.05)
    assert check(motor(curve=published), 1).curve == pytest.approx(0.0,
                                                                   abs=1e-9)


def test_an_output_side_curve_passes_through_the_gearbox():
    published = Curve(speed=np.array(SPEED) / 10,
                      torque=np.array(TORQUE) * 10 * 0.8, voltage=VOLTS,
                      side="output", agree=0.05)
    assert check(motor(curve=published), 10, gearbox=GEAR).curve == \
        pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("scale", [1.1, 0.9])
def test_the_curve_perturbed_ten_percent_fails(scale):
    published = Curve(speed=SPEED, torque=np.array(TORQUE) * scale,
                      voltage=VOLTS, side="motor", agree=0.05)
    m = motor(curve=published)
    with pytest.raises(DriveError, match="curve"):
        check(m, 1)
    with pytest.raises(DriveError, match="curve"):
        electrical(1.0, 1.0, 1, m)


def test_a_curve_names_its_side_and_tolerance():
    with pytest.raises(TypeError, match="'side'"):
        Curve(speed=SPEED, torque=TORQUE, voltage=VOLTS, agree=0.05)
    with pytest.raises(TypeError, match="'agree'"):
        Curve(speed=SPEED, torque=TORQUE, voltage=VOLTS, side="motor")


def test_an_envelope_without_a_current_limit_raises_naming_it():
    with pytest.raises(DriveError, match="i_peak"):
        envelope(motor(i_peak=None), 1, 48.0)
