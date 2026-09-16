"""
truth/release_checks.py — self-tests for release.py, and the degenerate fixture
that proves the package has teeth.

The first half is internal, like the other checks here: that a release frees
what it says it frees and nothing else. The second half is not, and is the
point of the file — a deliberately wrong analytic model, freezing a coordinate
the machine actually has, run through the same check a real milestone writes,
and failing. A check nobody has watched fail is a check with no evidence
behind it.
"""

import numpy as np

from params import N, PARAMS
from truth.chain import build
from truth.envelope import DEFAULT_SEED, sample
from truth.inverse import inverse_dynamics
from truth.release import release

HOLD_STEPS = 500
# The degenerate model: a "derivation" that assumes the elbow is locked at
# ELBOW_LOCKED and so carries one coordinate, the shoulder. Written out here by
# hand rather than imported, because the truth package imports the parameter
# block and nothing else from the model — and because a fixture that borrowed
# the real derivation would inherit whatever the real derivation gets right.
ELBOW_LOCKED = 0.0


def one_link_shoulder_torque(q1):
    """The locked-elbow model's holding torque at the shoulder [N m].

    With the elbow rigid at zero the arm is one body: the shoulder carries each
    mass times its lever arm about the base, times cos q1. Correct arithmetic,
    correct units, correct to the digit for the machine it describes — and that
    machine does not exist, which is the shape of the error this fixture is for.
    """
    p = PARAMS
    return p["g"] * np.cos(q1) * (p["m1"] * p["lc1"]
                                  + p["m2"] * (p["l1"] + p["lc2"]))


def test_release_frees_the_named_coordinate_and_nothing_else(seed=DEFAULT_SEED):
    """Hold the truth model's own gravity torque everywhere, then let one
    coordinate go: that one moves, and with nothing released nothing does."""
    model, data = build()
    q0 = sample(1, seed)[0]
    gravity = inverse_dynamics(model, data, q0, np.zeros(N), np.zeros(N))

    held = release(model, data, q0, [], hold=gravity, min_steps=HOLD_STEPS)
    assert held.stable and np.max(np.abs(held.rest - q0)) < 1e-6, (
        f"holding the truth model's own gravity torque with nothing released, "
        f"it still moved to {np.round(held.rest, 4)} from {np.round(q0, 4)}")

    out = release(model, data, q0, "q2", hold=gravity, min_steps=HOLD_STEPS)
    assert out.assumed.shape == (1,) and out.moved.shape == (1,)
    assert abs(out.moved[0]) > 1e-2, (
        f"the elbow was released with nothing holding it and moved "
        f"{out.moved[0]:.2e} rad — the release is not releasing")
    print(f"  [PASS] releasing q2 moves it {out.moved[0]:+.3f} rad; releasing "
          f"nothing moves nothing")


def test_releasing_a_coordinate_the_model_lacks_says_so():
    """The other answer a release can give, and it has to be a legible one: the
    truth model can only free a coordinate it has, and an assumption about one
    it does not have is the setup note's to argue in a sentence."""
    model, data = build()
    try:
        release(model, data, np.zeros(N), "platform_roll")
    except AssertionError as failure:
        assert "platform_roll" in str(failure) and "sentence" in str(failure)
        print("  [PASS] releasing a coordinate the model lacks names it and "
              "points at the setup note")
        return
    raise AssertionError("releasing a coordinate the model lacks did not raise")


def _the_locked_elbow_check(tol=1e-3):
    """The check a milestone would write for the locked-elbow derivation.

    Exactly the shape of `dynamics/statics_checks.py`'s equilibrium truth
    check: hold what the analytic model says holds this posture, settle, assert
    the machine is still there. The analytic model here has one coordinate, so
    it commands one — and says nothing about the elbow because, on its telling,
    there is no elbow to say anything about.
    """
    model, data = build()
    q0 = np.array([0.4, ELBOW_LOCKED])
    hold = np.zeros(N)
    hold[0] = one_link_shoulder_torque(q0[0])
    out = release(model, data, q0, "q2", hold=hold, min_steps=HOLD_STEPS)
    assert abs(out.moved[0]) < tol, (
        f"assumption 'the elbow is rigid at {ELBOW_LOCKED} rad' releases to "
        f"{out.moved[0]:+.4f} rad, and the shoulder goes with it: the truth "
        f"model comes to rest at {np.round(out.rest, 4)} rad, not "
        f"{np.round(q0, 4)}")
    return out


def test_a_frozen_degree_of_freedom_fails_the_truth_check():
    """The teeth: the degenerate fixture must fail, and here it does.

    Every number in the locked-elbow model reproduces. Its torque is right for
    the machine it describes, its units are right, and its self-consistency
    checks — a moment arm against a lever, a Jacobian against finite
    differences — all pass, because the frozen coordinate is missing from both
    sides of each of them. Released in a model that has the coordinate, it
    falls over. That is the error class that blocked the first real project
    through this plugin, reproduced at template scale.

    Wrapped as an expected failure so the run stays green while the failure
    stays printed. Delete this check when you adapt the template and the
    package stops having a demonstration that it works.
    """
    try:
        _the_locked_elbow_check()
    except AssertionError as failure:
        print("  [PASS] the frozen-elbow fixture fails the truth check, as it "
              "must:")
        print(f"         {' '.join(str(failure).split())}")
        return
    raise AssertionError(
        "the locked-elbow fixture passed the truth check — the check cannot "
        "see a frozen degree of freedom, which is the one thing it is for")
