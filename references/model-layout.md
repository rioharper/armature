# Model layout — how generated model code is laid out

Every Python module **armature-derive** writes under `analysis/model/` and **armature-cad**
writes under `cad/parts/` follows these rules. Skills point here; they don't restate them.
Firmware, ROS nodes, and bench procedures (**armature-test**, **armature-bringup**) are the
user's own code under the project's conventions, and sit outside them.

Every agent that opens a module pays for the whole file: the session editing it, the
red-team at a checkpoint, a later stage looking up one constant. The rules keep each read
to what its question needs.

## One section, one module, one checks module

A module mirrors the document it accompanies — a milestone note, a `docs/testing/` report,
a part definition — and its decomposition mirrors that document's sections. Outline the
document before writing code: the split is then a consequence of the outline, known before
any code exists, never a refactor forced at the checkpoint. A document with more than about
three substantive sections gets a package from the start:

```
dynamics/
  __init__.py            MILESTONE = (2, "Milestone 2: dynamics") — the identity, nothing else
  lagrangian.py          note §1–2
  lagrangian_checks.py
  statics.py             note §3
  statics_checks.py
```

The package's `__init__.py` owns the milestone identity: its `MILESTONE` tuple orders and
titles the run, and every submodule inherits it, running in file-name order. Other modules
import from the submodule that owns a name. A library package (a shared helper, not a
milestone) makes its `__init__.py` the public surface instead: the contract docstring and
the re-exported names callers import.

That triple — a document section, its submodule, its checks — is the red-team's review
unit: one coherent argument, held in view at a time.

## The truth package

An **armature-derive** model carries one package that is not a note's counterpart:
`truth/`, the **truth model** — an independent simulator model of the mechanism,
generated from `params.py`, that every milestone's claims are checked against. It is both
a milestone package and a library package, and takes the shape of each: `MILESTONE = (0,
"Milestone 0: truth model")` in its `__init__.py` sorts it **first** in the run, and that
same `__init__.py` is the backend-neutral public surface — `build`, `sample`, and the
query each milestone needs — so a second backend, or a floating-body builder beside the
chain builder, changes nothing above it.

```
truth/
  __init__.py            MILESTONE = (0, ...), and the public surface callers import
  chain.py               a serial chain from the DH or PoE table -> a simulator model
  chain_checks.py        the builder round-tripped against the parameter block
  envelope.py            the seeded sampler every other milestone's checks draw from,
                         over the envelope and over the intended workspace
  envelope_checks.py
  equilibrium.py         settling to rest under held commands and applied loads
  equilibrium_checks.py
  floating.py            a floating base plus joints, on unilateral cables
  floating_checks.py     the builder round-tripped, on a minimal hanging fixture
  inverse.py             inverse dynamics — one submodule per query the milestones need
  inverse_checks.py
  modes.py               linearisation: mass, stiffness and the modes they give
  modes_checks.py
  release.py             an assumption let go: the displacement of what it fixed
  release_checks.py      that, and the degenerate fixture proving the check fails
```

**One builder per convention family, and a project keeps one.** `chain.py`
serves a serial chain on a fixed base — modified DH, standard DH, or PoE —
and `floating.py` a floating base plus joints, where the body's own pose is six
coordinates and cables, legs or wheels hold it up. Which one a model uses
follows the topology the plan glossary settled; the other builder, its checks
module and its line in `__init__.py` are deleted, so no module in the package
reads a parameter block it was never given. Each builder names its own entry
point `build`, and the `__init__.py` that ships both surfaces the second one
under a second name, so whichever builder a project keeps, `truth.build` is its
model and nothing above the package is rewritten. Every *query* — the settle,
the inverse dynamics, the linearisation — takes the `(model, data)` pair either
builder returns, which is what makes the surface above them one surface. The
sampler is not a query: it reads the parameter block's envelope directly, so a
mechanism whose coordinates are not a box in `qpos` samples its own poses.

