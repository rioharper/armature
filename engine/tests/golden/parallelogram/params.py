"""
params.py — the balanced parallelogram's parameter block.

The links' lengths and masses, and the two counterweights' COMs, r1 and r3,
solved from the balance condition, so that the moment of mass is zero at
every posture:

    B1 = m1 r1 + m4 r4 + m2 a = 0,    B2 = m3 r3 + m4 c + m2 r2 = 0.

Every number is a `ledger.toml` entry's (ADR 0010), the ledger nearest this
file's folder, but r1 and r3, which are solved here from the entries.
"""

from pathlib import Path

from armature.ledger import load

LEDGER = load(path=Path(__file__).resolve().parent)

# What mechanism(p) reads, in SI: the ledger's section, and the two
# counterweights' COMs the balance condition gives. They are not inputs, so
# the ledger does not hold them, and a changed mass moves them with it.
PARAMS = LEDGER.section("mechanism")
PARAMS["r1"] = -(PARAMS["m4"] * PARAMS["r4"]
                 + PARAMS["m2"] * PARAMS["a"]) / PARAMS["m1"]
PARAMS["r3"] = -(PARAMS["m4"] * PARAMS["c"]
                 + PARAMS["m2"] * PARAMS["r2"]) / PARAMS["m3"]

# --- the drive's numbers (ADR 0006) ---
# What `drive.py`'s `drive(p)` reads, kept apart from PARAMS because the
# engine compiles PARAMS into the truth model and refuses a parameter it never
# reads. Each figure's basis is its ledger entry's. Both joints have the same
# motor, gearbox and driver.
DRIVE = LEDGER.section("drive")
