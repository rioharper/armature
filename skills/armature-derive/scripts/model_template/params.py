"""
params.py — Milestone 0: the parameter block, the intended workspace, the rate
envelope and the load cases.

Mirrors 00_setup.md's parameter table. This is the file to edit routinely:
when a design parameter changes (link length, payload, motor, ...), change it
in PARAMS and re-run run_all.py. The geometry those numbers build is
`mechanism.py`'s; the joint envelope is its joint ranges, and the symbols the
derivation works in are generated from PARAMS' keys, so each name is written
once.

If this block grows per-constant provenance and emits a `params.toml`, the
TOML is where anyone who needs a *value* looks it up; this file stays the
place for provenance, arithmetic, and generation. Standard library only, so a
CAD part file can read a mass target from it without the model's environment.

Example mechanism: planar 2R arm in gravity. Replace with your robot.
"""

from collections import namedtuple

# Run order and heading for `run_all.py`: the parameter block is Milestone 0
# and sorts first, so a load-case table that has lost a sign fails before any
# milestone that sizes against it runs. Self-tests in params_checks.py.
MILESTONE = (0, "Milestone 0: parameter block")

# --- numeric values (SI units) ---
# Exactly what mechanism(p) reads: the engine refuses a parameter defined and
# never used, as it refuses one used and never defined, naming it.
PARAMS = {
    "l1": 0.30,     # link 1 length [m]
    "l2": 0.25,     # link 2 length [m]
    "lc1": 0.15,    # link 1 COM distance from joint 1 [m]
    "lc2": 0.125,   # link 2 COM distance from joint 2 [m]
    "m1": 1.20,     # link 1 mass [kg]
    "m2": 0.80,     # link 2 mass, bare link — the payload is a tip load below [kg]
    "I1": 0.012,    # link 1 inertia about its COM, z-axis [kg m^2]
    "I2": 0.006,    # link 2 inertia about its COM, z-axis [kg m^2]
    "Ix1": 0.00024,  # link 1 inertia about its own long axis [kg m^2]
    "Ix2": 0.00016,  # link 2 inertia about its own long axis [kg m^2]
    "g": 9.81,      # gravitational acceleration [m/s^2]
    # Each motor's continuous torque, derated: the limit every holding margin
    # is slack against, and what the truth model's settle clamps a command to
    # [N m, motor side]. The derating, and its reason, is the spec's.
    "tau1": 15.0,   # shoulder motor
    "tau2": 6.0,    # elbow motor
}

# --- the drive's numbers (ADR 0006) ---
# What `drive.py`'s `drive(p)` reads, kept apart from PARAMS because the
# engine compiles PARAMS into the truth model and refuses a parameter it never
# reads. Every constant carries its **basis** in its comment, as the datasheet
# states it, and `drive.py` hands that basis to the engine as a keyword: a
# torque constant per A_rms and one per A_peak are 22 % apart, and a
# resistance line to line is twice a wye's per phase. A datum the datasheet
# does not give is left out, not guessed: the margin that needs it then reads
# UNCHECKED and fails, unless `drive.py`'s DRIVE_EXEMPT argues why it may not.
#
# Both motors are direct drive, so a motor's torque is its joint's and tau1,
# tau2 above are their derated continuous torques: `drive_checks.py` holds
# them to what each winding's thermal data supports.
DRIVE = {
    "kv1": 8.0,         # shoulder: rpm per volt, line-to-line peak back-EMF
    "ke1": 88.4,        # shoulder: V_rms/krpm, line to line
    "r1": 0.20,         # shoulder: ohm, line to line at 25 C, wye
    "rth1": 1.2,        # shoulder: winding to ambient, K/W
    "cth1": 300.0,      # shoulder: winding, J/K
    "kv2": 20.0,        # elbow: rpm per volt, line-to-line peak back-EMF
    "ke2": 35.4,        # elbow: V_rms/krpm, line to line
    "r2": 0.25,         # elbow: ohm, line to line at 25 C, wye
    "rth2": 1.2,        # elbow: winding to ambient, K/W
    "cth2": 150.0,      # elbow: winding, J/K
    "t_max": 120.0,     # winding limit, both motors [C]
    "t_ambient": 40.0,  # the hottest ambient the spec allows [C]
    "eta_driver": 0.95,  # each driver, constant, both directions of flow
    "i_peak": 40.0,     # each driver's peak, A_peak line
    "i_cont": 20.0,     # each driver's continuous, A_rms line
    "v_max": 56.0,      # each driver's overvoltage trip [V]
    "v_under": 40.0,    # each driver's undervoltage trip [V]
    "v_bus": 48.0,      # the source's set point, a PSU behind a diode [V]
    "p_source": 600.0,  # the source's rating [W]
    "c_bus": 10e-3,     # the bus capacitance, the bank's rating [F]
    "hotel": 5.0,       # the electronics' constant draw [W]
}

