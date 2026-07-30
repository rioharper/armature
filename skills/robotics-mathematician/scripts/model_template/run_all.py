"""
run_all.py — runs every milestone's self-tests in order, end to end.

Use this for the final "is the whole model internally consistent" check
after Milestone 3. During development, prefer running kinematics.py,
dynamics.py, or verification.py standalone so a check on one milestone
doesn't require re-importing (and re-building the symbolic model for)
the others.

    python run_all.py
"""

import numpy as np

import kinematics
import dynamics
import verification

if __name__ == "__main__":
    print("=== Milestone 1: kinematics ===")
    kinematics.test_jacobian_vs_finite_difference()

    print("\n=== Milestone 2: dynamics ===")
    dynamics.test_mass_matrix_properties()
    dynamics.test_skew_symmetry()
    dynamics.test_energy_conservation()

    print("\n=== Milestone 3: verification ===")
    verification.test_ik_roundtrip()

    print("\nAll self-tests passed across all milestones.\n")

    print("Symbolic results:")
    print("  T_0_ee =", kinematics.T_EE)
    print("  J =", kinematics.J)
    print("  M(q) =", dynamics.M_SYM)
    print("  g(q) =", dynamics.G_SYM)

    q_demo = np.zeros(kinematics.N)
    print("\nExample numbers (outstretched posture, params.PARAMS):")
    print("  static holding torques [N m]:", dynamics.static_torques(q_demo))

    wt, wq = verification.worst_case_static_torque()
    print("\n  worst-case static torque per joint [N m]:", wt)
    for j in range(kinematics.N):
        print(f"    joint {j+1}: {wt[j]:.3f} N m at posture "
              f"{np.round(wq[j], 3)} rad")
