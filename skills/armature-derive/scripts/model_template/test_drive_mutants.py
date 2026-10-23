"""
The drive checks' teeth: each mistake drive_checks.py exists to catch,
made on purpose — the engine monkeypatched, or the data read wrongly — and
the check that must then fail. A check never seen to fail is no evidence.
Keep it pointed at your own drive when you adapt the template.
"""

import importlib
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from armature import Budget, Space  # noqa: E402
from armature.drive import DriveError, kt_from_kv, margins  # noqa: E402

import drive  # noqa: E402
import drive_checks  # noqa: E402
from mechanism import truth  # noqa: E402
from missions import PRESSING  # noqa: E402
from params import DRIVE  # noqa: E402

ELECTRICAL = importlib.import_module("armature.drive.electrical")
MARGINS = importlib.import_module("armature.drive.margins")


def test_driver_efficiency_the_wrong_way_fails_the_bus_power_check(
        monkeypatch):
    """The driver's efficiency multiplying what a motor draws and dividing
    what it returns: the arm then regenerates more than it made."""
    original = ELECTRICAL._electrical

    def swapped(c, n, gearbox, driver, *rest):
        out = original(c, n, gearbox, driver, *rest)
        eta = driver.efficiency
        return replace(out, bus=np.where(out.power >= 0, out.power * eta,
                                         out.power / eta))

    monkeypatch.setattr(ELECTRICAL, "_electrical", swapped)
    with pytest.raises(AssertionError, match="bus power"):
        drive_checks.test_truth_bus_power_follows_the_flow_of_power()


def test_kt_by_the_trapezoidal_convention_fails_the_constants_check(
        monkeypatch):
    """drive.py reading Kt as 9.55/Kv: refused against Ke by the engine,
    and off the hand reading."""
    monkeypatch.setattr(drive, "kt_from_kv", lambda kv, per, convention: (
        kt_from_kv(kv, per=per, convention="trapezoidal")))
    with pytest.raises((AssertionError, DriveError)):
        drive_checks.test_each_motors_constants_agree_on_their_bases()


def _peak_v(drive_of, budget=Budget(global_points=8, polish_starts=1,
                                     polish_evals=20)):
    """The press's bus peak-V margin, searched over the drive's bands."""
    found = margins(drive_of, [PRESSING], Space(**drive.DRIVE_BANDS),
                    model=truth(), params=DRIVE, budget=budget)
    return {m.name: m for m in found}["bus: peak V"]


def test_the_capacitance_band_collapsed_fails_the_energy_relation():
    """drive(p) charging the bus at the bank's rating whatever the band
    says: the searched peak no longer reads the least capacitance. The
    honest drive, searched the same way, passes."""
    drive_checks.bus_peak_by_energy(_peak_v(drive.drive))

    def collapsed(p):
        return drive.drive({**p, "c_bus": DRIVE["c_bus"]})

    with pytest.raises(AssertionError, match="bus peaks"):
        drive_checks.bus_peak_by_energy(_peak_v(collapsed))


def test_an_event_never_halved_fails_the_resolution_check(monkeypatch):
    """The margins' check re-running each event at the search's own
    timestep: a resolution check that resolves nothing."""
    monkeypatch.setattr(MARGINS, "_halved", lambda mission: mission)
    with pytest.raises(AssertionError, match="half its timestep"):
        drive_checks.test_truth_an_event_is_confirmed_at_half_its_timestep()
