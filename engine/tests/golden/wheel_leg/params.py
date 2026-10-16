"""
params.py — the wheel leg's parameter block: a five-bar leg on a wheel.

The leg's five points at home in the torso's frame, its four links, the
torso, the wheel and the gears. PARAMS is built from POINTS and LINKS, so
each point and link is written once.
"""

POINTS = {"A": (-0.05, 0.0), "B": (-0.10, -0.10), "C": (0.0, -0.25),
          "E": (0.05, 0.0), "D": (0.11, -0.09)}  # [m]
LINKS = {  # name: (from, to, mass [kg], Izz [kg m^2])
    "l1": ("A", "B", 0.30, 1.0e-3), "l2": ("B", "C", 0.45, 2.0e-3),
    "l3": ("E", "D", 0.35, 1.5e-3), "l4": ("D", "C", 0.50, 2.5e-3)}
COM_AT = 0.4             # each link's COM, as a fraction from its first point
TORSO_COM = (0.0, 0.08)  # [m]
PUSH_AT = (0.0, 0.12)    # where the torso's site loads act [m]

PARAMS = {f"{k}{axis}": v[i] for k, v in POINTS.items()
          for i, axis in enumerate("xy")}
PARAMS.update({f"m_{k}": v[2] for k, v in LINKS.items()})
PARAMS.update({f"I_{k}": v[3] for k, v in LINKS.items()})
PARAMS.update({
    "g": 9.81,        # gravitational acceleration [m/s^2]
    "N": 20.0,        # each hip's gear ratio
    "N_hub": 10.0,    # the hub's gear ratio
    "J": 1e-5,        # each rotor's inertia [kg m^2]
    "kB": 2.0,        # the knee B's spring [N m/rad]
    "m_torso": 3.0,   # [kg]
    "I_torso": 0.02,  # [kg m^2]
    "m_cart": 0.2,    # the carriage's rail cart, not carried by the wheel [kg]
    "m_wheel": 0.4,   # [kg]
    "r": 0.06,        # the wheel's radius [m]
    "w": 0.015,       # the tyre's half width [m]
    "mu": 0.7,        # the tyre's friction coefficient on the floor
})

# The hips' working range [rad]: a box inside their joint ranges, over which
# the loop closes everywhere.
WORKSPACE = {"A": (-1.0, 1.0), "E": (-0.5, 2.0)}
# The radius of a skid pad round the knee B [m]. The description carries no
# pad; the variant that adds one reads this.
R_SKID = 0.09

BANDS = {}
