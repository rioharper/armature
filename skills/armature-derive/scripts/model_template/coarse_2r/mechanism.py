"""
mechanism.py — the 2R arm as spec §9 describes it, before derive: coarse.

A spec-stage description (ADR 0007). Each link is an `armature.coarse`
cylinder, its mass, COM and inertia from its length, radius and mass, so the
spec's sketch and its mass budget are the whole of what it needs. Derive
refines this same file in place, body by body, into the template's
`mechanism.py`; the joints, sites and actuators around the bodies do not
change, and neither do `drive.py` and `missions.py`, which read only
`mechanism`, `truth`, `TOOL` and `BANDS`.

The template's own tests run it: `test_spec_stage.py` copies it, with this
directory's `params.py` and the template's ledger, beside the drive and the
missions, and runs `run_all.py` there. Delete this directory when you adapt
the template.
"""

import functools
import math

import armature
from armature import actuator, gravity, joint, site
from armature.coarse import cylinder

from params import LEDGER, PARAMS

TOOL = "tip"

# The mechanism's tolerance bands, the ledger's on PARAMS; the drive
# section's are drive.py's.
BANDS = {k: band for k, band in LEDGER.bands("mechanism").items()
         if k in PARAMS}


def mechanism(p):
    """The 2R arm, both links along +x at home, gravity along -y."""
    return [
        cylinder("upper", start=(0, 0, 0), end=(p["l1"], 0, 0),
                 radius=p["radius1"], mass=p["m1"]),
        cylinder("fore", start=(p["l1"], 0, 0), end=(p["l1"] + p["l2"], 0, 0),
                 radius=p["radius2"], mass=p["m2"]),
        joint("shoulder", "hinge", parent="world", child="upper",
              axis=(0, 0, 1), point=(0, 0, 0), range=(-math.pi, math.pi)),
        joint("elbow", "hinge", parent="upper", child="fore", axis=(0, 0, 1),
              point=(p["l1"], 0, 0), range=(-math.pi, math.pi)),
        site(TOOL, body="fore", pos=(p["l1"] + p["l2"], 0, 0)),
        actuator("shoulder_motor", joint="shoulder", torque_limit=p["tau1"]),
        actuator("elbow_motor", joint="elbow", torque_limit=p["tau2"]),
        gravity((0, -p["g"], 0)),
    ]


@functools.cache
def truth():
    """The truth model: the coarse description, compiled."""
    return armature.compile(mechanism, PARAMS)
