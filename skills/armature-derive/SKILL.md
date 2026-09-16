---
name: armature-derive
description: Derive a robot's kinematics and dynamics as milestone-sized notes plus a re-runnable SymPy/SciPy model, red-teamed at each milestone. Use when a project needs equations of motion, a Jacobian, workspace or singularity analysis, actuator-sizing or statics math, or the user says "do the math" for a mechanism.
---

# Robotics Mathematician

You produce the analytical backbone of a robotics project: derivations to engineering-notebook standard, verified symbolically with SymPy and numerically with NumPy/SciPy. Read `references/derivation-standards.md` before writing any note — it sets the register, the per-file rules, and which layer each sentence lives in. Read `${CLAUDE_PLUGIN_ROOT}/references/model-layout.md` before writing any module — the file split and the 250-code-line budget the checkpoint enforces.

## Milestones

The derivation is four self-contained parts, each with its own `.md` note, its own module — a `.py`, or a package once the note outgrows one file — and the checks module beside it, built in that order on its own git branch (`armature/m0-setup`, `m1-kinematics`, `m2-dynamics`, `m3-verification`).

Milestones 1–3 close through the same **checkpoint**:

1. Run the self-tests via Bash — `python analysis/model/run_all.py` and `pytest`, which reach the same discovered checks, `layout.py`'s two gates among them. All must pass. The second gate is the **truth gate**: every checks module outside the truth package defines a `test_truth_*` callable, or carries `TRUTH_EXEMPT = "<why this module's claims need none>"`, and the run fails on one with neither. That is what stops the truth model being skipped in silence under time pressure, which is the only way it ever gets skipped; `references/model-layout.md` documents the gate and the exemption, and the red team challenges every exemption.
2. Dispatch the **armature-red-team** agent with the milestone's `.md`, its modules and their checks modules, earlier milestones as context. The review unit is a note section with its matching submodule and checks.
3. Resolve or explicitly accept every finding; log the resolution in the milestone `.md`'s revision note.
4. Merge the branch. The merge is the phase gate — the next milestone starts only after it.

Milestone 0's gate is just its commit and merge — nothing to red-team until kinematics makes a claim.

## File layout

```
analysis/derivation/
  00_setup.md          <- Milestone 0
  01_kinematics.md     <- Milestone 1
  02_dynamics.md       <- Milestone 2
  03_results.md        <- Milestone 3
analysis/model/
  params.py                <- Milestone 0 (parameter block, symbols, envelope, load cases)
  params_checks.py         <-   its self-tests: symbols mirror numbers, both signs present
  truth/                   <- Milestone 0, the truth model: an independent simulator model
    __init__.py            <-   MILESTONE, and the backend-neutral public surface
    chain.py               <-   a serial chain from the DH table -> a MuJoCo model
    chain_checks.py
    envelope.py            <-   the seeded sampler every milestone's checks draw from
    envelope_checks.py
    equilibrium.py         <-   settling to rest: what every equilibrium claim is checked on
    equilibrium_checks.py
    inverse.py             <-   inverse dynamics, what Milestone 2's torques are checked on
    inverse_checks.py
    modes.py               <-   linearisation: mass, stiffness, and the modes they give
    modes_checks.py
    release.py             <-   an assumption let go: what moves, and how far
    release_checks.py      <-   and the degenerate fixture that proves it has teeth
  kinematics.py            <- Milestone 1 (FK, Jacobian)
  kinematics_checks.py     <-   its self-tests
  dynamics/                <- Milestone 2, a package: one submodule per note section
    __init__.py            <-   MILESTONE, and nothing else
    lagrangian.py          <-   T, V by sympy.physics.mechanics -> M, C, g
    lagrangian_checks.py
    statics.py             <-   holding torques
    statics_checks.py
  verification.py          <- Milestone 3 (IK, worst-case search)
  verification_checks.py
  report_results.py        <- prints the symbolic results, the named configurations, the tables
  report_truth.py          <- prints the truth model itself and the configurations sampled
  layout.py                <- the two gates: the code-line budget and the truth check
  run_all.py               <- discovers the milestone modules, runs every self-test in order
  test_derivation.py       <- the same checks, exposed to pytest
```

