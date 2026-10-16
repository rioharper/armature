"""
mechanism_checks.py — self-tests for mechanism.py.

What `run_all.py` runs on a golden project copied on its own: the
description compiles, exactly.
"""

from mechanism import truth


def test_the_description_compiles_exactly():
    m = truth()
    assert m.approximate == (), (f"the truth model is approximate: "
                                 f"{m.approximate}")
    print(f"  [PASS] the description compiles exactly: coordinates "
          f"{list(m.coordinates)}, actuators {list(m.actuators)}")
