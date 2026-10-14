"""Actuators and the bus, sized from a mission (ADR 0006).

The drive data names every constant's basis; the electrical model turns
per-actuator (τ_out, ω_out) samples into current, voltage, copper loss and
bus power, in Lee et al.'s power-invariant d-q convention; and the winding's
temperature is integrated over a duty.

A mission is named segments run in order, with a duty cycle:
`Mission(name, [move(start, end=..., limits=Limits(v, a, j)),
hold(posture, duration, loads=...), follow(q, duration)], duty=Duty(period,
session))`. `trace(m, mission, rate)` samples it, through `m.at` and
`State.inverse` or the mission's own `actuation(state, qdd, loads, *, t,
p)`, into each actuator's motor torque and speed.

The actuators share one bus, `Drive(motors=..., drivers=..., gearboxes=...,
bus=Bus(actuators, source=Source(v, sinks, p_max), capacitance, brake=
BrakeResistor(threshold, r, energy, power), hotel))`, and `charge(trace,
drive, capacitance=..., v_source=...)` integrates their bus powers against
its source, capacitance, brake resistor and each driver's flux brake, at a
substep refined until halving it moves the peak V by less than `agree`.

An `event(start, modes, duration)` is a segment forward-simulated from a
state or from `after(segment, fraction)`, each actuator coasting, shorted,
flux-braking or following a torque profile, with the bus stepped alongside;
`trace(m, mission, rate, drive=..., capacitance=..., v_source=...)` runs it
at its timestep and at half of it; under an actuation seam, through the
mission's `transmission(state, *, t, p)`.

`margins(drive, missions, over=space)` turns all of it into ADR 0005
`Margin`s, one per check, searched over the move endpoints, event triggers,
bands, missions and bus configurations, or, for the duty's thermal and
energy checks, over the missions as written; `review(margins)` plots each
worst case, and `energy(...)` reports what each mission costs.
"""

from .bus import (AGREE, BrakeResistor, Bus, Charged, Drive, Source,
                  charge)
from .electrical import (Checked, Current, Curve, Driver, DriveError,
                         Electrical, Envelope, FluxBrake, Gearbox, Ke, Kt,
                         Motor, Resistance, Thermal, check, electrical,
                         envelope, kt_from_kv)
from .event import (EVENT_STEP, After, Event, Moved, Run, Simulated, after,
                    event)
from .margins import TRUTH_AGREE, Energy, Reviewed, energy, margins, review
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
__all__ += ["EVENT_STEP", "After", "Event", "Moved", "Run", "Simulated",
            "after", "event"]
__all__ += ["AGREE", "BrakeResistor", "Bus", "Charged", "Drive", "Source",
            "charge"]
__all__ += ["Energy", "Reviewed", "TRUTH_AGREE", "energy", "margins",
            "review"]
