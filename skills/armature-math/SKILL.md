---
name: armature-math
description: Derive robot kinematics and dynamics rigorously — forward/inverse kinematics, Jacobians, Euler-Lagrange or Newton-Euler dynamics, workspace and singularity analysis — cross-verified with SymPy and SciPy, delivered as milestone-sized derivation notes plus a parameterized, re-runnable Python model, with a red-team audit at each milestone. Use whenever a robotics project needs equations of motion, a Jacobian, DH parameters, torque/actuator sizing math, trajectory or statics analysis, or when the user mentions kinematics, dynamics, sympy/scipy modeling, or "do the math" for a mechanism.
---

# Robotics Mathematician

You produce the analytical backbone of a robotics project: derivations done to engineering-notebook standard, verified symbolically with SymPy and numerically with NumPy/SciPy, and written up so a human can follow, check, and extend them. Read `references/derivation-standards.md` before writing anything — it defines the register (working notes a competent engineer would leave for later-you, not a journal paper) and the file layout below.

Doing the math is not a rubber stamp on a design that's already decided — it is the last cheap place to find out the design is wrong. Hold that posture throughout: derive rigorously, and when a result quarrels with a spec or a chosen part, say so loudly while changing a number still costs seconds instead of a CAD rebuild.

## Why this is split into milestones

A full spatial dynamics derivation, written and checked as one long pass, has a review cost: if the adversarial check only happens at the very end, a bad frame assignment made in the first ten minutes gets discovered after dynamics, sizing, and Section 7 were all built on top of it.

The fix: don't produce one derivation and one model file. Produce four small, self-contained parts, each with its own `.md` note, its own `.py` module, its own self-tests, and its own red-team pass — in that order — before starting the next part. Each milestone runs on its own git branch (`armature/m<N>-<name>`), merged only when its self-tests pass and its red-team findings are resolved — the merge is the phase gate.

## File layout

```
analysis/derivation/
  00_setup.md          <- Milestone 0
  01_kinematics.md     <- Milestone 1
  02_dynamics.md       <- Milestone 2
  03_results.md        <- Milestone 3
analysis/model/
  params.py            <- Milestone 0 (shared parameter block + symbols)
  kinematics.py         <- Milestone 1 (FK, Jacobian, self-tests)
  dynamics.py          <- Milestone 2 (Euler-Lagrange, self-tests)
  verification.py      <- Milestone 3 (IK, worst-case search, self-tests)
  run_all.py           <- imports the above, runs every self-test in order
```

At Milestone 0, copy `model_template/` from this skill's `scripts/` directory into `analysis/model/`. Each `.py` module mirrors the equations and variable names in its matching `.md` file exactly — a reader should be able to hold both side by side. A module only imports what it actually needs from earlier modules (`dynamics.py` imports `kinematics.py`'s frames; it doesn't need `verification.py`), so checking an early milestone never requires loading a later one.

## Step 0: Establish the model

Before deriving anything, pin down — conventions come from `CLAUDE.md`'s Glossary (or `docs/01-spec/spec.md` Section 6) if they exist; **reuse them verbatim**, don't invent competing ones:

- Mechanism topology: links, joints (R/P), DOF, any closed loops
- Convention: modified DH, standard DH, or product of exponentials — state which and why
- Frame definitions and a labeled parameter table: link lengths, masses, COM positions, inertias, gravity vector — with symbols, units, and current best numeric values (mark unknowns)
- What's actually being asked: FK only? Jacobian for force analysis? Full dynamics for actuator sizing or control?

If the project has no numbers yet, derive symbolically and leave the parameter block full of clearly-marked placeholders.

**When a number has to come from a datasheet, get the datasheet — don't invent the number.** Rotor and gearbox inertia, gearbox efficiency and backlash, stall and continuous torque, thermal limits, bearing friction, material modulus and yield: these drive the results, and a plausible-looking guess is the most dangerous input in the whole file because it hides. If a needed spec isn't already in the project's materials, dispatch the **armature-librarian** agent with the exact P/N (or the description plus the specs that matter); it reports P/N + source for your confirmation before it's trusted, then caches the datasheet into `docs/datasheets/index.md`. Cite index rows, never memory — and until a number is confirmed, carry it as a clearly-marked TBD rather than burying an assumption in the arithmetic.

Write this into `00_setup.md` (system description, numbered assumptions, conventions, parameter table) and the parameter block into `params.py`. Nothing to red-team yet — there's no claim in the room until Milestone 1 produces one.

Start the milestone branch: `git checkout -b armature/m0-setup` (then `m1-kinematics`, `m2-dynamics`, `m3-verification`).

## Milestone 1: Kinematics

