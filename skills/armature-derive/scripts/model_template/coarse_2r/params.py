"""
params.py — the coarse 2R arm's parameter block, as spec §9 writes it.

PARAMS are what the coarse description reads: each link's length, radius
and mass, and the motors' derated torques. Everything else is the template's
own block, the drive's numbers, the bands, the workspace, the rate envelope
and the contact force, which `test_spec_stage.py` holds equal to it, since
the same `drive.py` and `missions.py` run on both. Derive turns this block
into the template's, adding the COM offsets and inertias its bodies then
take.
"""

PARAMS = {
    "l1": 0.30,    # link 1 length [m]
    "l2": 0.25,    # link 2 length [m]
    "radius1": 0.02,  # link 1 radius, a solid cylinder [m]
    "radius2": 0.02,  # link 2 radius, a solid cylinder [m]
    "m1": 1.20,    # link 1 mass [kg]
    "m2": 0.80,    # link 2 mass, bare [kg]
    "g": 9.81,     # gravitational acceleration [m/s^2]
    "tau1": 15.0,  # shoulder motor's derated continuous torque [N m]
    "tau2": 6.0,   # elbow motor's [N m]
}

DRIVE = {
    "kv1": 8.0, "ke1": 88.4, "r1": 0.20, "rth1": 1.2, "cth1": 300.0,
    "kv2": 20.0, "ke2": 35.4, "r2": 0.25, "rth2": 1.2, "cth2": 150.0,
    "t_max": 120.0, "t_ambient": 40.0, "eta_driver": 0.95, "i_peak": 40.0,
    "i_cont": 20.0, "v_max": 56.0, "v_under": 40.0, "v_bus": 48.0,
    "p_supply": 600.0, "c_bus": 10e-3, "hotel": 5.0,
}

BANDS = {"m2": (0.72, 0.88), "c_bus": (8e-3, 12e-3), "v_bus": (47.0, 49.0)}

WORKSPACE = {"shoulder": (-3.0, 3.0), "elbow": (0.30, 2.50)}
QD_LIMITS = {"shoulder": 3.0, "elbow": 4.0}
QDD_LIMITS = {"shoulder": 20.0, "elbow": 30.0}
F_CONTACT = 15.0
