"""
bus.py — DR-02: the PSU and the bus, against the stop's regeneration.

Mirrors docs/testing/DR-02-psu-sizing.md, *Regeneration*. The stop sized is
the e-stop at jog speed, JOG_STOP: J1 braked from JOG_SPEED to rest in
missions.STOP_TIME, φ held. DRIVE_MARGINS are armature.drive's margins on
drive.py's PSU over it, which run_all.py searches; DRIVE_EXEMPT argues the
two windings. Self-tests in bus_checks.py; report_dr02.py prints the tables.
"""

import math
from dataclasses import replace

from armature.drive import (CONFIRM_RATE, capacitance_needed, charge,
                            margins, trace)

from drive import drive
from mechanism import truth
from missions import stopping
from params import DRIVE, PARAMS

MILESTONE = (5, "DR-02: the PSU and the bus")

JOG_SPEED = 1.0  # J1's jog speed, the speed the e-stop is hit at [rad/s]
JOG_STOP = replace(stopping(JOG_SPEED), name="jog e-stop")

DRIVE_MARGINS = margins(drive, [JOG_STOP], model=truth(), params=DRIVE)

DRIVE_EXEMPT = {
    "J1_motor: winding": "the arm is balanced (A1), so the winding carries "
                         "no holding current; it heats only in a stop, 0.1 s "
                         "at the current the driver peak-current margin "
                         "bounds, and the motor's thermal RC is not in hand",
    "J2_motor: winding": "J2 only holds φ against the coupling during a "
                         "stop, under 0.1 A for 0.1 s, which the driver "
                         "peak-current margin bounds; no thermal RC is in "
                         "hand",
}


def j11(p=PARAMS):
    """DR-02 (1): the inertia J1 brakes with φ held [kg m²]. The forearm
    translates and the coupler turns with θ1 about C; the rotor reflects
    through N1²."""
    return (2 * p["I"] + p["m1"] * p["r1"] ** 2 + p["m4"] * p["r4"] ** 2
            + p["m2"] * p["a"] ** 2 + p["N1"] ** 2 * p["J_m"])


def bound(speed, d=DRIVE):
    """DR-02 (3): the bus's peak if all of ½ J11 ω0² lands on the
    capacitance, √(V0² + J11 ω0² / C) [V]: an upper bound, copper loss
    left out."""
    return math.sqrt(d["v_bus"] ** 2 + j11() * speed ** 2 / d["c_bus"])


def untripped():
    """drive.py's drive with its drivers' trip lifted to 1 kV, out of any
    stop's way, so a peak reads where the bus would go, not where it
    latched."""
    d = drive()
    return replace(d, drivers={a: replace(x, max_voltage=1e3)
                               for a, x in d.drivers.items()})


def peak(mission):
    """The bus's peak in `mission` with nothing tripped [V]: `charge` on its
    trace at the confirmation rate."""
    return charge(trace(truth(), mission, CONFIRM_RATE), untripped()).peak


def needed():
    """The least capacitance each worst case of the peak V needs [F], by
    `capacitance_needed`: reported, never checked."""
    return capacitance_needed(DRIVE_MARGINS)