At Milestone 0, copy `model_template/` from this skill's `scripts/` directory into `analysis/model/`. Each module mirrors the equations and variable names of its matching `.md` exactly, and imports only what it needs from earlier modules (`verification.py` imports `kinematics.py`'s FK; nothing imports `verification.py`). `dynamics/` is the one module that deliberately does *not* borrow: it turns its own `sympy.physics.mechanics` frames off the same DH table rather than reusing `kinematics.py`'s matrices, so the two milestones share the parameter block and nothing else.

**Outline the note before writing its module.** The note's section headings are the module's decomposition: a note with more than about three substantive sections starts as a package, one submodule per section, each with its checks module beside it. Whatever the note or module needs printed in full — a long symbolic result, a table — goes in a report module (`report_<scope>.py`), never inline in the module that computes it.

A module joins the run by shape, not by name: its self-tests are `test_*` callables in its sibling `<module>_checks.py`, and it carries a module-level `MILESTONE = (order, title)` — once per package, in `__init__.py`. Both commands discover it, so a module added later — a `spring.py` for a plan task — and a test added to a checks module that already exists are collected with no edit to `run_all.py` or `test_derivation.py`. During development check one milestone alone: `python analysis/model/run_all.py kinematics` (a module or package name) runs its checks without the budget, which only the full run enforces.

`params.py` is where a value is edited. A project whose parameter block grows per-constant provenance and emits a `params.toml` makes that TOML the lookup surface — anyone who needs a *value* reads it — and keeps `params.py` for provenance, arithmetic, and generation, splitting it along its registries when it passes the budget. The two are the only copies of the constants; a third representation makes the duplication worse.

## Step 0: Establish the model

Before deriving anything, pin down — conventions come from `CONTEXT.md` (or `docs/01-spec/spec.md` Section 6) if they exist; **reuse them verbatim**, don't invent competing ones:

- Mechanism topology: links, joints (R/P), DOF, any closed loops
- Convention: modified DH, standard DH, or product of exponentials — state which and why
- Frame definitions and a labeled parameter table: link lengths, masses, COM positions, inertias, gravity vector — with symbols, units, and current best numeric values (mark unknowns)
- What's actually being asked: FK only? Jacobian for force analysis? Full dynamics for actuator sizing or control?
- **The reading of every requirement you size against.** A requirement bounds a *measured quantity*, and the quantity is rarely the one its wording names: a deceleration and the accelerometer reading of it differ by one g, a torque at the joint and at the motor by the reduction, a mass dry and as flown by the battery. Quote the requirement's number against the instrument or definition that reads it, and write that reading into `00_setup.md` before deriving anything. Where the wording admits two readings that differ by more than the margin, decide, give the one sentence that decides it, and route the wording back to `armature-spec` — an ambiguity left implicit here survives spec, plan, and every milestone under it, and surfaces as a lost margin.

If the project has no numbers yet, derive symbolically and leave the parameter block full of clearly-marked placeholders. If the design itself is still open — more undecided architecture than one session can settle — call the Skill tool with "armature-wayfind" to chart the way first.

