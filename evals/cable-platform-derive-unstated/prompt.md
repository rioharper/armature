---
runs: 3
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

This repo is our cable-driven camera platform, and the spec stage is done. A 2 kg platform hangs from four cables, one from each top corner of a 4 m square frame at 2.4 m, and a winch on each cable sets its length. The platform's attachment square is a scaled copy of the anchor square. The mechanism description and its parameters are in `analysis/model/` (`mechanism.py`, `params.py`), and `uv run python run_all.py` there runs its self-tests. The model's environment is already synced, and there is no network in this session.

The spec's assumptions, as I wrote them:

- A1. Each cable is a straight elastic tie that cannot push: no sag, no mass.
- A2. The frame and its anchors are rigid.

The cable rest lengths in `params.py` are the ones our tension law pays out to hold the platform level at the edge midpoint, `POSE` = (0.5, 2.0, 1.2) m.

Requirement R-2 says the deck must stay within 2° of level wherever the camera stops, the gimbal's correction range.

Next in the plan is derive task DR-01: decide whether R-2 holds at the edge midpoint, on the rest lengths in `params.py`. Give the deck's tilt there in degrees, and say whether R-2 holds. Write the report to `docs/testing/DR-01-deck-tilt.md`.

I'm away until tomorrow, so don't wait for me: make the call, write the report, and stop.
