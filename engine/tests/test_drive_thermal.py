"""The winding's single-node thermal RC, against its closed forms.

Answer: C·dT/dt = P − (T − T_a)/R_th rises as T_a + P·R_th·(1 − e^(−t/τ))
with τ = R_th·C; a square wave, P for t_on of every period, settles to a
peak of T_a + P·R_th·(1 − a)/(1 − a·b) with a = e^(−t_on/τ) and
b = e^(−t_off/τ); and with R_φ(T) = R₀(1 + α(T − T₀)) under a constant
current the steady rise solves ΔT = R_th·R₀·(1 + α(T − T₀))·i².
"""

import math

import numpy as np
import pytest

from armature.drive import (Kt, Motor, Resistance, Thermal, heat, repeat,
                            rms_torque)

RC = Thermal(r_th=2.0, c_th=50.0, t_max=150.0, t_ambient=25.0)  # τ = 100 s


def test_a_constant_loss_rises_to_p_r_th_with_time_constant_r_th_c():
    """10 W through 2 K/W: 25 + 20·(1 − 1/e) = 37.6424 °C at one time
    constant, 25 + 20·(1 − e⁻⁵) = 44.8652 °C at five."""
    t = np.linspace(0.0, 500.0, 501)
    out = heat(t, RC, power=10.0)
    assert out.temperature[0] == 25.0
    assert out.temperature[100] == pytest.approx(37.6424, abs=1e-4)
    assert out.temperature[-1] == pytest.approx(44.8652, abs=1e-4)
    assert out.peak == pytest.approx(44.8652, abs=1e-4)
    settled = heat([0.0, 1e5], RC, power=10.0)
    assert settled.temperature[-1] == pytest.approx(25.0 + 10.0 * 2.0)


def test_a_square_wave_duty_reaches_its_periodic_steady_state():
    """10 W for 30 s of every 100 s: a = e^−0.3, b = e^−0.7, so the peak
    settles at 25 + 20·(1 − e^−0.3)/(1 − e^−1) = 33.2004 °C."""
    out = repeat([0.0, 30.0], RC, period=100.0, session=1e5,
                 power=[10.0, 0.0])
    assert out.periodic
    assert out.peak == pytest.approx(33.2004, abs=0.1)
    assert out.cycles < 20


def test_a_slow_winding_is_not_called_periodic_while_still_warming():
    """τ = 3600 s, 10 W for 60 s of every 360 s: a cycle warms it by under
    0.1 K while its peak is still 0.95 K short of the periodic
    25 + 20·(1 − e^(−1/60))/(1 − e^(−1/10)) = 28.4739 °C."""
    slow = Thermal(r_th=2.0, c_th=1800.0, t_max=150.0, t_ambient=25.0)
    out = repeat([0.0, 60.0], slow, period=360.0, session=1e6,
                 power=[10.0, 0.0])
    assert out.periodic
    assert out.peak == pytest.approx(28.4739, abs=0.1)


def test_a_session_that_ends_first_stops_the_duty_there():
    """One period is one 30 s pulse from ambient: 25 + 20·(1 − e^−0.3)
    = 30.1836 °C, not yet periodic."""
    out = repeat([0.0, 30.0], RC, period=100.0, session=100.0,
                 power=[10.0, 0.0])
    assert not out.periodic
    assert out.cycles == 1
    assert out.peak == pytest.approx(30.1836, abs=1e-4)
    cut = repeat([0.0, 30.0], RC, period=100.0, session=10.0,
                 power=[10.0, 0.0])
    assert cut.peak == pytest.approx(25 + 20 * (1 - math.exp(-0.1)))


def test_resistance_rising_with_temperature_raises_the_steady_rise():
    """R₀ = 0.1 Ω at 20 °C, α = 0.004/K, 10 A d-q, 2 K/W into 20 °C air:
    ΔT = 2·0.1·(1 + 0.004·ΔT)·100, so ΔT = 20/0.92 = 21.7391 K, against
    20 K with α = 0."""
    air = Thermal(r_th=2.0, c_th=50.0, t_max=150.0, t_ambient=20.0)

    def winding(alpha):
        return Motor(kt=Kt(0.1, per="A_rms", side="motor"), wiring="wye",
                     r=Resistance(0.1, between="phase", at=20.0, alpha=alpha))

    hot = heat([0.0, 1e4], air, current=[10.0, 10.0], motor=winding(0.004))
    assert hot.temperature[-1] == pytest.approx(20 + 20 / 0.92)
    cold = heat([0.0, 1e4], air, current=[10.0, 10.0], motor=winding(0.0))
    assert cold.temperature[-1] == pytest.approx(40.0)


def test_current_needs_the_motor_whose_winding_it_heats():
    with pytest.raises(TypeError, match="motor"):
        heat([0.0, 1.0], RC, current=[1.0, 1.0])


def test_rms_torque_is_over_the_whole_period():
    """2 N·m for 30 s of every 100 s is 2·√0.3 = 1.0954 N·m RMS."""
    assert rms_torque([0.0, 30.0], [2.0, 0.0], period=100.0) == \
        pytest.approx(2 * math.sqrt(0.3))
    assert rms_torque([0.0, 30.0], [-2.0, 0.0]) == pytest.approx(2.0)
    with pytest.raises(ValueError, match="period"):
        rms_torque([0.0, 30.0], [2.0, 0.0], period=10.0)
