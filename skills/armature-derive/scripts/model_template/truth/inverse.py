"""
truth/inverse.py — the truth model's inverse dynamics.

What the Lagrangian is checked against. MuJoCo computes the generalised forces
from its own body tree with its own recursive algorithm, having never seen T, V
or the equations that came out of them, so a term missing from the hand
derivation has nothing on this side to hide behind.

Self-tests in inverse_checks.py.
"""

import mujoco
import numpy as np


def inverse_dynamics(model, data, q_vals, qd_vals, qdd_vals):
    """Generalised forces that produce `qdd_vals` at the state (q, qd) [N m].

    Same coordinate ordering as the parameter block, because the joints were
    added to the model in DH-row order and MuJoCo keeps them that way.

    Asserts that no constraint is active. With the joint ranges taken from
    `Q_LIMITS` a sampled configuration sits strictly inside them and MuJoCo
    adds nothing; a configuration *on* a limit would have the limit's force
    folded into the answer, and a comparison against an analytic tau that knows
    nothing about limits would then fail for the wrong reason.
    """
    data.qpos[:] = np.asarray(q_vals, dtype=float)
    data.qvel[:] = np.asarray(qd_vals, dtype=float)
    data.qacc[:] = np.asarray(qdd_vals, dtype=float)
    mujoco.mj_inverse(model, data)
    assert data.nefc == 0, (
        f"{data.nefc} constraint(s) active at q={np.round(q_vals, 4)} — a "
        f"configuration on a joint limit; sample strictly inside Q_LIMITS")
    return np.array(data.qfrc_inverse)
