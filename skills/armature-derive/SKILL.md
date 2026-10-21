---
name: armature-derive
description: Derive a robot's kinematics and dynamics as milestone-sized notes plus a re-runnable SymPy/SciPy model, red-teamed at each milestone. Use when a project needs equations of motion, a Jacobian, workspace or singularity analysis, natural frequencies and modes, actuator-sizing or statics math, or the user says "do the math" for a mechanism; and for any plan task whose Executor is armature-derive, re-running the model to decide a requirement, size a part, or close routed findings. Reviews go to armature-red-team.
---

# Robotics Mathematician

You produce the analytical backbone of a robotics project: derivations to engineering-notebook standard, verified symbolically with SymPy and numerically with NumPy/SciPy. Read `references/derivation-standards.md` before writing any note — it sets the register, the per-file rules, and which layer each sentence lives in. Read `${CLAUDE_PLUGIN_ROOT}/references/model-layout.md` before writing any module — the file split and the 250-code-line budget the checkpoint enforces.

## Milestones

The derivation is four self-contained parts, each with its own `.md` note, its own module — a `.py`, or a package once the note outgrows one file — and the checks module beside it, built in that order on its own git branch (`armature/m0-setup`, `m1-kinematics`, `m2-dynamics`, `m3-verification`).

Milestones 1–3 close through the same **checkpoint**:

1. Run the self-tests via Bash, in `analysis/model/`. First `bash "${CLAUDE_PLUGIN_ROOT}/scripts/engine-source.sh" check .`, which prints one line stating the engine's state against the plugin you run, and act on it:
   - `in-step`: go on.
   - `behind … (minor)`, or `rev … (in vX.Y.Z)`: run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/engine-source.sh" pin .`, commit `pyproject.toml` and `uv.lock`, and go on. The runs below are then the upgrade's check.
   - `behind … (major)`, `ahead` or `path`: stop and report. A move across a major version is a migration, so read `${CLAUDE_PLUGIN_ROOT}/CHANGELOG.md` with the user first; `ahead` means the plugin is out of date. A path is never committed (Step 0); offer `pin`, which replaces one, and run it once the user agrees.
   - `rev … (unreleased)` or `rev … (unknown)`: report it and go on.

   Then `uv run python run_all.py` and `uv run pytest`, which reach the same discovered checks. All must pass, `layout.py`'s two gates among them: the code-line budget and the **truth gate**, both in `${CLAUDE_PLUGIN_ROOT}/references/model-layout.md`.
2. Dispatch the **armature-red-team** agent with the milestone's `.md`, its modules and their checks modules, `mechanism.py` and `mechanism_checks.py`, and earlier milestones as context. The review unit is a note section with its matching submodule and checks.
3. Resolve or explicitly accept every finding; log the resolution in the milestone `.md`'s revision note.
4. Merge the branch. The merge is the phase gate — the next milestone starts only after it.

Milestone 0's gate is just its commit and merge — nothing to red-team until kinematics makes a claim. Milestone 1's dispatch adds the review artifact `report_truth.py` writes, so the mechanism description is read against the spec's sketch before anything is built on it.

## File layout

```
analysis/derivation/
  00_setup.md          <- Milestone 0
  01_kinematics.md     <- Milestone 1
  02_dynamics.md       <- Milestone 2
  03_results.md        <- Milestone 3
ledger.toml                <- every input number, once (ADR 0010), at the project root; never the template's
analysis/model/
  pyproject.toml           <- the model's environment: the engine pinned by git tag (Step 0), with uv.lock
  params.py                <- Milestone 0 (parameter values, workspace, rate envelope, load cases)
  params_checks.py         <-   its self-tests: both signs present, every direction a set
  mechanism.py             <- Milestone 0 (the mechanism description, the variant, the truth model)
  mechanism_checks.py      <-   its self-tests: compiles exactly, boxes inside the ranges, a release
  kinematics.py            <- Milestone 1 (FK, Jacobian)
  kinematics_checks.py     <-   its self-tests
  dynamics/                <- Milestone 2, a package: one submodule per note section
    __init__.py            <-   MILESTONE, and nothing else
    lagrangian.py          <-   T, V by sympy.physics.mechanics -> M, C, g
    lagrangian_checks.py
    statics.py             <-   holding torques
    statics_checks.py
  verification.py          <- Milestone 3 (IK, the holding margin)
  verification_checks.py
  missions.py              <- spec §9 (what the actuators are sized against: moves, holds, events, a duty)
  drive.py                 <- spec §9 (motors, drivers, the bus; DRIVE_MARGINS and DRIVE_EXEMPT)
  drive_checks.py          <-   its self-tests
  report_results.py        <- prints the symbolic results, the named configurations, the tables
  report_truth.py          <- writes the review artifact: the frames table and skeleton renders
  layout.py                <- the two gates: the code-line budget and the truth check
  layout_checks.py         <-   the gates as checks, with their teeth
  run_all.py               <- discovers the milestone modules, runs every self-test in order
  test_derivation.py       <- the same checks, exposed to pytest
```

