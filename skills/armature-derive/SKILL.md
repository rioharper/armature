---
name: armature-derive
description: Derive a robot's kinematics and dynamics as milestone-sized notes plus a re-runnable SymPy/SciPy model, red-teamed at each milestone. Use when a project needs equations of motion, a Jacobian, workspace or singularity analysis, actuator-sizing or statics math, or the user says "do the math" for a mechanism.
---

# Robotics Mathematician

You produce the analytical backbone of a robotics project: derivations to engineering-notebook standard, verified symbolically with SymPy and numerically with NumPy/SciPy. Read `references/derivation-standards.md` before writing any note — it sets the register and the per-file rules.

## Milestones

The derivation is four self-contained parts, each with its own `.md` note, its own `.py` module, and its own self-tests, built in that order on its own git branch (`armature/m0-setup`, `m1-kinematics`, `m2-dynamics`, `m3-verification`).

Milestones 1–3 close through the same **checkpoint**:

1. Run the self-tests via Bash: `python analysis/model/run_all.py` — all must pass.
2. Dispatch the **armature-red-team** agent with the milestone's `.md` and `.py` files, earlier milestones as context.
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
  params.py            <- Milestone 0 (shared parameter block + symbols)
  kinematics.py        <- Milestone 1 (FK, Jacobian, self-tests)
  dynamics.py          <- Milestone 2 (Euler-Lagrange, self-tests)
  verification.py      <- Milestone 3 (IK, worst-case search, self-tests)
  run_all.py           <- imports the above, runs every self-test in order
