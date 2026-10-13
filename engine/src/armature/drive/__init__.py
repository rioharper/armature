"""Actuators and the bus, sized from a mission (ADR 0006).

The drive data names every constant's basis; the electrical model turns
per-actuator (τ_out, ω_out) samples into current, voltage, copper loss and
bus power, in Lee et al.'s power-invariant d-q convention; and the winding's
temperature is integrated over a duty.
"""

from .electrical import (Checked, Current, Curve, Driver, DriveError,
                         Electrical, Envelope, FluxBrake, Gearbox, Ke, Kt,
                         Motor, Resistance, Thermal, check, electrical,
                         envelope, kt_from_kv)

from .thermal import Heated, Repeated, heat, repeat, rms_torque

__all__ = ["Checked", "Current", "Curve", "DriveError", "Driver",
           "Electrical", "Envelope", "FluxBrake", "Gearbox", "Ke", "Kt",
           "Motor", "Resistance", "Thermal", "check", "electrical",
           "envelope", "kt_from_kv"]
__all__ += ["Heated", "Repeated", "heat", "repeat", "rms_torque"]
