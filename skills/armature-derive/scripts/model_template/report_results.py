"""
report_results.py — prints what the milestone notes cite instead of pasting:
the long symbolic results, the named configurations, and 03_results.md's tables.

    python analysis/model/report_results.py

A report renderer is never a milestone module — discovery skips `report.py`
and `report_*.py` — so table formatting never inflates the files a red-team
pass reads to check the equations. A plan task's tables get a `report_<task>.py`
of their own.

**This is where a named configuration belongs, and the only place.** Home,
outstretched, the workspace corners: a reader needs a posture they can picture
beside a number, and the notes quote these. What they are not is evidence — a
named posture is a symmetry plane, which is exactly where a wrong assumption
cancels — so no check in this model draws one. The evidence is the seeded
sample the checks modules take from `truth.envelope`, and the sweep minima
printed below say what the whole envelope does, not what four postures do.
"""

import numpy as np

from params import N, SIGMA_MIN, WORKSPACE
from kinematics import J, T_EE, singular_values
from dynamics.lagrangian import G_SYM, M_SYM
from dynamics.statics import static_torques
from truth.envelope import DEFAULT_SEED, sample, sample_workspace
from verification import worst_case_static_torque

# For the reader, not for a check. Replace with your mechanism's landmarks.
NAMED = {
    "home, outstretched (q = 0)": np.zeros(N),
    "elbow up 90 deg": np.array([0.0, np.pi / 2]),
    "workspace corner, elbow-up edge": np.array([WORKSPACE[0][0], WORKSPACE[1][0]]),
    "workspace corner, elbow folded": np.array([WORKSPACE[0][1], WORKSPACE[1][1]]),
}
SWEEP = 400

print("\n01_kinematics.md")
print("  T_0_ee =", T_EE)
print("  J =", J)

print(f"\n01_kinematics.md: sigma(J_v) swept, n = {SWEEP}, seed = {DEFAULT_SEED}")
for where, Q in (("intended workspace", sample_workspace(SWEEP, DEFAULT_SEED)),
                 ("full envelope", sample(SWEEP, DEFAULT_SEED))):
    sig = singular_values(Q)
    j = int(np.argmin(sig[:, -1]))
    print(f"  {where:<20} min sigma_min {sig[j, -1]:8.4f} m/rad at "
          f"q = {np.round(Q[j], 4)}")
print(f"  the bound the derivation needs inside the workspace: {SIGMA_MIN} m/rad")

print("\n02_dynamics.md")
print("  M(q) =", M_SYM)
print("  g(q) =", G_SYM)

print("\nNamed configurations, for the reader (never the evidence)")
print(f"  {'configuration':<34}{'sigma_min [m/rad]':>18}  static tau [N m]")
for name, qv in NAMED.items():
    print(f"  {name:<34}{singular_values(qv)[0, -1]:>18.4f}  "
          f"{np.round(static_torques(qv), 3)}")

# The worst static torque anywhere in the workspace, not just at one posture.
wt, wq = worst_case_static_torque()
print("\n03_results.md: worst-case static torque over the workspace")
print(f"  {'joint':<7}{'|tau| [N m]':>12}  posture [rad]")
for j in range(N):
    print(f"  {j + 1:<7}{wt[j]:>12.3f}  {np.round(wq[j], 3)}")
