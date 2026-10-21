"""
params.py — Milestone 0: the parameter block, the intended workspace, the rate
envelope and the load cases.

Mirrors 00_setup.md's parameter table. Every number here is a `ledger.toml`
entry's (ADR 0010), and this file holds only the structure around them: which
section the description and the drive read, the workspace and the rate limits
keyed to joints, and the load-case table. When a design parameter changes
(link length, payload, motor, ...), change its entry in the ledger and re-run
run_all.py. The geometry those numbers build is `mechanism.py`'s; the joint
envelope is its joint ranges, and the symbols the derivation works in are
generated from the section's keys, so each name is written once.

The ledger is the nearest `ledger.toml` at or above this file's folder: the
project's, at its root. `params_checks.py` fails a number written here.

Example mechanism: planar 2R arm in gravity. Replace with your robot.
"""

from collections import namedtuple
from pathlib import Path

from armature.ledger import load

# Run order and heading for `run_all.py`: the parameter block is Milestone 0
# and sorts first, so a load-case table that has lost a sign fails before any
# milestone that sizes against it runs. Self-tests in params_checks.py.
MILESTONE = (0, "Milestone 0: parameter block")

LEDGER = load(path=Path(__file__).resolve().parent)

# Exactly what mechanism(p) reads, in SI: the engine refuses a parameter
# defined and never used, as it refuses one used and never defined, naming
# it. Each link's inertia is one tensor about its COM, in base axes.
PARAMS = LEDGER.section("mechanism")

# The drive's numbers (ADR 0006), what `drive.py`'s `drive(p)` reads, kept
# apart from PARAMS because the engine compiles PARAMS into the truth model
# and refuses a parameter it never reads. Each is SI, and each datasheet
# figure's **basis** is its entry's: `drive.py` hands that basis to the engine
# as a keyword, because a torque constant per A_rms and one per A_peak are
# 22 % apart, and a resistance line to line is twice a wye's per phase.
DRIVE = LEDGER.section("drive")

# The requirements' thresholds, keyed by REQ id.
REQ = LEDGER.section("req")

# The **tolerance bands** are the ledger's: each entry the design does not
# know to better than a range carries `band = [lo, hi]`, and a margin searches
# it as an axis (`Band`) with both ends among its corners, so a worst case is
# stated at its worst band value and never at nominal alone. `mechanism.py`
# reads the mechanism section's, `drive.py` the drive section's.

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
WORKSPACE = {"shoulder": (REQ["REQ-004"], REQ["REQ-005"]),
             "elbow": (REQ["REQ-006"], REQ["REQ-007"])}

# The smallest singular value the position Jacobian must keep everywhere in
# WORKSPACE [m/rad]. Not a tolerance: it is the worst end-effector speed one
# rad/s of joint motion can buy, so its reciprocal is the joint speed and the
# joint torque a unit of Cartesian motion or force costs at the worst posture.
SIGMA_MIN = REQ["REQ-012"]

# The rate envelope: the fastest each degree of freedom is asked to move and
# to change speed, keyed by the truth model's dof names (a floating body's
# `f:x` ... `f:rz`; a hinge's is its joint's name), in rad/s and rad/s^2 (m/s
# and m/s^2 for a slide). These come from the spec's move classes, not from
# what the actuator happens to manage. A dynamics claim checked only at rest is
# a statics claim; these are what makes a sampled *state* rather than a sampled
# posture, and every Coriolis and inertial term lives in them.
QD_LIMITS = {"shoulder": REQ["REQ-008"], "elbow": REQ["REQ-009"]}
QDD_LIMITS = {"shoulder": REQ["REQ-010"], "elbow": REQ["REQ-011"]}

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

M_PAYLOAD = REQ["REQ-001"]      # payload carried at the tool site, not in m2
A_BASE = REQ["REQ-002"]         # worst base acceleration, in g
F_CONTACT = REQ["REQ-003"]      # worst contact force at the tool, any heading

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
