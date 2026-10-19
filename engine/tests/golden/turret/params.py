"""
params.py — the geared turret's parameter block.

The turret's mass, its COM off the bearing's axis and its inertia about the
COM, the muzzle's reach, and the pan motor's gear ratio and rotor inertia.
"""

PARAMS = {
    "m": 6.0,       # the turret, its payload included [kg]
    "d": 0.08,      # its COM, along +x from the bearing's axis [m]
    "h": 0.12,      # its COM, above the bearing [m]
    "Izz": 0.0216,  # its inertia about the COM, about the axis [kg m^2]
    "Ixx": 0.03,    # its inertia about the COM, across the axis [kg m^2]
    "reach": 0.30,  # the muzzle, along +x from the axis [m]
    "g": 9.81,      # gravitational acceleration [m/s^2]
    "N": 60.0,      # the pan's gear ratio
    "J_m": 3e-5,    # the pan motor's rotor, about its axis [kg m^2]
}

BANDS = {}
