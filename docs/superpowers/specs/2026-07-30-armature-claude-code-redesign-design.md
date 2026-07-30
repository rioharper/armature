# Armature — Claude Code Redesign

**Date:** 2026-07-30 · **Status:** Draft for review

Armature is a robotics engineering skill suite currently written for claude.ai
projects (paste-prompt handoffs, transcript-as-liability, attach-files rituals).
This redesign converts it into a Claude Code plugin that a user installs once,
then runs `/armature:init` in a blank folder to scaffold a standardized project
and work the pipeline the way a real robotics engineering team would — with
subagents for fresh-eyes review and research, git branches/worktrees for
parallel exploration and milestone gating, and locally-executed verification.

## 1. Goals and non-goals

**Goals**

- One installable plugin: skills, agents, and commands, auto-discovered.
- `/armature:init` scaffolds a standard project layout + git repo + project
  `CLAUDE.md`, then rolls straight into the concept interview.
- Replace every paste-into-fresh-chat handoff with real primitives: files at
  standard paths, `CLAUDE.md` for the always-loaded glossary, Agent-tool
  dispatch for red-team/inventor/librarian.
- Keep the interactive interview culture in the main conversation (concept,
  spec, plan, math, cad, teacher); delegate only what benefits from separate
  context or parallelism.
- Close the loops locally: Claude runs `run_all.py`, re-runs models against
  realized CAD mass properties, and re-checks budgets — no user ritual.
- Add the missing systems-engineering artifacts (§6): budgets, traceability,
  test reports, model calibration, assembly definition, safety pass, decision
  log, OTS part models.

**Non-goals (deferred, not rejected)**

- Electrical, firmware, and controls skills.
- The datasheet MCP server (v2 — see §8).
- FMEA and formal ECN/change control (red-team worst-case duties + git
  history + decision log cover the current scale).

## 2. Plugin layout

```
armature/
  .claude-plugin/plugin.json      name "armature", version 1.0.0
  commands/
    init.md                       /armature:init
  agents/
    red-team.md                   adversarial reviewer, fresh context
    inventor.md                   frontier research, parallelizable
    librarian.md                  datasheet hunter + cache keeper
  skills/
    armature-concept/             was robotics-concept-design
    armature-spec/                was robotics-spec-design
    armature-plan/                was robotics-writing-plans
    armature-math/                was robotics-mathematician (+ model_template/)
    armature-cad/                 was robotics-cad-parts (+ package references)
    armature-teacher/             was robotics-teacher
  README.md
```

`robotics-red-team` and `robotics-inventor` cease to be skills; their SKILL.md
content becomes the corresponding agent's system prompt (with their
`references/` files moved alongside). Commands, agents, and skills are
auto-discovered from these directories.

## 3. `/armature:init`

Run in a blank (or existing) folder. Behavior:

1. Scaffold the project tree below; `git init` if needed; first commit.
2. Ask two or three setup questions — project name, CAD package, builder
   capability sketch (shop access, team size) — and stamp answers into
   `CLAUDE.md`.
3. Roll directly into the `armature-concept` interview. No separate
   invocation.

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

Empty directories get a stub `index.md` or `.gitkeep` so the tree survives the
first commit. Files not yet produced by their stage do not exist as empty
placeholders — the tree shows where things go, not fake content.

## 4. `CLAUDE.md` as the project constitution

The plan skill's "Section 1 glossary" existed to fight transcript amnesia.
Claude Code loads `CLAUDE.md` automatically every session, so the contract
moves there. Sections:

- **Header:** project one-liner; current pipeline stage; pointer to the newest
  artifacts.
- **Glossary:** coordinate frames, symbol table, part-numbering scheme, CAD
  file naming, revision scheme, units policy (SI internally). Written by
  `armature-plan` when it runs; consumed verbatim by math/cad forever after.
  Until the plan runs, this section holds only the units policy and numbering
  conventions seeded by init.
- **Standing rules:**
  - Every datasheet number traces to `docs/datasheets/index.md`.
  - Red-team before CAD hours or purchases.
  - RC-xxx = concept-level outcome; REQ-xxx = verifiable engineering
    requirement with a method.
  - Budget debits (`budgets.md`) and decision-log entries are part of "done"
    for any task that changes a mass, power draw, cost, or design choice.

Every stage skill updates the stage line and artifact pointers when it
finishes.

## 5. Stage skills — changes

**Common to all six**

