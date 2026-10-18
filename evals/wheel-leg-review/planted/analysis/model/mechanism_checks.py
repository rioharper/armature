"""
mechanism_checks.py — self-tests for mechanism.py.

The description compiles exactly, and standing on its tyre the leg puts the
weight of everything but the rail cart on the floor: the closed form in
00_setup.md against the truth model.
"""

from mechanism import truth
from params import LINKS, PARAMS

CARRIED = ["m_torso", "m_wheel"] + [f"m_{k}" for k in LINKS]


def test_the_description_compiles_exactly():
    m = truth()
    assert m.approximate == (), (f"the truth model is approximate: "
                                 f"{m.approximate}")
    print(f"  [PASS] the description compiles exactly: coordinates "
          f"{list(m.coordinates)}, actuators {list(m.actuators)}")


def test_truth_the_tyre_carries_the_weight():
    """00_setup.md (2): at home, the hub on the floor, the tyre's normal
    load is g times every mass but the rail cart's."""
    want = PARAMS["g"] * sum(PARAMS[m] for m in CARRIED)
    tyre = truth().at().inverse().contacts["tyre"]
    assert abs(tyre.normal - want) < 1e-9, (tyre.normal, want)
    print(f"  [PASS] the tyre carries {tyre.normal:.3f} N at home, closed "
          f"form {want:.3f} N")