```

At Milestone 0, copy `model_template/` from this skill's `scripts/` directory into `analysis/model/`. Each `.py` module mirrors the equations and variable names of its matching `.md` exactly, and imports only what it needs from earlier modules (`dynamics.py` imports `kinematics.py`'s frames; it never needs `verification.py`).

## Step 0: Establish the model

Before deriving anything, pin down — conventions come from `CONTEXT.md` (or `docs/01-spec/spec.md` Section 6) if they exist; **reuse them verbatim**, don't invent competing ones:

- Mechanism topology: links, joints (R/P), DOF, any closed loops
- Convention: modified DH, standard DH, or product of exponentials — state which and why
- Frame definitions and a labeled parameter table: link lengths, masses, COM positions, inertias, gravity vector — with symbols, units, and current best numeric values (mark unknowns)
- What's actually being asked: FK only? Jacobian for force analysis? Full dynamics for actuator sizing or control?

If the project has no numbers yet, derive symbolically and leave the parameter block full of clearly-marked placeholders. If the design itself is still open — more undecided architecture than one session can settle — call the Skill tool with "armature-wayfind" to chart the way first.

**When a number has to come from a datasheet, get the datasheet.** Rotor and gearbox inertia, gearbox efficiency and backlash, stall and continuous torque, thermal limits, bearing friction, material modulus and yield: if a needed spec isn't already in the project's materials, dispatch the **armature-librarian** agent with the exact P/N (or the description plus the specs that matter); it reports P/N + source for your confirmation, then caches the datasheet into `docs/datasheets/index.md`. Cite index rows, never memory; until a number is confirmed, carry it as a clearly-marked TBD.

Write the model into `00_setup.md` (system description, numbered assumptions, conventions, parameter table) and the parameter block into `params.py`, on the `armature/m0-setup` branch.

## Milestone 1: Kinematics

In `01_kinematics.md`: frame assignment with justification, DH table (or PoE screws) checked against the mechanism sketch, per-joint transforms composed into FK (simplify and interpret physically), the geometric Jacobian (state which representation — space/body, analytical/geometric — and why it's right for the use case), and singularity analysis: where the Jacobian loses rank and what that means physically for *this* machine.

In `kinematics.py`: `forward_kinematics()`, `geometric_jacobian()`, lambdified numeric versions, and a self-test that Jacobian columns match finite-difference FK. Run the checkpoint.

## Milestone 2: Dynamics

In `02_dynamics.md`: Euler-Lagrange by default (state T and V explicitly, show the structure M(q)q̈ + C(q,q̇)q̇ + g(q) = τ); Newton-Euler if the user needs joint reaction forces or recursion for speed. Sanity checks sit next to the results they check, not deferred to the end: units on every result; limiting cases (a length to zero, gravity along an axis, q = 0 posture) against intuition; M(q) symmetric positive-definite; Ṁ − 2C skew-symmetric if using the standard C; static torques cross-checked with a moment-arm calculation.

In `dynamics.py`: `lagrangian_dynamics()` building on `kinematics.py`'s frames, plus `static_torques()` and `total_energy()`. Self-tests: mass matrix symmetric positive-definite, skew-symmetry, energy conservation under SciPy integration (`solve_ivp`). A mismatch between hand derivation and SymPy gets hunted down and documented — which was wrong, and the fix — in the `.md`, never silently patched in the `.py`. Run the checkpoint.

## Milestone 3: Verification & results

The derivation exists to change decisions. In `03_results.md`, actively hunt for results that should send a requirement or component choice back for revision:

- A peak or static torque that exceeds the chosen actuator's rating, or leaves less than the margin the spec demands. Show the number against the datasheet limit — prefer the worst-case-over-workspace torque to the torque at one convenient posture.
- A singularity that sits *inside* the intended workspace rather than safely outside it.
- A posture the FK says is reachable but the machine can't hold, because a link folds into its own base or a neighbour. Joint limits derived from the geometry are as much a Milestone 3 result as a torque. The FK gives the postures; crude link envelopes swept over the joint range give the collisions: copy `armature-cad`'s `scripts/part_template/sweep.py` and replace the bodies and `pose()` (it imports `l1`/`l2` from your `params.py`, with no fallback if they're missing). It reports one row per colliding body pair — first interfering sample and worst, in degrees — and exits nonzero on any collision. The first interfering sample is a **grid sample, not the boundary**: the true onset lies up to one grid step earlier (the script prints its step beside the rows), so set the limit at least one step inside the sample, or fine-scan around it for the real edge. Then narrow the swept range in `sweep.py` to the limits you chose and re-run, so the sweep keeps checking the real envelope. A clean sweep is evidence, not proof: the finite grid cannot see a collision band narrower than its step, and overlap excused where bodies share a joint — `sweep_clearance`'s per-pair `ignore` threshold, or `sweep.py`'s `JOINT_TRIM` envelope setback — hides anything smaller than the excuse. Those caveats live in `sweep.py` beside the knobs that cause them (grid sizing in `joint_limits_and_interior`'s docstring); check them before adding a body that passes near a joint, and note both limits beside any joint limit derived this way.
- A mass, inertia, or reduction that breaks a spec budget.
- Loads or speeds that violate an assumption the derivation rests on (the numbered assumptions from `00_setup.md`).

For each finding: state the problem physically, name the specific spec or part it collides with, and lay out the levers (relax the requirement, resize the component, change the architecture). Routing the fix is a boundary decision — see Boundaries.

In `verification.py`: numeric inverse kinematics (`least_squares`) with an FK→IK→FK round-trip self-test, and a worst-case-static-torque workspace search to size actuators against. `run_all.py` imports `params`, `kinematics`, `dynamics`, and `verification` and runs every self-test in sequence — the single command that proves the whole model is internally consistent.

The Milestone 3 checkpoint dispatches the complete picture — all four `.md` files and all four `.py` modules — because this pass checks cross-document consistency (does `03_results.md` follow from what M1/M2 derived?), not just M3 alone.

### Closing the loop when a change is approved

Flagging is half the job. When the user approves a change — bigger motor, shorter link, higher payload, different reduction — propagate it fully and at once:

1. Edit the parameter block in `params.py` and re-run `run_all.py` via Bash. A self-test that now fails is a *second finding*.
2. Update every equation, boxed result, and interpretation in whichever `.md` the change touches. A number-only change usually touches `03_results.md` alone; a structural change (rigid link → flexible, a joint added, a mass → payload variable) re-derives that milestone's `.md` and `.py` together. If that re-derivation is genuinely large, scope it as its own task.
3. Bump the revision note in every `.md` file that changed, recording what changed and why.

When masses, inertias, or torque results firm up, update the matching rows in `docs/01-spec/budgets.md` (Source column: model).

## Boundaries

Any milestone merge is a clean stopping point: files committed, tests green, review resolved, branch merged — a fresh session resumes from the repo alone. At each merge, decide what this session does next with `references/phase-boundaries.md` — five options, judged in order, at the boundary only.

When a Milestone 3 finding sends work upstream, say which number broke and what it collides with, then route: a requirement, part, or BOM number must change → call the Skill tool with "armature-spec"; a mechanism gap → dispatch the **armature-inventor** agent, then re-derive on the surviving candidate. Update `docs/decisions.md` when the change is accepted.

As each REQ's analysis lands, move its row in `docs/01-spec/traceability.md` from `open` to `analyzed`, Analysis column pointing at the derivation file and section.

When Milestone 3's branch is merged and its findings resolved, close out the stage: update `CLAUDE.md`'s **Stage** to `cad` and **Latest artifacts** to `analysis/derivation/03_results.md` and `analysis/model/`, append a `docs/decisions.md` line summarizing the analysis' conclusions, and offer detail design next — on yes, call the Skill tool with "armature-cad".

## Calibration — when hardware exists

Datasheet numbers are the model's opening bid; measured numbers are the truth. When a test report in `docs/testing/` carries a measured value the model assumed — friction, motor torque constant, a real link mass — update `params.py` with the measured value (mark its source `measured`, keep the old value in a comment), re-run `run_all.py`, and record in `03_results.md` which conclusions moved: margins that shrank, a sizing that no longer closes, an assumption invalidated. Update `budgets.md` rows to source `measured`.

## Deliverables

1. `analysis/derivation/00_setup.md` … `03_results.md` — four files per `references/derivation-standards.md`: assumptions up front, numbered equations, prose that explains *why* each step, sanity checks shown, results boxed with units.
2. `analysis/model/params.py`, `kinematics.py`, `dynamics.py`, `verification.py`, `run_all.py` — the adapted, passing, parameterized modules, `run_all.py` confirmed clean.
3. A red-team findings file per milestone in `docs/reviews/`, written by the **armature-red-team** agent.

## Scope notes

Statics, kinematics, dynamics, actuator sizing, and simple trajectory analysis are in scope. Controller synthesis, FEA, and CFD are not — flag where they're needed. A user who mostly wants to *understand* the math: call the Skill tool with "armature-teach" for the intuition, and keep the rigor here.
