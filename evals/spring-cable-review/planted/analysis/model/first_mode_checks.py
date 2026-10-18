"""
first_mode_checks.py — self-tests for first_mode.py.

The derivation's coordinates against its variant's, A3 released in the truth
model, and the first mode held to R-4.
"""

import armature

from first_mode import R4_FLOOR, derived, first_mode, modes, sag

# The slide's travel, from mechanism.py's range on z [m]: a sag kept under a
# twentieth of it moves no posture the rig works at.
TRAVEL = 0.2
KEPT = TRAVEL / 20


def test_the_derivation_accounts_for_the_variants_coordinates():
    """The rigid cable solves z, so the derivation names no coordinate."""
    armature.account(derived(), [])
    print(f"  [PASS] coordinates {list(derived().independent)}; "
          f"z solved by the cable's closure")


def test_truth_release_a3_on_the_sag():
    """A3 released: the elastic cable lets the bob settle by m g / k. Kept
    while it stays under a twentieth of the slide's travel."""
    moved, out = sag()
    assert abs(moved) < KEPT, f"A3 moves the bob {moved * 1e3:.3f} mm: {out}"
    print(f"  [PASS] {out}; kept, under {KEPT * 1e3:.0f} mm")


def test_the_first_mode_meets_r4():
    f = first_mode()
    assert f >= R4_FLOOR, f"the first mode, {f:.4g} Hz, is under R-4"
    print(f"  [PASS] first mode on A3: {f} Hz (the variant's modes "
          f"{modes()}), R-4's floor {R4_FLOOR:g} Hz")
