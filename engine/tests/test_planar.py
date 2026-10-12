"""`planar(plane)` locks every coordinate that would leave the plane.

Answer: on an Ibex-shaped mechanism, a floating torso on two five-bar legs
whose hinges all turn about y, `planar("xz")` leaves the torso x, z and
pitch, and every in-plane joint; the neck's yaw and the y-slide lock at home.
Trap: an arm whose roll joint carries its mass off the plane. Its planar
variant is right for the arm it describes, and the release must report the
roll falling, keyed by the planar reduction.
"""

import math

import mujoco
import numpy as np
import pytest
import sympy as sp

import armature
from armature import actuator, body, gravity, joint, lock, loop, planar, site

I = np.diag([0.002, 0.003, 0.002])
HIP_Z, KNEE_Z, AXLE_Z = 0.50, 0.35, 0.20
POINT = (0, 0.01, HIP_Z)  # the free joint's point, off the centreline
SIDES = {"l": 0.15, "r": -0.15}


def ibex(p):
    """A floating torso on two planar five-bar legs, each closing at its
    wheel's axle, plus a neck that yaws about z and a battery that slides
    across the plane, along y, and one along x, in it."""
    out = [
        body("torso", mass=p["m_torso"], com=(0, 0, 0.55),
             inertia=np.diag([0.05, 0.04, 0.03])),
        joint("base", "free", parent="world", child="torso",
              point=POINT),
        body("head", mass=0.5, com=(0.05, 0, 0.75), inertia=I),
        joint("neck", "hinge", parent="torso", child="head", axis=(0, 0, 1),
              point=(0, 0, 0.7), range=(-1, 1), home=0.2),
        body("battery", mass=1.0, com=(0, 0, 0.6), inertia=I),
        joint("shift", "slide", parent="torso", child="battery",
              axis=(0, 1, 0), point=(0, 0, 0.6), range=(-0.05, 0.05)),
        body("pack", mass=1.0, com=(-0.1, 0, 0.6), inertia=I),
        joint("trim", "slide", parent="torso", child="pack", axis=(1, 0, 0),
              point=(-0.1, 0, 0.6), range=(-0.05, 0.05)),
    ]
    for side, y in SIDES.items():
        front, rear, knee_f, knee_r, axle = (
            (0.05, y, HIP_Z), (-0.05, y, HIP_Z), (0.10, y, KNEE_Z),
            (-0.10, y, KNEE_Z), (0.0, y, AXLE_Z))
        mid = lambda a, b: tuple((u + v) / 2 for u, v in zip(a, b))
        out += [
            body(f"upper_f_{side}", mass=0.3, com=mid(front, knee_f), inertia=I),
            body(f"upper_r_{side}", mass=0.3, com=mid(rear, knee_r), inertia=I),
            body(f"lower_f_{side}", mass=0.2, com=mid(knee_f, axle), inertia=I),
            body(f"lower_r_{side}", mass=0.2, com=mid(knee_r, axle), inertia=I),
            body(f"wheel_{side}", mass=0.4, com=axle, inertia=I),
            joint(f"hip_f_{side}", "hinge", parent="torso",
                  child=f"upper_f_{side}", axis=(0, 1, 0), point=front,
                  range=(-1.5, 1.5)),
            joint(f"hip_r_{side}", "hinge", parent="torso",
                  child=f"upper_r_{side}", axis=(0, 1, 0), point=rear,
                  range=(-1.5, 1.5)),
            joint(f"knee_f_{side}", "hinge", parent=f"upper_f_{side}",
                  child=f"lower_f_{side}", axis=(0, 1, 0), point=knee_f,
                  range=(-2.5, 2.5)),
            joint(f"knee_r_{side}", "hinge", parent=f"upper_r_{side}",
                  child=f"lower_r_{side}", axis=(0, 1, 0), point=knee_r,
                  range=(-2.5, 2.5)),
            joint(f"spin_{side}", "hinge", parent=f"lower_f_{side}",
                  child=f"wheel_{side}", axis=(0, 1, 0), point=axle,
                  range=(-100, 100)),
            site(f"axle_f_{side}", body=f"lower_f_{side}", pos=axle),
            site(f"axle_r_{side}", body=f"lower_r_{side}", pos=axle),
            loop(f"leg_{side}", f"axle_f_{side}", f"axle_r_{side}"),
            actuator(f"motor_f_{side}", joint=f"hip_f_{side}", gear=10.0),
            actuator(f"motor_r_{side}", joint=f"hip_r_{side}", gear=10.0),
        ]
    return out + [site("nose", body="torso", pos=(0.2, 0, 0.55))]


P = {"m_torso": 6.0}
SAGITTAL = armature.reduce(ibex, planar("xz", assumption="A2"),
                           name="sagittal")
IN_PLANE = ("hip_f_l", "knee_f_l", "spin_l", "hip_r_l", "knee_r_l",
            "hip_f_r", "knee_f_r", "spin_r", "hip_r_r", "knee_r_r", "trim")


@pytest.fixture(scope="module")
def m():
    return armature.compile(SAGITTAL, P)


def test_the_torso_keeps_x_z_and_pitch(m):
    assert m.coordinates[:3] == ("base:x", "base:z", "base:ry")
    assert set(m.coordinates[3:]) == set(IN_PLANE)
    assert m.dofs == m.coordinates
    kinds = {m.model.joint(i).name: m.model.jnt_type[i]
             for i in range(m.model.njnt)}
    assert kinds["base:x"] == kinds["base:z"] == mujoco.mjtJoint.mjJNT_SLIDE
    assert kinds["base:ry"] == mujoco.mjtJoint.mjJNT_HINGE


