"""Fixture 5: a mass on a spring, and on a cable.

Answer: √(k/m)/2π = 7.1176 Hz at k = 1000 N/m and m = 0.5 kg; a slack cable
gives K = 0. Trap: the stiffness lives only in MuJoCo's passive force, so a
linearisation of the bias force alone reads both as 0 N/m and 0 Hz.
"""

import math

import numpy as np
import pytest

import armature
from armature import body, cable, joint

PARAMS = {"m": 0.5, "k": 1000.0, "drop": 1.0, "rest": 0.99}
SPRING = {"m": 0.5, "k": 1000.0}  # the spring reads neither drop nor rest
F_TRUE = math.sqrt(1000.0 / 0.5) / (2 * math.pi)


def _bob(p):
    r = 0.01  # a 10 mm sphere's inertia, so the body is a rigid body
    i = 0.4 * p["m"] * r ** 2
    return body("bob", mass=p["m"], com=(0, 0, 0),
                inertia=np.diag([i, i, i]))


def _slide(**spring):
    return joint("z", "slide", parent="world", child="bob", axis=(0, 0, 1),
                 point=(0, 0, 0), range=(-0.1, 0.1), **spring)


def on_spring(p):
    return [_bob(p), _slide(stiffness=p["k"])]


def on_cable(p):
    # Anchored `drop` above the bob, with EA chosen so EA / rest = k.
    return [_bob(p), _slide(),
            cable("hang", start=("world", (0, 0, p["drop"])),
                  end=("bob", (0, 0, 0)), ea=p["k"] * p["rest"],
                  rest_length=p["rest"])]


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
