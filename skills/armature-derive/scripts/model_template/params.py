"""
params.py — Milestone 0: parameter block + symbols + generalized coordinates.

Mirrors 00_setup.md. This is the only file you should need to edit routinely:
when a design parameter changes (link length, payload, motor, ...), change it
in PARAMS and re-run run_all.py. Every other module imports from here.

If this block grows per-constant provenance and emits a `params.toml`, the
TOML is where anyone who needs a *value* looks it up; this file stays the
place for provenance, arithmetic, and generation.

Example mechanism: planar 2R arm in gravity. Replace with your robot.
"""

from math import pi

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
    "Ix1": 0.00024,  # link 1 inertia about its own long axis [kg m^2]
    "Ix2": 0.00016,  # link 2 inertia about its own long axis [kg m^2]
    "g": 9.81,      # gravitational acceleration [m/s^2]
}

# --- symbolic parameters (must mirror PARAMS keys) ---
l1, l2, lc1, lc2, m1, m2, I1, I2, Ix1, Ix2, g = symbols(
    "l1 l2 lc1 lc2 m1 m2 I1 I2 Ix1 Ix2 g", positive=True
)
PARAM_SYMS = {"l1": l1, "l2": l2, "lc1": lc1, "lc2": lc2,
              "m1": m1, "m2": m2, "I1": I1, "I2": I2,
              "Ix1": Ix1, "Ix2": Ix2, "g": g}

# --- generalized coordinates ---
N = 2
t = symbols("t")
q = Matrix([sp.Function(f"q{i+1}")(t) for i in range(N)])   # q_i(t)
qd = q.diff(t)
qdd = qd.diff(t)

# --- modified DH table: rows of (alpha_{i-1}, a_{i-1}, d_i, theta_i) ---
# Revolute joint: theta_i contains q[i]. Prismatic: d_i contains q[i].
#
# This is the serial-chain convention, and the rest of this block follows it. A
# mechanism whose own body floats — a platform on cables, a legged or a wheeled
# body — has no such table: it declares `FLOATING_BODIES` and `FLOATING_CABLES`
# here instead, dicts of the fields `truth/floating.py` names, and builds the
# floating-body model. Pick the one the machine has; the plan glossary's
# convention family has already picked it.
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
# Link inertia tensors about each COM, in the link frame. **Every axis, even
# the ones this mechanism cannot turn about.** A planar arm's dynamics see only
# Izz, so a tensor written diag(0, 0, Izz) gives the same M, C and g — but that
# zero is the planar assumption written into the parameter block, where the
# truth model, which does not make that assumption, then reads it and refuses
# to build (a rigid body needs a physical inertia). Each link here is a slender
# rod along its own x: Ixx from the rod's radius, Iyy = Izz from its length.
INERTIA = [sp.diag(Ix1, I1, I1), sp.diag(Ix2, I2, I2)]
MASSES = [m1, m2]
GRAVITY_VEC = Matrix([0, -g, 0])   # gravity in the base frame

# --- the envelope ---
# The set of configurations every claim in this derivation is checked over:
# one (lo, hi) per generalized coordinate, in rad for a revolute joint and m
# for a prismatic one. The truth model's sampler draws from exactly this, and
# the simulator model carries it as its joint ranges, so "over the envelope"
# means one thing in the notes, the checks and the simulator. Narrow it when
# Milestone 3's collision sweep finds a real joint limit; a wider envelope than
# the machine has makes every worst case pessimistic, a narrower one makes
# every one of them unproven.
Q_LIMITS = [(-pi, pi), (-2.6, 2.6)]

# The rate envelope: the fastest each coordinate is asked to move and to change
# speed, one per generalized coordinate, in rad/s and rad/s^2 (m/s and m/s^2
# for a prismatic one). These come from the spec's move classes, not from what
# the actuator happens to manage. A dynamics claim checked only at rest is a
# statics claim; these are what makes a sampled *state* rather than a sampled
# posture, and every Coriolis and inertial term lives in them.
QD_LIMITS = [3.0, 4.0]
QDD_LIMITS = [20.0, 30.0]

# Plain symbols for lambdify, shared by every downstream module so the
# numeric-function signatures stay consistent across kinematics/dynamics/
# verification.
QS = symbols(f"x0:{N}")           # posture
QDS = symbols(f"v0:{N}")          # velocity
SUB_Q = list(zip(list(qd), QDS)) + list(zip(list(q), QS))
SUB_P = [(PARAM_SYMS[k], v) for k, v in PARAMS.items()]
