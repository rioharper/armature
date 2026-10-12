"""Validation fails before MjSpec is touched, naming the element at fault."""

import math

import mujoco
import numpy as np
import pytest

import armature
from armature import DescriptionError, actuator, body, cable, joint, lock, site

I = np.eye(3) * 1e-3


def arm(p, **change):
    """A two-body chain; `change` swaps in a faulty element by name."""
    elements = {
        "upper": body("upper", mass=p["m"], com=(0.5, 0, 0), inertia=I),
        "lower": body("lower", mass=p["m"], com=(1.5, 0, 0), inertia=I),
        "shoulder": joint("shoulder", "hinge", parent="world", child="upper",
                          axis=(0, 0, 1), point=(0, 0, 0), range=(-3, 3)),
        "elbow": joint("elbow", "hinge", parent="upper", child="lower",
                       axis=(0, 0, 1), point=(1, 0, 0), range=(-3, 3)),
        "tip": site("tip", body="lower", pos=(2, 0, 0)),
    }
    elements.update(change)
    return list(elements.values())


@pytest.fixture
def mjspec_untouched(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("MjSpec was called before validation finished")
    monkeypatch.setattr(mujoco, "MjSpec", refuse)


def _fails(mechanism, *names, params=None):
    with pytest.raises(DescriptionError) as err:
        armature.compile(mechanism, params or {"m": 1.0})
    for name in names:
        assert name in str(err.value)
    return err.value


def test_the_reference_arm_compiles():
    m = armature.compile(arm, {"m": 1.0})
    assert m.coordinates == ("shoulder", "elbow")


def test_duplicate_name(mjspec_untouched):
    err = _fails(lambda p: arm(p) + [site("elbow", body="upper", pos=(1, 0, 0))],
                 "site 'elbow'", "joint 'elbow'")
    assert "already used" in str(err)


def test_unreachable_body(mjspec_untouched):
    floating = body("loose", mass=1.0, com=(3, 0, 0), inertia=I)
    _fails(lambda p: arm(p) + [floating], "body 'loose'")


def test_body_hung_from_a_cycle_is_unreachable(mjspec_untouched):
    a = body("a", mass=1.0, com=(0, 1, 0), inertia=I)
    b = body("b", mass=1.0, com=(0, 2, 0), inertia=I)
    ab = joint("ab", "slide", parent="a", child="b", axis=(1, 0, 0),
               point=(0, 2, 0), range=(-1, 1))
    ba = joint("ba", "slide", parent="b", child="a", axis=(1, 0, 0),
               point=(0, 1, 0), range=(-1, 1))
    err = _fails(lambda p: arm(p) + [a, b, ab, ba], "body 'a'", "body 'b'")
    assert "unreachable" in str(err)


def test_non_unit_axis(mjspec_untouched):
    bad = joint("elbow", "hinge", parent="upper", child="lower",
                axis=(0, 0, 2), point=(1, 0, 0), range=(-3, 3))
    err = _fails(lambda p: arm(p, elbow=bad), "joint 'elbow'")
    assert "unit" in str(err)


def test_unit_axis_written_in_floats_passes():
    tilted = joint("elbow", "hinge", parent="upper", child="lower",
                   axis=(0, math.sqrt(0.5), math.sqrt(0.5)), point=(1, 0, 0),
                   range=(-3, 3))
    armature.compile(lambda p: arm(p, elbow=tilted), {"m": 1.0})


@pytest.mark.parametrize("inertia, why", [
    (np.diag([1.0, 1.0, 3.0]) * 1e-3, "triangle"),
    (np.diag([1.0, 0.0, 1.0]) * 1e-3, "positive-definite"),
    (np.diag([1.0, -1.0, 1.0]) * 1e-3, "positive-definite"),
    (np.array([[1, 0.5, 0], [0, 1, 0], [0, 0, 1]]) * 1e-3, "symmetric"),
])
def test_unphysical_inertia(mjspec_untouched, inertia, why):
    bad = body("lower", mass=1.0, com=(1.5, 0, 0), inertia=inertia)
    err = _fails(lambda p: arm(p, lower=bad), "body 'lower'")
    assert why in str(err)


def test_non_positive_mass(mjspec_untouched):
    bad = body("lower", mass=0.0, com=(1.5, 0, 0), inertia=I)
    _fails(lambda p: arm(p, lower=bad), "body 'lower'", "mass")


def test_undefined_parameter_names_the_element(mjspec_untouched):
    def mechanism(p):
        return arm(p, tip=site("tip", body="lower", pos=(p["reach"], 0, 0)))
    _fails(mechanism, "site 'tip'", "'reach'")


def test_undefined_parameter_inside_arithmetic(mjspec_untouched):
    def mechanism(p):
        return arm(p, tip=site("tip", body="lower",
                               pos=(math.cos(p["theta"]), 0, 0)))
    _fails(mechanism, "'theta'", "not defined")


def test_every_problem_is_reported_at_once(mjspec_untouched):
    bad_axis = joint("elbow", "hinge", parent="upper", child="lower",
                     axis=(1, 1, 0), point=(1, 0, 0), range=(-3, 3))
    bad_mass = body("upper", mass=-1.0, com=(0.5, 0, 0), inertia=I)
    err = _fails(lambda p: arm(p, elbow=bad_axis, upper=bad_mass),
                 "joint 'elbow'", "body 'upper'")
    assert len(err.problems) == 2


@pytest.mark.parametrize("change, name", [
    ({"elbow": joint("elbow", "ball", parent="upper", child="lower",
                     axis=(0, 0, 1), point=(1, 0, 0), range=(-3, 3))},
     "joint 'elbow'"),
    ({"elbow": joint("elbow", "hinge", parent="upper", child="lower",
                     axis=(0, 0, 1), point=(1, 0, 0), range=(3, -3))},
     "joint 'elbow'"),
    ({"elbow": joint("elbow", "hinge", parent="upper", child="lower",
                     axis=(0, 0, 1), point=(1, 0, 0), range=(-1, 1), home=2)},
     "joint 'elbow'"),
    ({"elbow": joint("elbow", "hinge", parent="upper", child="forearm",
                     axis=(0, 0, 1), point=(1, 0, 0), range=(-3, 3))},
     "joint 'elbow'"),
    ({"tip": site("tip", body="hand", pos=(2, 0, 0))}, "site 'tip'"),
    ({"rope": cable("rope", start=("world", (0, 0, 1)), end=("hand", (0, 0, 0)),
                    ea=1.0, rest_length=1.0)}, "cable 'rope'"),
    ({"rope": cable("rope", start=("world", (0, 0, 1)), end=("lower", (2, 0, 0)),
                    ea=1.0, rest_length=0.0)}, "cable 'rope'"),
    ({"motor": actuator("motor", joint="wrist")}, "actuator 'motor'"),
    ({"motor": actuator("motor", joint="elbow", gear=0.0)}, "actuator 'motor'"),
    ({"motor": actuator("motor", joint="elbow", rotor_inertia=-1e-5)},
     "actuator 'motor'"),
    ({"motor": actuator("motor", joint="elbow", torque_limit=0.0)},
     "actuator 'motor'"),
])
def test_other_faults_name_their_element(mjspec_untouched, change, name):
    _fails(lambda p: arm(p, **change), name)


def test_shape_errors_name_the_element():
    with pytest.raises(DescriptionError, match="joint 'elbow'"):
        joint("elbow", "hinge", parent="upper", child="lower", axis=(0, 1),
              point=(1, 0, 0), range=(-3, 3))
    with pytest.raises(DescriptionError, match="body 'lower'"):
        body("lower", mass=1.0, com=(0, 0, 0), inertia=(1, 1, 1))


def _free(**change):
    """The arm's upper link made a floating body; `change` faults it."""
    spec = dict(parent="world", child="upper", point=(0, 0, 0))
    spec.update(change)
    return {"shoulder": joint("shoulder", "free", **spec)}


@pytest.mark.parametrize("change, why", [
    (_free(parent="lower"), "hangs from the world"),
    (_free(axis=(0, 0, 1)), "takes no axis"),
    (_free(range=(-1, 1)), "takes no range"),
    (_free(home=0.5), "takes no home value"),
    (_free(stiffness=10.0), "takes no spring"),
    ({"elbow": joint("elbow", "hinge", parent="upper", child="lower",
                     point=(1, 0, 0), range=(-3, 3))}, "needs an axis"),
    ({"elbow": joint("elbow", "slide", parent="upper", child="lower",
                     axis=(1, 0, 0), point=(1, 0, 0))}, "needs a range"),
])
def test_joint_kind_faults(mjspec_untouched, change, why):
    err = _fails(lambda p: arm(p, **change), "joint '")
    assert why in str(err)


def test_an_actuator_cannot_drive_a_free_joint(mjspec_untouched):
    err = _fails(lambda p: arm(p, **_free(),
                               motor=actuator("motor", joint="shoulder")),
                 "actuator 'motor'")
    assert "free" in str(err)


def test_a_free_joint_is_locked_by_component():
    floating = lambda p: arm(p, **_free())
    m = armature.compile(floating, {"m": 1.0})
    assert m.coordinates == ("shoulder", "elbow")
    assert m.dofs[:6] == tuple(f"shoulder:{c}" for c in
                               ("x", "y", "z", "rx", "ry", "rz"))
    with pytest.raises(DescriptionError, match="no coordinate named 'shoulder'"):
        armature.compile(armature.reduce(floating, lock("shoulder", 0.0,
                                                        assumption="A1")),
                         {"m": 1.0})
    level = armature.reduce(floating, lock("shoulder:rz", 0.3, assumption="A1"))
    assert armature.compile(level, {"m": 1.0}).coordinates == (
        "shoulder:x", "shoulder:y", "shoulder:z", "shoulder:rx", "shoulder:ry",
        "elbow")


def test_symbolic_view_of_a_free_joint_matches_the_dofs():
    floating = lambda p: arm(p, **_free())
    view = armature.symbolic(floating, {"m": 1.0})
    assert view.coordinates == armature.compile(floating, {"m": 1.0}).dofs
