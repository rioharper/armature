"""
missions.py — what the machine is asked to do, as moves, holds and events,
with a duty cycle: the motion the actuators and the bus are sized against
(ADR 0006), written the way the spec's §6.4 states it. A written mission is
a `Mission`, which the duty margins run as written; a searched one is a
named function of a search point, `mission(p) -> Mission`, whose axes go in
SPACE, so its worst move is found rather than named. `drive.py` declares
the margins that run them. Example: the 2R arm presses a part against a
fixture, and any move it makes may be cut short by an e-stop. Replace with
your machine's.
"""

from armature import Band, Coordinates, Interval, Space
from armature.drive import (Duty, Limits, Mission, after, event, hold, move)

from params import F_CONTACT, PARAMS, QD_LIMITS, QDD_LIMITS, WORKSPACE
from mechanism import BANDS, TOOL, mechanism, truth

# A move runs rest to rest under LIMITS, profiled by ruckig in the joint
# coordinates. Its limits are the spec's rate envelope, per joint. The jerk is the
# move class's too: each joint reaches its acceleration limit in JERK_TIME.
JERK_TIME = 0.1  # s
LIMITS = Limits(v=QD_LIMITS, a=QDD_LIMITS,
                j={k: a / JERK_TIME for k, a in QDD_LIMITS.items()},
                along="coordinate")

# Where the arm waits, folded down, and where it presses. Both inside
# WORKSPACE, as every posture a mission reaches must be.
REST = {"shoulder": -1.2, "elbow": 1.2}
PRESS = {"shoulder": 0.6, "elbow": 0.6}

# The press: out, three seconds against the fixture at +x, which pushes back
# on the tool with F_CONTACT, and home. Ten seconds a cycle, four hours a
# session — the spec's duty, not the hold's own length, sizes the windings.
PRESSING = Mission("press", [
    move(REST, end=PRESS, limits=LIMITS),
    hold(PRESS, 3.0, loads={TOOL: (-F_CONTACT, 0.0, 0.0)}),
    move(PRESS, end=REST, limits=LIMITS),
], duty=Duty(period=10.0, session=4 * 3600.0))

# An e-stop shorts every motor: its driver is off, and the winding's own
# back-EMF brakes the joint, as a damping c = Kt Ke / R. STOP_TIME is long
# enough for the arm to come to rest against it. STOP_STEP is the
# simulation's timestep, a twentieth of the shorted shoulder's time constant
# J R / (Kt Ke), about 20 ms; each margin's check re-runs it at half the step.
STOP_TIME = 0.3  # s
STOP_STEP = 1e-3  # s
SHORTED = {a: "short" for a in truth().actuators}


def stopped(end, fraction):
    """A move from REST to `end`, a posture, cut short `fraction` of the
    way through by an e-stop. At fraction 1 the whole move runs and the stop
    finds the arm at rest, so the move uncut is searched too."""
    reach = move(REST, end=end, limits=LIMITS)
    return Mission("stop", [reach, event(after(reach, fraction), SHORTED,
                                         STOP_TIME, timestep=STOP_STEP)])


def stop(p):
    """The searched mission: any move from rest to anywhere in WORKSPACE,
    e-stopped anywhere along it."""
    return stopped(p.end, p.fraction)


MISSIONS = [PRESSING, stop]

# What a searched mission reads, and the peak margins search: every mechanism
# band, the move's end, and the e-stop's trigger. drive.py adds its own bands,
# and the margins add the mission's Choice. A machine that moves between any two
# postures, not from rest, searches its start too, with a second
# `Coordinates` axis.
SPACE = Space(**{k: Band(k, BANDS) for k in BANDS},
              end=Coordinates(mechanism, PARAMS, within=WORKSPACE),
              fraction=Interval(0.0, 1.0))
