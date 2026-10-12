"""
kinematics.py — Milestone 1: forward kinematics and the geometric Jacobian.

Mirrors 01_kinematics.md; its self-tests are in kinematics_checks.py. Imports
only mechanism.py, so a red-team pass on Milestone 1 reads this file, its
checks, and the description. Check it alone: `uv run python run_all.py kinematics`.

The frames are the description's, read through the engine's symbolic view:
each body's frame is its parent's turned about its joint's home axis by the
coordinate's distance from home, the product of exponentials (Lynch and Park,
ch. 4) written as a chain of SymPy frames. No transform is typed here, so the
derivation and the truth model cannot disagree about where a joint is — and
the truth checks one file over are about what is built on the frames.
Keep the structure if the note uses another convention: symbolic build ->
numeric functions.
"""

import numpy as np
import sympy as sp
from sympy.physics.mechanics import dynamicsymbols

from mechanism import TOOL, numeric, view

# Run order and heading for `run_all.py`, which discovers this module
# by the `test_*` callables in kinematics_checks.py, not by name.
MILESTONE = (1, "Milestone 1: kinematics")

VIEW = view()
# The coordinates this milestone is written in, the variant's, in order.
Q = list(VIEW.q.values())
TOOL_BODY = {s.name: s.body for s in VIEW.description.sites}[TOOL]


def forward_kinematics():
    """T_0_ee: the tool site's position and its body's orientation in the base
    frame, as a 4x4 homogeneous transform in the coordinates."""
    p = VIEW.sites[TOOL].pos_from(VIEW.origin).to_matrix(VIEW.world)
    R = VIEW.world.dcm(VIEW.frames[TOOL_BODY])
    return sp.trigsimp(R.row_join(p).col_join(sp.Matrix([[0, 0, 0, 1]])))


def geometric_jacobian():
    """6xN geometric Jacobian of the tool site, base frame: the partial
    velocities of the site's velocity and its body's angular velocity with
    respect to each coordinate's rate.

    Read off the velocities rather than assembled column by column from
    z x (p - o), so a slide, a hinge whose axis does not pass through the
    previous origin, or a joint out of order needs no branch to get wrong.
    """
    rates = [c.diff(dynamicsymbols._t) for c in Q]
    v = VIEW.sites[TOOL].vel(VIEW.world).to_matrix(VIEW.world)
    w = VIEW.frames[TOOL_BODY].ang_vel_in(VIEW.world).to_matrix(VIEW.world)
    return sp.trigsimp(v.col_join(w).jacobian(rates))


print("Building symbolic kinematics ...")
T_EE = forward_kinematics()
J = geometric_jacobian()
print("  FK and Jacobian built.")

# --- numeric functions, lambdified, parameterized by params.PARAMS ---
fk_num = numeric(T_EE)
J_num = numeric(J)


def singular_values(configs):
    """Singular values of the position Jacobian J_v at each configuration.

    One row per configuration, largest first — so column -1 is σ_min, the
    number the singularity claim is about. J_v rather than the full 6xN J
    because J_v is the block this derivation inverts: `verification.py`'s
    least-squares IK solves on the three position residuals, and a rank J_v
    loses is a direction the end-effector cannot be driven in however well
    conditioned the angular rows look.

    σ_min is a *rate*, in m per rad of joint motion: its reciprocal is the
    joint speed and the joint force one unit of Cartesian motion or force costs
    at that posture, which is why a small one is an architecture problem rather
    than a numerical one. For this arm it is exact — det J_v = l1 l2 sin(elbow)
    — so σ_min σ_max = |l1 l2 sin(elbow)| and the elbow singularity at
    elbow = 0 is visible in the sweep rather than inferred.
    """
    return np.array([np.linalg.svd(np.asarray(J_num(*qv), dtype=float)[:3, :],
                                   compute_uv=False)
                     for qv in np.atleast_2d(np.asarray(configs, dtype=float))])
