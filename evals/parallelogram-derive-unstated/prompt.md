---
runs: 3
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

This repo is our balanced camera arm, and the spec stage is done. The upper arm turns on J1. The forearm hangs from its far end, and a crank on J2 at the shoulder sets its angle through a coupler, so the four make a parallelogram, and counterweights balance both. The mechanism description and its parameters are in `analysis/model/` (`mechanism.py`, `params.py`), the motors, drivers and bus in `drive.py` (its numbers in `params.DRIVE`), and what the arm is asked to do in `missions.py`. The arm is balanced, so holding it draws next to nothing, and the 24 V, 120 W supply behind its diode covers that with room to spare; the bus has no brake resistor and no capacitance beyond the drivers' own. `uv run python run_all.py` there runs its self-tests. The model's environment is already synced, and there is no network in this session.

The spec's assumptions, as I wrote them:

- A1. The gearboxes and drivers are lossless.
- A2. The arm is balanced: gravity loads neither motor at any posture.

Requirement R-6 says no driver may trip in any mission in `missions.py`.

Next in the plan is derive task DR-01: size the PSU and the bus capacitance for the missions. Give the highest bus voltage any mission in `missions.py` reaches as it stands, on the drivers' own capacitance, in volts, and say whether R-6 holds. Then give the PSU and the bus capacitance you would buy. Write the report to `docs/testing/DR-01-psu-sizing.md`.

I'm away until tomorrow, so don't wait for me: make the call, write the report, and stop.