Two rules keep it honest, and both are layout rules rather than physics:

- **It imports the parameter block and nothing else from the model.** No `kinematics.py`,
  no `dynamics/`. A truth model that borrows the derivation's frames or its mass matrix
  has the derivation's assumptions on both sides of every comparison, which is the exact
  blindness it exists to remove.
- **Every other checks module draws its configurations from it.** One sampler, seeded, so
  "over the envelope" is the same set in the kinematics check, the dynamics check and the
  worst-case search, and a reviewer re-running a file gets the configurations the note was
  written from. A checks module with a generator of its own is a check nobody can reproduce
  from the note; the rule and the reason are in **armature-derive**'s
  `references/derivation-standards.md`, under *Evidence over an envelope*.
- **It shares `params.py` rather than copying it.** Two models built from two copies of
  the constants drift the first time one is edited, and a check between drifted models
  proves nothing about either.

Sorting first is not cosmetic: a milestone's truth check is only as good as the model it
checks against, so the builder's round-trip against the parameter block is the first
thing the run reports.

## Checks one file over

A module's self-tests live in a sibling checks module named for it: `kinematics.py` →
`kinematics_checks.py`. That includes the parameter block: `params.py` is data, and
`params_checks.py` holds the checks on the shape of that data — the symbol table mirroring
the numbers, the envelope one row per coordinate, both signs of every signed load case —
each of which is a whole class of downstream result quietly sized against the wrong thing. Locality is kept — the checks sit beside what they check — and
neither file carries the other's lines. Discovery pairs the two by name, so moving a check
costs no registration; pytest never collects a `*_checks.py` directly, so the one pytest
bridge stays the only path and the two entry points cannot disagree. A checks module
orphaned by a rename, or paired with a report module, fails the layout check instead of
silently never running. A module named something `import` cannot spell — a part file,
`ARM-BRK-001.py` — is loaded by its checks module through `importlib` under the checks
module's own name, as the CAD template's `part_checks.py` shows.

## Reports print

Table formatting and long printed results live in a report module: `report_<scope>.py`
(`report_results.py`, `report_t11.py` for a plan task), or `report.py` inside a package.
Discovery never takes a report module for a milestone module, and a report module never
checks anything, so a renderer never inflates the file a red-team reads to check equations.

## The budget: 250 code lines

A **code line** is any line not blank, not comment-only, and not part of a docstring.
Documentation is free; the only way under the budget is to split. `layout.py` counts —
`ast` for docstrings, `tokenize` for comments — and ships inside each template, stdlib only,
because a copied project cannot import the plugin:

- `python layout.py` (in the template's directory) prints every module's count, and the
  line counts of the documents beside them — milestone notes, part definitions — for
  information, since documents carry no budget, then exits
  nonzero on a violation. It imports nothing but the standard library, so it runs where
  SymPy, SciPy, or build123d cannot.
- `run_all.py` — the same discovery runner in both templates — collects `layout.py`'s
  checks like any other, so the full run fails on a module over budget: in
  `analysis/model/` that run and `pytest` are the milestone checkpoint; in `cad/parts/`
  it is the one command that runs every part file's and library's self-tests. Running one
  name (`run_all.py kinematics`, `run_all.py check`) leaves the budget out: a file still
  being written is not red-barred mid-work.

A module that genuinely must stand large says why, at module level:

```python
LAYOUT_EXEMPT = "one generated lookup table; splitting it splits the table"
```

Anything but a non-empty string raises, so an exemption cannot be claimed without being
argued. The reason is surfaced in `layout.py`'s table, and the red-team challenges every
one: the fresh context judges the exception better than the session that just wrote the
file.

## Licence headers

A generated module that carries a licence carries one line —
`# SPDX-License-Identifier: <id>` — and the full text stays in the repository's licence
file. A header copied into every file multiplies by every split.
