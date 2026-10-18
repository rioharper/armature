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

## The engine and the project's half

An **armature-derive** model checks every milestone's claims against the **truth model**:
the project's mechanism description, compiled in full by the **engine**. The engine is the
plugin's `engine/` package, imported as `armature`, which a project pins rather than
copies. It holds the description's elements and their validation, the compiler, the
queries on a state (`pose`, `jacobian`, `inverse`, `settle`, `wrench`, `linearise`,
`release`), the reductions and `account`, the symbolic view, the sampler, the worst-case
search (`armature.search`, which takes a `Margin` over a `Space` of named axes) and the
review artifact. It is a standard Python package, outside this file's rules, so a fix
reaches a project as a version bump, never a re-copy. Its tests check it on the golden
mechanisms, against the verb matrix in `engine/tests/golden/matrix.py` (ADR 0008). Its docstrings are its
reference, and `armature/__init__.py` is the map.

The project keeps its half beside its milestone modules:

```
pyproject.toml           the model's environment: the engine as an editable path dependency
params.py                the values, keyed by name; standard library only
mechanism.py             MILESTONE = (0, ...); mechanism(p), DERIVED, and the truth model
mechanism_checks.py      compiles exactly, boxes inside the ranges, a release that fails
report_truth.py          writes the review artifact: frames table and skeleton renders
missions.py              what the actuators are sized against, from spec §6.4
drive.py                 drive(p), DRIVE_MARGINS = margins(...), DRIVE_EXEMPT
drive_checks.py          the drive's data against hand-worked answers
```

Spec §9 writes this half first, with a coarse `mechanism.py`, and derive refines the
same files (ADR 0007).

`mechanism.py` holds the description, `mechanism(p)`, and `DERIVED`, the variant the
derivation reads. It gives every other module the cached `truth()`, `derived()` and
`view()`, and the conversions between the engine's named states and the derivation's numeric
functions: `COORDINATES`, `numeric`, `vector`, `named` and `commands`. It sorts first, beside
`params.py`, so the run reports the description compiling exactly before any milestone
makes a claim against it.

Three rules keep it honest, all of them layout rules rather than physics:

- **`mechanism.py` imports `params.py` and the engine, and nothing else from the model.**
  No `kinematics.py`, no `dynamics/`. A truth model that borrows the derivation's frames or
  its mass matrix has the derivation's assumptions on both sides of every comparison, which
  is the exact blindness it exists to remove. The derivation reads its frames from the same
  description, so an error in the description is common-mode; validation when it compiles
  and the review artifact are its checks. Every simplification stays on the derivation's
  side, as a reduction the truth model does not make.
- **Every checks module draws its configurations from the engine's sampler**,
  `armature.sample` and `armature.sample_states`, and every worst case is a `Margin` the
  search finds. One sampler, seeded, whose map the search's `Coordinates` axis shares, so
  "over the envelope" is the same set in the kinematics check, the dynamics check and the
  worst-case search, and a reviewer re-running a file gets the configurations the note was written
  from. A checks module with a generator of its own is a check nobody can reproduce from the
  note; the rule and the reason are in **armature-derive**'s
  `references/derivation-standards.md`, under *Evidence over an envelope*.
- **Values live once, in `params.py`; geometry lives once, in `mechanism.py`.** The engine
  refuses a parameter the description reads and `params.py` never defines, or one defined
  and never read, naming it. `params.py` stays standard library only, so a CAD part file
  reads a mass target from it without the model's environment.

## Checks one file over

A module's self-tests live in a sibling checks module named for it: `kinematics.py` →
`kinematics_checks.py`. That includes the parameter block: `params.py` is data, and
`params_checks.py` holds the checks on the shape of that data — both signs of every signed
load case, every load direction a set, every tolerance band a parameter's and around its
nominal —
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

## The truth gate

A milestone's self-consistency checks are blind to the assumption sitting on both sides of
them, so a milestone whose only evidence is self-consistency has shown its equations
consistent and nothing about the machine. The gate is what stops the truth model being
skipped in silence, which is the only way it ever gets skipped:

**Every checks module in a model with a `mechanism.py`, its packages included, defines a
`test_truth_*` callable, or says why it does not.** That includes `mechanism_checks.py`, whose release checks are truth
checks. `layout.py` reports one truth column per module — the count, `n/a`, or
the exemption — and the full run fails on a gated module with neither. The prefix is a
naming convention rather than a registry because `layout.py` imports nothing but the
standard library: it reads the source's function names with `ast`, so it works on a machine
where MuJoCo will not import, which is exactly the machine most likely to have skipped the
truth model.

**Every module-level `Margin` in such a model passes `truth=` and `agree=`, or its module
says why it does not**, with the same exemption below. A margin computed from the
derivation is the derivation's claim at the one point that sizes the design; the search
evaluates `truth` at its worst point and its pre-polish best, and `run_all.py` fails a
disagreement beyond `agree`. `layout.py` reads a margin from the source as it reads a check's
name, as an assignment whose value calls `Margin` or `armature.Margin`. An assignment
calling armature.drive's `margins`, imported from `armature.drive`, carries its own truth,
the resolution check, and passes; a `margins(...)` imported from anywhere else is held as
a bare margin.

Two things sit outside the gate by nature, and the check knows it: `layout.py` itself, whose
`layout_checks.py` argues its `TRUTH_EXEMPT`, and
**any directory with no `mechanism.py`**, where the gate reports `n/a` and passes, which is
what lets the same file ship in the CAD part template unchanged. The engine is outside it
too: it is not the project's code, and its own tests check it.

A module that genuinely makes no claim a truth model can reach says so, at module level,
with the same argued-exemption mechanism the budget uses and the same reader parsing it:

```python
TRUTH_EXEMPT = "a naming convention and a units table; no physical claim to check"
```

Anything but a non-empty string raises. The reason appears in `layout.py`'s table and the
red-team challenges it — the exemption a session writes under time pressure is exactly the
one a fresh context should read. The model template ships one worked example: `params_checks.py`
argues that a block of *data* has no claim a simulator can be asked about, since its constants
are held against the truth model where they are used. No module in either template claims a
`LAYOUT_EXEMPT`.

## The budget: 250 code lines

A **code line** is any line not blank, not comment-only, and not part of a docstring.
Documentation is free; the only way under the budget is to split. `layout.py` counts —
`ast` for docstrings, `tokenize` for comments — and ships inside each template, stdlib only,
because it has to run where the model's environment does not:

- `python layout.py` (in the template's directory) prints every module's count and its
  truth column, and the line counts of the documents beside them — milestone notes, part
  definitions — for information, since documents carry no budget, then exits
  nonzero on a violation of either gate. It imports nothing but the standard library, so it runs where
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
