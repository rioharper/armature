"""
params.py — the coarse 2R arm's parameter block, as spec §9 writes it.

It reads the template's own `ledger.toml`, the numbers the derived arm reads,
so nothing here is copied. PARAMS are what the coarse description reads: each
link's length, radius and mass, and the motors' derated torques. A project at
the spec stage has a mechanism section holding exactly these; the template's
is the derived arm's, so this block takes the entries it shares, and the
radii, which the derived arm states as inertias, from each link's part
entries. The rest has the template's structure: the drive section, the
workspace, the rate envelope and the contact force, since the same `drive.py`
and `missions.py` run on both.
"""

from pathlib import Path

from armature.ledger import load

LEDGER = load(path=Path(__file__).resolve().parent)
MECHANISM = LEDGER.section("mechanism")

PARAMS = {**{k: MECHANISM[k]
             for k in ("l1", "l2", "m1", "m2", "g", "tau1", "tau2")},
          "radius1": LEDGER.section("part.upper-link")["radius"],
          "radius2": LEDGER.section("part.fore-link")["radius"]}
DRIVE = LEDGER.section("drive")
REQ = LEDGER.section("req")

WORKSPACE = {"shoulder": (REQ["REQ-004"], REQ["REQ-005"]),
             "elbow": (REQ["REQ-006"], REQ["REQ-007"])}
QD_LIMITS = {"shoulder": REQ["REQ-008"], "elbow": REQ["REQ-009"]}
QDD_LIMITS = {"shoulder": REQ["REQ-010"], "elbow": REQ["REQ-011"]}
F_CONTACT = REQ["REQ-003"]  # the fixture's push back on the tool, pressing
