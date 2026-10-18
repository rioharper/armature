"""
skid_checks.py — self-tests for skid.py.

The pad's clearance at home against the closed form, A3's postures held to
α = 0 over the leg's lengths, and R-5 on them. The margin itself is
run_all.py's.
"""

from armature import clearance

from run_all import searched
from skid import (SKID_AT_ALPHA_ZERO, alpha, closed_form_mm, model, skid_mm,
                  standing, straight)

HOME_MM = 120.0  # 00_setup.md (1) at home: 150 + 60 − 90 mm


def test_truth_the_pad_clears_the_floor_by_the_closed_form_at_home():
    """00_setup.md (1): at home the knee B sits 150 mm above the pin C, so
    the pad clears the floor by 150 + r − r_skid."""
    got = skid_mm(0.0, 0.0)
    assert abs(got - HOME_MM) < 1e-6, got
    assert abs(clearance(standing(0.0, 0.0), "tyre")) < 1e-9
    print(f"  [PASS] the pad clears the floor by {got:.3f} mm at home, closed "
          f"form {HOME_MM:g} mm; the tyre on the floor")


def test_the_straight_postures_stand_the_leg_under_the_hips():
    """A3's postures: α = 0 at each, from the shortest leg to the
    longest, and the clearance there agrees with the closed form."""
    hips = straight()
    worst = max(abs(alpha(*h)) for h in hips)
    assert worst < 1e-9, worst
    lengths = [-model().at(q={"A": a, "E": e}).pose("C2").position[1]
               for a, e in hips]
    assert min(lengths) < 0.10 and max(lengths) > 0.25, lengths
    for h in hips[::10]:
        assert abs(skid_mm(*h) - closed_form_mm(*h)) < 1e-6, h
    print(f"  [PASS] {len(hips)} postures at α = 0 (|α| ≤ {worst:.1e} rad), "
          f"legs {min(lengths) * 1e3:.0f} to {max(lengths) * 1e3:.0f} mm")


def test_r5_holds_at_alpha_zero():
    worst = searched(SKID_AT_ALPHA_ZERO)
    assert worst.passes, worst
    print(f"  [PASS] least skid clearance at α = 0: {worst.value:.2f} mm, "
          f"R-5 met")
