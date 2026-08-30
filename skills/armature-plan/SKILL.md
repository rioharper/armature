---
name: armature-plan
description: Convert a robotics engineering spec into a phased, actionable implementation plan covering kinematics/dynamics analysis, CAD workflow, prototyping, fabrication, and integration — and write the project's shared vocabulary (frames, symbols, naming) into CLAUDE.md so every later session stays grounded. Use whenever the user has a design spec or design document and wants a plan, roadmap, timeline, task breakdown, next steps, or "how do I actually build this" — or asks to plan out a robotics project, even informally.
---

# Robotics Writing Plans

You take a finished (or finished-enough) engineering spec and turn it into a plan someone can actually execute — phase by phase, task by task, with exit criteria — and write the shared language (coordinate frames, symbols, part naming) into `CLAUDE.md`, where it keeps every future session about this project coherent.

## Inputs

Read `docs/01-spec/spec.md`, `docs/01-spec/bom.md`, and `CLAUDE.md` from disk — the spec is normally produced by the **armature-spec** skill. If no spec exists, don't fabricate one — do a compressed requirements capture (mission, constraints, chosen architecture, builder capability) and note in the plan that it rests on an informal spec, or suggest running armature-spec first if the project is substantial. Audience and differentiation should already be settled further upstream, in **armature-concept**'s concept brief if one exists — this skill takes that as given rather than re-interrogating it.

Before writing, resolve with the user: available hours per week, hard deadlines, whether analysis (kinematics/dynamics) should precede or parallel CAD, and any gaps the spec left open. Their calendar is theirs to state, never yours to assume.

Work these questions in rounds. Each round, ask the **frontier** — the questions whose prerequisites are already settled (a phase-ordering question waits until the spec gap that drives it is resolved); recompute the frontier after each round. Deliver rounds through the AskUserQuestion tool, your recommended answer as the first option labeled "(Recommended)", so a single word can accept it; the tool takes 4 questions per call, so a larger frontier spans consecutive calls within the round. Facts are your job; decisions are the user's: send a lookupable (a lead time, a part's availability, a datasheet number) to a subagent — the **armature-librarian** agent for parts and datasheets — and keep asking the rest of the frontier while it runs.

## The plan document

Write to `docs/02-plan/plan.md`. Structure:

### 1. Glossary & conventions — written into `CLAUDE.md`

This is the point of the skill, wherever it's written — it's what makes conversation #47 about this robot as grounded as conversation #2. Claude Code loads `CLAUDE.md` automatically every session, so that's where the shared language belongs: write it into `CLAUDE.md`'s Glossary section (extending whatever units policy and naming conventions `/armature:init` already seeded there), not into the plan file. The plan file itself keeps a one-line pointer: `Glossary: see CLAUDE.md`.

Content requirements, regardless of destination:

- **Coordinate frames:** define every frame the project will use ({W} world, {B} base, {E} end-effector, per-joint frames…), their origins, axis conventions (right-handed, z-up or z-along-joint — pick and state), and the convention family (e.g., modified DH, or product-of-exponentials). Once chosen, these are law.
- **Symbol table:** q for joint positions, τ for torques, m_i, l_i, I_i for link properties, etc., with units. The **armature-math** skill will consume this table verbatim, so make it complete.
- **Naming conventions:** part numbering scheme (e.g., `ARM-LNK-002`), CAD file naming, revision scheme, units policy (SI internally, always).
- **Definitions of done** for a task, a phase, and the project.

### 2. Phase breakdown

Decompose into phases where each phase ends in something *demonstrable or testable* — never "phase 3: keep working on arm." Typical arc (adapt, don't copy):

1. **Analysis & sizing** — kinematic model, workspace check, actuator sizing from dynamics, DOF/reachability verification. Tasks here should explicitly say "derive FK/IK/Jacobian/dynamics" and name **armature-math** as the tool for those tasks.
2. **Concept CAD & layout** — master sketch / skeleton model driving all subassemblies, envelope check, interference and service-access check, mass rollup vs. budget.
3. **Prototype the risky bits** — one prototype per top risk from the spec's risk register, each with a question it must answer and a kill criterion. Each test task names its procedure/report file under `docs/testing/` per `references/test-report-template.md` — that file is what "done" points to, not a pass/fail line in the plan.
4. **Detail design & DFM** — part-by-part CAD, tolerance decisions, COTS selection with actual part numbers, drawings for anything outsourced, BOM with costs against budget. If the spec came with a **design-driver BOM** (from armature-spec), this phase expands it into the full procurement BOM rather than starting over — the design drivers and their datasheets are already settled; here you add quantities, fasteners, costs, and lead times. Any part still carrying a TBD or assumed spec gets a task to source and confirm its datasheet *before* its drawing is released; don't let an unverified number reach the shop.
5. **Fabrication & subsystem bring-up** — build order chosen so subsystems are testable standalone; electrical/wiring as first-class tasks, not an afterthought.
6. **Integration & verification** — trace every Must requirement (REQ-xxx) to a test in this phase. A requirement with no test is a wish. Each test task names its procedure/report file under `docs/testing/` per `references/test-report-template.md`, and this phase additionally fills the Test column of `docs/01-spec/traceability.md` — a Must REQ with no test row is the gap this exists to catch.
7. **Iteration reserve** — an explicit phase, not leftover time. The first build is a hypothesis; budget for revising the worst mechanism.

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

`Executor` is `armature-math`, `armature-cad`, `armature-inventor` (agent), or `user` — name it so a fresh session knows which skill or agent picks the task up, or that it's hands-on-hardware work no skill performs. Estimates in hours, dependencies explicit, exit criteria observable. Keep tasks under ~a day of work; split anything bigger.

### 4. CAD process guidance

Plans should encode good CAD practice, not just "do CAD": top-down skeleton/master-sketch modeling so envelope changes propagate; design around downloaded COTS models from day one; check service access (can you swap every sensor and fastener?); mass properties tracked against the spec's mass budget at every phase gate.

### 5. Risks → plan hooks

Pull the spec's risk register into the plan: every high risk gets either a prototype task, an analysis task, or a scheduled decision point. Note revisit triggers on the timeline.

## Style

Plain, specific, imperative. No motivational filler. Dates and hours are estimates and labeled as such. If the spec's scope doesn't fit the user's stated hours, say so in the plan's first paragraph and propose what to cut — a plan that pretends is worse than no plan.

## Hand-offs

- Kinematics/dynamics tasks → **armature-math**
- "I'm stuck, need a better approach for phase N" → dispatch the **armature-inventor** agent
- "Explain this concept the plan assumes I know" → **armature-teacher**
- "Stress-test this plan (or the spec under it) for gaps before I commit" → dispatch the **armature-red-team** agent

Once the plan is written, update `CLAUDE.md` — set Stage to `analysis`, point Latest artifacts at the plan, and confirm the Glossary section is written — and log the planning decisions (phases chosen, prototypes selected, hours assumed) in `docs/decisions.md`.
