"""Fixture 5: a mass on a spring, and on a cable.

Answer: √(k/m)/2π = 7.1176 Hz at k = 1000 N/m and m = 0.5 kg; a slack cable
gives K = 0; the force to hold the bob is m·g less the cable's k·stretch;
at rest the spring's slide carries m·g and the cable's carries nothing.
Trap: the stiffness lives only in MuJoCo's passive force, so a
linearisation of the bias force alone reads both as 0 N/m and 0 Hz, and is
shown doing so.
"""

import mujoco
import numpy as np
import pytest

import armature
from golden import spring_cable
from golden.answers import CABLE_FREQUENCY, IMU_PEAK, PULL

# The description is the golden project's, the mass on a cable. The spring is
# its control, built from the same bob and slide.
PARAMS = spring_cable.PARAMS
on_cable = spring_cable.mechanism
SPRING = {k: PARAMS[k] for k in ("m", "k")}  # it reads neither drop nor rest
F_TRUE = CABLE_FREQUENCY.value
G = 9.81  # the engine's default gravity [m/s^2]
WEIGHT = PARAMS["m"] * G
REST = PARAMS["drop"] - PARAMS["rest"] - WEIGHT / PARAMS["k"]  # the hung bob


def stretch(z):
    """The cable's stretch with the bob at z: its span less its rest
    length, zero once slack."""
    return max(PARAMS["drop"] - z - PARAMS["rest"], 0.0)


def on_spring(p):
    return [spring_cable.bob(p), spring_cable.slide(stiffness=p["k"])]


def test_frequency_is_the_closed_form():
    assert F_TRUE == pytest.approx(7.1176, abs=1e-4)


@pytest.mark.parametrize("z", [-0.05, 0.0, 0.03])
def test_spring_reads_its_stiffness(z):
    lin = armature.compile(on_spring, SPRING).at(q={"z": z}).linearise()
    assert lin.stiffness == pytest.approx(np.array([[1000.0]]), rel=1e-6)
    assert lin.mass == pytest.approx(np.array([[0.5]]), rel=1e-12)
    assert lin.frequencies == pytest.approx([F_TRUE], rel=1e-6)


@pytest.mark.parametrize("z", [-0.05, -0.005])
def test_taut_cable_reads_its_stiffness(z):
    # The cable spans 1.0 − z against a 0.99 rest length: taut for z < 0.01.
    lin = armature.compile(on_cable, PARAMS).at(q={"z": z}).linearise()
    assert lin.stiffness == pytest.approx(np.array([[1000.0]]), rel=1e-6)
    assert lin.frequencies == pytest.approx([F_TRUE], rel=1e-6)


def test_slack_cable_reads_zero():
    lin = armature.compile(on_cable, PARAMS).at(q={"z": 0.05}).linearise()
    assert lin.stiffness[0, 0] == 0.0
    assert lin.frequencies == pytest.approx([0.0])


def test_record_carries_method_and_step():
    lin = armature.compile(on_spring, SPRING).at().linearise(eps=1e-7)
    assert lin.dofs == ("z",)
    assert "mjd_inverseFD" in lin.method
    assert lin.eps == 1e-7
    assert "mjd_inverseFD" in str(lin) and "1e-07" in str(lin)
    with pytest.raises(ValueError):
        lin.stiffness[0, 0] = 0.0


# --- the trap, shown failing ---------------------------------------------------
def bias_stiffness(m, z, h=1e-6):
    """The derivation's K: a central difference of MuJoCo's bias force alone,
    gravity and Coriolis, with the passive force left out."""
    data = mujoco.MjData(m.model)

    def bias(at):
        data.qpos[0] = at
        mujoco.mj_forward(m.model, data)
        return data.qfrc_bias[0]
    return (bias(z + h) - bias(z - h)) / (2 * h)


@pytest.mark.parametrize("model, params", [(on_spring, SPRING),
                                           (on_cable, PARAMS)],
                         ids=["spring", "cable"])
def test_a_bias_only_linearisation_reads_zero(model, params):
    m = armature.compile(model, params)
    wrong = bias_stiffness(m, -0.02)
    right = m.at(q={"z": -0.02}).linearise().stiffness[0, 0]
    assert abs(wrong) < 1e-6  # gravity's force does not vary with z
    assert right == pytest.approx(1000.0, rel=1e-6)
    assert abs(wrong - right) > 0.99 * right


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="the trap: the bias force alone carries no "
                          "stiffness")
