"""
report_dr01.py — prints the tables of docs/testing/DR-01-first-mode.md.

    uv run python report_dr01.py
"""

import math

from first_mode import R4_FLOOR, first_mode, modes, sag
from mechanism import truth

moved, released = sag()
rest = truth().at().settle()
f1 = first_mode()

print("| Quantity | Value | From |")
print("|---|---|---|")
print(f"| first mode on A3 | {'∞' if math.isinf(f1) else f'{f1:.4g}'} Hz | "
      f"first_mode.first_mode(), "
      f"the variant's modes {modes()} |")
print(f"| R-4's floor | {R4_FLOOR:g} Hz | spec R-4 |")
print(f"| A3 released: the bob's static sag | {moved * 1e3:.3f} mm | "
      f"test_truth_release_a3_on_the_sag |")
print(f"| the cable's tension at rest | {rest.tension['hang']:.3f} N | "
      f"the truth model, settled |")
print()
print(released)
