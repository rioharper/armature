"""
drive.py — the drive: each actuator's motor and driver, the bus they share,
and the margins that size them over the missions (ADR 0006).

`drive(p)` builds the engine's `Drive` from params.DRIVE, each constant with
its basis as a keyword, so a slip between A_rms and A_peak, or line and
phase, is a disagreement the engine names rather than a number it uses. The
gear ratio and the rotor's inertia are not here: they are the description's
`actuator`, said once, and the engine reads them from the compiled model.

DRIVE_MARGINS are `armature.drive.margins`: one ADR 0005 margin per check,
discovered by `run_all.py` like any other and searched once a run. The peak
margins (each (tau, omega) sample inside the torque-speed envelope at the
bus's lowest voltage, the driver's peak current, the bus's peak and minimum
voltage, the supply's power) search SPACE, every mission, and the bus's
capacitance and supply bands; the duty margins (each winding's temperature,
each driver's RMS current) run the written missions over their duty. Each
margin's truth re-runs its worst case at 1 kHz with every event at half its
timestep: a resolution check, which `layout.py`'s gate accepts as its truth.

A margin whose data is missing — a winding with neither thermal data nor a
continuous rating — is UNCHECKED, and `run_all.py` fails it, unless
DRIVE_EXEMPT names it with the reason it may stand unchecked.

Example: two direct-drive motors on a 48 V supply behind a diode, which
cannot sink, so what the arm regenerates lands on the bus capacitance alone.
Replace with your machine's. Self-tests in drive_checks.py.
"""

from armature import Budget
from armature.drive import (Bus, Current, Drive, Driver, Ke, Motor,
                            Resistance, Source, Thermal, energy, kt_from_kv,
                            margins)

from params import BANDS, DRIVE
from missions import MISSIONS, SPACE

# Run order and heading for `run_all.py`: after the derivation's milestones,
# since the drive reads the truth model only. At the spec stage, where those
# milestones do not exist yet, it runs alone.
MILESTONE = (4, "Drive: the actuators and the bus, over the missions")

# Which motor is whose, by the description's actuator name, and the suffix
# of its numbers in params.DRIVE.
MOTORS = {"shoulder_motor": "1", "elbow_motor": "2"}

# Each margin's search, per mission. ADR 0005's default spends 64 Sobol
# points per dimension and three polishes; every corner is evaluated either
# way, and a drive margin's evaluation traces a whole mission, so this
# spends less beside them.
BUDGET = Budget(global_points=64, polish_starts=2, polish_evals=40)


def thermal(p, k):
    """Motor `k`'s winding RC, or None where the datasheet gives none."""
    names = (f"rth{k}", f"cth{k}", "t_max", "t_ambient")
    if not all(n in p for n in names):
        return None
    return Thermal(*(p[n] for n in names))


def motor(p, k):
    """Motor `k`. Kt from its Kv by the sinusoidal convention (8.27/Kv), the
    one these motors' sinusoidal commutation implies; its datasheet Ke beside
    it, so the engine holds the two to within 2 %."""
    return Motor(kt=kt_from_kv(p[f"kv{k}"], convention="sinusoidal"),
                 ke=Ke(p[f"ke{k}"], per="V_rms/krpm", between="line",
                       side="motor"),
                 r=Resistance(p[f"r{k}"], between="line"), wiring="wye",
                 thermal=thermal(p, k))


def driver(p):
    return Driver(efficiency=p["eta_driver"],
                  i_peak=Current(p["i_peak"], per="A_peak"),
                  i_continuous=Current(p["i_cont"], per="A_rms"),
                  max_voltage=p["v_max"], undervoltage=p["v_under"])


def drive(p):
    """The drive at the parameters `p`: params.DRIVE, with any band's value
    of a search point in. The bus's capacitance and supply voltage are its
    bands, which the margins search as their own axes."""
    return Drive(
        motors={a: motor(p, k) for a, k in MOTORS.items()},
        drivers={a: driver(p) for a in MOTORS},
        bus=Bus(actuators=tuple(MOTORS),
                source=Source(v=BANDS["v_bus"], sinks=False,
                              p_max=p["p_supply"]),
                capacitance=BANDS["c_bus"], hotel=p["hotel"]))


DRIVE_MARGINS = margins(drive, MISSIONS, SPACE, params=DRIVE, budget=BUDGET)

# The margins that may stand UNCHECKED, by name, each with its argued reason:
# `{"elbow_motor: winding": "the elbow only ever holds; its driver's RMS
# current margin bounds the same heat"}`. `run_all.py` prints each one, and
# fails an entry that names no margin or one that is checked after all.
DRIVE_EXEMPT = {}


def energies():
    """Each written mission's energy at nominal, by `armature.drive.energy`:
    reported in report_results.py, never checked."""
    return energy(drive, MISSIONS, SPACE, params=DRIVE)
