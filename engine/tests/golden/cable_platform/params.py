"""
params.py — the cable platform's parameter block: Plumb Rev 1.0's rig.

The anchor square (4 m, at 2.4 m) is a scaled copy of the attachment square
(0.15 m). The platform is described hung at HOME, the room centre; PARAMS'
rest lengths are those the level-platform tension law of Plumb's Milestone 1
Rev 1.0 (01_kinematics.md §3) gives at POSE, the edge midpoint, carrying m.
"""

import numpy as np

G = 9.81          # gravitational acceleration, the engine's default [m/s^2]
EA = 44_000.0     # each cable's axial stiffness [N]
I_P = 0.02        # the platform's inertia about its COM, every axis [kg m^2]
ANCHORS = np.array([[0, 0, 2.4], [4, 0, 2.4], [4, 4, 2.4], [0, 4, 2.4]],
                   float)  # [m]
ATTACH = np.array([[-0.075, -0.075, 0], [0.075, -0.075, 0],
                   [0.075, 0.075, 0], [-0.075, 0.075, 0]])  # about the point
COM = np.array([0.0, 0.0, -0.10])  # below the point [m]
HOME = np.array([2.0, 2.0, 1.2])   # the room centre [m]
POSE = np.array([0.5, 2.0, 1.2])   # the edge midpoint [m]

PARAMS = {
    "m": 2.0,                     # the platform's mass [kg]
    "l0_1": 2.306986964007753,    # each cable's rest length at POSE [m]
    "l0_2": 4.10772522279266,
    "l0_3": 4.10772522279266,
    "l0_4": 2.306986964007753,
}

BANDS = {}
