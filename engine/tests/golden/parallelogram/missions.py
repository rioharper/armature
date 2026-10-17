"""
missions.py — what the arm is asked to do, as the engine's missions
(ADR 0006): a stop. J1 slews at its top speed and is braked to rest at a
constant deceleration, while J2 holds the crank, so φ stays where it is.
`drive.py` holds the motors and the bus the stop runs on.
"""

from armature.drive import Mission, follow

SLEW_SPEED = 3.0  # J1's top speed [rad/s]
STOP_TIME = 0.1   # J1's braking time, top speed to rest [s]
START = -0.15     # J1 where braking starts, so the stop ends at home [rad]
HELD = 0.0        # J2, held: the crank at home's φ = π/2 [rad]


def stopping(speed, duration=STOP_TIME, start=START):
    """J1 braked from `speed` (rad/s) to rest in `duration` (s) at constant
    deceleration from `start` (rad), J2 held at HELD."""
    rate = speed / duration
    return Mission("stop", [follow(
        lambda t: {"J1": start + speed * t - 0.5 * rate * t * t, "J2": HELD},
        duration,
        qd=lambda t: {"J1": speed - rate * t, "J2": 0.0},
        qdd=lambda t: {"J1": -rate, "J2": 0.0})])


STOP = stopping(SLEW_SPEED)
MISSIONS = [STOP]
