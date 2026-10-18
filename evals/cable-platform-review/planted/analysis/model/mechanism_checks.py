"""
mechanism_checks.py — self-tests for mechanism.py.

The description compiles exactly, and hung at the room centre on the law's
rest lengths there the platform carries its weight on four equal tensions:
the closed form in 00_setup.md against the truth model.
"""

import numpy as np

import armature

from deck import centre_law
from mechanism import mechanism, truth
from params import HOME, PARAMS


def test_the_description_compiles_exactly():
    m = truth()
    assert m.approximate == (), (f"the truth model is approximate: "
                                 f"{m.approximate}")
    print(f"  [PASS] the description compiles exactly: coordinates "
          f"{list(m.coordinates)}, actuators {list(m.actuators)}")


def test_truth_the_centre_hangs_on_four_equal_tensions():
    """00_setup.md (1): at the room centre each cable carries
    T = m g L / 4h, and the platform rests where it was hung."""
    params, want = centre_law(PARAMS["m"])
    rest = armature.compile(mechanism, params).at(
        q={"hang": (HOME, np.eye(3))}).settle()
    moved = np.linalg.norm(rest.q["hang"].position - HOME)
    assert rest.stable and moved < 1e-6, rest
    got = np.array(list(rest.tension.values()))
    assert np.allclose(got, want, rtol=1e-6), (got, want)
    print(f"  [PASS] at the room centre each cable carries {got[0]:.3f} N, "
          f"closed form {want[0]:.3f} N; moved {moved:.1e} m")