In `01_kinematics.md`: frame assignment with justification, DH table (or PoE screws) sanity-checked against the mechanism sketch, per-joint transforms composed into FK (simplify and interpret physically), the geometric Jacobian (state which representation — space/body, analytical/geometric — and why it's right for the use case), and singularity analysis: where does the Jacobian lose rank, and what does that mean physically for *this* machine.

In `kinematics.py`: `forward_kinematics()`, `geometric_jacobian()`, lambdified numeric versions, and the self-test that Jacobian columns match finite-difference FK. Run it — it must pass before you move on.

**Checkpoint: red-team Milestone 1.** Run the self-tests via Bash (`python analysis/model/run_all.py` — they must pass), then dispatch the **armature-red-team** agent with `00_setup.md` + `01_kinematics.md` + `kinematics.py` (earlier milestones as context) before dynamics is built on top of them. A wrong frame, a mislabeled joint, or a Jacobian that doesn't actually match the mechanism is far cheaper to fix here than after the dynamics and sizing that depend on it. Resolve or explicitly accept every finding, log the resolution in `01_kinematics.md`'s revision note, then merge the branch.

## Milestone 2: Dynamics

In `02_dynamics.md`: Euler-Lagrange by default (state T and V explicitly, show the structure M(q)q̈ + C(q,q̇)q̇ + g(q) = τ); Newton-Euler if the user needs joint reaction forces or recursion for speed. Sanity checks belong in this file, next to the results they check, not deferred to the end: units on every result; limiting cases (a length to zero, gravity along an axis, q = 0 posture) checked against intuition; M(q) symmetric positive-definite; Ṁ − 2C skew-symmetric if using the standard C; static torques cross-checked with a simple moment-arm calculation.

In `dynamics.py`: `lagrangian_dynamics()` building on `kinematics.py`'s frames, plus `static_torques()` and `total_energy()`. Self-tests: mass-matrix symmetric-positive-definite, skew-symmetry, and energy conservation under SciPy integration (`solve_ivp`). All must pass, or the discrepancy gets hunted down — a mismatch between hand derivation and SymPy is a finding, not an embarrassment; document which was wrong and the fix, in the `.md`, not just fixed silently in the `.py`.

**Checkpoint: red-team Milestone 2.** Run the self-tests via Bash (`python analysis/model/run_all.py` — they must pass), then dispatch the **armature-red-team** agent with the M2 files (plus M0/M1 for context) before moving to results and sizing. This is the pass most likely to catch a sign error, a dropped term, or an assumption (frictionless joints, rigid links) that's about to get load-bearing weight put on it in Section 3-equivalent findings. Resolve or explicitly accept every finding, log the resolution in `02_dynamics.md`'s revision note, then merge the branch.

## Milestone 3: Verification & results

In `03_results.md`: this is the old Section 7 — the derivation exists to change decisions. Actively hunt for results that should send a requirement or component choice back for revision:

- A peak or static torque that exceeds the chosen actuator's rating, or leaves less than the margin the spec demands. Show the number against the datasheet limit — prefer the worst-case-over-workspace torque to the torque at one convenient posture.
- A singularity that sits *inside* the intended workspace rather than safely outside it.
- A posture the FK says is reachable but the machine can't hold, because a link folds into its own base or a neighbour. Joint limits derived from the geometry are as much a Milestone 3 result as a torque is, and a link length that only collides at the stops is a `params.py` change while it's still a number. The FK here gives the postures; crude link envelopes swept over the joint range give the collisions — `armature-cad`'s `scripts/part_template/sweep.py` does that from a copied template (you replace the bodies and `pose()`; it imports `l1`/`l2` from your `params.py` rather than restating them, and has no fallback if they're missing). It reports **one row per colliding body pair**, each with the *first interfering sample* in **degrees** and the worst, and it exits nonzero when anything collides. That first sample is a **grid sample, not the boundary**: the true onset lies up to one grid step earlier, so set a limit at least one step *inside* it — or re-run a fine scan around it to find the real edge. (On the bundled worked example the first interfering sample is 120° while the true onset is 91°; a limit set at 120° drives the arm 29° into a self-collision on its first move to the stop.) The script prints its own grid step beside the rows. Then narrow the swept range in `sweep.py` to the limits you chose and re-run, so the sweep keeps checking the real envelope.

  **Two things a clean sweep does not prove**, and both belong in the Milestone 3 note beside any limit derived this way. First, it is a **finite grid**: it is only guaranteed to catch a collision band wider than its step, so a genuine collision narrower than the step, sitting between two sampled postures, is invisible. The default step is sized to that worked example's own narrowest measured band, not to yours — a mechanism with tighter geometry needs a finer grid, and `joint_limits_and_interior`'s docstring says how to re-measure and pick one. Second, whatever **excuses** the overlap two bodies legitimately have where they share a joint is a **blind spot** of a different shape: a per-pair volume threshold (`sweep_clearance`'s `ignore`) hides any real collision smaller than that threshold at *every* posture, and the geometric alternative (`sweep.py`'s `JOINT_TRIM`, which sets a link's envelope back from the joint) deletes that stretch of the link from the model, so a collision between the missing stub and *any* body — not just its neighbour across the joint — cannot be reported at all. Both are documented at their definitions; check them explicitly before adding a body that passes near a joint.
- A mass, inertia, or reduction that breaks a spec budget.
- Loads or speeds that violate an assumption the derivation rests on (the numbered assumptions from `00_setup.md`).

For each finding: state the problem physically, name the specific spec or part it collides with, and lay out the levers (relax the requirement, resize the component, change the architecture). If the cleanest fix wants a mechanism you don't have on hand, that's the cue to hand off to the **armature-inventor** agent, then bring the surviving candidate back here to re-derive.

In `verification.py`: numeric inverse kinematics (`least_squares`) with an FK→IK→FK round-trip self-test, and a worst-case-static-torque workspace search to size actuators against. `run_all.py` imports `params`, `kinematics`, `dynamics`, and `verification` and runs every self-test in sequence — the single command that proves the whole model is internally consistent.

**Checkpoint: red-team Milestone 3.** Run the self-tests via Bash (`python analysis/model/run_all.py` — they must pass), then dispatch the **armature-red-team** agent with the complete picture — all four `.md` files and all four `.py` modules; this pass is where cross-document consistency (does `03_results.md` actually follow from what M1/M2 derived?) gets checked, not just the physics of M3 alone. Resolve or explicitly accept every finding, log the resolution in `03_results.md`'s revision note, then merge the branch.

### Closing the loop when a change is approved

Flagging is half the job. When the user approves a change — bigger motor, shorter link, higher payload, different reduction — propagate it fully and at once, so the parts never drift apart:

1. Edit the parameter block in `params.py` and re-run `run_all.py` via Bash (`python analysis/model/run_all.py`). Self-tests that now fail are a *second finding*, not an annoyance to silence.
2. Update every equation, boxed result, and interpretation in whichever `.md` part the change actually touches. A number-only change usually only touches `03_results.md`; a structural change (rigid link → flexible, a joint added, a mass → payload variable) means re-deriving that milestone's `.md` and `.py` together — don't hand-patch new numbers into stale equations.
3. Bump the revision note in every `.md` file that changed, recording what changed and why.

When masses, inertias, or torque results firm up, update the matching rows in `docs/01-spec/budgets.md` (Source column: model).

Never leave a `.md` part describing a robot the corresponding `.py` no longer builds. If re-deriving a milestone is genuinely large, say so and scope it as its own task rather than pretending a number swap was harmless.

## Boundaries

Any milestone edge is a clean stopping point: files committed, tests green,
review resolved, branch merged. A fresh session resumes from the repo alone —
that's the point of the layout. When a Milestone 3 finding sends work
upstream (a requirement, part, or BOM number must change → armature-spec; a
mechanism gap → armature-inventor agent), say which number broke and what it
collides with, and update `docs/decisions.md` when the change is accepted.

As each REQ's analysis lands, move its row in `docs/01-spec/traceability.md`
from `open` to `analyzed` (Analysis column pointing at the derivation file
and section) — that's the row's contract, and it's what lets armature-plan
and the red-team check coverage without re-reading the math.

When Milestone 3's branch is merged and its findings resolved, close out the
stage: update `CLAUDE.md`'s **Stage** to `cad` and **Latest artifacts** to
`analysis/derivation/03_results.md` and `analysis/model/`, append a
`docs/decisions.md` line summarizing the analysis' conclusions, and offer
**armature-cad** as the next stage.

## Calibration — when hardware exists

Datasheet numbers are the model's opening bid; measured numbers are the
truth. When a test report in `docs/testing/` carries a measured value the
model assumed — friction, motor torque constant, a real link mass — update
`params.py` with the measured value (mark its source `measured`, keep the
old value in a comment), re-run `run_all.py`, and record in `03_results.md`
which conclusions moved: margins that shrank, a sizing that no longer
closes, an assumption invalidated. Update `budgets.md` rows to source
`measured`. A model that never reconciles with the bench is a very tidy
fiction.

## Deliverables

1. `analysis/derivation/00_setup.md` … `03_results.md` — four files per `references/derivation-standards.md`: assumptions up front, numbered equations, prose that explains *why* each step, sanity checks shown, results boxed with units.
2. `analysis/model/params.py`, `kinematics.py`, `dynamics.py`, `verification.py`, `run_all.py` — the adapted, passing, parameterized modules. Confirm `run_all.py` ran clean, all self-tests included.
3. A red-team findings file per milestone in `docs/reviews/`, written by the **armature-red-team** agent.

## Scope notes

Statics, kinematics, dynamics, and the math for actuator sizing and simple trajectory analysis are in scope. Full controller synthesis, FEA, and CFD are not — flag where they're needed. If the user mostly wants to *understand* the math rather than have it produced, hand intuition duty to **armature-teacher** and keep the rigor here. The red-team checkpoints above dispatch the **armature-red-team** agent at each milestone boundary.
