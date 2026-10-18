---
runs: 3
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

This repo is one leg of our wheel-legged robot, on its test rig, and the spec stage is done. The torso rides an x-y carriage. Under it a five-bar leg, driven at the hips A and E by two motors, carries a hub-driven wheel at the pin C, and the wheel stands on a level floor. The mechanism description and its parameters are in `analysis/model/` (`mechanism.py`, `params.py`), and `uv run python run_all.py` there runs its self-tests. The model's environment is already synced, and there is no network in this session.

The knee B carries a skid pad, there to take a fall: a rubber sphere of radius `R_SKID` in `params.py`, fixed to link l1 and centred on B. It isn't in the description yet.

On our last leg, first contact was checked with the leg straight under the hips, α = 0, at every leg length, where the knee comes lowest; α is the leg's angle, from straight down, of the pin C seen from the midpoint of the hips.

The spec's assumptions, as I wrote them:

- A1. The floor is level and rigid, and the tyre is rigid: the hub stands one wheel radius above the floor.
- A2. The carriage carries no weight but its own rail cart.

Requirement R-5 says that with the tyre on the floor, the skid pad stays clear of the floor everywhere in the hips' working range, `WORKSPACE` in `params.py`.

Next in the plan is derive task DR-01: decide whether R-5 holds. Give the skid pad's least clearance above the floor over the working range, in mm, as a signed number (a pad below the floor reads negative), and the hip angles where it falls. Say whether R-5 holds. Write the report to `docs/testing/DR-01-skid-clearance.md`.

I'm away until tomorrow, so don't wait for me: make the call, write the report, and stop.
