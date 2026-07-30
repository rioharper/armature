---
name: armature-writing-plans
description: Convert a robotics engineering spec into a phased implementation plan with exit criteria, and author the project's CLAUDE.md glossary — frames, symbols, naming — that every later session inherits. Use whenever the user has a spec or design document and wants a plan, roadmap, timeline, task breakdown, next steps, or "how do I actually build this", or asks to plan out a robotics project even informally.
---

# Armature Writing Plans

You take a finished-enough engineering spec and turn it into a plan someone can execute — phase by phase, task by task, with exit criteria — and you author the shared language that keeps every future session about this project coherent.

Read `../references/conventions.md` first. You are the skill that writes `CLAUDE.md`, so the conventions in that file are your output, not just your input.

## Inputs

Read `docs/spec.md` and `docs/bom.yaml`. If no spec exists, don't fabricate one — do a compressed requirements capture (mission, constraints, chosen architecture, builder capability), note in the plan that it rests on an informal spec, and suggest **armature-spec-design** if the project is substantial. Audience and differentiation are settled upstream in `docs/concept-brief.md`; take them as given.

Before writing, resolve with the user: available hours per week, hard deadlines, and whether analysis should precede or parallel CAD. Don't guess at their calendar.

## Step 1: Author CLAUDE.md

This is the point of the skill. `CLAUDE.md` sits at the repo root, Claude Code loads it into every session automatically, and every downstream skill inherits it without being asked. That auto-loading is what makes session #47 about this robot as grounded as session #2 — so the file has to be complete, not gestured at.

Write, using `references/claude-md-template.md`:

- **Coordinate frames** — every frame the project will use ({W} world, {B} base, {E} end-effector, per-joint frames), their origins, axis conventions (right-handed, and z-up or z-along-joint — pick and state), and the convention family (modified DH, or product of exponentials). Once chosen, these are law.
- **Symbol table** — `q` for joint positions, `τ` for torques, `m_i`, `l_i`, `I_i` for link properties, with units. **armature-mathematician** consumes this verbatim into `params.py`, so make it complete and make the symbol names legal Python identifiers where they'll become code.
- **Naming** — part-numbering scheme (`ARM-LNK-002`), CAD file naming, units policy (SI internally, always).
- **Definitions of done** for a task, a phase, and the project.

Commit it on its own: `plan: establish project glossary in CLAUDE.md`. A skill that later needs to change a frame or a symbol edits this file and says so in its commit — a symbol meaning two things in two files is the drift this exists to prevent.

## Step 2: Write the plan

Write `docs/plan.md`. Decompose into phases where each ends in something *demonstrable or testable* — never "phase 3: keep working on arm." Typical arc, adapt rather than copy:

1. **Analysis & sizing** — kinematic model, workspace check, actuator sizing from dynamics, DOF and reachability verification. Name **armature-mathematician** as the tool for these tasks.
2. **Concept CAD & layout** — master sketch driving all subassemblies, envelope check, interference and service-access check, mass rollup against budget.
3. **Prototype the risky bits** — one prototype per top risk from the spec's risk register, each with a question it must answer and a kill criterion.
4. **Detail design & DFM** — part-by-part definitions via **armature-cad-parts**, tolerance decisions, drawings for anything outsourced. This phase expands `docs/bom.yaml` into the full procurement BOM rather than starting over: the design drivers and datasheets are settled, so here you add quantities, fasteners, costs, and lead times. Any part still carrying `tbd` or `assumed` status gets a task to source and confirm its datasheet *before* its drawing is released.
5. **Fabrication & subsystem bring-up** — build order chosen so subsystems are testable standalone; electrical and wiring as first-class tasks.
6. **Integration & verification** — trace every Must requirement to a test in this phase. A requirement with no test is a wish.
7. **Iteration reserve** — an explicit phase, not leftover time. The first build is a hypothesis; budget for revising the worst mechanism.

### Task format

```
- [ ] T3.2 Prototype cable-driven wrist
      Answers: can 2 mm Dyneema hold tension over 500 cycles at r=8 mm?
      Depends on: T3.1 · Est: 6h · Needs: printed pulley set, load cell
      Done when: 500-cycle test logged, elongation < 1%, OR killed and
      T3.2b (geared wrist) activated
```

Estimates in hours, dependencies explicit, exit criteria observable. Keep tasks under a day; split anything bigger.

The checkboxes are live. A task closes by being checked off in the same commit as the work it describes, so `git log docs/plan.md` is the project's actual history rather than a plan that drifted from reality by week three. Phases close with a tag: `git tag phase/<project>-1-complete`.

### CAD process guidance

Encode good practice, not just "do CAD": top-down skeleton modelling so envelope changes propagate; design around downloaded COTS models from day one; check service access — can every sensor and fastener be reached after assembly?; mass properties tracked against the spec's budget at every phase gate.

### Risks to plan hooks

Pull the spec's risk register in: every high risk gets a prototype task, an analysis task, or a scheduled decision point. Note revisit triggers on the timeline.

**Done when** `CLAUDE.md` defines every frame and symbol the analysis will need, every Must requirement in the spec appears in a Phase 6 verification task, and every high risk has a hook. Commit `plan:`, and update `.armature/state.md` to phase 1.

## Style

Plain, specific, imperative. No motivational filler. Dates and hours are estimates and labelled as such. If the spec's scope doesn't fit the user's stated hours, say so in the plan's first paragraph and propose what to cut — a plan that pretends is worse than no plan.

## Review

Launch **armature-red-team** as a subagent on the plan and the spec beneath it before work starts against it. Its consistency checker mechanically verifies the Must-requirement-to-test tracing you just wrote by hand, which is exactly the check most likely to have a hole in it.

## Hand-offs

- Kinematics and dynamics tasks → **armature-mathematician**
- Detail-design tasks, part by part → **armature-cad-parts**
- Stuck on approach for phase N → **armature-inventor**
- A concept the plan assumes the user knows → **armature-teacher**
