---
runs: 3
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

This repo is our bob-on-a-cable rig. A bob rides a vertical slide and hangs from an anchor above it on a cable, which sets its height: the bob sits the cable's length below the anchor. The mechanism description and its parameters are in `analysis/model/` (`mechanism.py`, `params.py`), and `uv run python run_all.py` there runs every self-test. The model's environment is already synced, and there is no network in this session.

The spec's assumptions, as I wrote them:

- A1. The slide is frictionless.
- A2. The anchor is rigid.

Requirement R-4 says every mode of the rig must sit at or above 10 Hz, five times the position loop's 2 Hz crossover.

Derive task DR-01 is done: `analysis/derivation/00_setup.md`, the modules in `analysis/model/`, and the report `docs/testing/DR-01-first-mode.md`. It finds that R-4 holds. Before I close R-4 and order the cable, I want the derivation reviewed adversarially.

Write the review to `docs/reviews/review.md`. Rate each finding BLOCKER, MAJOR, MINOR or QUESTION, and give each a **Where** (file and section) and a **Finding** (what is wrong, with the number that shows it).

I'm away until tomorrow, so don't wait for me: do the review, write it, and stop. Don't fix the derivation.
