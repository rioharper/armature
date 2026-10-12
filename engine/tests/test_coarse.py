"""Coarse bodies: each helper's mass, COM and inertia against its textbook
closed form, written here in the solid's own principal axes and turned into
base axes by a rotation built independently (scipy). `compose` against a hand
parallel-axis sum, and against solids it must reproduce when cut in two."""

import math

import numpy as np
import pytest
import sympy as sp
from scipy.spatial.transform import Rotation

import armature
from armature import (DescriptionError, box, compose, cylinder, joint, point,
                      rod, sphere)

TILT = Rotation.from_euler("zyx", [0.7, -0.4, 1.1]).as_matrix()


def _turned(principal, axis_first=None):
    """`principal` (a diagonal, about the solid's own axes) in base axes:
    the solid's first axis along `axis_first`, or along TILT's columns."""
    if axis_first is None:
        rotation = TILT
    else:  # any rotation taking x to the axis; the others are symmetric
        rotation = Rotation.align_vectors([axis_first], [[1, 0, 0]])[0]
        rotation = rotation.as_matrix()
    return rotation @ np.diag(principal) @ rotation.T


def _numbers(b):
    return float(b.mass), np.array(b.com, float), np.array(b.inertia, float)


def _assert_body(b, mass, com, inertia):
    m, c, i = _numbers(b)
    inertia = np.asarray(inertia, float)
    assert m == pytest.approx(mass, rel=1e-12)
    assert c == pytest.approx(com, abs=1e-12)
    assert i == pytest.approx(inertia, abs=1e-12 * max(1.0, np.abs(inertia).max()))


# --- each helper against its closed form ---------------------------------------
def test_point():
    _assert_body(point("p", at=(0.1, -0.2, 0.3), mass=0.7), 0.7,
                 (0.1, -0.2, 0.3), np.zeros((3, 3)))


@pytest.mark.parametrize("given", [{"mass": 0.6}, {"linear_density": 0.6 / 0.5}])
def test_rod_along_a_tilted_line(given):
    start = np.array([0.2, 0.1, -0.3])
    direction = TILT[:, 0]
    b = rod("r", start=start, end=start + 0.5 * direction, **given)
    across = 0.6 * 0.5 ** 2 / 12
    _assert_body(b, 0.6, start + 0.25 * direction,
                 _turned([0.0, across, across], direction))


@pytest.mark.parametrize("given", [{"mass": 2.4},
                                   {"density": 2.4 / (0.3 * 0.2 * 0.1)}])
def test_box_in_base_axes(given):
    b = box("b", center=(1, 2, 3), size=(0.3, 0.2, 0.1), **given)
    _assert_body(b, 2.4, (1, 2, 3), np.diag([2.4 * (0.2 ** 2 + 0.1 ** 2) / 12,
                                             2.4 * (0.3 ** 2 + 0.1 ** 2) / 12,
                                             2.4 * (0.3 ** 2 + 0.2 ** 2) / 12]))


def test_box_on_turned_axes():
    b = box("b", center=(0, 0, 0), size=(0.3, 0.2, 0.1), mass=2.4, axes=TILT)
    _assert_body(b, 2.4, (0, 0, 0), _turned([2.4 * (0.2 ** 2 + 0.1 ** 2) / 12,
                                             2.4 * (0.3 ** 2 + 0.1 ** 2) / 12,
                                             2.4 * (0.3 ** 2 + 0.2 ** 2) / 12]))


@pytest.mark.parametrize("given", [{"mass": 1.5},
                                   {"density": 1.5 / (math.pi * 0.04 ** 2 * 0.4)}])
def test_cylinder_along_a_tilted_axis(given):
    start = np.array([0.0, 0.5, 0.2])
    axis = TILT[:, 2]
    b = cylinder("c", start=start, end=start + 0.4 * axis, radius=0.04, **given)
    across = 1.5 * (3 * 0.04 ** 2 + 0.4 ** 2) / 12
    _assert_body(b, 1.5, start + 0.2 * axis,
                 _turned([1.5 * 0.04 ** 2 / 2, across, across], axis))


@pytest.mark.parametrize("given", [{"mass": 3.0},
                                   {"density": 3.0 / (4 / 3 * math.pi * 0.05 ** 3)}])
def test_sphere(given):
    b = sphere("s", center=(0, 0, 1), radius=0.05, **given)
    _assert_body(b, 3.0, (0, 0, 1), np.eye(3) * 2 / 5 * 3.0 * 0.05 ** 2)


# --- compose --------------------------------------------------------------------
def test_compose_is_the_hand_parallel_axis_sum():
    """A 2 kg sphere of radius 0.1 at the origin and a 1 kg point at
    (0.3, 0.3, 0). By hand: M = 3, COM (0.1, 0.1, 0). The sphere sits
    r = (−0.1, −0.1, 0) from it and adds 2 (0.02 E − r rᵀ); the point sits
    (0.2, 0.2, 0) away and adds 1 (0.08 E − r rᵀ); the sphere's own moment is
    0.4 · 2 · 0.01 = 0.008."""
    b = compose("arm", sphere("ball", center=(0, 0, 0), radius=0.1, mass=2.0),
                point("tip", at=(0.3, 0.3, 0), mass=1.0))
    _assert_body(b, 3.0, (0.1, 0.1, 0.0), [[0.068, -0.060, 0.0],
                                           [-0.060, 0.068, 0.0],
                                           [0.0, 0.0, 0.128]])
    assert b.name == "arm"


def test_two_half_boxes_are_the_whole_box():
    whole = box("whole", center=(0.1, 0.2, 0.3), size=(0.6, 0.2, 0.1),
                mass=4.0, axes=TILT)
    shift = TILT[:, 0] * 0.15
    halves = [box(f"half{k}", center=np.array([0.1, 0.2, 0.3]) + s * shift,
                  size=(0.3, 0.2, 0.1), mass=2.0, axes=TILT)
              for k, s in enumerate((-1, 1))]
    _assert_body(compose("whole", *halves), *_numbers(whole))


