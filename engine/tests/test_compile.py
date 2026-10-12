"""What the compiler owns: base-frame numbers at home, radians, explicit
inertia, and states keyed by coordinate name."""

import math
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import mujoco
import numpy as np
import pytest

import armature
from armature import State, body, joint, site
from armature.compiler import _spec

G = 9.81
INERTIA = np.array([[2.0, 0.3, 0.1],
                    [0.3, 3.0, 0.2],
                    [0.1, 0.2, 4.0]]) * 1e-3
PARAMS = {"m": 1.5, "l": 0.4, "x": 0.2, "h": 0.5}


def pendulum(p):
    """A bob hung `l` below a hinge about y at (x, 0, h), written at home."""
    return [body("bob", mass=p["m"], com=(p["x"], 0, p["h"] - p["l"]),
                 inertia=INERTIA),
            joint("swing", "hinge", parent="world", child="bob", axis=(0, 1, 0),
                  point=(p["x"], 0, p["h"]), range=(-2.0, 2.0)),
            site("tip", body="bob", pos=(p["x"], 0, p["h"] - 2 * p["l"]))]


def offset_home(p):
    """The pendulum written at a home where its coordinate reads 0.5 rad."""
    *elements, = pendulum(p)
    elements[1] = joint("swing", "hinge", parent="world", child="bob",
                        axis=(0, 1, 0), point=(p["x"], 0, p["h"]),
                        range=(-1.0, 1.0), home=0.5)
    return elements


def two_slides(p):
    """Two stacked slides, so coordinate order can be told from naming."""
    i = np.eye(3) * 1e-3
    return [body("cart", mass=1.0, com=(0, 0, 0), inertia=i),
            body("top", mass=1.0, com=(0, 0, 1), inertia=i),
            joint("b", "slide", parent="world", child="cart", axis=(1, 0, 0),
                  point=(0, 0, 0), range=(-1, 1), stiffness=100.0),
            joint("a", "slide", parent="cart", child="top", axis=(0, 1, 0),
                  point=(0, 0, 1), range=(-1, 1), stiffness=300.0)]


def _site(compiled, q, name):
    """A site's world position at `q`, read through the MjModel escape hatch."""
    data = mujoco.MjData(compiled.model)
    data.qpos[:] = q
    mujoco.mj_forward(compiled.model, data)
    return data.site(name).xpos.copy()


def test_numbers_are_base_frame_at_home():
    m = armature.compile(pendulum, PARAMS)
    assert _site(m, 0.0, "tip") == pytest.approx([0.2, 0, -0.3], abs=1e-12)
    # A quarter turn about +y at (0.2, 0, 0.5) carries (0, 0, −0.8) to (−0.8, 0, 0).
    assert _site(m, math.pi / 2, "tip") == pytest.approx([-0.6, 0, 0.5],
                                                         abs=1e-12)


@pytest.mark.parametrize("q", [0.0, 0.7, -1.3])
def test_pendulum_linearises_to_its_closed_form(q):
    lin = armature.compile(pendulum, PARAMS).at(q={"swing": q}).linearise()
    m, l = PARAMS["m"], PARAMS["l"]
    assert lin.stiffness[0, 0] == pytest.approx(m * G * l * math.cos(q),
                                                rel=1e-6)
    assert lin.mass[0, 0] == pytest.approx(m * l ** 2 + INERTIA[1, 1],
                                           rel=1e-12)


def test_inertia_is_the_description_full_tensor():
    m = armature.compile(pendulum, PARAMS)
    data = mujoco.MjData(m.model)
    mujoco.mj_forward(m.model, data)
    bob = m.model.body("bob")
    rot = data.body("bob").ximat.reshape(3, 3)
    assert bob.mass[0] == 1.5
    assert rot @ np.diag(bob.inertia) @ rot.T == pytest.approx(INERTIA,
                                                               abs=1e-15)