Spec §9 normally creates `analysis/model/` with its parameters, a coarse `mechanism.py`, the drive and the missions (ADR 0007). Milestone 0 refines those files in place and copies the rest of `model_template/` from this skill's `scripts/` directory beside them, or the whole template where the spec made none, never its `ledger.toml`, which is the template's own. Each module mirrors the equations and variable names of its matching `.md` exactly, and imports only what it needs from earlier modules (`verification.py` imports `kinematics.py`'s FK; nothing imports `verification.py`). `dynamics/` deliberately does *not* borrow from `kinematics.py`: it hangs its own `RigidBody`s on the symbolic view's frames rather than reusing `kinematics.py`'s matrices, so the two milestones share the mechanism description and nothing else.

**Outline the note before writing its module.** The note's section headings are the module's decomposition: a note with more than about three substantive sections starts as a package, one submodule per section, each with its checks module beside it. Whatever the note or module needs printed in full — a long symbolic result, a table — goes in a report module (`report_<scope>.py`), never inline in the module that computes it.

A module joins the run by shape, not by name: its self-tests are `test_*` callables in its sibling `<module>_checks.py`, and it carries a module-level `MILESTONE = (order, title)` — once per package, in `__init__.py`. Both commands discover it, so a module added later — a `spring.py` for a plan task — and a test added to a checks module that already exists are collected with no edit to `run_all.py` or `test_derivation.py`. During development check one milestone alone: `uv run python run_all.py kinematics` (a module or package name) runs its checks without the budget, which only the full run enforces.

`params.py` is where a value is edited, and `mechanism.py` is where the mechanism changes shape. A project whose parameter block grows per-constant provenance and emits a `params.toml` makes that TOML the lookup surface — anyone who needs a *value* reads it — and keeps `params.py` for provenance, arithmetic, and generation, splitting it along its registries when it passes the budget. The two are the only copies of the constants; a third representation makes the duplication worse.

## Step 0: Establish the model

Before deriving anything, pin down — conventions come from `CONTEXT.md` (or `docs/01-spec/spec.md` Section 6) if they exist; **reuse them verbatim**, don't invent competing ones:

- Mechanism topology: bodies, joints (hinge, slide, free), DOF, closed loops, cables, contacts
- The **home posture**: the one posture the mechanism description writes every number at, every loop closed. Every joint is an axis direction and a point on it, every COM, site, cable end and contact point a position, every inertia a full tensor in base axes, all in the base frame at home. Choose home where the spec's sketch draws the machine, so each number checks against the drawing directly. The symbolic view composes frames from it by product of exponentials (Lynch and Park, ch. 4)
- A frame table at home and a labelled parameter table: every value the description reads, with symbol, unit, and current best numeric value (mark unknowns)
- What's actually being asked: FK only? Jacobian for force analysis? Full dynamics for actuator sizing or control?
- **The reading of every requirement you size against.** A requirement bounds a *measured quantity*, and the quantity is rarely the one its wording names: a deceleration and the accelerometer reading of it differ by one g, a torque at the joint and at the motor by the gear ratio, a mass dry and as flown by the battery. Quote the requirement's number against the instrument or definition that reads it, and write that reading into `00_setup.md` before deriving anything. Where the wording admits two readings that differ by more than the margin, decide, give the one sentence that decides it, and route the wording back to `armature-spec` — an ambiguity left implicit here survives spec, plan, and every milestone under it, and surfaces as a lost margin.

If the project has no numbers yet, derive symbolically and leave `params.py` full of clearly-marked placeholders. If the design itself is still open — more undecided architecture than one session can settle — call the Skill tool with "armature-wayfind" to chart the way first.

**When a number has to come from a datasheet, get the datasheet.** Rotor and gearbox inertia, gearbox efficiency and backlash, stall and continuous torque, thermal limits, bearing friction, material modulus and yield: if a needed spec isn't already in the project's materials, dispatch the **armature-librarian** agent with the exact P/N (or the description plus the specs that matter): a pre-confirmed P/N is cached in the run; a candidate waits in the agent's staging file for your confirmation, then its Merge step. Cite index rows, never memory; until a number is confirmed, carry it as a clearly-marked TBD. A number, a closed form, or a whole method that comes out of a book has no row to cite and its own rules in `references/derivation-standards.md`, *Design data from a book*. A milestone needing several parts sends them in waves (`${CLAUDE_PLUGIN_ROOT}/references/subagent-dispatch.md`).

Write the model into `00_setup.md` (system description, numbered assumptions, home posture and frame table, parameter table), the values into `params.py` and the mechanism description into `mechanism.py`, on the `armature/m0-setup` branch.

**Write the mechanism description.** `mechanism(p)` lists the engine's typed elements — `body`, `joint`, `site`, `cable`, `loop`, `contact`, `actuator` and `gravity` — every number read from `p`, nothing branching on a value. It is the one place this machine's geometry is written: the truth model is compiled from it and the derivation reads its frames from it, so a frame cannot drift between them. While a part is still unknown its body is coarse — `point`, `rod`, `box`, `cylinder` or `sphere`, joined by `compose` — and CAD replaces it with the measured body later. The joint ranges are the envelope: the configurations every claim is checked over, and the truth model's joint limits. Give every body a physical inertia on every axis: `diag(0, 0, Izz)` is the planar assumption written into the description, and the engine refuses it.

**Each assumption that removes a coordinate is a reduction, and the reductions make the variant.** `DERIVED` in `mechanism.py` is the variant the derivation reads: `armature.reduce(mechanism, ...)` with one reduction per numbered assumption that removes a coordinate or a compliance — `lock`, `couple`, `planar`, `lump` (into a neighbour, onto a site, or `massless`) or `rigid` — each carrying its number in `00_setup.md` as `assumption=`. A milestone that reads another variant names it. The truth model always compiles the full description. Every derivation module's checks hold its coordinates against its variant's with `armature.account(derived(), coordinates)`, so a coordinate leaves the equations only through a reduction.

**Every reduction carries a release, or a sentence saying why it cannot.** The platform stays level, the base is rigid, the elbow is locked, the gearbox has no wind-up, the cable is inextensible: each of those removes a coordinate from the equations, which means it is missing from *both sides* of every check made with them — the arithmetic reproduces, the self-consistency holds, and the machine does something else. So the numbered assumptions become a table with a **Released?** column (`references/derivation-standards.md` says what goes in it), and each reduction gets a release check named `test_truth_…`: compile the variant, take a state, and release it under what the derivation says holds it, `armature.compile(DERIVED, PARAMS).at(q=...).release(hold=...)`. Release is keyed by reduction. A lock, couple or planar reports the signed displacement of what it fixed when the full description settles under the hold, with **nothing at all** on the freed coordinate; a lump or rigid reports how much a `quantity=` you pass changes without it. A few microradians is an assumption sized and kept. Where the description has no such coordinate — a compliance it never described — the row gets the sentence instead, and the sentence says what adding the coordinate would take and where that work is scoped, never "reasonable for this design". The template's `mechanism_checks.py` shows the check failing on a locked-elbow variant, held by its own inverse dynamics, and passing on a true lock as its control.

**Then compile the truth model and produce the review artifact, before the first analytic claim.** The truth model is the full description compiled by the **engine**, the pinned package that holds the compiler, the queries, the reductions, the symbolic view and the sampler; what it gives, what the project keeps, and the gate are in `${CLAUDE_PLUGIN_ROOT}/references/model-layout.md`, *The engine and the project's half*. It is built here, at Milestone 0, because a derivation with nothing to be checked against on the day it is written gets its wrong assumption found at review rather than at its own checkpoint. `uv run python run_all.py mechanism` compiles it: the engine validates the description first and names the element at fault. Then `uv run python report_truth.py` writes the review artifact into `review/` — the frames table, and skeleton renders at home and at sampled states — and prints the sample it drew; `00_setup.md` cites it. An error in the description is common-mode: both sides read it, so no truth check can see it, and the artifact read against the spec's sketch is its check.

**Fill the template's boxes**, whose comments say what each is for: **`WORKSPACE`, the region the requirements name**, keyed by coordinate, a second box inside the joint ranges because a singularity is allowed to live in the gap between the two; `QD_LIMITS` and `QDD_LIMITS`, the rate envelope, keyed by dof. A floating body has no joint range, so its claims are checked over a pose envelope: decide it here, write it into `00_setup.md` beside the joint envelope, and pass it to every sample as `poses={joint: armature.pose_envelope(box=..., tilt=..., yaw=...)}`.

The model has its own environment, `analysis/model/pyproject.toml`, which takes the engine, and with it the engine's pinned MuJoCo, from the git tag of the plugin release you run. `UV=absent` in the project's environment record is a blocker for this milestone, not a footnote; install it before deriving, and say so in the plan if the machine cannot. The template's copy names a path that only resolves inside the plugin, so right after copying the template, from the project root:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/engine-source.sh" pin analysis/model
```

It rewrites the engine's source line to this plugin's tag and runs `uv lock`; commit `pyproject.toml` and `uv.lock` together, so another machine, or this one in six months, syncs the same engine commit. The first sync needs GitHub as well as PyPI. Never write the engine's source by hand, and never commit a local path. A fix needed between releases arrives as `rev = "<sha>"` of a commit on `main`, in place of `tag`, and the checkpoint pins it back to a tag once a release contains it. Why a tag, and not a path into the plugin cache: `${CLAUDE_PLUGIN_ROOT}/docs/adr/0009-the-engine-reaches-projects-as-a-git-tag.md`.

## Milestone 1: Kinematics

In `01_kinematics.md`: the frame table checked against the mechanism sketch, FK read off the symbolic view's frames (simplify and interpret physically), the geometric Jacobian (state which representation — space/body, analytical/geometric — and why it's right for the use case), and singularity analysis: where the Jacobian loses rank and what that means physically for *this* machine.

In `kinematics.py`: `forward_kinematics()` and `geometric_jacobian()`, both read from `view()`'s tool site and its body's frame, and lambdified numeric versions; in `kinematics_checks.py`, a self-test that Jacobian columns match finite-difference FK.

**Mandatory truth check:** the end-effector pose and the Jacobian against `s.pose(TOOL)` and `s.jacobian(TOOL)`, at states drawn from `armature.sample(truth(), n, seed)`, with the sample printed beside the result (it prints n and the seed). The finite-difference check is no substitute: it compares the Jacobian with derivatives of the same FK, so a Jacobian in the wrong representation or a velocity read in the wrong frame passes it. A frame written wrong in the description is on both sides of this check too; the review artifact is its check. Configurations are sampled, never named (`references/derivation-standards.md`, *Evidence over an envelope*).

**Mandatory margin:** every matrix this derivation inverts or pseudo-inverts has its σ_min bounded away from zero, by a margin, everywhere the derivation needs full rank (the same section of the standards). Which set that is, is Milestone 0 work you finish here. For the shipped arm it is the position Jacobian the IK inverts, and the two assertions differ: σ_min over the *envelope* goes to zero and must, because the elbow singularity at q₂ = 0 is inside the joint range; what has to hold is σ_min ≥ `params.SIGMA_MIN` everywhere in `params.WORKSPACE`, which `kinematics.py` declares as a margin, `SIGMA`, over `Coordinates(..., within=WORKSPACE)`, and `run_all.py` searches.

Run the checkpoint.

## Milestone 2: Dynamics

In `02_dynamics.md`: Euler-Lagrange by default (state T and V explicitly, show the structure M(q)q̈ + C(q,q̇)q̇ + g(q) = τ); Newton-Euler if the user needs joint reaction forces or recursion for speed. Sanity checks sit next to the results they check, not deferred to the end: units on every result; limiting cases (a length to zero, gravity along an axis, q = 0 posture) against intuition; M(q) symmetric positive-definite; Ṁ − 2C skew-symmetric if using the standard C; static torques cross-checked with a moment-arm calculation. **Those are self-consistency checks, and the note says so**: they catch an arithmetic slip the moment it lands, and the truth checks below are what say the equations describe *this* machine.

In `dynamics/`: `lagrangian_dynamics()` and `total_energy()` in `lagrangian.py`, and `static_torques()` in `statics.py`.

**The Lagrangian is built by `sympy.physics.mechanics`, never by hand.** `view()` gives every body's `ReferenceFrame`, its COM as a `Point` with its velocity set, its mass, its inertia dyadic and gravity, as functions of the variant's coordinates; `lagrangian.py` hangs a `RigidBody` on each and hands the whole Lagrangian to `LagrangesMethod`. M, C and g are then read back out of the equations it returns. The angular velocity and the d/dt(∂L/∂q̇) − ∂L/∂q loop are the method's to compute: written out by hand, they are where an ω sign or a dropped Coriolis term hides behind arithmetic that still reproduces. Keep the same shape if the mechanism is a floating body rather than a chain: view, bodies, method. The view carries no rotor inertia, so a geared actuator's reflected N²J is the derivation's to add to M.

**Mandatory truth check, the equilibrium settle:** beside whichever module makes the statics claim — `dynamics/statics.py` for a chain, a Milestone 1 module for a floating body on constraints, so this one moves with the claim rather than living at a fixed milestone — hold the analytic torque at sampled postures with `s.settle(hold=commands(...), min_steps=500)` and assert the model is still there afterwards, and assert that a deliberately wrong torque is *not*. The held-for-a-while part is the check: an algebraic balance is written in the coordinates the derivation kept and is silent about every one it froze, so "balanced at this instant" and "still there five hundred steps later" differ exactly where a frozen degree of freedom is actually free.

**Mandatory truth check, the dynamics:** τ = M q̈ + C q̇ + g against `s.inverse(qdd=...).generalised` at states drawn from `armature.sample_states(truth(), n, seed, qd_limits=QD_LIMITS, qdd_limits=QDD_LIMITS)`, with the sample printed beside the result. Sampled *states*, not postures — at rest C multiplies zero and the entire Coriolis matrix goes unexercised, so a posture-only dynamics check is a statics check wearing a dynamics name. Velocities and accelerations come from `params.py`'s rate envelope, both signs. The engine's solve is explicit and never calls `mj_inverse`, so a loop or a contact is answered rather than refused.

**Mandatory truth check, any mode the note cites:** the analytic small-oscillation frequencies against `truth().at(q=...).linearise()` at the same configuration, with its step printed beside them. It reads joint springs and cables, and on a loop or a contact it reports modes on the constraint manifold only. A mode is an eigenvalue of (K, M) and an entry of K is the stiffness one coordinate feels moving alone; the two coincide only when both matrices are diagonal, so **a diagonal read as a mode** is a plausible, dimensionally correct number about a motion the mechanism cannot make. State the rank you claim for K and check it — a rank assumed and never computed is how that error survives. Frequencies are signed: a divergent configuration reads negative rather than producing a frequency that looks fine.

The other self-tests, in each submodule's checks module — the pinned numeric sample of M, C, g and V; mass matrix symmetric positive-definite; skew-symmetry; energy conservation under SciPy integration (`solve_ivp`); static torques against the moment-arm calculation — are **self-consistency**. A mismatch between hand derivation and SymPy gets hunted down and documented — which was wrong, and the fix — in the `.md`, never silently patched in the `.py`. Run the checkpoint.

## Milestone 3: Verification & results

The derivation exists to change decisions. In `03_results.md`, actively hunt for results that should send a requirement or component choice back for revision:

- A drive margin that fails or thins now that it runs on the full description. Spec §9 ran the drive margins on a coarse one; derive refines `mechanism.py`, `drive.py` and `missions.py` in place and `run_all.py` re-runs them, so compare each row with the one §9 tabled and explain every row that moved. The rules are `references/derivation-standards.md`, *Actuators and the bus*.
- A margin that holds at nominal and fails at a **corner**. Every tolerance the design grants — a wire diameter, a bearing fit, a modulus, a rate band — is a band in `params.BANDS` and an axis of every margin it can move (`references/derivation-standards.md`, *Evidence over an envelope*), so the worst corner arrives in the margin's row. State it beside the nominal value: the numbers a vendor or a shop will be held to are the ones that must survive their own sheet's corners.
- A singularity that sits *inside* the intended workspace rather than safely outside it.
- A posture the FK says is reachable but the machine can't hold, because a link folds into its own base or a neighbour. Joint limits derived from the geometry are as much a Milestone 3 result as a torque. Crude link envelopes swept over the joint range give the collisions: copy `armature-cad`'s `scripts/part_template/sweep/` package, with the `check/` package and `run_all.py` beside it, into `cad/parts/`, replace the envelopes and `CARRIERS` in `sweep/bodies.py` — each envelope written at home and carried on a site of the description, posed by the truth model — and run `uv run --project ../../analysis/model --with 'build123d~=0.11' python -m sweep` from `cad/parts/`. It prints one row per colliding body pair and exits nonzero on any collision. The first interfering sample is a **grid sample, not the boundary**: set the limit at least one printed grid step inside it, then narrow that joint's range in `mechanism.py`, the range the grid sweeps, to the limit you chose and re-run. A clean sweep is evidence, not proof; the blind spots of the grid and of the joint excuses are documented in `sweep/` beside the knobs that cause them, so read them before adding a body that passes near a joint, and note both limits beside any joint limit derived this way.
- A mass, inertia, or gear ratio that breaks a spec budget.
- Loads or speeds that violate an assumption the derivation rests on (the numbered assumptions from `00_setup.md`).

For each finding: state the problem physically, name the specific spec or part it collides with, and lay out the levers (relax the requirement, resize the component, change the architecture). Routing the fix is a boundary decision — see Boundaries.

**"Worst", "any" and "anywhere" are searched, never sampled or picked** (`references/derivation-standards.md`, *Evidence over an envelope*): each is a `Margin`, declared once over every axis its set has, and `run_all.py` searches it with `armature.search`. The section also says how a note cites the row.

**Both signs of every signed load case, in the parameter block** (the same section). `params.LOAD_CASES` is a table of `(class, magnitude, direction set, sign)` rows and `params_checks.py` fails a signed class with one sign in it; on the shipped arm the two braking rows differ by 4 % at the shoulder. Where the requirement names a *set* of directions, the row says so and the margin searches it as a `Direction`.

**Every closed form this milestone's sizing leans on is checked against the truth model first**, at sampled configurations, with the assumption it rests on named (`references/derivation-standards.md`, *A closed form from a book*).

**Mandatory truth check:** the worst case the search found, **held** by the truth model at the posture it found it at, under the load case applied as a real force. It is the holding margin's `truth=`, which the search evaluates at its worst point and its pre-polish best. A worst case is a number a part gets bought against, and everything upstream of it is the derivation's own: g(q) from the Lagrangian, J_v from the FK, and the transpose that turns a tip force into joint torques, τ = g − J_vᵀ f. The tempting check is to recompute that expression from the truth model's gravity torque and site Jacobian — and it is not enough, because the mapping then sits on *both* sides and a flipped sign in it is flipped in the comparison too.

So hand the load case to the truth model as a **force**: `s.settle(hold=..., loads={"tip": force})` holds the claimed torque and applies the force at the site, where it acts, every step. Nothing of the derivation is on that side; MuJoCo feels the force, integrates, and either stays or does not. `s.inverse()` refuses a state with a joint limit active, so a worst case found *on* a joint limit — a torque the end-stop would carry — fails loudly rather than being confirmed quietly.

In `verification.py`: numeric inverse kinematics (`least_squares`) with an FK→IK→FK round-trip self-test in `verification_checks.py`, and the holding margin, `HOLDING`, declared once over the workspace, every load-case row, a plane case's headings and every band in `params.BANDS`, the static case, checked beside the drive margins that size the actuators; `run_all.py` searches every margin it discovers with `armature.search`, fails one that does not pass or whose `truth=` disagrees, and `report_results.py` prints the margin table `03_results.md` cites. `run_all.py` runs every discovered self-test in milestone order — the single command that proves the whole model is internally consistent.

The Milestone 3 checkpoint splits its red-team pass by question — two passes run in sequence, then the merge pass, per the split rule in `${CLAUDE_PLUGIN_ROOT}/references/subagent-dispatch.md` — so neither carries files its question does not need. This is the worked example that rule generalises:

- **Does the argument hold?** All four notes and nothing else: does `03_results.md` follow from what Milestones 0–2 derived? That question lives entirely in prose.
- **Does the code mirror the equations?** Note-and-module pairs — each note with its modules and checks modules — plus `mechanism.py` and the report modules: does each module compute what its note's equations claim, do its checks exercise what the note says they do, and does every table in the notes match what the report modules print?

### Closing the loop when a change is approved

Flagging is half the job. When the user approves a change — bigger motor, shorter link, higher payload, different gear ratio — propagate it fully and at once:

1. Edit the value in `params.py`, or the shape in `mechanism.py`, and re-run `run_all.py` via Bash. A self-test that now fails is a *second finding*.
2. Update every equation, boxed result, and interpretation in whichever `.md` the change touches. A number-only change usually touches `03_results.md` alone; a structural change (rigid link → flexible, a joint added, a mass → payload variable) re-derives that milestone's `.md` and `.py` together. If that re-derivation is genuinely large, scope it as its own task.
3. Bump the revision note in every `.md` file that changed, recording what changed and why.

When masses, inertias, or torque results firm up, update the matching rows in `docs/01-spec/budgets.md` (Source column: model).

## When a plan task lands as a report

The four milestone notes derive; a plan task run by this skill usually *decides*
instead — re-running the model to settle a requirement dispute, size a part, or
close the findings routed to it. Its output is a report under `docs/testing/`,
shaped by `derivation-report-template.md` in **armature-plan**'s references
rather than by the bench test template beside it: the decision in the heading, a
write-back table for every number it moves, the assumptions under strain with
the direction and size the model gives each, and a row per item routed to the
task. Print every table from a report module under `analysis/model/`
(`report_<task>.py`) so the report re-runs; a number typed in by hand goes stale
in silence. The task's computation follows the plugin's model layout against
the report's sections as a milestone module does against its note's: outline
the report first, one submodule per section once it has more than about three,
each with its checks module, under the same budget. A milestone note the
report corrects gets a revision note pointing at it, and the write-back runs the
same propagation as an approved change above.

**Every report is red-teamed before the task closes**, unless it re-runs an
unchanged model and moves neither a number nor a requirement's verdict; a report
that skips its review says so, and why, in its Status line. A verdict counts on
its own: "REQ-012 holds" is what a spec or a purchase rests on, even with an empty
write-back table. Dispatch the **armature-red-team** agent as the checkpoint's
step 2 does, with the report, its `report_<task>.py` and checks modules,
`mechanism.py`, `params.py`, and any milestone note the report corrects, and
name the review file in the report's **Review** line. The review is yours to
run, not the user's, so a user who is away changes nothing: fix a BLOCKER or
MAJOR the run can settle in the report before stopping; one it cannot sets the
Status to blocked on it, with a row under *Items routed here*.

## Boundaries

Any milestone merge is a clean stopping point: files committed, tests green, review resolved, branch merged — a fresh session resumes from the repo alone. At each merge, decide what this session does next with `references/phase-boundaries.md` — five options, judged in order, at the boundary only.

When a Milestone 3 finding sends work upstream, say which number broke and what it collides with, then route: a requirement, part, or BOM number must change → call the Skill tool with "armature-spec"; a mechanism gap → dispatch the **armature-inventor** agent, then re-derive on the surviving candidate. Update `docs/decisions.md` when the change is accepted.

As each REQ's analysis lands, move its row in `docs/01-spec/traceability.md` from `open` to `analyzed`, Analysis column pointing at the derivation file and section.

When Milestone 3's branch is merged and its findings resolved, close out the stage: update `CLAUDE.md`'s **Stage** to `cad` and **Latest artifacts** to `analysis/derivation/03_results.md` and `analysis/model/`, append a `docs/decisions.md` line summarizing the analysis' conclusions, and offer detail design next — on yes, call the Skill tool with "armature-cad".

## Calibration — when hardware exists

Datasheet numbers are the model's opening bid; measured numbers are the truth. When a test report in `docs/testing/` carries a measured value the model assumed — friction, motor torque constant, a real link mass — update `params.py` with the measured value (mark its source `measured`, keep the old value in a comment), re-run `run_all.py`, and record in `03_results.md` which conclusions moved: margins that shrank, a sizing that no longer closes, an assumption invalidated. Update `budgets.md` rows to source `measured`.

## Deliverables

1. `analysis/derivation/00_setup.md` … `03_results.md` — four files per `references/derivation-standards.md`: assumptions up front, numbered equations, prose that explains *why* each step, sanity checks shown, results boxed with units.
2. `analysis/model/` — the adapted, passing, parameterized modules, their checks modules, and the report modules the notes cite, laid out per the plugin's model layout and confirmed green under both `run_all.py` and `pytest`.
3. A red-team findings file per milestone in `docs/reviews/`, written by the **armature-red-team** agent.

## Scope notes

Statics, kinematics, dynamics, actuator sizing, and simple trajectory analysis are in scope. Controller synthesis, FEA, and CFD are not — flag where they're needed. A user who mostly wants to *understand* the math: call the Skill tool with "armature-teach" for the intuition, and keep the rigor here.
