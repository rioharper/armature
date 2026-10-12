"""
dynamics — Milestone 2: Euler-Lagrange dynamics, one submodule per section
of 02_dynamics.md, each with its self-tests in a sibling checks module:

    lagrangian.py   §1–2  T, V, Euler-Lagrange -> M(q), C(q, q̇), g(q)
    statics.py      §3    holding torques against gravity

Depends on mechanism.py only — `lagrangian.py` hangs its bodies on the
description's symbolic view rather than borrowing kinematics.py's matrices —
so a red-team pass on one section reads that submodule, its checks, and the
note section. Check the milestone alone: `uv run python run_all.py dynamics`.
"""

# Run order and heading for `run_all.py`. Every submodule inherits them and
# runs in file-name order; import from the submodule that owns a name.
MILESTONE = (2, "Milestone 2: dynamics")
