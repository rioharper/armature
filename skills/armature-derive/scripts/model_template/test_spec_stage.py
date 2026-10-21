"""
The spec stage's entry point (ADR 0007), run on a coarse description.

Spec §9 copies this template, writes a coarse `mechanism.py` from
`armature.coarse` bodies, its `params.py`, `drive.py` and `missions.py`, and
runs `run_all.py` before derive exists. This test does the same with
`coarse_2r/`, the 2R arm as §9 would describe it: it copies what §9 keeps —
the runner, the gates, the drive and the missions — beside the coarse
description into a temporary directory and runs `run_all.py` there, which
must search the same drive margins and pass. The project's ledger is the
template's own, which the coarse arm reads too. Delete it, and `coarse_2r/`,
when you adapt the template.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COARSE = HERE / "coarse_2r"
# What spec §9 copies beside its own params.py and mechanism.py. The
# derivation's milestones are derive's to write, and are left behind.
SPEC_STAGE = ("run_all.py", "layout.py", "layout_checks.py", "drive.py",
              "drive_checks.py", "missions.py")
# Every drive margin's name on this 2R arm, as drive.py's margins name them.
DRIVE_MARGINS = [
    f"{a}: {check}" for a in ("shoulder_motor", "elbow_motor")
    for check in ("envelope at V_min", "driver peak current")] + [
    "bus: peak V", "bus: minimum V", "bus: source power"] + [
    f"{a}: {check}" for a in ("shoulder_motor", "elbow_motor")
    for check in ("winding temperature", "driver RMS current")]


def test_the_drive_margins_run_on_a_coarse_description(tmp_path):
    # The ledger stands at the project's root, which here is the model's
    # folder, as the template's stands beside its files.
    for name in (*SPEC_STAGE, "ledger.toml"):
        shutil.copy(HERE / name, tmp_path / name)
    for path in COARSE.glob("*.py"):
        shutil.copy(path, tmp_path / path.name)
    run = subprocess.run([sys.executable, "run_all.py"], cwd=tmp_path,
                         capture_output=True, text=True, encoding="utf-8",
                         env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                         timeout=900)
    assert run.returncode == 0, (
        f"run_all.py failed on the coarse description:\n{run.stdout[-4000:]}"
        f"\n{run.stderr[-4000:]}")
    missing = [n for n in DRIVE_MARGINS if f"[PASS] {n}:" not in run.stdout]
    assert not missing, f"the coarse run printed no passing row for {missing}"
    assert "All self-tests passed across all milestones." in run.stdout
