"""
mechanism_checks.py — self-tests for mechanism.py.

The description compiles exactly, and the arm is balanced, A1 in
00_setup.md: at sampled postures the truth model needs no torque from either
motor to hold still.
"""

import armature
from armature.sampler import DEFAULT_SEED

from mechanism import truth

N = 24  # postures sampled for the balance


def test_the_description_compiles_exactly():
    m = truth()
    assert m.approximate == (), (f"the truth model is approximate: "
                                 f"{m.approximate}")
    print(f"  [PASS] the description compiles exactly: coordinates "
          f"{list(m.coordinates)}, actuators {list(m.actuators)}")


def test_truth_the_balanced_arm_needs_no_holding_torque():
    """00_setup.md (1): B1 = B2 = 0 leaves no gravity torque anywhere, so
    the static current A3 sizes the PSU for is zero."""
    m, worst = truth(), 0.0
    for s in armature.sample(m, N, DEFAULT_SEED):
        q = {c: s.q[c] for c in m.independent}
        torque = m.at(q=q).inverse().torque
        worst = max(worst, *(abs(t) for t in torque.values()))
    assert worst < 1e-9, f"a holding torque of {worst:.3g} N m"
    print(f"  [PASS] largest holding torque {worst:.1e} N m over n = {N} "
          f"postures, seed = {DEFAULT_SEED}")
