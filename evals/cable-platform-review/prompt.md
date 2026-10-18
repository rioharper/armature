---
runs: 3
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

This repo is our cable-driven camera platform. A 2 kg platform hangs from four cables, one from each top corner of a 4 m square frame at 2.4 m, and a winch on each cable sets its length. The mechanism description and its parameters are in `analysis/model/` (`mechanism.py`, `params.py`), and `uv run python run_all.py` there runs every self-test. The model's environment is already synced, and there is no network in this session.

The spec's assumptions, as I wrote them:

- A1. Each cable is a straight elastic tie that cannot push: no sag, no mass.
- A2. The frame and its anchors are rigid.
- A3. The platform stays level. Its attachment square is a scaled copy of the anchor square, so the cables only ever translate it.

The cable rest lengths in `params.py` are the ones our tension law pays out to hold the platform level at the edge midpoint, `POSE` = (0.5, 2.0, 1.2) m.

Requirement R-2 says the deck must stay within 2° of level wherever the camera stops, the gimbal's correction range.

Derive task DR-01 is done: `analysis/derivation/00_setup.md`, the modules in `analysis/model/`, and the report `docs/testing/DR-01-deck-tilt.md`. It finds that R-2 holds at the edge midpoint. Before I close R-2 and order the gimbal, I want the derivation reviewed adversarially.

Write the review to `docs/reviews/review.md`. Rate each finding BLOCKER, MAJOR, MINOR or QUESTION, and give each a **Where** (file and section) and a **Finding** (what is wrong, with the number that shows it).

I'm away until tomorrow, so don't wait for me: do the review, write it, and stop. Don't fix the derivation.
