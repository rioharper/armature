"""
report_results.py — prints what the milestone notes cite instead of pasting:
the long symbolic results, the named configurations, 03_results.md's tables,
and the drive's margins, energy and capacitance needed.

    uv run python report_results.py

A report renderer is never a milestone module — discovery skips `report.py`
and `report_*.py` — so table formatting never inflates the files a red-team
pass reads to check the equations. A plan task's tables get a `report_<task>.py`
of their own.

**This is where a named configuration belongs, and the only place.** Home,
outstretched, the workspace corners: a reader needs a posture they can picture
beside a number, and the notes quote these. What they are not is evidence — a
named posture is a symmetry plane, which is exactly where a wrong assumption
cancels — so no check in this model draws one. The evidence is the seeded
sample the checks modules draw from the engine's sampler, and each margin's
searched worst case, the table at the end, found by the same discovery
`run_all.py` runs them by.

**This is also the only place a symbolic result is simplified.** The build
never is (ADR 0012): each entry prints `trigsimp`'d where its operation count
is at most SIMPLIFY_CAP, and as the coordinates it depends on where it is
over, so the report stays readable at six joints.
"""

import numpy as np
import sympy as sp

import armature
from armature.sampler import DEFAULT_SEED

from params import SIGMA_MIN, WORKSPACE
from mechanism import COORDINATES, truth, vector
from kinematics import J, T_EE, singular_values
from dynamics.equations import G_SYM, M_SYM, q
from dynamics.statics import static_torques
from drive import capacitances, energies
from run_all import (discover_exemptions, discover_margins, exempt_row,
                     searched)

# For the reader, not for a check. Replace with your mechanism's landmarks.
LOW = np.array([WORKSPACE[c][0] for c in COORDINATES])
HIGH = np.array([WORKSPACE[c][1] for c in COORDINATES])
NAMED = {
    "home, outstretched (q = 0)": np.zeros(len(COORDINATES)),
    "elbow up 90 deg": np.array([0.0, np.pi / 2]),
    "workspace corner, elbow-up edge": LOW,
    "workspace corner, elbow folded": HIGH,
}
SWEEP = 400
# The most operations (`sympy.count_ops`) an entry may have and still print
# simplified. Every entry of this arm's M and g is under 30; a spatial 6R's
# run 8 to 16,249, and the 13 under the cap trigsimp in 19 s.
SIMPLIFY_CAP = 200


def print_entries(name, matrix):
    """Each entry of `matrix`, `trigsimp`'d where it is at most SIMPLIFY_CAP
    operations, otherwise as the coordinates it depends on."""
    for i in range(matrix.rows):
        for j in range(matrix.cols):
            at = f"{name}[{i}, {j}]" if matrix.cols > 1 else f"{name}[{i}]"
            entry, ops = matrix[i, j], sp.count_ops(matrix[i, j])
            if ops <= SIMPLIFY_CAP:
                print(f"  {at} = {sp.trigsimp(entry)}")
                continue
            depends = [str(c.func) for c in q if entry.has(c)]
            print(f"  {at}: {ops} operations, a function of "
                  f"({', '.join(depends)})")


print("\n01_kinematics.md")
print_entries("T_0_ee", T_EE)
print_entries("J", J)

# The envelope holds the elbow singularity, and a sample of it says so; the
# bound inside WORKSPACE is a margin, searched, in the table at the end.
envelope = armature.sample(truth(), SWEEP, DEFAULT_SEED)
Q = [vector(s.q) for s in envelope]
sig = singular_values(Q)
j = int(np.argmin(sig[:, -1]))
print(f"\n01_kinematics.md: sigma(J_v) over the full envelope, coordinates "
      f"{list(COORDINATES)}")
print(f"  min sigma_min {sig[j, -1]:.4f} m/rad at q = {np.round(Q[j], 4)}, "
      f"over {envelope}")
print(f"  the bound the derivation needs inside the workspace: {SIGMA_MIN} m/rad")

print("\n02_dynamics.md")
print_entries("M", M_SYM)
print_entries("g", G_SYM)

print("\nNamed configurations, for the reader (never the evidence)")
print(f"  {'configuration':<34}{'sigma_min [m/rad]':>18}  static tau [N m]")
for name, qv in NAMED.items():
    print(f"  {name:<34}{singular_values(qv)[0, -1]:>18.4f}  "
          f"{np.round(static_torques(qv), 3)}")

# Every margin the milestones declare, searched: the row a note cites, then
# the worst of each Choice combination, so a note can say which load case
# binds and by how much the others clear. The drive's are among them, one
# row per check under the drive's heading; an UNCHECKED one names the data it
# lacks and, where DRIVE_EXEMPT lets it stand, prints the reason in place of
# FAILS, as run_all.py does.
print("\nMargins: the worst case of each, searched (armature.search)")
exempt = discover_exemptions()
worsts = {}
for title, margin in discover_margins():
    worst = worsts[margin.name] = searched(margin)
    print(f"  [{title}] [EXEMPT] {exempt_row(worst, exempt[margin.name])}"
          if margin.name in exempt else f"  [{title}] {worst}")
    if len(worst.cases) > 1:
        for case in sorted(worst.cases, key=lambda c: c.value):
            choices = ", ".join(f"{k} = {v}" for k, v in case.choices.items())
            print(f"      {choices:<24}{case.value:>12.6g} {worst.unit}")

# What each written mission costs, at nominal: reported, never checked.
print("\nDrive: each written mission's energy over one run, at nominal [J]")
print(f"  {'mission':<16}{'source':>10}{'regenerated':>13}{'copper':>10}"
      f"{'per session':>14}")
for e in energies():
    session = "" if e.per_session is None else f"{e.per_session:.4g}"
    print(f"  {e.mission:<16}{e.source:>10.4g}{e.regenerated:>13.4g}"
          f"{e.copper:>10.4g}{session:>14}")

# The least capacitance each worst case of the bus's peak V needs to stay
# under its lowest trip, the number a spec buys against: reported, never
# checked. Closed form where nothing sinks below the trip; bisected otherwise.
print("\nDrive: the capacitance each worst case of the bus's peak V needs")
print(f"  {'mission':<16}{'bus':<12}{'C [mF]':>10}  {'under':<26}"
      f"{'found by':<13}{'brake pulse [J]':>15}")
for n in capacitances(worsts):
    pulse = "" if n.brake_pulse is None else f"{n.brake_pulse:.4g}"
    found = "closed form" if n.exact else "bisection"
    print(f"  {n.mission:<16}{n.drive or '':<12}{n.capacitance * 1e3:>10.4g}"
          f"  {n.against:<26}{found:<13}{pulse:>15}")
