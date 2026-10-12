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
sample the checks modules draw from the engine's sampler, and the sweep minima
printed below say what the whole envelope does, not what four postures do.
"""

import numpy as np

import armature
from armature.sampler import DEFAULT_SEED

from params import SIGMA_MIN, WORKSPACE
from mechanism import COORDINATES, truth, vector
from kinematics import J, T_EE, singular_values
from dynamics.lagrangian import G_SYM, M_SYM
from dynamics.statics import static_torques
from verification import GRID_POINTS, N, OPT_STARTS, worst_over_load_cases

# For the reader, not for a check. Replace with your mechanism's landmarks.
LOW = np.array([WORKSPACE[c][0] for c in COORDINATES])
HIGH = np.array([WORKSPACE[c][1] for c in COORDINATES])
NAMED = {
    "home, outstretched (q = 0)": np.zeros(N),
    "elbow up 90 deg": np.array([0.0, np.pi / 2]),
    "workspace corner, elbow-up edge": LOW,
    "workspace corner, elbow folded": HIGH,
}
SWEEP = 400

print("\n01_kinematics.md")
print("  T_0_ee =", T_EE)
print("  J =", J)

print(f"\n01_kinematics.md: sigma(J_v) swept, coordinates {list(COORDINATES)}")
for where, samples in (
        ("intended workspace",
         armature.sample(truth(), SWEEP, DEFAULT_SEED, within=WORKSPACE)),
        ("full envelope", armature.sample(truth(), SWEEP, DEFAULT_SEED))):
    Q = [vector(s.q) for s in samples]
    sig = singular_values(Q)
    j = int(np.argmin(sig[:, -1]))
    print(f"  {where:<20} min sigma_min {sig[j, -1]:8.4f} m/rad at "
          f"q = {np.round(Q[j], 4)}")
    print(f"  {'':<20} {samples}")
print(f"  the bound the derivation needs inside the workspace: {SIGMA_MIN} m/rad")

print("\n02_dynamics.md")
print("  M(q) =", M_SYM)
print("  g(q) =", G_SYM)

print("\nNamed configurations, for the reader (never the evidence)")
print(f"  {'configuration':<34}{'sigma_min [m/rad]':>18}  static tau [N m]")
for name, qv in NAMED.items():
    print(f"  {name:<34}{singular_values(qv)[0, -1]:>18.4f}  "
          f"{np.round(static_torques(qv), 3)}")

# "Worst" over the workspace, by two methods, for every row of the load-case
# table — both signs of the signed one among them. The grid step is printed
# beside the numbers because it bounds what the grid alone could have missed,
# and the two methods are printed separately because a gap between them is a
# finding rather than a rounding, and the note says which way it went.
worst = worst_over_load_cases()
print("")
print("03_results.md: worst |tau| over WORKSPACE, per load case [N m]")
print(f"  grid {GRID_POINTS} points per axis, step {np.round(worst[0].step, 4)} rad;"
      f" multi-start optimiser, {OPT_STARTS} starts")
print(f"  {'load case':<11}{'class':<19}{'joint':>8}{'grid':>9}{'optimiser':>11}"
      f"{'worst':>9}  posture [rad]")
for w in worst:
    for j in range(N):
        print(f"  {w.case.name if j == 0 else '':<11}"
              f"{w.case.kind if j == 0 else '':<19}{COORDINATES[j]:>8}"
              f"{w.grid[j]:>9.3f}{w.opt[j]:>11.3f}{w.tau[j]:>9.3f}  "
              f"{np.round(w.q[j], 3)}")
