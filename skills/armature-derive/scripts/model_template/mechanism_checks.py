"""
mechanism_checks.py — self-tests for mechanism.py, 00_setup.md.

The description is checked three ways, none of them by a truth check on the
description itself: both sides read it, so an error in it is on both sides of
every comparison (ADR 0003). The engine validates it when it compiles, naming
the element at fault; `report_truth.py` prints the review artifact the red team
reads against the spec's sketch; and CAD's measured bodies replace its guesses.
What is checked here is what the rest of the model leans on — that the boxes in
params.py sit inside the envelope the description declares — and that a
release can fail, which is what every reduction's release check rests on.
"""

import math
from dataclasses import replace

import armature
from armature import lock

from mechanism import commands, derived, mechanism, truth
from params import PARAMS, QDD_LIMITS, QD_LIMITS, WORKSPACE

# The degenerate variant: a "derivation" that assumes the elbow is rigid at
# ELBOW_LOCKED and so carries one coordinate, the shoulder. Every number it
# produces is right for the one-body arm it describes, and that arm does not
# exist. Its assumption is A0, a number 00_setup.md's own list never takes.
ELBOW_LOCKED = 0.0


def rigid_elbow(at=ELBOW_LOCKED):
    """The locked-elbow variant, the elbow held at `at`."""
    return armature.reduce(mechanism, lock("elbow", at, assumption="A0"),
                           name="rigid elbow")


def test_the_description_compiles_exactly():
    """Validated and compiled, with nothing approximated.

    `armature.compile` refuses a description with a duplicate name, an
    unreachable body, a non-unit axis, an unphysical inertia, a loop open at
    home, or a parameter used and undefined or defined and unused, naming the
    element at fault; so reaching the assertions below is most of the check.
    `approximate` names any body a lump left massless, which the truth model
    then carries at a floor rather than exactly.
    """
    m, v = truth(), derived()
    assert m.approximate == (), f"the truth model is approximate: {m.approximate}"
    assert v.approximate == (), (f"the derivation's variant is approximate: "
                                 f"{v.approximate}")
    print(f"  [PASS] the description compiles exactly: "
          f"{len(m.description.bodies)} bodies, coordinates "
          f"{list(m.coordinates)}, actuators {list(m.actuators)}")


def test_the_workspace_sits_inside_the_joint_ranges():
    """WORKSPACE, a box in params.py, strictly inside the envelope the
    description's joint ranges declare.

    The workspace is a claim about the machine — *this is where it works* —
    and every later result leans on it: the singular-value bound, the IK's
    convergence set, the posture each worst case is found at. Its keys are the
    coordinates the derivation keeps, every one of them, and on a limit the
    truth model's settle reads the limit's force rather than the mechanism's,
    so a box touching a range is a box whose worst case the end-stop carries.
    """
    ranges = {j.name: j.range for j in truth().description.joints}
    assert set(WORKSPACE) == set(derived().independent), (
        f"WORKSPACE names {sorted(WORKSPACE)}; the derivation's coordinates "
        f"are {list(derived().independent)}")
    for name, (lo, hi) in WORKSPACE.items():
        low, high = ranges[name]
        assert low < lo < hi < high, (
            f"WORKSPACE[{name!r}] = ({lo}, {hi}) does not sit strictly inside "
            f"the joint's range ({low}, {high}) in mechanism.py")
    print(f"  [PASS] WORKSPACE sits strictly inside the joint ranges on "
          f"{len(WORKSPACE)} coordinates")


def test_the_rate_envelope_names_every_independent_dof():
    """QD_LIMITS and QDD_LIMITS against the truth model's dofs, by the
    sampler's own rule: every independent dof limited, nothing else named, no
    negative magnitude. A dof left out would only ever be sampled at rest."""
    samples = armature.sample_states(truth(), 1, qd_limits=QD_LIMITS,
                                     qdd_limits=QDD_LIMITS)
    assert len(samples) == 1
    print(f"  [PASS] the rate envelope limits every independent dof: "
          f"{sorted(QD_LIMITS)}")


def test_commands_hold_a_joint_torque_through_any_gear(gear=50.0, tol=1e-12):
    """`commands` turns the derivation's joint torques into motor torques,
    which is what every settle and release here holds. The shipped arm is
    direct drive, where a gear divided and a gear multiplied read the same,
    so the check runs on the same arm through a 50:1 reduction: the motor
    torques it gives are the ones the truth model's own inverse solves for."""
    def geared(p):
        return [replace(e, gear=gear) if hasattr(e, "gear") else e
                for e in mechanism(p)]   # every actuator, geared

    s = armature.compile(geared, PARAMS).at(q={"shoulder": 0.4, "elbow": 1.1})
    inv = s.inverse()
    held = commands(inv.generalised, s.compiled)
    gap = max(abs(held[a] - inv.torque[a]) for a in inv.torque)
    assert gap < tol, f"commands gives {held}; the motors need {dict(inv.torque)}"
    print(f"  [PASS] commands match the motor torques through a {gear:g}:1 gear")


def _the_locked_elbow_check(at=ELBOW_LOCKED, q_shoulder=0.4, tol=1e-3):
    """The release check a milestone writes for the locked-elbow derivation.

    Exactly the shape every reduction's release takes: hold what the variant
    says holds this posture — its own inverse dynamics, so the one-body arm's
    gravity torque — and release it in the full description, where the elbow
    is free, then assert the coordinate the assumption fixed stayed put.
    """
    s = armature.compile(rigid_elbow(at), PARAMS).at(q={"shoulder": q_shoulder})
    out = s.release(hold=s.inverse().torque)
    assert abs(out.moved["elbow"]) < tol, " ".join(str(out).split())
    return out


def test_truth_a_true_lock_passes_its_release():
    """The control: with the forearm hanging straight down the elbow carries
    no gravity torque, so a lock there is true, and the same check passes —
    the locked value away from home, the upper arm held by the variant's own
    torque. A check that failed every variant would be no evidence either."""
    out = _the_locked_elbow_check(at=0.7, q_shoulder=-math.pi / 2 - 0.7)
    print(f"  [PASS] a true lock releases to nothing: the elbow moves "
          f"{out.moved['elbow']:+.1e} rad")


def test_truth_a_frozen_degree_of_freedom_fails_its_release():
    """The teeth: a variant that freezes a coordinate the machine has must fail
    its release, and here it does.

    Every number in the locked-elbow variant reproduces. Its torque is right
    for the machine it describes, its units are right, and its
    self-consistency checks would all pass, because the frozen coordinate is
    missing from both sides of each of them. Released in the full description,
    which has the coordinate, it falls over, and the release names the elbow,
    the assumption, and how far.

    Wrapped as an expected failure so the run stays green while the failure
    stays printed. Delete it when you adapt the template, and give each
    reduction in DERIVED a release check of this shape that passes.
    """
    try:
        _the_locked_elbow_check()
    except AssertionError as failure:
        print("  [PASS] the frozen-elbow fixture fails its release, as it "
              "must:")
        print(f"         {failure}")
        return
    raise AssertionError(
        "the locked-elbow fixture passed its release — the check cannot see a "
        "frozen degree of freedom, which is the one thing it is for")