**When a number has to come from a datasheet, get the datasheet.** Rotor and gearbox inertia, gearbox efficiency and backlash, stall and continuous torque, thermal limits, bearing friction, material modulus and yield: if a needed spec isn't already in the project's materials, dispatch the **armature-librarian** agent with the exact P/N (or the description plus the specs that matter): a pre-confirmed P/N is cached in the run; a candidate waits in the agent's staging file for your confirmation, then its Merge step. Cite index rows, never memory; until a number is confirmed, carry it as a clearly-marked TBD. Design data that lives in a book rather than on a vendor sheet — fatigue endurance points, finite-life tables, friction pairs — has no row to cite and its own rule in `references/derivation-standards.md`. **So does a formula or a method out of a book**, in the same place: a closed form is checked against the truth model at sampled configurations *before the note cites it*, with the assumption it rests on named in the check as a constant the failure message quotes; a reference algorithm — a workspace method, a force-distribution law, a stiffness model, a DH convention — is tagged `standard` and cited by book and chapter in `00_setup.md`, because the red team's whole job on one is to read the derivation against the book and it cannot do that without knowing which book. A milestone needing several parts sends them in waves (`${CLAUDE_PLUGIN_ROOT}/references/subagent-dispatch.md`).

Write the model into `00_setup.md` (system description, numbered assumptions, conventions, parameter table) and the parameter block into `params.py`, on the `armature/m0-setup` branch.

**Every assumption that fixes a coordinate carries a release, or a sentence saying why it cannot.** The platform stays level, the base is rigid, the elbow is locked, the gearbox has no wind-up, the cable is inextensible: each of those removes a coordinate from the equations, which means it is missing from *both sides* of every check made with them — the arithmetic reproduces, the self-consistency holds, and the machine does something else. So the numbered assumptions become a table with a **Released?** column (`references/derivation-standards.md` says what goes in it), and each such row gets `truth.release(model, data, q0, freed, hold=...)`: the analytic command held on every coordinate the derivation kept, **nothing at all** on the one the assumption fixed, settled, and the displacement reported with its sign. A few microradians is an assumption sized and kept. Where the truth model has no such coordinate — a compliance the parameter block never described — the row gets the sentence instead, and the sentence says what adding the coordinate would take and where that work is scoped, never "reasonable for this design". The template's `truth/release_checks.py` runs the degenerate version for you to read: a locked-elbow "derivation" whose torque is right to the digit for a machine that does not exist, which releases 1.57 rad and takes the shoulder with it.

**Then build the truth model, before the first analytic claim.** `truth/` is an independent simulator model of the mechanism — MuJoCo — generated from `params.py` and sharing none of the derivation's simplifying assumptions, and every milestone after this one checks its claims against it. It is built here, at Milestone 0, and not later, because a derivation has nothing to be checked against on the day it is written otherwise, and a check that arrives months after the note is a review finding rather than a checkpoint.

The template ships the chain builder working on its example mechanism. Adapting it is: fill the parameter block, including **`Q_LIMITS`, the envelope** — one `(lo, hi)` per generalized coordinate, which the sampler draws from and the simulator model carries as its joint ranges, so "over the envelope" means one thing in the notes, the checks and the simulator — and **`WORKSPACE`, the region the requirements actually name**, which is a second box because the envelope is what the joints can reach and a singularity is allowed to live in the gap between the two; give every link a **physical inertia tensor**, every axis of it, because a planar derivation that only ever uses `Izz` will happily carry `diag(0, 0, Izz)` and a rigid body cannot be built from it — that zero is the planar assumption written into the parameter block; then run `python analysis/model/run_all.py truth`, which round-trips the built model's link count, masses, COMs, inertias, joint types and ranges against the block.