def test_the_bias_only_trap_reads_the_cables_stiffness():
    """The check a derivation writes for its bias-only K: that it reads the
    cable's 1000 N/m at a taut posture. It must fail."""
    m = armature.compile(on_cable, PARAMS)
    assert bias_stiffness(m, -0.02) == pytest.approx(PARAMS["k"], rel=1e-3)


# --- inverse and the wrench ----------------------------------------------------
@pytest.mark.parametrize("z", [-0.05, -0.02, REST, 0.0, 0.05])
def test_inverse_needs_the_weight_less_the_cables_pull(z):
    """No actuator holds the bob, so the force it needs is left as the
    residual: m·g − k·stretch, signed; m·g once the cable is slack."""
    inv = armature.compile(on_cable, PARAMS).at(q={"z": z}).inverse()
    need = WEIGHT - PARAMS["k"] * stretch(z)
    assert inv.generalised["z"] == pytest.approx(need, abs=1e-9)
    assert inv.residual == pytest.approx(abs(need), abs=1e-9)
    assert inv.torque == {}


def test_at_rest_the_spring_carries_the_weight_in_its_slide():
    """The spring is the slide's own: at its rest, sagged m·g/k, the slide
    carries the bob's weight, k·sag, up its axis and nothing across it."""
    sag = WEIGHT / PARAMS["k"]
    s = armature.compile(on_spring, SPRING).at(q={"z": -sag})
    assert s.inverse().residual < 1e-9
    w = s.wrench("bob")
    assert w.joint == "z"
    assert w.force == pytest.approx([0.0, 0.0, WEIGHT], abs=1e-9)
    assert w.force[2] == pytest.approx(PARAMS["k"] * sag, rel=1e-12)
    assert w.torque == pytest.approx(np.zeros(3), abs=1e-12)


def test_at_rest_the_cable_carries_the_weight_and_the_slide_nothing():
    """The cable is an applied force, as the platform's are: at its rest the
    slide carries nothing, and the cable's tension, k·stretch, is m·g."""
    s = armature.compile(on_cable, PARAMS).at(q={"z": REST})
    assert PARAMS["k"] * stretch(REST) == pytest.approx(WEIGHT, rel=1e-12)
    assert s.wrench("bob").force == pytest.approx(np.zeros(3), abs=1e-9)
    out = s.settle()
    assert out.stable and abs(out.moved["z"]) < 1e-9
    assert out.tension["hang"] == pytest.approx(WEIGHT, rel=1e-9)


# --- an accelerometer on the bob (#151) ----------------------------------------
RANGE = 1.5 * G  # the accelerometer's ±1.5 g full scale [m/s^2]


def test_the_pull_stays_inside_the_sag_so_the_cable_never_slackens():
    """4 mm against a 4.905 mm sag: at the top of the swing the cable still
    stretches, so the bob swings on the elastic cable throughout."""
    assert PULL < WEIGHT / PARAMS["k"]
    assert stretch(REST + PULL) > 0.0


@pytest.mark.parametrize("z", [REST - PULL, REST, REST + PULL],
                         ids=["bottom", "rest", "top"])
def test_the_linearised_swing_read_as_specific_force_is_the_imu_peak(z):
    """At the bottom of the swing the bob accelerates up at ω²·δ, and an
    accelerometer on it reads that plus g, the specific force. The bob's
    acceleration alone is the bait: outside the window, inside the range."""
    lin = armature.compile(on_cable, PARAMS).at(q={"z": z}).linearise()
    omega2 = (2 * np.pi * lin.frequencies[0]) ** 2
    acceleration = omega2 * PULL
    reading = acceleration + G
    assert IMU_PEAK.inside(reading)
    assert acceleration == pytest.approx(IMU_PEAK.bait, rel=1e-6)
    assert not IMU_PEAK.inside(acceleration)
    assert reading > RANGE > acceleration  # it saturates; the bait passes


def test_the_imu_peak_is_the_closed_form():
    """k/m = 2000 s⁻², so ω²·δ = 8.0 m/s² and the reading 17.81 m/s²."""
    assert IMU_PEAK.value == pytest.approx(17.81, abs=1e-9)
    assert IMU_PEAK.bait == pytest.approx(8.0, abs=1e-9)
    assert IMU_PEAK.unit == "m/s²"
