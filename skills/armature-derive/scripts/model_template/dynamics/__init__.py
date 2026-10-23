"""
dynamics — Milestone 2: the equations of motion, one submodule per section
of 02_dynamics.md, each with its self-tests in a sibling checks module:

    equations.py    §1–2  T, V; the engine's M(q), C(q, q̇) q̇, g(q), plus rotors
    statics.py      §3    holding torques against gravity

Depends on mechanism.py only — `equations.py` reads the engine's equations,
formed on the description's symbolic view rather than on kinematics.py's
matrices — so a red-team pass on one section reads that submodule, its
checks, and the note section. Check the milestone alone: `uv run python run_all.py dynamics`.
"""

# Run order and heading for `run_all.py`. Every submodule inherits them and
# runs in file-name order; import from the submodule that owns a name.
MILESTONE = (2, "Milestone 2: dynamics")
