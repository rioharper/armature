"""
dynamics/statics.py — 02_dynamics.md §3: holding torques against gravity.

Self-tests in statics_checks.py.
"""

import numpy as np

from dynamics.lagrangian import g_num


def static_torques(q_vals):
    """Joint torques to hold posture q against gravity, g(q) of eq. (2) [N m].

    Positive about each joint's axis as the description writes it; the
    magnitude is what an actuator holds.
    """
    return np.asarray(g_num(*q_vals), dtype=float).flatten()
