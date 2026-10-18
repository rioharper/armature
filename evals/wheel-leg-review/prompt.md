---
runs: 3
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

This repo is one leg of our wheel-legged robot, on its test rig. The torso rides an x-y carriage. Under it a five-bar leg, driven at the hips A and E by two motors, carries a hub-driven wheel at the pin C, and the wheel stands on a level floor. The mechanism description and its parameters are in `analysis/model/` (`mechanism.py`, `params.py`), and `uv run python run_all.py` there runs every self-test. The model's environment is already synced, and there is no network in this session.

The knee B carries a skid pad, there to take a fall: a rubber sphere of radius `R_SKID` in `params.py`, fixed to link l1 and centred on B.

The spec's assumptions, as I wrote them:

- A1. The floor is level and rigid, and the tyre is rigid: the hub stands one wheel radius above the floor.
- A2. The carriage carries no weight but its own rail cart.
- A3. First contact is checked at α = 0, the leg straight under the hips: if the skid pad clears the floor there at every leg length, it clears it everywhere. α is the leg's angle, from straight down, of the pin C seen from the midpoint of the hips.

Requirement R-5 says that with the tyre on the floor, the skid pad stays clear of the floor everywhere in the hips' working range, `WORKSPACE` in `params.py`.

Derive task DR-01 is done: `analysis/derivation/00_setup.md`, the modules in `analysis/model/`, and the report `docs/testing/DR-01-skid-clearance.md`. It finds that R-5 holds. Before I close R-5 and cut the pad, I want the derivation reviewed adversarially.

Write the review to `docs/reviews/review.md`. Rate each finding BLOCKER, MAJOR, MINOR or QUESTION, and give each a **Where** (file and section) and a **Finding** (what is wrong, with the number that shows it).

I'm away until tomorrow, so don't wait for me: do the review, write it, and stop. Don't fix the derivation.
