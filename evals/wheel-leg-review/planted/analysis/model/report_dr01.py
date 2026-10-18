"""
report_dr01.py — prints the tables of docs/testing/DR-01-skid-clearance.md.

    uv run python report_dr01.py
"""

from armature import search

from skid import SKID_AT_ALPHA_ZERO, skid_mm, straight

worst = search(SKID_AT_ALPHA_ZERO)
ya, ye = worst.at["hips"]

print("| Quantity | Value | From |")
print("|---|---|---|")
print(f"| least skid clearance at α = 0 | {worst.value:.2f} mm | "
      f"skid.SKID_AT_ALPHA_ZERO, searched |")
print(f"| where it falls | A = {ya:.3f}, E = {ye:.3f} rad | the same |")
print(f"| postures searched at α = 0 | {len(straight())} | skid.straight() |")
print(f"| clearance at home | {skid_mm(0.0, 0.0):.2f} mm | skid.skid_mm(), "
      f"(1) |")
print()
print(worst)