**Two builders, one per convention family; keep the one this machine has.** `truth/chain.py` builds a serial chain on a fixed base off the DH or PoE table — the parameter block above. `truth/floating.py` builds the plan glossary's other family, a **floating base plus joints**: the body's own pose is six coordinates, any links hang off it by their joints, and cables, legs or wheels hold it up. Its parameter block declares `FLOATING_BODIES` and `FLOATING_CABLES` instead of `DH`, and `truth.build_floating()` reads them. **A cable is unilateral** — a spatial tendon with a rest-length deadband from zero to its unstretched length and a stiffness of EA/L — so it pulls when stretched and does nothing at all when slack, and `truth.cable_forces` reads a slack cable as exactly zero. That is the point of the builder: a pose a bilateral tension solve calls feasible, every cable "in tension", can be a pose where one hangs slack and carries nothing, and the load it was assumed to carry goes somewhere the derivation never looked. The query surface is the same either way: `settle`, `inverse_dynamics`, `linearise` and `cable_forces` take the `(model, data)` pair either builder returns, and both builders name their own entry point `build` — so delete the builder this mechanism does not use, its checks module and its line in `truth/__init__.py`, and `truth.build` is the one that remains with nothing above it rewritten. The sampler is the exception, and it is worth knowing before Milestone 1 rather than during it: `truth.sample` reads `Q_LIMITS` out of the parameter block, one row per generalized coordinate, and a floating body's pose is not a box in its seven `qpos` — three positions and a quaternion. Decide here what pose envelope a floating mechanism's claims are checked over, write it into `00_setup.md` beside the joint envelope, and sample from that.

Two things the truth package must not do, and the layout rule in `references/model-layout.md` says so: it must not import `kinematics.py` or `dynamics/` — a truth model that borrows the derivation's frames has the derivation's assumptions on both sides of every comparison — and it must not copy a constant out of `params.py`, because two models built from two copies drift the first time one is edited.

`MUJOCO=absent` in the project's environment record is a blocker for this milestone, not a footnote; install it before deriving, and say so in the plan if the machine cannot.

## Milestone 1: Kinematics

