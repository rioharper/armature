# Armature — robotics engineering plugin for Claude Code

Armature is a robotics engineering pipeline packaged as a Claude Code plugin.
Install it once, then run `/armature:init` in a blank folder — it scaffolds a
standard project, stamps a `CLAUDE.md`, and rolls into the concept interview.
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
| `armature-red-team` | agent | Adversarial review of an existing artifact — writes findings to `docs/reviews/`. Fresh context by construction; run before CAD hours or purchases. |
| `armature-inventor` | agent | Frontier research — papers, novel mechanisms, unusual actuators/materials — writes briefs to `docs/research/`. |
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

(Section numbers refer to the design spec at
`docs/superpowers/specs/2026-07-30-armature-claude-code-redesign-design.md`.)

## How state works

Files are the state — every stage reads its inputs from the paths above and
writes its outputs there, so a fresh session can pick up exactly where the
last one left off. `CLAUDE.md` is loaded automatically every session and
carries the glossary and standing rules forward, replacing paste-prompt
handoffs. `budgets.md`, `traceability.md`, and `decisions.md` are living
documents that every later stage debits or updates, not one-time snapshots.

## Install

Install as a Claude Code plugin — via a marketplace, or locally with
`--plugin-dir` pointed at this repo. Loose-skill copying into
`~/.claude/skills/` is no longer supported: agents and `/armature:init` are
plugin components, not standalone skill directories.

Once installed, run `/armature:init` in a blank folder to start everything.
