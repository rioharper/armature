"""
report_truth.py — the Milestone 0 review artifact: what the red team checks the
description against the spec's sketch with.

    uv run python report_truth.py [directory]

An error in mechanism.py is common-mode — the derivation and the truth model
both read it, so no truth check can see it (ADR 0003). This puts it in front of
a reader instead. It writes the engine's review artifact into `directory`
(default: `review/` beside this file): `frames.md`, every joint axis and point,
COM, mass, inertia, site and actuator in the base frame at home, exactly as
the description wrote them, then a skeleton render at home and at each sampled
state — inertia boxes, joint axes, each body's COM. It prints the table, the
renders' paths, and the sample they were drawn from, so 00_setup.md can cite
them and a reviewer can reproduce a surprising render at the state that made it.
"""

import sys
from pathlib import Path

import armature
from armature.sampler import DEFAULT_SEED

from mechanism import mechanism, truth
from params import PARAMS

# A few states beside home: enough to see each joint turn, few enough to read.
RENDERED = 4

directory = (Path(sys.argv[1]) if len(sys.argv) > 1
             else Path(__file__).resolve().parent / "review")
samples = armature.sample(truth(), RENDERED, DEFAULT_SEED)
states = {f"sample-{i + 1}": {c: s.q[c] for c in truth().independent}
          for i, s in enumerate(samples)}
artifact = armature.review(mechanism, PARAMS, directory, states)

print(artifact.frames.read_text(encoding="utf-8"))
print(f"Renders, from {samples}:\n")
for label, path in artifact.renders.items():
    at = ", ".join(f"{c} = {v:.4f}" for c, v in states.get(label, {}).items())
    print(f"  {path}" + (f"   ({at})" if at else "   (home)"))