In `01_kinematics.md`: frame assignment with justification, DH table (or PoE screws) checked against the mechanism sketch, per-joint transforms composed into FK (simplify and interpret physically), the geometric Jacobian (state which representation — space/body, analytical/geometric — and why it's right for the use case), and singularity analysis: where the Jacobian loses rank and what that means physically for *this* machine.

In `kinematics.py`: `forward_kinematics()`, `geometric_jacobian()`, and lambdified numeric versions; in `kinematics_checks.py`, a self-test that Jacobian columns match finite-difference FK.

**Mandatory truth check:** end-effector position and the Jacobian against the truth model's site position and site Jacobian, at configurations drawn from `truth.sample(n, seed)`, with `n` and the seed printed beside the result. The finite-difference check is not a substitute and never was — it compares the Jacobian with derivatives of the same length function, so a frame assigned to the wrong axis, a DH row transcribed wrong, or a tool offset applied in the wrong frame passes it with both sides carrying the mistake. And the configurations are sampled, never named: `q = 0`, the outstretched posture and the workspace corners are the mechanism's symmetry planes, which is exactly where a wrong assumption is invisible.

**Mandatory sweep:** every matrix this derivation inverts or pseudo-inverts gets its singular values swept over the sampled envelope, the smallest printed by `report_results.py`, and a check bounds it away from zero everywhere the derivation needs full rank. For the shipped arm that is the position Jacobian the IK inverts, and the two assertions are different: σ_min over the *envelope* goes to zero and must, because the elbow singularity at q₂ = 0 is inside the joint range and that is the machine; what has to hold is σ_min ≥ `params.SIGMA_MIN` everywhere in `params.WORKSPACE`, the region the requirements name. Deciding which set is which is Milestone 0 work you finish here — the envelope is what the joints reach, the intended workspace is what a requirement asks for, and a singularity is allowed to live in the gap. A rank assumed and never computed is how a rank-3 stiffness matrix gets four modes read off it, and σ_min is a rate rather than a tolerance: its reciprocal is the joint speed and joint torque one unit of Cartesian motion or force costs at the worst posture. The rule is in `references/derivation-standards.md` under **Evidence over an envelope**, with the sampling rule it belongs to.

Run the checkpoint.

## Milestone 2: Dynamics

In `02_dynamics.md`: Euler-Lagrange by default (state T and V explicitly, show the structure M(q)q̈ + C(q,q̇)q̇ + g(q) = τ); Newton-Euler if the user needs joint reaction forces or recursion for speed. Sanity checks sit next to the results they check, not deferred to the end: units on every result; limiting cases (a length to zero, gravity along an axis, q = 0 posture) against intuition; M(q) symmetric positive-definite; Ṁ − 2C skew-symmetric if using the standard C; static torques cross-checked with a moment-arm calculation. **Those last are self-consistency checks, and say so in the note**: each holds the model against itself or against a property every correct Lagrangian has, so each is blind to an assumption that sits on both sides of the comparison. They catch an arithmetic slip the moment it lands, which is worth having; they are not what makes the dynamics right.

In `dynamics/`: `lagrangian_dynamics()` and `total_energy()` in `lagrangian.py`, and `static_torques()` in `statics.py`.

**The Lagrangian is built by `sympy.physics.mechanics`, never by hand.** `lagrangian.py` turns a `ReferenceFrame` per link off the DH table, places each joint origin and each COM as a `Point`, gives every point its velocity through the one- and two-point velocity theorems, hangs a `RigidBody` with mass and an inertia dyadic on each link frame, and hands the whole Lagrangian to `LagrangesMethod`. M, C and g are then read back out of the equations it returns. Two steps that used to be written out — the angular velocity read from Ṙ Rᵀ, and the d/dt(∂L/∂q̇) − ∂L/∂q loop — are exactly where an ω sign or a dropped Coriolis term used to hide behind arithmetic that still reproduced, so they are not written out. Keep the same shape if the mechanism is a floating body rather than a chain: frames, points, velocity theorems, bodies, method.

**Mandatory truth check, the equilibrium settle:** beside whichever module makes the statics claim — `dynamics/statics.py` for a chain, a Milestone 1 module for a floating body on constraints, so this one moves with the claim rather than living at a fixed milestone — hold the analytic torque at sampled postures with `truth.settle(..., hold=tau, min_steps=...)` and assert the model is still there afterwards, and assert that a deliberately wrong torque is *not*. The held-for-a-while part is the check: an algebraic balance is written in the coordinates the derivation kept and is silent about every one it froze, so "balanced at this instant" and "still there five hundred steps later" differ exactly where a frozen degree of freedom is actually free. That difference is what blocked the first real project through this plugin, and it is why the check exists.

**Mandatory truth check, the dynamics:** τ = M q̈ + C q̇ + g against `truth.inverse_dynamics` at states drawn from `truth.sample_states(n, seed)`, with `n` and the seed printed beside the result. Sampled *states*, not postures — at rest C multiplies zero and the entire Coriolis matrix goes unexercised, so a posture-only dynamics check is a statics check wearing a dynamics name. Velocities and accelerations come from the parameter block's rate envelope (`QD_LIMITS`, `QDD_LIMITS`), both signs.

Run it against every backend the machine has — `truth.available()` lists them, and the check prints which ran. **Pinocchio is an optional second backend for chain inverse dynamics and is only ever optional**: `inverse_dynamics(..., backend="pinocchio")` builds the same chain from the same parameter block and runs its own RNEA where Pinocchio imports, and falls back to MuJoCo and says so where it does not. Two recursive algorithms in two codebases off one parameter block is a third independent implementation for free; it is not worth a conda requirement, and Pinocchio has no Windows pip wheel and no unilateral constraints, so it can never be the model a checkpoint depends on. Whether this machine has it is the `Pinocchio` line of the project's environment record (the plugin's `references/environment-record.md`), written by `scripts/env-probe.sh pinocchio`; `absent` there costs nothing, where `MUJOCO=absent` is a blocker.

**Mandatory truth check, any mode the note cites:** the analytic small-oscillation frequencies against `truth.linearise` at the same configuration, with the finite-difference step printed beside them. A mode is an eigenvalue of (K, M) and an entry of K is the stiffness one coordinate feels moving alone; the two coincide only when both matrices are diagonal, so **a diagonal read as a mode** is a plausible, dimensionally correct number about a motion the mechanism cannot make. State the rank you claim for K and check it — a rank assumed and never computed is how that error survives. Frequencies are signed: a divergent configuration reads negative rather than producing a frequency that looks fine.

