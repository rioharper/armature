"""`Coordinates(fixed=...)`: a margin's space holds the coordinates it cannot
depend on out of its axes (#193).

Answer: the axes and the states themselves, and a search's worst against
the same search over an `Interval` of the free coordinate alone.
"""

import numpy as np
import pytest

import armature
from armature import Coordinates, Interval, Margin, Space, search
from test_closure_basis import floating_five_bar
from test_fixture_five_bar import PARAMS, five_bar


def test_a_fixed_hinge_is_no_axis_and_holds_its_value():
    space = Coordinates(five_bar, PARAMS, within={"A": (-0.4, 0.4)},
                        fixed={"E": 0.1})
    assert space.dims == 1
    for u in ((0.0,), (0.4,), (1.0,)):
        assert space.value(u).q["E"] == pytest.approx(0.1)


def test_a_fixed_floating_body_needs_no_envelope_and_spans_nothing():
    pose = (np.array([0.0, 0.0, 0.1]), np.eye(3))
    space = Coordinates(floating_five_bar, PARAMS, fixed={"float": pose})
    assert space.dims == 2
    s = space.value((0.3, 0.6))
    assert s.q["float"].position == pytest.approx(pose[0])


def test_the_worst_over_the_free_axis_is_the_intervals():
    """σ_min of the pin's reduced Jacobian over A with E held: the same
    worst as an `Interval` over A that builds the state itself."""
    m = armature.compile(five_bar, PARAMS)

    def sigma(s):
        j = s.jacobian("C2").linear[:2] @ s.closure_basis().G
        return float(np.linalg.svd(j, compute_uv=False)[-1])
    within = {"A": (-0.4, 0.4)}
    held = search(Margin("held", lambda p: sigma(p.state), "m/rad",
                         over=Space(state=Coordinates(
                             five_bar, PARAMS, within=within,
                             fixed={"E": 0.1}))))
    alone = search(Margin("alone", lambda p: sigma(m.at(
        q={"A": p.a, "E": 0.1})), "m/rad", over=Space(a=Interval(-0.4, 0.4))))
    assert held.value == pytest.approx(alone.value, abs=1e-9)


def test_fixing_a_drawn_or_dependent_coordinate_raises():
    with pytest.raises(ValueError, match="also drawn"):
        Coordinates(five_bar, PARAMS, within={"E": (0, 0.1)},
                    fixed={"E": 0.1}).dims
    with pytest.raises(ValueError, match="solved, not drawn"):
        Coordinates(five_bar, PARAMS, fixed={"B": 0.1}).dims
