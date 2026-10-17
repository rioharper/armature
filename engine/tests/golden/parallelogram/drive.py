"""
drive.py — the drive: a motor, a gearbox and a driver on each of J1 and J2,
and the bus they share (ADR 0006).

`drive(p)` builds the engine's `Drive` from params.DRIVE, each constant's
basis a keyword. The gear ratios and the rotors' inertia are the
description's, never repeated here.
"""

from armature.drive import (Bus, Current, Drive, Driver, Gearbox, Kt, Motor,
                            Resistance, Source)

from params import DRIVE

# Run order and heading for `run_all.py`: after the derivation's milestones.
MILESTONE = (4, "Drive: the actuators and the bus")

MOTORS = ("J1_motor", "J2_motor")  # the description's actuators, by name


def motor(p):
    """Each joint's motor: its torque constant per A_rms and its line-to-line
    resistance, wye wound."""
    return Motor(kt=Kt(p["kt"], per="A_rms", side="motor"),
                 r=Resistance(p["r"], between="line"), wiring="wye")


def driver(p):
    """Each joint's driver: its efficiency, one constant whichever way power
    flows, its peak line current, and the bus voltages it trips at."""
    return Driver(efficiency=p["eta_driver"],
                  i_peak=Current(p["i_peak"], per="A_peak"),
                  max_voltage=p["v_max"], undervoltage=p["v_under"])


def drive(p=DRIVE):
    """The drive at the parameters `p`. The source is a PSU behind a diode,
    which cannot sink."""
    return Drive(
        motors={a: motor(p) for a in MOTORS},
        drivers={a: driver(p) for a in MOTORS},
        gearboxes={a: Gearbox(forward=p["eta_gear"]) for a in MOTORS},
        bus=Bus(actuators=MOTORS,
                source=Source(v=p["v_bus"], sinks=False,
                              p_max=p["p_source"]),
                capacitance=p["c_bus"]))
