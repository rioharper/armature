# ADR 0004 — The model machinery is a package projects pin, not a template they copy

2026-10-11 — Status: accepted (reverses #48's placement of the truth model inside the model template; distribution still open)

The mechanism description's elements, its compiler, the truth-model queries,
the reductions, the symbolic view and the sampler live in one Python package in
this repository: `engine/`, imported as `armature`. It is versioned, pinned to
one MuJoCo minor (`mujoco ~= 3.15.0`), and tested by its own pytest, which is
where the five fixture mechanisms run. A project depends on it rather than
copying it, and the model template keeps only the project's half: the
description, the milestone modules and their checks modules. The template's
`truth/` package is deleted, not patched. The engine is a standard Python
package, outside `references/model-layout.md`'s rules (sibling checks modules,
the 250-line budget); those stay the rulebook for the code a project writes.
This settles one of the pipeline-v2 decisions, how projects take the model
machinery, except for distribution.

#48 put the truth model inside the template deliberately: a copied project
cannot import the plugin, and the template's own `run_all.py` and pytest were
to be the only test seam. A month later every copy had forked. Plumb's truth
model imports the derivation it is meant to check; Ibex pins nothing and never
probed MuJoCo; `layout.py` and `run_all.py` drifted between the two templates.
The bugs found on 2026-10-11 — springs and cables linearised as 0 N/m,
constraints refused, floating bodies misread — would have to be re-copied into
each project by hand, because a fix to a copied template reaches none of them.
A pinned package is the only shape in which a fix reaches a project as a version
bump.

The cost accepted: a project gains a dependency that has to be versioned and
installed, and can no longer patch its truth model in place; a MuJoCo upgrade
becomes an engine release. How the package reaches a project (PyPI, a git URL,
or an install from the plugin root) is not decided here. Until it is, a project
in development, such as Ibex running the plugin with `--plugin-dir`, takes it as
an editable path dependency on this repository. Revisit if no distribution
works offline and reproducibly, or if projects start needing local forks of
engine behaviour.
