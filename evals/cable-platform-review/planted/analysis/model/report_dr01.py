"""
report_dr01.py — prints the tables of docs/testing/DR-01-deck-tilt.md.

    uv run python report_dr01.py
"""

from deck import (R2_LIMIT, at_the_edge, centre_law, deck_tilt,
                  release_at_the_centre)

turned, released = release_at_the_centre()
_, centre = centre_law()
edge = at_the_edge()

print("| Quantity | Value | From |")
print("|---|---|---|")
print(f"| deck tilt at the edge midpoint, on A3 | {deck_tilt():.3f}° | "
      f"deck.deck_tilt() |")
print(f"| R-2's limit | {R2_LIMIT:g}° | spec R-2 |")
print(f"| A3 released at the room centre: largest turn | {turned:.1e}° | "
      f"test_truth_release_a3_at_the_room_centre |")
print(f"| the law's tension at the room centre, each cable | "
      f"{centre[0]:.3f} N | deck.centre_law(), (1) |")
print("| tensions at the edge midpoint, c1 to c4 | "
      + ", ".join(f"{t:.2f}" for t in edge.tension.values())
      + " N | deck.at_the_edge() |")
print()
print(released)
