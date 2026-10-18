"""
bus_checks.py — self-tests for bus.py.

J11 against the truth model's mass matrix, and the jog stop's peak against
the energy relation's bound. The drive margins themselves are run_all.py's.
"""

from armature.drive import CONFIRM_RATE, charge, trace

from bus import JOG_SPEED, JOG_STOP, bound, j11, peak
from drive import drive
from mechanism import truth
from missions import HELD
from params import DRIVE


def test_truth_j11_is_the_truth_models_inertia_about_j1():
    """DR-02 (1) against the truth model's M at home, rotors included; J11
    is the same at every posture."""
    lin = truth().at(q={"J1": 0.0, "J2": HELD}).linearise()
    i = lin.dofs.index("J1")
    assert abs(lin.mass[i][i] - j11()) < 1e-9 * j11(), (lin.mass, j11())
    print(f"  [PASS] J11 = {j11():.5f} kg m², the truth model's "
          f"{lin.mass[i][i]:.5f}")


def test_truth_the_jog_stop_lifts_the_bus_under_its_bound():
    """The jog stop's peak, nothing tripped, sits under (3)'s lossless
    bound and within 3 % of it: the copper loss is all that separates
    them."""
    reached, most = peak(JOG_STOP), bound(JOG_SPEED)
    assert DRIVE["v_bus"] < reached <= most, (reached, most)
    assert reached > 0.97 * most, (reached, most)
    print(f"  [PASS] the jog e-stop lifts the bus to {reached:.2f} V, "
          f"under the lossless {most:.2f} V")


def test_the_jog_stop_trips_nothing_on_the_psu():
    tripped = charge(trace(truth(), JOG_STOP, CONFIRM_RATE), drive()).tripped
    assert not tripped, tripped
    print("  [PASS] the jog e-stop trips nothing")
