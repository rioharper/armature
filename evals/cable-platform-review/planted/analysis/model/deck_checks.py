"""
deck_checks.py — self-tests for deck.py.

The derivation's coordinates against its variant's, A3 released in the truth
model, the level platform held at the edge midpoint, and the deck's tilt
held to R-2.
"""

import armature

from deck import (R2_LIMIT, SLIDES, at_the_edge, deck_tilt, derived,
                  release_at_the_centre)

# A3 is kept while the release turns the deck by under a tenth of R-2's
# range: the gimbal's correction is then all R-2's [deg].
KEPT = R2_LIMIT / 10


def test_the_derivation_accounts_for_the_variants_coordinates():
    """The locked turns leave the platform's point: three slides."""
    armature.account(derived(), list(SLIDES))
    print(f"  [PASS] coordinates {list(derived().independent)}; the turns "
          f"locked by A3")


def test_truth_release_a3_at_the_room_centre():
    """A3 released: the full description, free to turn, hung at the room
    centre on the law's rest lengths there, against the level variant. Kept
    while it turns the deck by under a tenth of R-2's range."""
    turned, out = release_at_the_centre()
    assert out.settled.stable, out
    assert turned < KEPT, f"A3 turns the deck {turned:.4f} deg: {out}"
    print(f"  [PASS] {out}; largest turn {turned:.2e} deg, kept, under "
          f"{KEPT:g} deg")


def test_the_level_platform_holds_the_edge_midpoint():
    """params.py's rest lengths carry the platform at POSE: the variant
    settled from there stays, every cable taut."""
    rest = at_the_edge()
    moved = max(abs(v) for v in rest.moved.values())
    assert rest.stable and moved < 1e-6, rest
    assert min(rest.tension.values()) > 0, rest.tension
    print(f"  [PASS] the level platform rests at the edge midpoint, moved "
          f"{moved:.1e} m; tensions "
          + ", ".join(f"{c} {t:.2f} N" for c, t in rest.tension.items()))


def test_the_deck_meets_r2_at_the_edge_midpoint():
    t = deck_tilt()
    assert t <= R2_LIMIT, f"the deck tilts {t:.4g} deg, over R-2"
    print(f"  [PASS] deck tilt at the edge midpoint on A3: {t:.3f} deg, "
          f"R-2's limit {R2_LIMIT:g} deg")
