"""
report_results.py — prints what the milestone notes cite instead of pasting:
the long symbolic results, the named configurations, and 03_results.md's tables.

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
"""

import numpy as np

import armature
from armature.sampler import DEFAULT_SEED

from params import SIGMA_MIN, WORKSPACE
from mechanism import COORDINATES, truth, vector
from kinematics import J, T_EE, singular_values
from dynamics.lagrangian import G_SYM, M_SYM
from dynamics.statics import static_torques
from run_all import discover_margins, searched

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

print("\n01_kinematics.md")
print("  T_0_ee =", T_EE)
print("  J =", J)

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
print("  M(q) =", M_SYM)
print("  g(q) =", G_SYM)

print("\nNamed configurations, for the reader (never the evidence)")
print(f"  {'configuration':<34}{'sigma_min [m/rad]':>18}  static tau [N m]")
for name, qv in NAMED.items():
    print(f"  {name:<34}{singular_values(qv)[0, -1]:>18.4f}  "
          f"{np.round(static_torques(qv), 3)}")

# Every margin the milestones declare, searched: the row a note cites, then
# the worst of each Choice combination, so a note can say which load case
# binds and by how much the others clear.
print("\nMargins: the worst case of each, searched (armature.search)")
for title, margin in discover_margins():
    worst = searched(margin)
    print(f"  [{title}] {worst}")
    if len(worst.cases) > 1:
        for case in sorted(worst.cases, key=lambda c: c.value):
            choices = ", ".join(f"{k} = {v}" for k, v in case.choices.items())
            print(f"      {choices:<24}{case.value:>12.6g} {worst.unit}")

