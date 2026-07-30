"""
Milestone 3. Round-trip IK, and the sizing assertion that makes the derivation
capable of failing rather than merely observing.
"""

import numpy as np
import pytest

pytestmark = pytest.mark.m3


def test_ik_roundtrip(ver, kin):
    rng = np.random.default_rng(0x1C3)
    for _ in range(16):
        q_true = rng.uniform(-1.0, 1.0, size=kin.N)
        target = np.asarray(kin.forward_kinematics_num(q_true), dtype=float)[:3, 3]
        q_solved = ver.inverse_kinematics(target)
        reached = np.asarray(kin.forward_kinematics_num(q_solved), dtype=float)[:3, 3]
        np.testing.assert_allclose(reached, target, rtol=1e-5, atol=1e-6)


def test_worst_case_torque_within_actuator_rating(ver, params):
    """
    The point of the whole derivation. Worst case over the workspace, not torque
    at one convenient posture — and asserted against the datasheet limit, so an
    undersized actuator turns the suite red instead of producing a paragraph
    noting that it might be a concern.
    """
    limits = getattr(params, "TAU_LIMITS", None)
    if limits is None:
        pytest.skip("params.TAU_LIMITS not defined — nothing to size against")

    margin = getattr(params, "TORQUE_MARGIN", 1.5)
    worst, postures = ver.worst_case_static_torque()

    over = [
        f"joint {i+1}: {abs(t):.3f} N*m vs {lim:.3f} N*m rated "
        f"(margin {margin}x needs {lim / margin:.3f}) at q={np.round(postures[i], 3)}"
        for i, (t, lim) in enumerate(zip(worst, limits))
        if abs(t) > lim / margin
    ]
    assert not over, "worst-case torque exceeds rating with margin:\n  " + "\n  ".join(over)