The other self-tests, in each submodule's checks module — the pinned numeric sample of M, C, g and V; mass matrix symmetric positive-definite; skew-symmetry; energy conservation under SciPy integration (`solve_ivp`); static torques against the moment-arm calculation — are **self-consistency**, and the note says so. Each holds M, C and g against each other or against a property any correct Lagrangian has, so a term missing from T or V is missing from both sides of every one of them. They catch an arithmetic slip the moment it lands. The truth check is what says the equations describe *this* machine. A mismatch between hand derivation and SymPy gets hunted down and documented — which was wrong, and the fix — in the `.md`, never silently patched in the `.py`. Run the checkpoint.

## Milestone 3: Verification & results

The derivation exists to change decisions. In `03_results.md`, actively hunt for results that should send a requirement or component choice back for revision:

- A peak or static torque that exceeds the chosen actuator's rating, or leaves less than the margin the spec demands. Show the number against the datasheet limit — prefer the worst-case-over-workspace torque to the torque at one convenient posture.
- A margin that holds at nominal and fails at a **corner**. Every tolerance the design grants — a wire diameter, a bearing fit, a modulus, a rate band — spans a range, and the corners of their product are where the margins are thinnest: worst case over tolerance, the companion of the worst case over workspace above. Sweep them as a function of the model (one row per corner, each carrying the quantities the grant bounds) and state the worst corner's value beside the nominal one. Monotone quantities make the corners the extremes; sweep a non-monotone one on a grid, under the same caveat the joint sweep carries. A margin stated at nominal alone is unproven, and the numbers a vendor or a shop will be held to are the ones that must survive their own sheet's corners.
- A singularity that sits *inside* the intended workspace rather than safely outside it.
- A posture the FK says is reachable but the machine can't hold, because a link folds into its own base or a neighbour. Joint limits derived from the geometry are as much a Milestone 3 result as a torque. The FK gives the postures; crude link envelopes swept over the joint range give the collisions: copy `armature-cad`'s `scripts/part_template/sweep/` package, with the `check/` package and `run_all.py` beside it, into `cad/parts/` and replace the bodies and `pose()` in `sweep/bodies.py` (it imports `l1`/`l2` from your `params.py`, with no fallback if they're missing); `python -m sweep` from `cad/parts/` runs it. It reports one row per colliding body pair — first interfering sample and worst, in degrees — and exits nonzero on any collision. The first interfering sample is a **grid sample, not the boundary**: the true onset lies up to one grid step earlier (the script prints its step beside the rows), so set the limit at least one step inside the sample, or fine-scan around it for the real edge. Then narrow the swept range in `sweep/grid.py` to the limits you chose and re-run, so the sweep keeps checking the real envelope. A clean sweep is evidence, not proof: the finite grid cannot see a collision band narrower than its step, and overlap excused where bodies share a joint — `sweep_clearance`'s per-pair `ignore` threshold, or `sweep/bodies.py`'s `JOINT_TRIM` envelope setback — hides anything smaller than the excuse. Those caveats live in `sweep/` beside the knobs that cause them (grid sizing in `joint_limits_and_interior`'s docstring); check them before adding a body that passes near a joint, and note both limits beside any joint limit derived this way.
- A mass, inertia, or reduction that breaks a spec budget.
- Loads or speeds that violate an assumption the derivation rests on (the numbered assumptions from `00_setup.md`).

For each finding: state the problem physically, name the specific spec or part it collides with, and lay out the levers (relax the requirement, resize the component, change the architecture). Routing the fix is a boundary decision — see Boundaries.