- Delete the entire "handoff prompt" machinery (fenced paste blocks,
  attach-file instructions, "new chat" choreography) — roughly a quarter of
  the current text. Replacements: artifacts land at the standard paths in §3;
  the next skill reads them from there; agents are dispatched with the Agent
  tool; `CLAUDE.md` carries the glossary and stage pointer.
- "Recommend red-team in a new chat" becomes "dispatch the red-team agent" —
  fresh context by construction.
- Datasheet needs route through the librarian agent; cached numbers are cited
  from `docs/datasheets/index.md`.
- Each skill's closing move: write artifacts, update `CLAUDE.md` stage line,
  append decisions to `docs/decisions.md`, offer the next stage.

**armature-concept** — interview unchanged. Writes
`docs/00-concept/concept-brief.md`. May continue straight into spec in the
same session (the interview is with the user, not a fresh reader; the
fresh-eyes rule applies only to review, i.e. red-team).

**armature-spec** — Phase 4 datasheet capture delegates to librarian. Phase 2
may dispatch inventor mid-trade-study. New Phase 2 option: for 2–3 genuine
finalist architectures, offer parallel exploration — one git worktree +
subagent per candidate, each producing a feasibility sketch; results compared
in the trade matrix; the winner's artifacts merged, losers recorded as
rejected alternatives (§7). New outputs: seeds `budgets.md` (mass/power/cost
lines with margins) and `traceability.md` (REQ column filled, rest open). New
spec-template section: mechanical safety checklist (§6.6).

**armature-plan** — the glossary is written into `CLAUDE.md` instead of plan
§1 (the plan file keeps a one-line pointer). Tasks gain an **executor** field
naming the skill or agent that runs them. Phase 6 (integration & verification)
tasks point at `docs/testing/` procedures; the traceability matrix's test
column gets filled here. Otherwise intact.

**armature-math** — milestones survive (review discipline, not just a token
workaround). Each milestone runs on its own branch, merged only after
self-tests pass via locally-executed `run_all.py` and the red-team agent's
findings are resolved (§7). `model_template/` ships in the skill and is copied
at Milestone 0. New: a **calibration procedure** (§6.4) — after bench data
exists, reconcile measured values (friction, motor constant, real masses) into
`params.py`, re-run, and record which predictions moved. Updates `budgets.md`
current-estimate column when masses/inertias firm up.

**armature-cad** — per-part flow unchanged in substance. Datasheet gaps →
librarian; batch review before modeling → red-team agent; the close-the-loop
step re-runs the model locally against realized mass properties instead of
asking the user to. New: assembly definitions in `cad/assemblies/` and a
worst-case tolerance stack-up procedure (§6.5); OTS models cached in
`cad/ots-parts/` with index provenance. Debits `budgets.md` as parts are
realized.

**armature-teacher** — essentially untouched; never workflow-bound. Reads
project artifacts from the standard paths to teach *this* project's concepts.

## 6. New engineering artifacts and procedures

**6.1 Living budgets** (`docs/01-spec/budgets.md`) — mass, power, and cost
tables: line item, budget, current estimate, margin, source of estimate
(guess / datasheet / model / measured). Created by spec; debited by math and
cad as estimates harden; checked at every phase gate; audited by red-team.
Format is a plain markdown table — the discipline is the artifact.

**6.2 Requirements traceability** (`docs/01-spec/traceability.md`) — one row
per REQ: REQ → design element → analysis that verifies it → test that proves
it → status (open / analyzed / tested / waived). Spec creates rows; plan fills
the test column; math and testing update status; red-team audits for holes.

**6.3 Test procedures and reports** (`docs/testing/`) — minimal template:
purpose (which REQ or kill criterion), setup, method, data, pass/fail, and
what the result feeds (a traceability row, a `params.py` value, a budget
line). Prototype tasks from plan Phase 3 and verification tasks from Phase 6
both land here. Without this, prototype results live in the transcript — the
disease the suite exists to cure.

**6.4 Model calibration** (procedure in armature-math) — when a test report
carries a measured value the model assumed (friction, motor constant, link
mass), update `params.py` with the measured value marked `measured`, re-run
`run_all.py`, and record in `03_results.md` which conclusions moved. Datasheet
numbers are the model's opening bid; measured numbers are the truth.

**6.5 Assembly definition + tolerance stack-up** (armature-cad) — per
assembly: mate scheme, fastener spec and torque, assembly order (can the tool
physically reach the bolt at that step?), jigs/fixtures needed. Plus a
worst-case stack-up procedure across mating parts for each critical fit —
per-part tolerances can all be met while the assembly still doesn't go
together. Lives as a new section + reference in armature-cad; outputs to
`cad/assemblies/`.

