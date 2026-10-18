"""
report_dr02.py — prints the tables of docs/testing/DR-02-psu-sizing.md.

    uv run python report_dr02.py
"""

from armature import search

from bus import (DRIVE_MARGINS, JOG_SPEED, JOG_STOP, bound, j11, needed,
                 peak)
from params import DRIVE

reached = peak(JOG_STOP)
returned = DRIVE["c_bus"] * (reached ** 2 - DRIVE["v_bus"] ** 2) / 2
[cap] = needed()

print("| Quantity | Value | From |")
print("|---|---|---|")
print(f"| J11 | {j11():.4f} kg m² | bus.j11(), (1) |")
print(f"| jog speed | {JOG_SPEED:g} rad/s | bus.JOG_SPEED |")
print(f"| ½ J11 ω0² | {j11() * JOG_SPEED ** 2 / 2:.4f} J | (2) |")
print(f"| returned to the bus | {returned:.4f} J | ½ C (V² − V0²) at the peak |")
print(f"| bus peak, nothing tripped | {reached:.2f} V | bus.peak(JOG_STOP) |")
print(f"| lossless bound | {bound(JOG_SPEED):.2f} V | bus.bound(), (3) |")
print(f"| lowest trip | {DRIVE['v_max']:g} V | each driver's max_voltage |")
print(f"| capacitance needed | {cap.capacitance * 1e3:.3f} mF, against "
      f"{DRIVE['c_bus'] * 1e3:g} mF fitted | bus.needed() |")
print()
for margin in DRIVE_MARGINS:
    if not margin.unchecked:
        print(search(margin))