def test_a_rod_cut_unevenly_is_the_whole_rod():
    start, end = np.array([0.0, 0.0, 0.0]), np.array([0.3, -0.4, 1.2])
    cut = start + 0.3 * (end - start)
    whole = rod("whole", start=start, end=end, linear_density=0.8)
    parts = compose("whole", rod("a", start=start, end=cut, linear_density=0.8),
                    rod("b", start=cut, end=end, linear_density=0.8))
    _assert_body(parts, *_numbers(whole))


def test_compose_of_one_part_is_that_part():
    c = cylinder("c", start=(0, 0, 0), end=(0, 0, 0.3), radius=0.02, mass=0.4)
    _assert_body(compose("link", c), *_numbers(c))


# --- symbols ---------------------------------------------------------------------
def test_helpers_give_exact_closed_forms_on_symbols():
    m, a, b, c, r, h, rho = sp.symbols("m a b c r h rho", positive=True)
    bx = box("b", center=(0, 0, 0), size=(a, b, c), mass=m)
    assert sp.simplify(bx.inertia[0][0] - m * (b ** 2 + c ** 2) / 12) == 0
    cy = cylinder("c", start=(0, 0, 0), end=(0, 0, h), radius=r, density=rho)
    assert sp.simplify(cy.mass - rho * sp.pi * r ** 2 * h) == 0
    assert sp.simplify(cy.inertia[2][2] - cy.mass * r ** 2 / 2) == 0
    assert sp.simplify(cy.inertia[0][0]
                       - cy.mass * (3 * r ** 2 + h ** 2) / 12) == 0
    assert cy.com == (0, 0, h / 2)
    s = compose("s", point("p", at=(a, 0, 0), mass=m),
                point("q", at=(-a, 0, 0), mass=m))
    assert sp.simplify(s.inertia[1][1] - 2 * m * a ** 2) == 0


def coarse_arm(p):
    """A 2R arm written the spec-stage way: two cylinders, a point motor at
    the elbow composed into the upper link."""
    l1, l2 = p["l1"], p["l2"]
    return [
        compose("upper",
                cylinder("tube", start=(0, 0, 0), end=(l1, 0, 0),
                         radius=p["r"], density=p["rho"]),
                point("motor", at=(l1, 0, 0), mass=p["m_motor"])),
        cylinder("fore", start=(l1, 0, 0), end=(l1 + l2, 0, 0), radius=p["r"],
                 density=p["rho"]),
        joint("shoulder", "hinge", parent="world", child="upper",
              axis=(0, 0, 1), point=(0, 0, 0), range=(-3, 3)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 0, 1),
              point=(l1, 0, 0), range=(-3, 3)),
    ]


COARSE = {"l1": 0.3, "l2": 0.25, "r": 0.02, "rho": 1500.0, "m_motor": 0.4}


def test_a_coarse_description_compiles_and_reads_symbolically():
    m = armature.compile(coarse_arm, COARSE)
    tube = 1500.0 * math.pi * 0.02 ** 2 * 0.3
    assert m.model.body("upper").mass[0] == pytest.approx(tube + 0.4, rel=1e-12)
    com = (tube * 0.15 + 0.4 * 0.3) / (tube + 0.4)
    assert m.model.body("upper").pos[0] == pytest.approx(com, rel=1e-12)
    view = armature.symbolic(coarse_arm, COARSE)
    l1, l2, rho, r = (view.params[k] for k in ("l1", "l2", "rho", "r"))
    # the parameters are real, not positive, so a length reads |l|
    assert sp.simplify(view.mass["fore"]
                       - rho * sp.pi * r ** 2 * sp.Abs(l2)) == 0
    assert view.mass["upper"].has(l1)


# --- faults -----------------------------------------------------------------------
@pytest.mark.parametrize("make, why", [
    (lambda: box("b", center=(0, 0, 0), size=(1, 1, 1)), "not neither"),
    (lambda: box("b", center=(0, 0, 0), size=(1, 1, 1), mass=1.0, density=1.0),
     "not both"),
    (lambda: box("b", center=(0, 0, 0), size=(1, 1, 1), mass=1.0,
                 axes=np.diag([1.0, 1.0, -1.0])), "not a rotation"),
    (lambda: box("b", center=(0, 0, 0), size=(1, 1, 1), mass=1.0,
                 axes=np.eye(3) * 1.1), "not a rotation"),
    (lambda: cylinder("b", start=(1, 0, 0), end=(1, 0, 0), radius=0.1,
                      mass=1.0), "no length"),
    (lambda: rod("b", start=(1, 0, 0), end=(1, 0, 0), mass=1.0), "no length"),
    (lambda: compose("b"), "at least one part"),
    (lambda: compose("b", (1.0, (0, 0, 0))), "is not a body"),
])
def test_faults_name_the_body(make, why):
    with pytest.raises(DescriptionError, match=why) as err:
        make()
    assert "body 'b'" in str(err.value)


@pytest.mark.parametrize("alone", [
    point("link", at=(0.5, 0, 0), mass=1.0),
    rod("link", start=(0, 0, 0), end=(1, 0, 0), mass=1.0)])
def test_a_point_or_a_rod_alone_fails_validation(alone):
    def mechanism(p):
        return [alone, joint("j", "hinge", parent="world", child="link",
                             axis=(0, 0, 1), point=(0, 0, 0), range=(-1, 1))]
    with pytest.raises(DescriptionError, match="body 'link'.*positive-definite"):
        armature.compile(mechanism, {})
