"""
params.py — Milestone 0: parameter block + symbols + generalized coordinates.

Mirrors 00_setup.md. This is the only file you should need to edit routinely:
when a design parameter changes (link length, payload, motor, ...), change it
in PARAMS and re-run run_all.py. Every other module imports from here.

Example mechanism: planar 2R arm in gravity. Replace with your robot.
"""

import sympy as sp
from sympy import Matrix, symbols

# --- numeric values (SI units) ---
PARAMS = {
    "l1": 0.30,     # link 1 length [m]
    "l2": 0.25,     # link 2 length [m]
    "lc1": 0.15,    # link 1 COM distance from joint 1 [m]
    "lc2": 0.125,   # link 2 COM distance from joint 2 [m]
    "m1": 1.20,     # link 1 mass [kg]
    "m2": 0.80,     # link 2 mass (include payload here or add m_p) [kg]
    "I1": 0.012,    # link 1 inertia about its COM, z-axis [kg m^2]
    "I2": 0.006,    # link 2 inertia about its COM, z-axis [kg m^2]
    "g": 9.81,      # gravitational acceleration [m/s^2]
}

# --- symbolic parameters (must mirror PARAMS keys) ---
l1, l2, lc1, lc2, m1, m2, I1, I2, g = symbols(
    "l1 l2 lc1 lc2 m1 m2 I1 I2 g", positive=True
)
PARAM_SYMS = {"l1": l1, "l2": l2, "lc1": lc1, "lc2": lc2,
              "m1": m1, "m2": m2, "I1": I1, "I2": I2, "g": g}

# --- generalized coordinates ---
N = 2
t = symbols("t")
q = Matrix([sp.Function(f"q{i+1}")(t) for i in range(N)])   # q_i(t)
qd = q.diff(t)
qdd = qd.diff(t)

# --- modified DH table: rows of (alpha_{i-1}, a_{i-1}, d_i, theta_i) ---
# Revolute joint: theta_i contains q[i]. Prismatic: d_i contains q[i].
DH = [
    (0, 0,  0, q[0]),
    (0, l1, 0, q[1]),
]
# Transform from the last joint frame to the end-effector / tool frame:
T_TOOL = Matrix([[1, 0, 0, l2],
                 [0, 1, 0, 0],
                 [0, 0, 1, 0],
                 [0, 0, 0, 1]])

# COM of each link, expressed in that link's own frame:
COM_LOCAL = [Matrix([lc1, 0, 0]), Matrix([lc2, 0, 0])]
# Link inertia tensors about each COM, in the link frame (here: planar,
# only Izz matters). Use full 3x3 tensors for spatial mechanisms.
INERTIA = [sp.diag(0, 0, I1), sp.diag(0, 0, I2)]
MASSES = [m1, m2]
GRAVITY_VEC = Matrix([0, -g, 0])   # gravity in the base frame

# Plain symbols for lambdify, shared by every downstream module so the
# numeric-function signatures stay consistent across kinematics/dynamics/
# verification.
QS = symbols(f"x0:{N}")           # posture
QDS = symbols(f"v0:{N}")          # velocity
SUB_Q = list(zip(list(qd), QDS)) + list(zip(list(q), QS))
SUB_P = [(PARAM_SYMS[k], v) for k, v in PARAMS.items()]
