"""Actuators and the bus, sized from a mission (ADR 0006).

The drive data names every constant's basis; the electrical model turns
per-actuator (τ_out, ω_out) samples into current, voltage, copper loss and
bus power, in Lee et al.'s power-invariant d-q convention; and the winding's
temperature is integrated over a duty.

A mission is named segments run in order, with a duty cycle:
`Mission(name, [move(start, end=..., limits=Limits(v, a, j)),
hold(posture, duration, loads=...), follow(q, duration)], duty=Duty(period,
session))`. `trace(m, mission, rate)` samples it, through `m.at` and
`State.inverse` or the mission's own `actuation`, into each actuator's motor
torque and speed.

The actuators share one bus, `Drive(motors=..., drivers=..., gearboxes=...,
bus=Bus(actuators, source=Source(v, sinks, p_max), capacitance, brake=
BrakeResistor(threshold, r, energy, power), hotel))`, and `charge(trace,
drive, capacitance=..., v_source=...)` integrates their bus powers against
its source, capacitance, brake resistor and each driver's flux brake, at a
substep refined until halving it moves the peak V by less than `agree`.
"""

from .bus import (AGREE, BrakeResistor, Bus, Charged, Drive, Source,
                  charge)
from .electrical import (Checked, Current, Curve, Driver, DriveError,
                         Electrical, Envelope, FluxBrake, Gearbox, Ke, Kt,
                         Motor, Resistance, Thermal, check, electrical,
                         envelope, kt_from_kv)
from .mission import (CONFIRM_RATE, SEARCH_RATE, Duty, Follow, Hold, Limits,
                      Mission, Move, Trace, follow, hold, move, trace)
from .thermal import Heated, Repeated, heat, repeat, rms_torque

__all__ = ["Checked", "Current", "Curve", "DriveError", "Driver",
           "Electrical", "Envelope", "FluxBrake", "Gearbox", "Ke", "Kt",
           "Motor", "Resistance", "Thermal", "check", "electrical",
           "envelope", "kt_from_kv"]
__all__ += ["Heated", "Repeated", "heat", "repeat", "rms_torque"]
__all__ += ["CONFIRM_RATE", "Duty", "Follow", "Hold", "Limits", "Mission",
            "Move", "SEARCH_RATE", "Trace", "follow", "hold", "move", "trace"]
__all__ += ["AGREE", "BrakeResistor", "Bus", "Charged", "Drive", "Source",
            "charge"]
