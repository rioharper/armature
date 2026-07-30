# Armature: robotics engineering plugin for Claude Code

Armature is a robotics engineering pipeline packaged as a Claude Code plugin.

AI has permeated every part of software engineering… but not so much in robotic design. As someone who dabbles in both, I felt like a suite for rapidly iterating on robotic concepts, creating SpecOps, and crunching the dynamics and kinematics with you was sorely missing.

Will this replace a mechanical engineer? Hell no. However, it will make your life a little easier and get past some of the monotony. I’ve found it extremely helpful for my own projects, and I think engineers deserve the beauty of Claude Code too.

Install it once, then run `/armature:init` in a blank folder. It'll scaffold a
standard project, stamp `CLAUDE.md`, and roll right into the concept interview.
From there you work concept → spec → plan → analysis → CAD the way a real
engineering team would: budgets tracked, requirements traced, decisions
logged, and a red-team pass before anything gets built or bought.

## The pipeline

Six stage skills form the main path, each an interactive interview run in the
main conversation, handing its output to the next:

| Stage | Skill | Produces |
|---|---|---|
| 1 | `armature-concept` | `docs/00-concept/concept-brief.md` — who it's for, why it beats what exists. Interrogates *why*, not *how*. |
| 2 | `armature-spec` | `docs/01-spec/spec.md`, `bom.md`, `budgets.md`, `traceability.md` — engineering spec, trade studies, design-driver BOM, living budgets, requirements traceability. |
| 3 | `armature-plan` | `docs/02-plan/plan.md` plus the glossary written into `CLAUDE.md` — phased implementation plan and the shared vocabulary (frames, symbols, naming) that keeps later sessions grounded. |
| 4 | `armature-math` | `analysis/derivation/*.md` + `analysis/model/*.py` — milestone-sized derivation notes and a re-runnable, cross-verified Python model. |
| 5 | `armature-cad` | `cad/parts/`, `cad/assemblies/` — per-part definitions (interfaces, loads, material, datums, tolerances, inertia targets), assembly mate schemes, and a build recipe for the chosen CAD package. |

Cross-cutting skill and agents, pulled in from any stage:

| Name | Kind | Role |
|---|---|---|
| `armature-teacher` | skill | Explains a concept, equation, or design decision using this project's own artifacts. Analogy first, then formalism. |
| `armature-red-team` | agent | Adversarial review of an existing artifact — writes findings to `docs/reviews/`. Fresh context by construction; run before CAD hours or purchases. The chat will invoke it as a subagent at crucial milestones. |
| `armature-inventor` | agent | Frontier research: papers, novel mechanisms, unusual actuators/materials, it'll write briefs to `docs/research/`. |
| `armature-librarian` | agent | Hunts datasheets and OTS CAD models, verifies part numbers, caches results to `docs/datasheets/` and `cad/ots-parts/`. |

## The project layout

`/armature:init` scaffolds this tree:

```
<project>/
  CLAUDE.md                  project constitution (§4)
  docs/
    00-concept/
      concept-brief.md       armature-concept output (RC-xxx requirements)
    01-spec/
      spec.md                armature-spec output (REQ-xxx requirements)
      bom.md                 design-driver BOM → grows into procurement BOM
      budgets.md             living mass/power/cost budgets with margins (§6.1)
      traceability.md        REQ → design element → analysis → test → status (§6.2)
    02-plan/
      plan.md                armature-plan output
    testing/                 test procedures + reports (§6.3)
    reviews/                 red-team findings, dated
    research/                inventor briefs
    datasheets/
      index.md               P/N, source URL, retrieval date, key numbers
      *.pdf                  cached datasheets
    decisions.md             one-line-per-decision log (§6.7)
  analysis/                  armature-math derivations (.md) + model (.py)
  cad/
    parts/                   part definitions
    assemblies/              assembly definitions (§6.5)
    ots-parts/
      index.md               model file → P/N → datasheet entry
      *                      vendor STEP/native models
  .gitignore
```

## Install

Install as a Claude Code plugin — via a marketplace, or locally with
`--plugin-dir` pointed at this repo.

Once installed, run `/armature:init` in a blank folder to start everything.
