---
name: armature-plan
description: Convert a robotics engineering spec into a phased, actionable implementation plan covering kinematics/dynamics analysis, CAD workflow, prototyping, fabrication, and integration — with shared vocabulary (frames, symbols, naming) so all later conversations stay grounded. Use whenever the user has a design spec or design document and wants a plan, roadmap, timeline, task breakdown, next steps, or "how do I actually build this" — or asks to plan out a robotics project, even informally.
---

# Robotics Writing Plans

You take a finished (or finished-enough) engineering spec and turn it into a plan someone can actually execute — phase by phase, task by task, with exit criteria — plus the shared language (coordinate frames, symbols, part naming) that keeps every future conversation about this project coherent.

## Inputs

Read the spec first. Usually it's a markdown file produced by the **armature-spec** skill; it may also be uploaded or pasted. If no spec exists, don't fabricate one — do a compressed requirements capture (mission, constraints, chosen architecture, builder capability) and note in the plan that it rests on an informal spec, or suggest running armature-spec first if the project is substantial. Audience and differentiation should already be settled further upstream, in **armature-concept**'s concept brief if one exists — this skill takes that as given rather than re-interrogating it.

Before writing, resolve with the user: available hours per week, hard deadlines, and whether analysis (kinematics/dynamics) should precede or parallel CAD. Don't guess at their calendar.

## The plan document

Write to a markdown file. Structure:

### 1. Project glossary & conventions (the shared language)

This section is the point of the skill — it's what makes conversation #47 about this robot as grounded as conversation #2.

- **Coordinate frames:** define every frame the project will use ({W} world, {B} base, {E} end-effector, per-joint frames…), their origins, axis conventions (right-handed, z-up or z-along-joint — pick and state), and the convention family (e.g., modified DH, or product-of-exponentials). Once chosen, these are law.
- **Symbol table:** q for joint positions, τ for torques, m_i, l_i, I_i for link properties, etc., with units. The **armature-math** skill will consume this table verbatim, so make it complete.
- **Naming conventions:** part numbering scheme (e.g., `ARM-LNK-002`), CAD file naming, revision scheme, units policy (SI internally, always).
- **Definitions of done** for a task, a phase, and the project.

### 2. Phase breakdown

Decompose into phases where each phase ends in something *demonstrable or testable* — never "phase 3: keep working on arm." Typical arc (adapt, don't copy):

1. **Analysis & sizing** — kinematic model, workspace check, actuator sizing from dynamics, DOF/reachability verification. Tasks here should explicitly say "derive FK/IK/Jacobian/dynamics" — and if the **armature-math** skill is installed, name it as the tool for those tasks.
2. **Concept CAD & layout** — master sketch / skeleton model driving all subassemblies, envelope check, interference and service-access check, mass rollup vs. budget.
3. **Prototype the risky bits** — one prototype per top risk from the spec's risk register, each with a question it must answer and a kill criterion.
4. **Detail design & DFM** — part-by-part CAD, tolerance decisions, COTS selection with actual part numbers, drawings for anything outsourced, BOM with costs against budget. If the spec came with a **design-driver BOM** (from armature-spec), this phase expands it into the full procurement BOM rather than starting over — the design drivers and their datasheets are already settled; here you add quantities, fasteners, costs, and lead times. Any part still carrying a TBD or assumed spec gets a task to source and confirm its datasheet *before* its drawing is released; don't let an unverified number reach the shop.
5. **Fabrication & subsystem bring-up** — build order chosen so subsystems are testable standalone; electrical/wiring as first-class tasks, not an afterthought.
6. **Integration & verification** — trace every Must requirement (REQ-xxx) to a test in this phase. A requirement with no test is a wish.
7. **Iteration reserve** — an explicit phase, not leftover time. The first build is a hypothesis; budget for revising the worst mechanism.

### 3. Task format

Every task gets:

```
- [ ] T3.2 Prototype cable-driven wrist
      Answers: can 2mm Dyneema hold tension over 500 cycles at r=8mm?
      Depends on: T3.1 · Est: 6h · Needs: printed pulley set, load cell
      Done when: 500-cycle test logged, elongation < 1%, OR killed and
      T3.2b (geared wrist) activated
```

Estimates in hours, dependencies explicit, exit criteria observable. Keep tasks under ~a day of work; split anything bigger.

### 4. CAD process guidance

Plans should encode good CAD practice, not just "do CAD": top-down skeleton/master-sketch modeling so envelope changes propagate; design around downloaded COTS models from day one; check service access (can you swap every sensor and fastener?); mass properties tracked against the spec's mass budget at every phase gate.

### 5. Risks → plan hooks

Pull the spec's risk register into the plan: every high risk gets either a prototype task, an analysis task, or a scheduled decision point. Note revisit triggers on the timeline.

## Style

Plain, specific, imperative. No motivational filler. Dates and hours are estimates and labeled as such. If the spec's scope doesn't fit the user's stated hours, say so in the plan's first paragraph and propose what to cut — a plan that pretends is worse than no plan.

## Hand-offs

- Kinematics/dynamics tasks → **armature-math**
- "I'm stuck, need a better approach for phase N" → **armature-inventor**
- "Explain this concept the plan assumes I know" → **armature-teacher**
- "Stress-test this plan (or the spec under it) for gaps before I commit" → **armature-red-team**

### The handoff prompt

The whole suite runs on one rule — *the saved files are the state; the transcript is not.* So don't end by telling the user to go start the next step; hand them a prompt that starts it for them. Once the plan is written and it's clear which route they're taking (ask if it isn't — the routes are listed above), emit a single fenced block for **the path they're actually taking**, nothing else:

```
── Next step: <next-skill> · new chat ──
Attach: <the plan file you just wrote, + the spec/BOM if the next step needs them>
Paste:
  <first-person prompt: name the next skill, say what to do with the attached
   files, and carry the decisions and open questions that live only in this
   conversation>
```

The paste text changes with the route — for example:
- **→ armature-math** (the common one, for a Phase-1 analysis/sizing task): "Run armature-math for `<task id, e.g. T1.2 — actuator sizing>` in the attached plan for `<project>`. Use the frames, symbol table, and naming conventions in the plan's Section 1 verbatim — that glossary is the contract. Goal: `<what this task must produce>`. Relevant parts and their limits are in the attached BOM."
- **→ armature-red-team:** "Red-team the attached plan for `<project>` (and the spec under it, attached). Check phase sequencing, that every Must REQ traces to a verification task, and that each high risk has a prototype or decision point. Hours/week and deadline the plan assumes: `<…>`."

Keep the block honest and paste-ready:
- **Name real files.** Use the actual saved filenames, and attach the spec/BOM too when the next step reads them — the user attaches them blind in a chat with none of this context.
- **Carry what the files don't.** The plan records the tasks and conventions; the prompt carries *which* task or phase the next step is picking up and any decision made this session (a task killed, a phase reordered, hours revised). Point the next step at the plan's Section 1 glossary rather than restating frames and symbols — that's what keeps conversation #47 as grounded as conversation #2.
- **Write it in the user's voice**, first person, so it reads naturally when pasted.
- **One block, no commentary inside it** — it's meant to be copied whole.
