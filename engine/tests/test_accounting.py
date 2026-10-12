"""Coordinate accounting, and a release keyed by reduction.

A derivation's coordinates must be its variant's, by name: a coordinate leaves
the equations only through a reduction, which carries its assumption number
and is sized by its release. Trap: a derivation that drops the elbow without
saying so must fail, naming the elbow.
"""

import math

import numpy as np
import pytest
import sympy as sp

import armature
from armature import (AccountingError, account, actuator, body, cable, couple,
                      gravity, joint, lock, lump, planar, rigid, site)

I = np.eye(3) * 1e-3


def arm(p):
    return [
        body("upper", mass=1.0, com=(0.15, 0, 0), inertia=I),
        body("fore", mass=0.8, com=(0.425, 0, 0), inertia=I),
        joint("shoulder", "hinge", parent="world", child="upper",
              axis=(0, 0, 1), point=(0, 0, 0), range=(-3, 3)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 0, 1),
              point=(0.3, 0, 0), range=(-2.6, 2.6)),
        actuator("shoulder_motor", joint="shoulder"),
        gravity((0, -9.81, 0)),
    ]


RIGID_ELBOW = armature.reduce(arm, lock("elbow", 0.0, assumption="A3"),
                              name="rigid elbow")


def test_a_matching_derivation_passes():
    m = armature.compile(arm, {})
    account(m, ["shoulder", "elbow"])
    account(m, ("elbow", "shoulder"))  # by name, in any order
    account(m, armature.symbolic(arm, {}).q.values())  # its dynamicsymbols
    account(m, sp.symbols("shoulder elbow"))
    account(armature.compile(RIGID_ELBOW, {}), ["shoulder"])


def test_a_dropped_coordinate_fails_naming_it():
    with pytest.raises(AccountingError) as err:
        account(armature.compile(arm, {}), ["shoulder"])
    assert len(err.value.problems) == 1
    assert "'elbow'" in err.value.problems[0]
    assert "reduction" in err.value.problems[0]


def test_a_locked_coordinate_left_in_fails_naming_its_reduction():
    with pytest.raises(AccountingError) as err:
        account(armature.compile(RIGID_ELBOW, {}), ["shoulder", "elbow"])
    assert "'elbow'" in str(err.value)
    assert "lock 'elbow' at 0.0 (assumption A3)" in str(err.value)


def test_unknown_and_repeated_names_fail():
    m = armature.compile(arm, {})
    with pytest.raises(AccountingError, match="'wrist', which is not a "
                                              "coordinate"):
        account(m, ["shoulder", "elbow", "wrist"])
    with pytest.raises(AccountingError, match="'elbow' more than once"):
        account(m, ["shoulder", "elbow", "elbow"])
    with pytest.raises(TypeError, match="not a coordinate"):
        account(m, [3])


def test_a_solved_coordinate_may_be_left_to_its_closure():
    tied = armature.reduce(arm, couple("elbow", "shoulder", 0.5,
                                       assumption="A4"))
    m = armature.compile(tied, {})
    account(m, ["shoulder"])
    account(m, ["shoulder", "elbow"])
    with pytest.raises(AccountingError, match="'shoulder'"):
        account(m, ["elbow"])


def test_a_floating_body_is_accounted_by_its_components():
    def hung(p):
        return [body("plate", mass=1.0, com=(0, 0, 0), inertia=I),
                joint("float", "free", parent="world", child="plate",
                      point=(0, 0, 0))]
    names = [f"float:{c}" for c in ("x", "y", "z", "rx", "ry", "rz")]
    account(armature.compile(hung, {}), names)
    level = armature.reduce(hung, planar("xz", assumption="A1"))
    account(armature.compile(level, {}), ["float:x", "float:z", "float:ry"])
    with pytest.raises(AccountingError, match="'float:y', which variant"):
        account(armature.compile(level, {}), names)


def test_a_couple_is_released_by_its_followers_departure():
    """The full description has no belt: the elbow, sprung, sags off the
    coupled value. Its departure is q_a − home_a − ratio (q_b − home_b) at
    rest, homes and ratio both away from the trivial ones."""
    def sprung(p):
        out = arm(p)
        out[2] = joint("shoulder", "hinge", parent="world", child="upper",
                       axis=(0, 0, 1), point=(0, 0, 0), range=(-3, 3),
                       home=0.1)
        out[3] = joint("elbow", "hinge", parent="upper", child="fore",
                       axis=(0, 0, 1), point=(0.3, 0, 0), range=(-2.6, 2.6),
                       home=0.2, stiffness=5.0)
        return out
    belt = couple("elbow", "shoulder", 0.5, assumption="A4")
    s = armature.compile(armature.reduce(sprung, belt), {}).at(
        q={"shoulder": 0.5})
    assert s.q["elbow"] == pytest.approx(0.2 + 0.5 * 0.4, abs=1e-12)
    out = s.release(hold=s.inverse().torque)
    rest = out.settled.q
    departure = (rest["elbow"] - 0.2) - 0.5 * (rest["shoulder"] - 0.1)
    assert out.sized[belt] == pytest.approx(departure, abs=1e-14)
    assert out.moved == {"elbow": out.sized[belt]}
    assert departure < -0.01  # the forearm sags: the belt was carrying it