def test_inertia_never_comes_from_a_geom():
    spec = _spec(armature.describe(pendulum, PARAMS))
    spec.body("bob").add_geom(type=mujoco.mjtGeom.mjGEOM_SPHERE, size=[0.2, 0, 0],
                              density=7800.0)
    model = spec.compile()
    assert model.body("bob").mass[0] == 1.5
    assert sorted(model.body("bob").inertia) == pytest.approx(
        np.linalg.eigvalsh(INERTIA), abs=1e-15)


def test_range_and_home_are_never_read_as_degrees():
    m = armature.compile(offset_home, PARAMS)
    assert m.model.jnt_range[0] == pytest.approx([-1.0, 1.0])
    assert m.model.qpos0[0] == pytest.approx(0.5)
    # At its home value the bob sits where it was written.
    assert _site(m, 0.5, "tip") == pytest.approx([0.2, 0, -0.3], abs=1e-12)
    assert m.at().q["swing"] == 0.5


def test_state_is_keyed_by_coordinate_name():
    m = armature.compile(two_slides, {})
    assert m.coordinates == ("b", "a")
    lin = m.at(q={"a": 0.1, "b": -0.2}).linearise()
    assert lin.dofs == ("b", "a")
    assert np.diag(lin.stiffness) == pytest.approx([100.0, 300.0], rel=1e-6)
    s = m.at(q={"a": 0.1})
    assert dict(s.q) == {"b": 0.0, "a": 0.1}
    assert dict(s.qd) == {"b": 0.0, "a": 0.0}


def test_state_is_immutable():
    s = armature.compile(two_slides, {}).at(q={"a": 0.1})
    with pytest.raises(FrozenInstanceError):
        s.q = {}
    with pytest.raises(TypeError):
        s.q["a"] = 0.2


def test_at_refuses_unknown_names_and_out_of_range_values():
    m = armature.compile(two_slides, {})
    with pytest.raises(KeyError, match="'c'"):
        m.at(q={"c": 0.0})
    with pytest.raises(KeyError, match="'c'"):
        m.at(qd={"c": 0.0})
    with pytest.raises(ValueError, match="joint 'a'"):
        m.at(q={"a": 1.5})


def test_no_query_reads_data_another_left_behind():
    m = armature.compile(pendulum, PARAMS)
    first, other = m.at(q={"swing": 0.3}), m.at(q={"swing": -1.1})
    before = first.linearise()
    other.linearise()
    after = first.linearise()
    assert np.array_equal(before.stiffness, after.stiffness)
    assert np.array_equal(before.mass, after.mass)


def test_linearise_refuses_an_active_limit():
    # at() refuses a value outside the range, so build the state by hand.
    m = armature.compile(pendulum, PARAMS)
    beyond = State(m, MappingProxyType({"swing": 2.1}),
                   MappingProxyType({"swing": 0.0}))
    with pytest.raises(RuntimeError, match="limit on joint 'swing'"):
        beyond.linearise()


def branching(p):
    """world → a → c, and world → b, written so the order they appear in
    differs from the order the tree is walked."""
    i = np.eye(3) * 1e-3
    return [body("a", mass=1.0, com=(1, 0, 0), inertia=i),
            body("b", mass=1.0, com=(-1, 0, 0), inertia=i),
            body("c", mass=1.0, com=(2, 0, 0), inertia=i),
            joint("ja", "hinge", parent="world", child="a", axis=(0, 0, 1),
                  point=(0, 0, 0), range=(-1, 1)),
            joint("jb", "hinge", parent="world", child="b", axis=(0, 0, 1),
                  point=(0, 0, 0), range=(-1, 1)),
            joint("jc", "hinge", parent="a", child="c", axis=(0, 0, 1),
                  point=(1.5, 0, 0), range=(-1, 1))]


def test_coordinates_follow_the_tree_on_both_sides():
    m = armature.compile(branching, {})
    assert m.coordinates == ("ja", "jc", "jb")
    assert armature.symbolic(branching, {}).coordinates == m.coordinates
