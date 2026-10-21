"""
params.py — the wheel leg's parameter block: a five-bar leg on a wheel.

The leg's five points at home in the torso's frame, its four links, the
torso, the wheel and the gears. Every number is a `ledger.toml` entry's (ADR
0010), the ledger nearest this file's folder, and POINTS and LINKS are read
from its entries, so each point and link is written once.
"""

from pathlib import Path

from armature.ledger import load

LEDGER = load(path=Path(__file__).resolve().parent)

# Exactly what mechanism(p) reads, in SI: each point's x and y, each link's
# mass and inertia, then the torso, the wheel and the gears.
PARAMS = LEDGER.section("mechanism")

# The leg's points and links, keyed as the description names them: a point
# is its (x, y) [m], a link its (from, to, mass [kg], Izz [kg m^2]).
POINTS = {k: (PARAMS[f"{k}x"], PARAMS[f"{k}y"]) for k in "ABCED"}
ENDS = {"l1": ("A", "B"), "l2": ("B", "C"), "l3": ("E", "D"),
        "l4": ("D", "C")}
LINKS = {name: (*ends, PARAMS[f"m_{name}"], PARAMS[f"I_{name}"])
         for name, ends in ENDS.items()}

PART = {k: LEDGER.section(f"part.{k}") for k in ("leg", "torso", "skid-pad")}
COM_AT = PART["leg"]["com-at"]    # each link's COM, as a fraction from its
                                  # first point
TORSO_COM = PART["torso"]["com"]  # in the torso's frame [m]
PUSH_AT = PART["torso"]["push"]   # where the torso's site loads act [m]

# The hips' working range [rad]: a box inside their joint ranges, over which
# the loop closes everywhere.
REQ = LEDGER.section("req")
WORKSPACE = {"A": (REQ["REQ-001"], REQ["REQ-002"]),
             "E": (REQ["REQ-003"], REQ["REQ-004"])}
# The radius of a skid pad round the knee B [m]. The description carries no
# pad; the variant that adds one reads this.
R_SKID = PART["skid-pad"]["radius"]
