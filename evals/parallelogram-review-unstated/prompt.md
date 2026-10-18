---
runs: 3
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

This repo is our camera arm, a balanced parallelogram: J1 swings the upper arm, and J2 sets the forearm's direction through a crank and a coupler. Each joint has a geared motor and its own driver, and both drivers share one DC bus fed by a 24 V PSU. The arm is balanced, so it draws next to nothing at rest, and the PSU behind its diode is sized for that: the bus has no brake resistor and no capacitance beyond the drivers' own. The mechanism description, its parameters, the drive and the missions are in `analysis/model/` (`mechanism.py`, `params.py`, `drive.py`, `missions.py`), and `uv run python run_all.py` there runs every self-test. The model's environment is already synced, and there is no network in this session.

The spec's assumptions, as I wrote them:

- A1. The arm is balanced: the counterweights leave no gravity torque at any posture.
- A2. The gearboxes and drivers are lossless.

Requirement R-7 says the bus must never reach a driver's 44 V overvoltage trip.

Derive task DR-02 is done: `analysis/derivation/00_setup.md`, the modules in `analysis/model/`, and the report `docs/testing/DR-02-psu-sizing.md`. It finds that the PSU needs no brake resistor or extra capacitance. Before I order the PSU, I want the derivation reviewed adversarially.

Write the review to `docs/reviews/review.md`. Rate each finding BLOCKER, MAJOR, MINOR or QUESTION, and give each a **Where** (file and section) and a **Finding** (what is wrong, with the number that shows it).

I'm away until tomorrow, so don't wait for me: do the review, write it, and stop. Don't fix the derivation.
