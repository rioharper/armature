"""
kinematics.py — Milestone 1: forward kinematics + Jacobian + self-tests.

Mirrors 01_kinematics.md. Run standalone (`python kinematics.py`) to check
just this milestone without touching dynamics or verification — that's the
whole point of the split: a red-team pass on Milestone 1 only needs this
file plus params.py, not the full model.

Uses modified DH (Craig convention). Adapt the joint table in params.py or
the transform below if your derivation writeup uses a different convention
— but keep the structure: symbolic build -> numeric functions -> self-test.
"""

import numpy as np
import sympy as sp
from sympy import cos, sin, Matrix

from params import DH, T_TOOL, N, q, QS, SUB_Q, SUB_P


def dh_transform(alpha, a, d, theta):
    """Modified DH single-link transform (Craig, eq. 3.6)."""
    ca, sa, ct, st = cos(alpha), sin(alpha), cos(theta), sin(theta)
    return Matrix([
        [ct,      -st,      0,   a],
        [st * ca,  ct * ca, -sa, -sa * d],
        [st * sa,  ct * sa,  ca,  ca * d],
        [0,        0,        0,   1],
    ])


def forward_kinematics():
    """Returns (list of T_0_i for each link frame, T_0_ee)."""
    T = sp.eye(4)
    frames = []
    for row in DH:
        T = T * dh_transform(*row)
        frames.append(sp.trigsimp(T))
    T_ee = sp.trigsimp(T * T_TOOL)
    return frames, T_ee


def geometric_jacobian(frames, T_ee):
    """6xN geometric Jacobian of the end-effector, base frame."""
    p_ee = T_ee[:3, 3]
    cols = []
    for i, row in enumerate(DH):
        # Modified DH (Craig): joint i acts about z of frame {i}, and the
        # origin of frame {i} lies on that axis. (Standard DH would use
        # frame {i-1} here — adjust if you change conventions.)
        T_i = frames[i]
        z = T_i[:3, 2]
        p = T_i[:3, 3]
        is_prismatic = not row[3].has(q[i])   # q in d_i => prismatic
        if is_prismatic:
            Jv, Jw = z, Matrix([0, 0, 0])
        else:
            Jv, Jw = z.cross(p_ee - p), z
        cols.append(Jv.col_join(Jw))
    return sp.trigsimp(Matrix.hstack(*cols))


print("Building symbolic kinematics ...")
FRAMES, T_EE = forward_kinematics()
J = geometric_jacobian(FRAMES, T_EE)
print("  FK and Jacobian built.")

# --- numeric functions, lambdified, parameterized by params.PARAMS ---
fk_num = sp.lambdify(QS, T_EE.subs(SUB_Q).subs(SUB_P), "numpy")
J_num = sp.lambdify(QS, J.subs(SUB_Q).subs(SUB_P), "numpy")


def test_jacobian_vs_finite_difference(trials=5, h=1e-7, tol=1e-5):
    rng = np.random.default_rng(0)
    for _ in range(trials):
        qv = rng.uniform(-np.pi, np.pi, N)
        Jn = np.asarray(J_num(*qv), dtype=float)[:3, :]   # linear part
        for i in range(N):
            dq = np.zeros(N); dq[i] = h
            p1 = np.asarray(fk_num(*(qv + dq)), dtype=float)[:3, 3]
            p0 = np.asarray(fk_num(*(qv - dq)), dtype=float)[:3, 3]
            fd = (p1 - p0) / (2 * h)
            assert np.allclose(Jn[:, i], fd, atol=tol), \
                f"Jacobian col {i} mismatch at q={qv}"
    print("  [PASS] Jacobian matches finite-difference FK")


if __name__ == "__main__":
    print("Running Milestone 1 self-tests ...")
    test_jacobian_vs_finite_difference()
    print("Milestone 1 self-tests passed.\n")
    print("  T_0_ee =", T_EE)
    print("  J =", J)
