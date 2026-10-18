"""
mechanism_checks.py — self-tests for mechanism.py.

The description compiles exactly, and the bob hangs where the cable carries
its weight: the closed-form rest in 00_setup.md against the truth model.
"""

from mechanism import truth
from params import PARAMS

G = 9.81  # the engine's default gravity, the bob's [m/s^2]


def test_the_description_compiles_exactly():
    m = truth()
    assert m.approximate == (), (f"the truth model is approximate: "
                                 f"{m.approximate}")
    print(f"  [PASS] the description compiles exactly: coordinates "
          f"{list(m.coordinates)}, actuators {list(m.actuators)}")


def test_truth_the_bob_hangs_where_the_cable_carries_its_weight():
    """00_setup.md (2): at rest the cable's tension is m g, so it is
    stretched m g / k and the bob sits at drop − rest − m g / k."""
    p = PARAMS
    weight = p["m"] * G
    want = p["drop"] - p["rest"] - weight / p["k"]
    rest = truth().at().settle()
    assert rest.stable and abs(rest.q["z"] - want) < 1e-6, rest
    assert abs(rest.tension["hang"] - weight) < 1e-6, rest.tension
    print(f"  [PASS] at rest z = {rest.q['z'] * 1e3:.3f} mm, closed form "
          f"{want * 1e3:.3f} mm; tension {rest.tension['hang']:.3f} N")