**"Worst", "any" and "anywhere" are computed, never sampled**, and the rule with its reasons is in `references/derivation-standards.md`. An exact set method where the set is convex — an LP, a hull, a zonotope, a norm with a closed form; a multi-start optimiser where none exists; a dense sweep only with its grid step printed beside the result. The template's search runs the grid *and* the optimiser over every row of the load-case table and returns the worse of the two, because a grid cannot see a peak narrower than its step and an optimiser cannot certify a global maximum: the pair bracket the answer, and a gap between them wider than the margin's precision is itself the finding.

**Both signs of every signed load case, in the parameter block.** `params.LOAD_CASES` is a table of `(class, magnitude, direction set, sign)` rows and `params_checks.py` fails a signed class with one sign in it. On the shipped arm the two braking rows differ by 4 % at the shoulder, so a one-sign reading undersizes it — and the sign that binds is not the one anybody writes first. Where the requirement names a *set* of directions rather than a direction, the row says so and the search answers it exactly: the worst tip force over a circle of headings is a norm, not thirty-six headings tried.

**Every closed form this milestone's sizing leans on is checked against the truth model first**, at sampled configurations, with the assumption it rests on named — `references/derivation-standards.md`, *A closed form from a book*. A formula out of a book has somebody else's arithmetic, which reproduces, and the only open question is whether this mechanism is in the class the formula is a theorem about. The first project through this plugin sized a motor off a bifilar yaw stiffness on converging cables and was 27× low.

**Mandatory truth check:** the worst case the search found, **held** by the truth model at the posture it found it at, under the load case applied as a real force. A worst case is the number an actuator gets bought against, and everything upstream of it is the derivation's own: g(q) from the Lagrangian, J_v from the FK, and the transpose that turns a tip force into joint torques, τ = g − J_vᵀ f. The tempting check is to recompute that expression from the truth model's gravity torque and site Jacobian — and it is not enough, because the mapping then sits on *both* sides and a flipped sign in it is flipped in the comparison too. That is this plugin's own failure mode, rebuilt one level up, and it is easy to do by accident.

So hand the load case to the truth model as a **force**: `truth.site_wrench` converts a force at a site into the body wrench `settle` applies (at the body's centre of mass, which is where MuJoCo's `xfrc_applied` acts — not its frame origin, and the difference is a silent moment error), then hold the claimed torque and settle. Nothing of the derivation is on that side; MuJoCo feels the force, integrates, and either stays or does not. `truth.inverse_dynamics` asserts no constraint is active, so a worst case found *on* a joint limit — a torque the end-stop would carry — fails loudly rather than being confirmed quietly.

In `verification.py`: numeric inverse kinematics (`least_squares`) with an FK→IK→FK round-trip self-test in `verification_checks.py`, and the worst-case search — `grid_search`, `optimiser_search`, `worst_case_torque` per load case — to size actuators against; `report_results.py` prints the tables `03_results.md` cites, the grid and the optimiser side by side with the grid step. `run_all.py` runs every discovered self-test in milestone order — the single command that proves the whole model is internally consistent.

The Milestone 3 checkpoint splits its red-team pass by question — two passes run in sequence, then the merge pass, per the split rule in `${CLAUDE_PLUGIN_ROOT}/references/subagent-dispatch.md` — so neither carries files its question does not need. This is the worked example that rule generalises:

- **Does the argument hold?** All four notes and nothing else: does `03_results.md` follow from what Milestones 0–2 derived? That question lives entirely in prose.
- **Does the code mirror the equations?** Note-and-module pairs — each note with its modules and checks modules — plus the report modules: does each module compute what its note's equations claim, do its checks exercise what the note says they do, and does every table in the notes match what the report modules print?

### Closing the loop when a change is approved

Flagging is half the job. When the user approves a change — bigger motor, shorter link, higher payload, different reduction — propagate it fully and at once:

1. Edit the parameter block in `params.py` and re-run `run_all.py` via Bash. A self-test that now fails is a *second finding*.
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
