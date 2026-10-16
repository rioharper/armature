"""
params.py — the mass on a cable's parameter block.

The cable is anchored `drop` above the bob, its EA chosen so that EA / rest
is k: an elastic cable, a spring that only pulls.
"""

PARAMS = {
    "m": 0.5,       # the bob [kg]
    "k": 1000.0,    # the cable's stiffness, EA / rest [N/m]
    "drop": 1.0,    # the anchor, above the bob's home [m]
    "rest": 0.99,   # the cable's rest length [m]
}

BANDS = {}