# The **tolerance bands**: each parameter the design does not know to better
# than a range, as (lo, hi) around its nominal, in the parameter's units. A
# margin searches each one as an axis (`Band`) with both ends among its
# corners, so a worst case is stated at its worst band value and never at
# nominal alone. The forearm's mass is a budget until CAD measures the part,
# and +-10 % is what the budget is held to. The bus's two are DRIVE's, which
# `drive(p)` reads at each band value: an electrolytic bank is +-20 %, and the
# source's set point +-2 %; the least capacitance on the highest source is
# where regeneration lifts the bus furthest. A band is a PARAMS key or a DRIVE
# key, and `params_checks.py` fails one that names neither or leaves its
# nominal outside.
BANDS = {
    "m2": (0.72, 0.88),
    "c_bus": (8e-3, 12e-3),
    "v_bus": (47.0, 49.0),
}

# The **intended workspace**: the subset of the envelope the machine is
# actually required to work in, and the only region where the derivation is
# entitled to assume full rank. One (lo, hi) per coordinate the derivation
# keeps, keyed by the description's joint name, in rad for a hinge and m for a
# slide. It is a second box because the envelope (`mechanism.py`'s joint
# ranges) is what the joints can reach and the workspace is what the
# requirements ask for, and the gap between them is where the singularities are
# allowed to live. This 2R arm's position Jacobian has determinant
# l1 l2 sin(elbow), so it loses rank at elbow = 0 — an elbow singularity
# sitting squarely inside the envelope — and the machine is committed to the
# elbow-up branch to stay off it. Name yours from the requirement, not from
# what happens to be non-singular. Strictly inside the joint ranges on every
# coordinate, including the ones with no singularity in them: a worst case
# found *on* a joint limit is a worst case the limit is carrying, and the truth
# model's settle names the limit among the constraints holding it there.
WORKSPACE = {"shoulder": (-3.0, 3.0), "elbow": (0.30, 2.50)}

# The smallest singular value the position Jacobian must keep everywhere in
# WORKSPACE [m/rad]. Not a tolerance: it is the worst end-effector speed one
# rad/s of joint motion can buy, so its reciprocal is the joint speed and the
# joint torque a unit of Cartesian motion or force costs at the worst posture.
# The bound below is 0.037 at the elbow-up edge elbow = 0.30, rounded down.
SIGMA_MIN = 0.035

# The rate envelope: the fastest each degree of freedom is asked to move and
# to change speed, keyed by the truth model's dof names (a floating body's
# `f:x` ... `f:rz`; a hinge's is its joint's name), in rad/s and rad/s^2 (m/s
# and m/s^2 for a slide). These come from the spec's move classes, not from
# what the actuator happens to manage. A dynamics claim checked only at rest is
# a statics claim; these are what makes a sampled *state* rather than a sampled
# posture, and every Coriolis and inertial term lives in them.
QD_LIMITS = {"shoulder": 3.0, "elbow": 4.0}
QDD_LIMITS = {"shoulder": 20.0, "elbow": 30.0}

# --- load cases ---
# Every load the actuators are sized against, as a **table** rather than a
# sentence: one row per (class, magnitude, direction set, sign), and **both
# signs of every signed row spelled out**. A signed case written once and read
# in one sign is how a design gets sized against the gentler half of its own
# requirement — a 0.5 g deceleration read as upward when downward is the case
# that binds, a cable pull read inboard when outboard is the one that lifts a
# foot. The reading is not left to whoever runs the search: the row exists or
# the case was not considered, and `params_checks.py` fails a signed class with
# only one sign in the table.
#
# `direction` is a **set**, not a direction: a unit vector in the base frame
# where the load has one, or `PLANE_XY` where the requirement says "from any
# direction in the plane". A set is answered exactly — the worst tip force over
# the unit circle is the norm of the Jacobian column projected onto it — and
# never by trying a handful of headings.
LoadCase = namedtuple("LoadCase", "name kind magnitude direction sign")

PLANE_XY = "any-in-plane"       # the unit circle in the base frame's xy plane

M_PAYLOAD = 0.50     # payload carried at the tool site, not in m2 [kg]
A_BASE = 0.5         # worst base acceleration the spec's move classes reach [g]
F_CONTACT = 15.0     # worst contact force at the tool, any heading [N]

LOAD_CASES = [
    LoadCase("hold", "static", 0.0, (0.0, 0.0, 0.0), 0),
    LoadCase("payload", "carried mass", M_PAYLOAD * PARAMS["g"],
             (0.0, -1.0, 0.0), 0),
    LoadCase("brake +x", "base acceleration",
             M_PAYLOAD * A_BASE * PARAMS["g"], (1.0, 0.0, 0.0), +1),
    LoadCase("brake -x", "base acceleration",
             M_PAYLOAD * A_BASE * PARAMS["g"], (1.0, 0.0, 0.0), -1),
    LoadCase("contact", "contact force", F_CONTACT, PLANE_XY, 0),
]
