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
    "l1": 0.30,       # link 1 length [m]
    "l2": 0.25,       # link 2 length [m]
    "radius1": 0.02,  # link 1 radius, a solid cylinder [m]
    "radius2": 0.02,  # link 2 radius, a solid cylinder [m]
    "m1": 1.20,       # link 1 mass [kg]
    "m2": 0.80,       # link 2 mass, bare [kg]
    "g": 9.81,        # gravitational acceleration [m/s^2]
    "tau1": 15.0,     # shoulder motor's derated continuous torque [N m]
    "tau2": 6.0,      # elbow motor's [N m]
}

# The drive's numbers, each with its basis as the datasheet states it, which
# drive.py hands the engine as a keyword. A datum the datasheet does not give
# is left out, not guessed, and the margin that needs it reads UNCHECKED.
DRIVE = {
    "kv1": 8.0,         # shoulder: rpm per volt, line-to-line peak back-EMF
    "ke1": 88.4,        # shoulder: V_rms/krpm, line to line
    "r1": 0.20,         # shoulder: ohm, line to line at 25 C, wye
    "rth1": 1.2,        # shoulder: winding to ambient, K/W
    "cth1": 300.0,      # shoulder: winding, J/K
    "kv2": 20.0,        # elbow: rpm per volt, line-to-line peak back-EMF
    "ke2": 35.4,        # elbow: V_rms/krpm, line to line
    "r2": 0.25,         # elbow: ohm, line to line at 25 C, wye
    "rth2": 1.2,        # elbow: winding to ambient, K/W
    "cth2": 150.0,      # elbow: winding, J/K
    "t_max": 120.0,     # winding limit, both motors [C]
    "t_ambient": 40.0,  # the hottest ambient the spec allows [C]
    "eta_driver": 0.95,  # each driver, constant, both directions of flow
    "i_peak": 40.0,     # each driver's peak, A_peak line
    "i_cont": 20.0,     # each driver's continuous, A_rms line
    "v_max": 56.0,      # each driver's overvoltage trip [V]
    "v_under": 40.0,    # each driver's undervoltage trip [V]
    "v_bus": 48.0,      # the source's set point, a PSU behind a diode [V]
    "p_source": 600.0,  # the source's rating [W]
    "c_bus": 10e-3,     # the bus capacitance, the bank's rating [F]
    "hotel": 5.0,       # the electronics' constant draw [W]
}

# The forearm's mass budget +-10 %, the capacitor bank +-20 %, the source's
# set point +-2 %.
BANDS = {"m2": (0.72, 0.88), "c_bus": (8e-3, 12e-3), "v_bus": (47.0, 49.0)}

WORKSPACE = {"shoulder": (-3.0, 3.0), "elbow": (0.30, 2.50)}  # [rad]
QD_LIMITS = {"shoulder": 3.0, "elbow": 4.0}      # [rad/s]
QDD_LIMITS = {"shoulder": 20.0, "elbow": 30.0}   # [rad/s^2]
F_CONTACT = 15.0  # the fixture's push back on the tool while pressing [N]
