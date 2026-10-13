"""Actuators and the bus, sized from a mission (ADR 0006).

A mission is named segments run in order, with a duty cycle:
`Mission(name, [move(start, end=..., limits=Limits(v, a, j)),
hold(posture, duration, loads=...), follow(q, duration)], duty=Duty(period,
session))`. `trace(m, mission, rate)` samples it, through `m.at` and
`State.inverse` or the mission's own `actuation`, into each actuator's motor
torque and speed.
"""

from .mission import (CONFIRM_RATE, SEARCH_RATE, Duty, Follow, Hold, Limits,
                      Mission, Move, Trace, follow, hold, move, trace)

__all__ = ["CONFIRM_RATE", "Duty", "Follow", "Hold", "Limits", "Mission",
           "Move", "SEARCH_RATE", "Trace", "follow", "hold", "move", "trace"]
