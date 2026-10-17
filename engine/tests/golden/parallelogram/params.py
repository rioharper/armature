"""
params.py — the balanced parallelogram's parameter block.

The links' lengths and masses, and the two counterweights' COMs, r1 and r3,
solved from the balance condition, so that the moment of mass is zero at
every posture:

    B1 = m1 r1 + m4 r4 + m2 a = 0,    B2 = m3 r3 + m4 c + m2 r2 = 0.
"""

PARAMS = {
    "a": 0.40,    # the upper arm, O to P [m]
    "b": 0.35,    # the forearm, P to the tip [m]
    "c": 0.08,    # the crank, O to C, and the forearm's lever, P to Q [m]
    "r2": -0.15,  # the forearm's COM, along +y from P [m]
    "r4": 0.20,   # the coupler's COM, along +x from C [m]
    "m1": 3.0,    # the upper arm, its counterweight included [kg]
    "m2": 1.0,    # the forearm [kg]
    "m3": 2.0,    # the crank, its counterweight included [kg]
    "m4": 0.3,    # the coupler [kg]
    "g": 9.81,    # gravitational acceleration [m/s^2]
    "N1": 50.0,   # J1's gear ratio
    "N2": 30.0,   # J2's gear ratio
    "I": 2e-3,    # each body's inertia about its COM, every axis [kg m^2]
    "J_m": 2e-5,  # each motor's rotor, about its axis [kg m^2]
}
PARAMS["r1"] = -(PARAMS["m4"] * PARAMS["r4"]
                 + PARAMS["m2"] * PARAMS["a"]) / PARAMS["m1"]
PARAMS["r3"] = -(PARAMS["m4"] * PARAMS["c"]
                 + PARAMS["m2"] * PARAMS["r2"]) / PARAMS["m3"]

# --- the drive's numbers (ADR 0006) ---
# What `drive.py`'s `drive(p)` reads, kept apart from PARAMS because the
# engine compiles PARAMS into the truth model and refuses a parameter it never
# reads. Each constant carries its basis. Both joints have the same motor,
# gearbox and driver.
DRIVE = {
    "kt": 0.08,         # each motor: N m per A_rms, motor side
    "r": 0.20,          # each motor: ohm, line to line at 25 C, wye
    "eta_gear": 1.0,    # each gearbox, both directions of flow
    "eta_driver": 1.0,  # each driver, both directions of flow
    "i_peak": 20.0,     # each driver's peak, A_peak line
    "v_max": 44.0,      # each driver's overvoltage trip [V]
    "v_under": 10.0,    # each driver's undervoltage trip [V]
    "v_bus": 24.0,      # the source's set point, a PSU behind a diode [V]
    "p_source": 120.0,  # the source's rating [W]
    "c_bus": 1e-3,      # the bus capacitance, the drivers' own [F]
}

BANDS = {}
