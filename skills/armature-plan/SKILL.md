---
name: armature-plan
description: Convert a robotics engineering spec into a phased implementation plan — analysis, CAD, prototyping, fabrication, integration — and write the project's shared vocabulary (frames, symbols, naming) into CONTEXT.md. Use when the user has a spec or design document and wants an implementation plan for building it, or asks to plan a robotics build with no spec behind it.
---

# Robotics Implementation Planning

You take a finished (or finished-enough) engineering spec and turn it into a plan someone can execute — phase by phase, task by task, with exit criteria — and write the project's shared language into `CONTEXT.md`.

## Inputs

Read `docs/01-spec/spec.md`, `docs/01-spec/bom.md`, `CLAUDE.md`, and `CONTEXT.md` (if present) from disk — the spec is normally produced by **armature-spec**. If no spec exists, do a compressed requirements capture (mission, constraints, chosen architecture, builder capability) and note in the plan that it rests on an informal spec — or, for a substantial project, offer armature-spec: on yes, call the Skill tool with "armature-spec". If the spec is still foggy — more open decisions than one session can settle — call the Skill tool with "armature-wayfind" to chart the way first. Audience and differentiation are settled upstream, in **armature-pitch**'s concept brief if one exists; take them as given.

Before writing, resolve with the user: available hours per week, hard deadlines, whether analysis (kinematics/dynamics) precedes or parallels CAD, and any gaps the spec left open. Their calendar is theirs to state, never yours to assume.

Work these questions in rounds. Each round, ask the **frontier** — the questions whose prerequisites are already settled (a phase-ordering question waits until the spec gap that drives it is resolved); recompute the frontier after each round. Deliver rounds through the AskUserQuestion tool, your recommended answer as the first option labeled "(Recommended)", so a single word can accept it; the tool takes 4 questions per call, so a larger frontier spans consecutive calls within the round. Facts are your job; decisions are the user's: send a lookupable (a lead time, a part's availability, a datasheet number) to the **armature-librarian** agent and keep asking the rest of the frontier while it runs.

**Checkpoint each round.** After each round, write the plan as it stands to `docs/02-plan/plan.md`, opening with a `> Draft — open questions: …` line carrying the live frontier. If that Draft line is already in the file on invocation, resume from it: settled answers stand, and its open questions seed the frontier. The finished plan drops the line.

## The plan document

Write to `docs/02-plan/plan.md`. Structure:

### 1. Glossary & conventions — written into `CONTEXT.md`

This is the point of the skill — it's what makes conversation #47 about this robot as grounded as conversation #2. The shared language lives in `CONTEXT.md` at the project root: create the file if it doesn't exist (this is usually its first content), and confirm `CLAUDE.md`'s Glossary section points at it so every session auto-loads the pointer. The plan file itself keeps a one-line pointer: `Glossary: see CONTEXT.md`.

Each named term gets a tight definition (one or two sentences, what it IS) followed by an `_Avoid_:` line listing the synonyms it displaces — pick arm *or* link *or* boom, ban the rest. The `_Avoid_` lines are what the inline-challenge rule in `CLAUDE.md` enforces.

Content requirements, regardless of destination:

- **Coordinate frames:** define every frame the project will use ({W} world, {B} base, {E} end-effector, per-joint frames…), their origins, axis conventions (right-handed, z-up or z-along-joint — pick and state), and the convention family (e.g., modified DH, or product-of-exponentials). Once chosen, these are law.
- **Symbol table:** q for joint positions, τ for torques, m_i, l_i, I_i for link properties, etc., with units. The **armature-derive** skill consumes this table verbatim, so make it complete.
- **Naming conventions:** part numbering scheme (e.g., `ARM-LNK-002`), CAD file naming, revision scheme, units policy (SI internally, always).
- **Definitions of done** for a task, a phase, and the project.

### 2. Phase breakdown

Decompose into phases where each phase ends in something *demonstrable or testable*. Typical arc (adapt, don't copy):

1. **Analysis & sizing** — kinematic model, workspace check, actuator sizing from dynamics, DOF/reachability verification. Derivation tasks say "derive FK/IK/Jacobian/dynamics" and carry `armature-derive` as Executor.
2. **Concept CAD & layout** — master sketch / skeleton model driving all subassemblies, envelope check, interference and service-access check, mass rollup vs. budget.
3. **Prototype the risky bits** — each prototype task carries the question it must answer and a kill criterion.
4. **Detail design & DFM** — part-by-part CAD, tolerance decisions, COTS selection with actual part numbers, drawings for anything outsourced, BOM with costs against budget. If the spec came with a **design-driver BOM** (from armature-spec), expand it into the full procurement BOM — the design drivers and their datasheets are settled; add quantities, fasteners, costs, and lead times. Any part still carrying a TBD or assumed spec gets a task to source and confirm its datasheet *before* its drawing is released.
5. **Fabrication & subsystem bring-up** — build order chosen so subsystems are testable standalone; electrical/wiring as first-class tasks.
6. **Integration & verification** — trace every Must requirement (REQ-xxx) to a test task and fill the Test column of `docs/01-spec/traceability.md`; a Must REQ with no test row is the gap this phase exists to catch.
7. **Iteration reserve** — an explicit phase: budget for revising the worst mechanism.

### 3. Task format

Every task gets:

```
- [ ] T3.2 Prototype cable-driven wrist
      Executor: user
      Answers: can 2mm Dyneema hold tension over 500 cycles at r=8mm?
      Depends on: T3.1 · Est: 6h · Needs: printed pulley set, load cell
      Done when: 500-cycle test logged, elongation < 1%, OR killed and
      T3.2b (geared wrist) activated
```

`Executor` is `armature-derive`, `armature-cad`, `armature-inventor` (agent), or `user` — name it so a fresh session knows which skill or agent picks the task up, or that it's hands-on-hardware work no skill performs. Estimates in hours, dependencies explicit, exit criteria observable. Keep tasks under ~a day of work; split anything bigger.

A test task — prototype (phase 3) or verification (phase 6) — names its procedure/report file under `docs/testing/` per `references/test-report-template.md`; that file, filled in, is what its `Done when` points to.

**Word tasks to survive the wait.** A task may sit for weeks while the project moves under it, so write the behavioral contract, not the route: state what the result must do, name parts, interfaces, and symbols rather than file paths or line numbers, make `Done when` verifiable by a session that never saw this conversation, and where a task borders a neighbor, state what's out of its scope.

### 4. CAD process guidance

Plans encode good CAD practice: top-down skeleton/master-sketch modeling so envelope changes propagate; design around downloaded COTS models from day one; check service access (can you swap every sensor and fastener?); mass properties tracked against the spec's mass budget at every phase gate.

### 5. Risks → plan hooks

Pull the spec's risk register into the plan: every high risk gets a prototype task, an analysis task, or a scheduled decision point; note revisit triggers on the timeline.

## Style

Plain, specific, imperative. No motivational filler. Dates and hours are estimates and labeled as such. If the spec's scope doesn't fit the user's stated hours, say so in the plan's first paragraph and propose what to cut.

## Hand-offs

- Kinematics/dynamics derivation: call the Skill tool with "armature-derive".
- "I'm stuck, need a better approach for phase N": dispatch the **armature-inventor** agent.
- A concept the plan assumes the user knows: call the Skill tool with "armature-teacher".
- Stress-testing the plan (or the spec under it) before committing: dispatch the **armature-red-team** agent.

Once the plan is written, update `CLAUDE.md` — Stage → `analysis`, Latest artifacts → the plan — and log the planning decisions (phases chosen, prototypes selected, hours assumed) in `docs/decisions.md`.
