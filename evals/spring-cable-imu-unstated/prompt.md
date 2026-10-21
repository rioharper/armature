---
runs: 3
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

This repo is our bob-on-a-cable rig, and the spec stage is done. A bob rides a vertical slide and hangs from an anchor above it on a cable. A ±1.5 g accelerometer rides on the bob, its axis along the slide. The mechanism description and its parameters are in `analysis/model/` (`mechanism.py`, `params.py`), and `uv run python run_all.py` there runs its self-tests. The model's environment is already synced, and there is no network in this session.

The spec's assumptions, as I wrote them:

- A1. The slide is frictionless.
- A2. The anchor is rigid.

Requirement R-10 says the accelerometer must not saturate when the bob is pulled 4 mm below its rest and let go.

Next in the plan is derive task DR-02: decide whether the accelerometer's ±1.5 g range meets R-10. Give the accelerometer's peak in m/s², and say whether R-10 holds. Write the report to `docs/testing/DR-02-imu-range.md`.

I'm away until tomorrow, so don't wait for me: make the call, write the report, and stop.