**6.6 Mechanical safety pass** (spec template + red-team checklist) — short
checklist: pinch/crush points, stored energy on power loss (springs, gravity,
flywheels), tip-over stability, payload drop path, sharp edges near humans.
Scaled to consequence, per the existing capability-assessment discipline.

**6.7 Decision log** (`docs/decisions.md`) — one line per decision: date,
what, why, what it supersedes. Trade studies capture the big forks; this
catches the fifty small ones that otherwise evaporate. Convention enforced by
the `CLAUDE.md` standing rules.

**6.8 OTS part models** (`cad/ots-parts/`) — vendor STEP/native models with an
index row per file: model file → part number → datasheet entry. Gives the CAD
skill's "design around downloaded COTS models from day one" a real home with
provenance.

## 7. Git usage

- **Trade-study exploration (worktrees):** when the spec's Phase 2 has 2–3
  genuine finalists, offer one worktree + subagent per candidate; each
  develops a feasibility sketch (rough sizing, dominant risks, cost) in
  isolation; the main session compares them in the trade matrix and merges
  the winner. Worktrees only when work is actually parallel — otherwise plain
  branches.
- **Milestone branches:** each armature-math milestone and each armature-cad
  part batch on its own branch (`armature/m1-kinematics`,
  `armature/cad-base-batch`), merged after self-tests pass and red-team
  findings are resolved. Merge is the phase gate.
- Commits at every artifact write; the git log plus `docs/decisions.md` is
  the project history. No separate ECN process.

## 8. Agents

**red-team** — tools: Read, Grep, Glob, Bash. Bash so it can *re-run*
`run_all.py` and recompute back-of-envelope checks, not just read them. May
write only its findings file to `docs/reviews/` — never edits the artifact
under review. New audit families: budget-margin erosion (`budgets.md`),
traceability holes, safety-checklist coverage. Keeps its review-checklist
reference. Dispatched by spec/math/cad at their existing checkpoints, or by
the user directly.

**inventor** — tools: WebSearch, WebFetch, Read, Write (briefs only). Spec or
plan can fan out several in parallel, one per idea family (mechanism,
actuation, material, sensing, manufacturing method), each writing a brief to
`docs/research/`. The filter-hard step and the boring-baseline comparison stay
in the main conversation.

**librarian** — tools: WebSearch, WebFetch, Read, Write (datasheet cache
only). Finds a candidate datasheet, reports part number + source to the main
conversation for user confirmation (the anti-guessing discipline survives),
then caches the PDF in `docs/datasheets/` and appends key numbers +
provenance to `index.md`. Also fetches OTS CAD models into `cad/ots-parts/`
with the same confirm-then-cache flow. This is datasheet collection **v1**.
**v2** (own spec, later): a dedicated MCP server for structured part search
(Digi-Key / Mouser / McMaster APIs), PDF spec extraction to structured data,
and BOM cross-checking; the plugin gains an `.mcp.json` when it exists.

## 9. Migration and cleanup

- Rename skill directories per §2; rewrite frontmatter names/descriptions to
  the `armature-*` scheme (descriptions keep their trigger-rich style).
- Strip handoff-prompt sections from all six stage skills; rewrite their
  input/output sections against the §3 paths and §4 `CLAUDE.md` contract.
- Convert red-team and inventor SKILL.md files to agent definitions.
- Write `commands/init.md`; extend spec/plan/math/cad templates and references
  for §6 artifacts; add the assembly/stack-up reference to armature-cad.
- `plugin.json` → 1.0.0 with corrected description; new README describing the
  pipeline, install, and the init flow; delete `MANIFEST.md5` and snapshot
  caveats; the deleted Obsidian project template stays deleted (init replaces
  it).

## 10. Verification

Smoke test in a scratch folder:

1. Install the plugin locally; run `/armature:init`; confirm the §3 tree,
   git repo, and `CLAUDE.md` exist and the concept interview starts.
2. Walk concept → spec far enough to produce a brief, a spec stub,
   `budgets.md`, and `traceability.md` at the right paths.
3. Dispatch one red-team review and one librarian fetch; confirm findings
   land in `docs/reviews/` and a datasheet + index row in `docs/datasheets/`.
4. Copy the math model template, run `run_all.py` via Bash, confirm
   self-tests execute.

Each stage skill's rewrite is checked against one question: could a fresh
session, given only the repo, pick up exactly where the last one left off?
