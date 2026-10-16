"""
params.py — the 2R arm's parameter block.

Each link's length, COM and inertia (a slender rod's, on every axis), the
gears and rotor inertias, and the motors' torque limit.
"""

PARAMS = {
    "l1": 0.30,       # link 1 length [m]
    "l2": 0.25,       # link 2 length [m]
    "lc1": 0.15,      # link 1 COM from the shoulder [m]
    "lc2": 0.125,     # link 2 COM from the elbow [m]
    "m1": 1.20,       # link 1 mass [kg]
    "m2": 0.80,       # link 2 mass [kg]
    "I1": 0.012,      # link 1 inertia about its COM, across the link [kg m^2]
    "I2": 0.006,      # link 2's [kg m^2]
    "Ix1": 0.00024,   # link 1 inertia about its own axis [kg m^2]
    "Ix2": 0.00016,   # link 2's [kg m^2]
    "g": 9.81,        # gravitational acceleration [m/s^2]
    "N1": 50.0,       # shoulder gear ratio
    "N2": 30.0,       # elbow gear ratio
    "J1": 2e-5,       # shoulder rotor inertia [kg m^2]
    "J2": 1e-5,       # elbow rotor inertia [kg m^2]
    "limit": 0.5,     # each motor's torque limit [N m]
}

BANDS = {}
