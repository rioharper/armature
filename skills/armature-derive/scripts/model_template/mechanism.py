"""
mechanism.py — Milestone 0: the mechanism description, the one place this
machine's geometry is written down.

Mirrors 00_setup.md's system description and frame table. `mechanism(p)` lists
the engine's typed elements, every number in the base frame at the home
posture (ADR 0003): a joint is an axis direction and a point on it, a COM or a
site is a position, an inertia is a full tensor in base axes. Check each one
against the spec's sketch directly; there are no transforms to chain.

Both sides read it. Called with floats, the engine compiles it into the truth
model; called with symbols, it is the derivation's frames and points. So a
frame is written once and cannot drift — and an error in it is common-mode,
which is why it gets checks of its own: validation when it compiles, and the
review artifact `report_truth.py` prints for the red team.

Example mechanism: a planar 2R arm in gravity, both links along +x at home.
Replace with your robot. Self-tests in mechanism_checks.py.
"""

import functools
import math

import numpy as np

import armature
from armature import actuator, body, gravity, joint, site

from params import LEDGER, PARAMS

# The mechanism's tolerance bands: its ledger section's, which compile into
# the truth model. A band on a drive number is the drive margins' own
# (`drive.py`), and the derivation never sees it.
BANDS = LEDGER.bands("mechanism")
# Run order and heading for `run_all.py`. Milestone 0, beside the parameter
# block it reads.
MILESTONE = (0, "Milestone 0: the mechanism description")

# The site every end-effector claim is about.
TOOL = "tip"


def mechanism(p):
    """The 2R arm. Gravity along -y, so the arm swings in the xy plane.

    Each link's inertia is one tensor, about its COM in base axes, as the
    ledger states it and CAD writes it back. It is a slender rod's **on every
    axis**, even the ones a planar arm cannot turn about: diag(0, 0, Izz)
    gives a planar derivation the same M, C and g, but that zero is the
    planar assumption written into the description, and the truth model,
    which does not make it, refuses a body with no inertia about an axis.

    The joint ranges are the envelope: the configurations every claim is checked
    over, and what the truth model carries as its joint limits. The elbow's is
    the whole turn because its stops are not set yet — Milestone 3's collision
    sweep is what finds where they belong, and then this range narrows.
    """
    return [
        body("upper", mass=p["m1"], com=(p["lc1"], 0, 0), inertia=p["I1"]),
        body("fore", mass=p["m2"], com=(p["l1"] + p["lc2"], 0, 0),
             inertia=p["I2"]),
        joint("shoulder", "hinge", parent="world", child="upper",
              axis=(0, 0, 1), point=(0, 0, 0), range=(-math.pi, math.pi)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 0, 1),
              point=(p["l1"], 0, 0), range=(-math.pi, math.pi)),
        # The elbow pin's seat on the upper link: armature-cad's sweep carries
        # link 1's envelope on it, as it carries link 2's on the tool.
        site("elbow_pin", body="upper", pos=(p["l1"], 0, 0)),
        site(TOOL, body="fore", pos=(p["l1"] + p["l2"], 0, 0)),
        # Direct drive, so a motor's torque is its joint's. A geared motor
        # takes gear= and rotor_inertia=, and the derivation then adds the
        # reflected N^2 J to M itself: the symbolic view carries no rotors.
        # torque_limit is the motor's derated rating; a settle clamps there.
        actuator("shoulder_motor", joint="shoulder", torque_limit=p["tau1"]),
        actuator("elbow_motor", joint="elbow", torque_limit=p["tau2"]),
        gravity((0, -p["g"], 0)),
    ]


# The variant the derivation reads: the description reduced by each
# simplification 00_setup.md numbers, every reduction carrying its assumption.
# This arm's derivation makes none, so it reads the description whole. A
# platform assumed level would read
#
#     DERIVED = armature.reduce(mechanism,
#                               lock("platform:rx", 0.0, assumption="A2"),
#                               lock("platform:ry", 0.0, assumption="A2"),
#                               name="level platform")
#
# and each reduction then gets a release check (mechanism_checks.py shows one
# failing). The truth model always compiles the full description.
DERIVED = mechanism


@functools.cache
def truth():
    """The truth model: the full description, compiled. Every truth check
    queries a state of it, `truth().at(q={...})`."""
    return armature.compile(mechanism, PARAMS)


@functools.cache
def derived():
    """The variant the derivation reads, compiled: what the coordinate
    accounting holds the derivation's coordinates against."""
    return armature.compile(DERIVED, PARAMS)


@functools.cache
def view():
    """The derivation's frames, points, masses and dyadics: the symbolic view
    of `DERIVED`, as functions of its coordinates."""
    return armature.symbolic(DERIVED, PARAMS)


@functools.cache
def equations():
    """M q̈ + C q̇ + g = τ of `DERIVED`, formed by the engine on the view
    (`armature.equations`, ADR 0012), BANDS kept as keywords: what
    dynamics/equations.py adds this machine's rotors to, and whose `numeric`
    every numeric function here is."""
    return armature.equations(DERIVED, PARAMS, BANDS)


# The derivation's coordinates, in the order every numeric function below takes
# them. The names are the description's joints: `s.q["elbow"]` on the truth
# side is the `elbow(t)` in the equations.
COORDINATES = view().coordinates


def numeric(expr, rates=False):
    """`expr`, written in the view's coordinates (and their rates), as a NumPy
    function of the coordinates' values in COORDINATES order — then the rates',
    when `rates` — with PARAMS substituted for the parameters. A parameter
    with a tolerance band in BANDS stays a keyword, at its nominal unless
    given, so a margin evaluates the derivation at the band value its truth
    model was compiled with: `g_num(*q, m2=0.88)`. The engine's, which swaps
    by `xreplace` and lambdifies with `cse=True`."""
    return equations().numeric(expr, rates)


def bands():
    """A `Band` axis for every parameter in BANDS, named for it: spread into
    a margin's space, `Space(**bands(), state=...)`, so every band is
    searched, with both its ends among the corners."""
    return {k: armature.Band(k, BANDS) for k in BANDS}


def band_values(p):
    """A search point's value of every banded parameter, by name: what the
    numeric functions take as keywords."""
    return {k: p[k] for k in BANDS}


def vector(mapping):
    """A state's values (`s.q`, `s.qd`, or a sample's accelerations), keyed by
    name, as an array in COORDINATES order: what the numeric functions take."""
    return np.array([float(mapping[c]) for c in COORDINATES])


def named(values):
    """Values in COORDINATES order, keyed by name: what `at()` takes."""
    return dict(zip(COORDINATES, (float(v) for v in values)))


def commands(torques, compiled=None):
    """Joint torques, keyed by coordinate, as the actuators' commands: what
    `settle` and `release` hold on `compiled` (default: the truth model). Each
    actuator supplies its joint's torque over its gear."""
    compiled = compiled or truth()
    return {a.name: float(torques[a.joint]) / float(a.gear)
            for a in compiled.description.actuators}