def test_the_out_of_plane_coordinates_lock_at_home(m):
    locks = m.description.locks
    assert set(locks) == {"base:y", "base:rx", "base:rz", "neck", "shift"}
    assert {n: float(l.at) for n, l in locks.items()} == {
        "base:y": 0.01, "base:rx": 0.0, "base:rz": 0.0, "neck": 0.2,
        "shift": 0.0}
    assert all(l.assumption == "A2" for l in locks.values())
    full = armature.compile(ibex, P)
    assert "base" in full.coordinates and "neck" in full.coordinates


def test_the_symbolic_view_has_the_same_coordinates(m):
    view = armature.symbolic(SAGITTAL, P)
    assert view.coordinates == m.dofs
    assert view.axes["base:ry"].to_matrix(view.world) == sp.Matrix([0, 1, 0])


def test_the_variant_moves_in_the_plane(m):
    """Pitched, moved and with a hip turned, the legs still close and every
    point stays at its home y."""
    assert m.dependent == ("knee_f_l", "knee_r_l", "knee_f_r", "knee_r_r")
    s = m.at(q={"base:x": 0.3, "base:z": 0.6, "base:ry": 0.2, "hip_f_l": 0.3,
                "hip_r_r": -0.2})
    nose = s.pose("nose")
    pitch = turn_y(0.2)  # the slides read the point's position, not a shift
    assert nose.position == pytest.approx(
        [0.3, 0.01, 0.6] + pitch @ np.array([0.2, -0.01, 0.05]), abs=1e-12)
    assert nose.rotation == pytest.approx(pitch, abs=1e-12)
    for side, y in SIDES.items():
        for end in ("f", "r"):
            assert s.pose(f"axle_{end}_{side}").position[1] == pytest.approx(
                y, abs=1e-12)
        assert s.pose(f"axle_f_{side}").position == pytest.approx(
            s.pose(f"axle_r_{side}").position, abs=1e-10)


def turn_y(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


# --- release: an arm that rolls out of the plane --------------------------------
def rolling(p):
    """A pitch hinge about y, in the xz plane, then a roll hinge about x
    whose body hangs its mass off to +y: gravity turns it out of the plane."""
    return [
        body("arm", mass=1.0, com=(0.2, 0, 0), inertia=I),
        body("hand", mass=p["m_hand"], com=(0.4, 0.1, 0), inertia=I),
        joint("pitch", "hinge", parent="world", child="arm", axis=(0, 1, 0),
              point=(0, 0, 0), range=(-3, 3)),
        joint("roll", "hinge", parent="arm", child="hand", axis=(1, 0, 0),
              point=(0.4, 0, 0), range=(-3, 3)),
        actuator("pitch_motor", joint="pitch"),
        gravity((0, 0, -9.81)),
    ]


IN_XZ = planar("xz", assumption="A7")


def test_planar_releases_the_roll_keyed_by_the_reduction():
    s = armature.compile(armature.reduce(rolling, IN_XZ),
                         {"m_hand": 0.5}).at(q={"pitch": 0.0})
    out = s.release(hold=s.inverse().torque)
    assert set(out.sized) == {IN_XZ}
    assert set(out.sized[IN_XZ]) == {"roll"}
    # It falls from the +y side towards −z: a turn about +x by about −π/2,
    # and the sign says which way.
    assert out.sized[IN_XZ]["roll"] == pytest.approx(-math.pi / 2, abs=0.05)
    assert out.moved == {"roll": out.sized[IN_XZ]["roll"]}
    assert out.assumed == {"roll": 0.0}
    assert "planar 'xz' (assumption A7) moved 'roll' -1.5" in str(out)


def test_planar_is_sized_at_nothing_when_nothing_leaves_the_plane():
    hanging =armature.reduce(lambda p: [
        e if getattr(e, "name", None) != "hand" else
        body("hand", mass=0.5, com=(0.4, 0, -0.1), inertia=I)
        for e in rolling(p)], IN_XZ)
    s = armature.compile(hanging, {"m_hand": 0.5}).at()
    out = s.release(hold=s.inverse().torque)
    assert abs(out.sized[IN_XZ]["roll"]) < 1e-6


def test_an_explicit_lock_wins_over_planar():
    both = armature.reduce(rolling, IN_XZ, lock("roll", 0.3, assumption="A8"))
    m = armature.compile(both, {"m_hand": 0.5})
    assert m.description.locks["roll"].at == 0.3
    assert m.description.locked_by["roll"] == lock("roll", 0.3,
                                                   assumption="A8")


@pytest.mark.parametrize("bad, why", [
    (planar("xw", assumption="A1"), "plane must be"),
    (planar("xz", assumption=None), "carries no assumption"),
])
def test_planar_faults(bad, why):
    with pytest.raises(armature.DescriptionError, match=why):
        armature.compile(armature.reduce(rolling, bad), {"m_hand": 0.5})


def test_two_planes_are_refused():
    with pytest.raises(armature.DescriptionError, match="one plane"):
        armature.compile(armature.reduce(rolling, IN_XZ,
                                         planar("xy", assumption="A9")),
                         {"m_hand": 0.5})