# --- every kind in one variant: assumption numbers, and release by reduction ---
def rig(p):
    """A cart on a tethered slide carrying an arm (pitch, a sprung flex, an
    out-of-plane roll at the hand) and a tail (with a wag coupled to the
    pitch), all in the xz plane but the roll."""
    return [
        body("cart", mass=2.0, com=(0, 0, 0), inertia=I),
        body("arm", mass=1.0, com=(0.2, 0, 0), inertia=I),
        body("fore", mass=0.5, com=(0.6, 0, 0), inertia=I),
        body("hand", mass=0.2, com=(0.85, 0.05, 0), inertia=I),
        body("boom", mass=0.4, com=(-0.2, 0, 0), inertia=I),
        body("tip", mass=0.1, com=(-0.5, 0, 0), inertia=I),
        joint("x", "slide", parent="world", child="cart", axis=(1, 0, 0),
              point=(0, 0, 0), range=(-1, 1)),
        joint("pitch", "hinge", parent="cart", child="arm", axis=(0, 1, 0),
              point=(0, 0, 0), range=(-3, 3)),
        joint("flex", "hinge", parent="arm", child="fore", axis=(0, 1, 0),
              point=(0.4, 0, 0), range=(-2, 2), stiffness=50.0),
        joint("roll", "hinge", parent="fore", child="hand", axis=(1, 0, 0),
              point=(0.8, 0, 0), range=(-3, 3)),
        joint("tail", "hinge", parent="cart", child="boom", axis=(0, 1, 0),
              point=(0, 0, 0), range=(-3, 3)),
        joint("wag", "hinge", parent="boom", child="tip", axis=(0, 1, 0),
              point=(-0.4, 0, 0), range=(-3, 3)),
        cable("tether", start=("world", (-1, 0, 0)), end=("cart", (0, 0, 0)),
              ea=1e4, rest_length=1.0),
        site("end", body="hand", pos=(0.9, 0, 0)),
        actuator("pitch_motor", joint="pitch"),
        gravity((0, 0, -9.81)),
    ]


REDUCTIONS = (planar("xz", assumption="A1"), lock("tail", 0.0, assumption="A2"),
              couple("wag", "pitch", 1.0, assumption="A3"),
              lump("hand", into="fore", assumption="A4"),
              rigid("tether", assumption="A5"), rigid("flex", assumption="A6"))


def test_every_reduction_carries_its_assumption_number():
    for r in REDUCTIONS:
        broken = type(r)(**{**r.__dict__, "assumption": None})
        with pytest.raises(armature.DescriptionError,
                           match="carries no assumption"):
            armature.compile(armature.reduce(rig, broken), {})
    for make, args in ((lock, ("tail", 0.0)), (couple, ("wag", "pitch", 1.0)),
                       (planar, ("xz",)), (lump, ("hand", "fore")),
                       (rigid, ("tether",))):
        with pytest.raises(TypeError, match="assumption"):
            make(*args)


def test_a_variant_is_judged_on_its_parents_parameters():
    """A reduction can take an element out of the equations, never out of
    the description: the parameters it read are still read, and one the
    description never read is still refused."""
    def weighed(p):
        out = rig({})
        out[3] = body("hand", mass=p["m_hand"], com=(0.85, 0.05, 0), inertia=I)
        out[12] = cable("tether", start=("world", (-1, 0, 0)),
                        end=("cart", (0, 0, 0)), ea=p["ea"], rest_length=1.0)
        return out
    params = {"m_hand": 0.2, "ea": 1e4}
    gone = armature.reduce(weighed, lump("hand", into=armature.massless,
                                         assumption="A4"),
                           rigid("tether", assumption="A5"),
                           planar("xz", assumption="A1"))
    armature.compile(gone, params)
    armature.symbolic(gone, params)
    with pytest.raises(armature.DescriptionError,
                       match="'spare' is defined but never used"):
        armature.compile(gone, {**params, "spare": 1.0})


def test_the_frames_table_lists_every_reduction_with_its_assumption():
    table = armature.frames(armature.reduce(rig, *REDUCTIONS), {})
    rows = table.sections["Reductions"]
    assert [r["name"] for r in rows] == [str(r) for r in REDUCTIONS]
    assert [r["assumption"] for r in rows] == [f"A{i}" for i in range(1, 7)]
    text = table.markdown()
    for r in REDUCTIONS:
        assert str(r) in text


def test_release_is_keyed_by_reduction():
    v = armature.compile(armature.reduce(rig, *REDUCTIONS), {})
    assert v.coordinates == ("x", "pitch", "wag")
    assert v.dependent == ("x", "wag")
    s = v.at(q={"pitch": -0.3})
    out = s.release(hold=s.inverse().torque,
                    quantity=lambda s: s.inverse().torque["pitch_motor"])
    assert tuple(out.sized) == REDUCTIONS
    plane, tail, wag, hand, tether, flex = REDUCTIONS
    assert set(out.sized[plane]) == {"roll"}
    # Displacement is what a lock, couple or planar held; a rigid joint's
    # weld is sized by the quantity, not here.
    assert set(out.moved) == {"roll", "tail", "wag"}
    assert set(out.assumed) == {"roll", "tail"}
    assert out.sized[tail] == out.moved["tail"]
    assert out.sized[wag] == out.moved["wag"]
    assert out.sized[tail] == pytest.approx(-math.pi / 2, abs=1e-3)  # hangs
    # Each is released alone, the others kept: planar still welds the hand to
    # the forearm, so lumping it there moves nothing but the floor's 1e-6.
    assert 0.0 < abs(out.sized[hand]) < 1e-5
    # Statics loads neither the tether's length nor the motor through flex.
    assert abs(out.sized[tether]) < 1e-12 and abs(out.sized[flex]) < 1e-12
    for r in REDUCTIONS:
        assert str(r) in str(out)
