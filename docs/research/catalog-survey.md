# Catalog survey: what else in mattpocock/skills is worth absorbing into Armature

**Question:** Beyond wayfinder and tdd (already being absorbed), which patterns/skills in Matt
Pocock's skills repo are worth absorbing into Armature?

**Date:** 2026-08-30 · **Method:** read every `SKILL.md` (plus supporting reference files,
`docs/`, and `.agents/`) in the local clone at `C:\Users\rioha\Documents\skills`
(github.com/mattpocock/skills), against Armature's README, SKILL.md set, and agent definitions
in this repo. Primary sources only — the skill files themselves. Unless a path is given, each
row's source is `skills/<bucket>/<name>/SKILL.md` in that clone.

**Maturity key:** released = `engineering/`/`productivity/` (shipped in the plugin, has a docs
page); misc = released but unpromoted (no docs page); in-progress = beta, excluded from the
plugin (`skills/in-progress/README.md`); retro is explicitly a stub.

## Recommendation table

| # | Skill (bucket) | What it is | Robotics fit | Maturity | Touches | Verdict | Reason |
|---|---|---|---|---|---|---|---|
| 1 | grilling (productivity) | Interview engine: design-tree of decisions, ask the whole *frontier* per round, recommended answer per question, facts are the agent's job | All — interviews are Armature's front half | released | concept, spec, plan | **adapt** | Three mechanics Armature's free-form rounds lack; keep Armature's domain-scripted question content |
| 2 | domain-modeling (eng) | Live glossary discipline (CONTEXT.md, `_Avoid_:` anti-synonyms) + minimum-viable ADRs behind a three-gate test | All — vocabulary drift kills multi-session projects | released | plan (glossary), init (decisions.md), all stages | **adapt** | `_Avoid_` lines + inline challenge + ADR tier over decisions.md; keep CLAUDE.md as the home, don't add CONTEXT.md |
| 3 | diagnosing-bugs (eng) | Six-phase debug loop gated on a *tight* red-capable feedback loop before any hypothesis; ships a HITL bash template | Hardware/firmware debugging is its best unclaimed use | released | new skill (or plan §5–6 bring-up + math) | **adapt** | Loop-first discipline + HITL template map directly to bench debugging; ladder items 1–9 need hardware equivalents |
| 4 | wizard (eng) | Generates a stage-by-stage interactive bash walkthrough (progress, confirm gates, value capture) from `template.sh` | Bring-up/test procedures are exactly this shape | released | plan (fab/bring-up phases), docs/testing | **adapt** | Reuse stage/confirm/capture pattern for bring-up runners logging to test reports; swap the .env/gh-secret helpers |
| 5 | research (eng) | Background agent, primary sources, cited md note in repo convention location | Any engineering question | released | inventor, librarian | **skip** | Inventor (frontier briefs) + librarian (verified datasheets) are the specialized versions with stronger provenance; residual generic gap is thin |
| 6 | prototype (eng) | Throwaway code answering one design question; LOGIC branch = single-HTML state-machine walkthrough; kept as primary source on a branch | Software/firmware behavior (modes, e-stop, gait sequencing) | released | future behavior/firmware stage; plan §3 | **adapt (later)** | Physical prototyping + kill criteria already in plan; the LOGIC-branch interactive state-machine HTML covers discrete behavior, which armature-math (continuous) doesn't |
| 7 | to-spec (eng) | Conversation → spec synthesis, no interview, published to issue tracker | Software teams | released | — | **skip** | armature-spec/plan produce richer artifacts; no tracker in Armature's file-based flow |
| 8 | to-tickets (eng) | Tracer-bullet vertical slices with blocking edges; expand–contract for wide refactors | Software builds | released | plan §3 task format | **skip** | Plan tasks already carry Depends/Done-when; worth one borrowed line: bias early phases toward one-joint-end-to-end (tracer-bullet) slices |
| 9 | triage (eng) | Issue/PR state machine with verify-then-grill and `.out-of-scope/` rejection KB | External request surfaces | released | — | **skip** | A robotics project has no inbound issue stream; decisions.md `supersedes` column + trade studies already record rejections |
| 10 | triage/AGENT-BRIEF.md | Durable brief rules: behavioral not procedural, no paths/line numbers, testable acceptance criteria, explicit out-of-scope | All — briefs for AFK agents | released | red-team + inventor + librarian dispatches, plan tasks | **absorb** | Directly strengthens agent dispatch prompts and plan task wording; near-zero cost (`skills/engineering/triage/AGENT-BRIEF.md`) |
| 11 | code-review (eng) | Two-axis review (Standards vs Spec) in parallel subagents, never merged | Software | released | red-team | **skip** | Red-team's single fresh-context checklist already spans both axes; splitting would lose the cross-document reads it says projects die on |
| 12 | codebase-design (eng) | Deep-module vocabulary (module/interface/depth/seam/leverage/locality) | Software modules | released | — | **skip** | armature-cad's interface-first part definitions are already the mechanical analog; analysis/model layout is prescribed by armature-math |
| 13 | codebase-design/DESIGN-IT-TWICE.md | 3+ parallel subagents design radically different interfaces, compare on named criteria | Trade studies | released | spec, inventor | **skip** | Armature already dispatches parallel inventors one-per-idea-family and mandates trade-off matrices — same pattern, already native |
| 14 | improve-codebase-architecture (eng) | Deepening survey + HTML report + grilling loop | Software repo upkeep | released | — | **skip** | Software-maintenance flow; Armature's analysis cards already fill the visual-report niche |
| 15 | resolving-merge-conflicts (eng) | Resolve hunks by intent traced to primary sources; never abort | Generic git | released | — | **skip** | No robotics delta; math milestone branches are sequential and merge cleanly by design |
| 16 | implement (eng) | Thin ticket-execution wrapper (tdd inside, code-review after) | Software | released | — | **skip** | Armature's build stage is physical; tdd absorption is handled elsewhere |
| 17 | ask-matt (eng) + PHASE-BOUNDARIES.md | Router over the whole set + a 5-option decision tree for phase boundaries (continue/clear/handoff/subagent/compact) | All — long math/CAD sessions hit context limits | released | README or a small reference; teacher | **adapt** | Stage line in CLAUDE.md already routes stages; the phase-boundary tree is the genuinely missing guidance (`skills/engineering/ask-matt/PHASE-BOUNDARIES.md`) |
| 18 | setup-matt-pocock-skills (eng) | Per-repo config: issue tracker choice, triage labels, domain-doc layout via `docs/agents/*.md` pointer files | — | released | init | **note only** | Its role — skills read per-repo config from a stamped location — is exactly what /armature:init's CLAUDE.md constitution already does |
| 19 | grill-me / grill-with-docs (prod/eng) | One-line wrappers composing grilling (+ domain-modeling) | — | released | — | **skip** | Wrapper pattern noted under .agents/invocation.md (row 26) |
| 20 | handoff (prod) | Compact conversation → handoff md in OS temp dir; suggested-skills section; redaction | Multi-session continuity | released | all stage skills, init | **adapt** | Armature's continuity is artifact-based (Stage line + docs on disk) — better than temp files; the missing piece is mid-interview checkpointing: write a Draft + open-questions block into the stage doc |
| 21 | claude-handoff (in-progress) | Handoff straight into `claude --bg` background agent | — | in-progress | — | **skip** | Harness-specific and beta |
| 22 | teach (prod) | Stateful learning workspace: MISSION, learning records, ZPD, retrieval practice, reference docs | Learning robotics theory | released | teacher | **adapt (low)** | armature-teacher is stateless per-concept; borrow just the learning-record log so it stops re-explaining and calibrates depth; the HTML course machinery is out of scope |
| 23 | to-questionnaire (prod) | "Grill the send, not the subject": generate a most-important-first questionnaire for the person who holds the knowledge | Machinist/vendor-FAE/professor queries are routine in hardware | released | spec, cad (DFM questions for the shop) | **adapt** | Spec-stage unknowns often live in a third party's head; small, self-contained pattern |
| 24 | wait-what (prod) | Re-pitch the last message in Simplified Technical English using the project glossary | Communication repair | released | — | **skip** | armature-teacher already re-explains, project-grounded, analogies-first |
| 25 | writing-for-agents (prod) + SKILL-MECHANICS.md | The discipline for writing agent docs: context pointers, two loads, completion criteria, leading words, no-op hunting | Plugin maintenance (contributor-facing) | released | Armature's own SKILL.md/agent files | **absorb (house style)** | Adopt as the standard for editing Armature's skills; complements docs/research/writing-standard.md (prose register) with structure/variance levers |
| 26 | .agents/invocation.md (repo convention) | Cross-skill calls phrased as "Call the Skill tool with \"name\"", never prose /mentions; model- vs user-invoked audit | Plugin mechanics | conventions doc | all skills' hand-off sections | **absorb** | Mechanical hit-rate improvement for Armature's prose hand-offs ("hand off to armature-spec"); init already models `disable-model-invocation` |
| 27 | .agents/writing-docs.md + docs/ pages | Per-skill human docs: defining constraint, "your situation → where to go" routing table, observed Common questions, "It's working if" | User onboarding | conventions doc | README, future docs/ | **adapt** | Armature README describes the pipeline but routes poorly from a user's situation; one routing table is the cheap version |
| 28 | loop-me (in-progress) | Grill life workflows into delegable specs | — | in-progress | — | **skip** | Personal-automation domain |
| 29 | retro (in-progress, STUB) | Post-session environment-improvement audit (navigation, checks, no-ops, tool economy) | Plugin maintenance | stub | — | **skip** | Stub by its own README; category list worth revisiting once it graduates |
| 30 | setup-ts-deep-modules (in-progress) | dependency-cruiser entry-point enforcement | TypeScript | in-progress | — | **skip** | Language-specific |
| 31 | writing-beats/-fragments/-shape (in-progress) | Explore/exploit article-writing pipeline with concept grounding | Prose | in-progress | — | **skip** | Article writing; the "ground a concept before leaning on it" idea already lives in armature-teacher's sequence |
| 32 | git-guardrails-claude-code (misc) | PreToolUse hook blocking destructive git | Any repo | misc | — | **skip** | User-level safety config, not plugin behavior; note plugins *can* ship hooks if Armature ever wants to guard project history |
| 33 | setup-pre-commit / migrate-to-shoehorn / scaffold-exercises (misc) | Husky/Prettier setup; TS test-typing migration; course scaffolding | TS/web/course | misc | — | **skip** | No robotics surface |

## Notes on the flagged comparisons

### 1. Grilling rounds vs Armature's free-form interviews (rows 1, 19)

Armature already interviews in rounds with reflection between them (concept: 2–4 questions;
spec: 3–5, `skills/armature-spec/SKILL.md`). Grilling adds three mechanics worth folding in
(`skills/productivity/grilling/SKILL.md`):

- **The frontier.** Only ask questions whose prerequisites are settled; recompute after each
  round. Armature's phase scripts approximate this coarsely (phases order the topics); the
  frontier rule makes it explicit *within* a round and stops compound questions that assume
  unheard answers.
- **A recommended answer per question** (the `➡️` line). Lets the user accept in a word;
  matches armature-spec's existing "lead with the recommended option" instinct but makes it a
  format contract.
- **Facts are the agent's job, never the user's** — dispatch a subagent for anything lookupable
  (a datasheet number → librarian) and keep asking the rest of the frontier while it runs.
  Armature's skills read files first but don't state the during-interview version of this rule.

Adapt, don't absorb: grilling is content-free; Armature's value is the domain-scripted question
sets. Fold the three mechanics into the interview sections of concept/spec/plan.

### 2. domain-modeling's CONTEXT.md + ADRs vs armature-plan's CLAUDE.md glossary (row 2)

Same goal, different lifecycle. Armature writes the glossary **once**, at plan stage, into
CLAUDE.md ("Once set, they are law", `skills/armature-plan/SKILL.md`); decisions go to
`docs/decisions.md` as one-liners (`skills/init/SKILL.md`). domain-modeling's deltas:

- **Continuous inline maintenance** — challenge a term the moment it conflicts, any stage
  ("Your glossary defines X, but you seem to mean Y"). Robotics synonyms drift hard
  (arm/link/boom, base/chassis/frame, {W} vs {0}); today nothing polices the glossary after
  plan writes it.
- **`_Avoid_:` anti-synonym lines** (`CONTEXT-FORMAT.md`) — pick the canonical term, ban the
  rest. Trivial to add to the CLAUDE.md glossary template.
- **The three-gate ADR test** (hard to reverse ∧ surprising without context ∧ real trade-off)
  with a 1–3 sentence minimum ADR (`ADR-FORMAT.md`). Armature's one-line log is right for
  volume but flattens the *why* on load-bearing choices (e.g. "belt drive over harmonic —
  why?"). Add a tier: entries passing the three gates get a short ADR paragraph (in
  decisions.md or a `docs/adr/`), everything else stays one line.

Keep CLAUDE.md as the single home — it auto-loads every session, which is the entire point of
Armature's design; a separate CONTEXT.md would reintroduce a pointer hop.

### 3. diagnosing-bugs for hardware/firmware (row 3)

The core transfer is the gate: **no red-capable loop, no hypothesis** — which is precisely the
discipline bench debugging lacks ("it's probably the ESC" is the anchoring failure Phase 3's
3–5 ranked falsifiable hypotheses prevent). `scripts/hitl-loop.template.sh` is the key asset:
most hardware loops need a human (flash, press, probe, read the scope), and the template turns
that into a structured, capturable loop — same primitive the wizard uses. A robotics adaptation
needs a hardware loop ladder to replace items 1–9 (serial-log capture harness, bench jig
script, re-run `analysis/model` against measurement, A/B swap of a suspected part) and maps
"tagged debug logs" to tagged serial prints. Also fits armature-math directly:
"measurement disagrees with model" is this loop with the model as the oracle. Caveat from the
field: its own docs page (`docs/engineering/diagnosing-bugs.md`) reports over-firing on light
questions (their issue #578) — absorb with a high trigger threshold or user-invoked.

### 4. wizard for bring-up walkthroughs (row 4)

`template.sh`'s library (stage N-of-M progress, `step`/`capture`/`confirm`, idempotent writes)
is a bring-up procedure runner wearing web clothes. Adaptation: stages = wiring/first-power-on/
first-motion steps; `confirm` gates the irreversible (first battery connect, first torque
command); `capture` records measured values (voltage at TP3, no-load current) and writes them
into a `docs/testing/` report instead of `.env`/GitHub secrets. Armature-plan's phases 5–6
already name per-test procedure files — the wizard makes them executable. Caveat: bash-only;
Armature's SolidWorks users are on Windows (Git Bash works; a PowerShell variant may be worth
it). Overlaps deliberately with the HITL template from row 3 — one shared "human-loop script"
primitive could serve both.

### 5. research/prototype vs inventor/librarian (rows 5–6)

No collision. research = generic cited note; inventor and librarian are the specialized forms
with *stronger* rules (librarian: "never lets an unverified number into the record"). The one
transferable convention — findings as a committed md on a `research/<slug>` branch — this repo
already uses (`docs/research/writing-standard.md`). prototype's physical half is already in
armature-plan phase 3 (one prototype per top risk, kill criterion); its LOGIC branch (a
double-clickable HTML that drives a state machine through hard cases) covers discrete behavior
— mode logic, e-stop transitions, gait sequencing — which no Armature skill owns. Park it until
a firmware/behavior stage exists.

### 6. The tracker ecosystem (rows 7–10, 18)

to-spec/to-tickets/triage all assume `/setup-matt-pocock-skills` has configured an issue
tracker + label vocabulary. Armature's equivalent infrastructure decision is files-in-repo with
CLAUDE.md as the stamped config — a deliberate solo-builder fit, and plan tasks already carry
the ticket essentials (Executor/Depends on/Done when). Absorb only **AGENT-BRIEF.md**'s
durability rules (behavioral contracts, no file paths or line numbers, testable acceptance
criteria, explicit out-of-scope) into agent dispatch prompts and plan task wording; skip the
rest of the machine.

### 7. Handoff / session continuity (rows 17, 20–21)

Armature's continuity is artifact-based and stronger than a conversation summary: Stage line,
Latest artifacts, everything on disk, every write committed. Two real gaps: (a) a mid-interview
crash loses the interview — adopt a checkpoint convention (each stage skill may write its
output doc early as `Draft — open questions: …` and resume from it); (b) no guidance for long
math/CAD sessions approaching the context limit — PHASE-BOUNDARIES.md's ordered five-option
tree (continue → clear → handoff → subagent → compact, judged at boundaries only) is worth a
short reference or a paragraph in armature-math's milestone section, which already creates
natural boundaries (branch merges).

### 8. docs/ and .agents/ worth mining (rows 25–27)

- `.agents/writing-docs.md`: the docs-page frame — lead with the **defining constraint**, a
  "your situation → where to go" routing table, Common questions **sourced from observed
  evidence** (issues, community), "It's working if" signals. Armature's cheapest win is one
  routing table in the README.
- `.agents/invocation.md`: phrase operative cross-skill hand-offs as explicit Skill-tool calls;
  keep `/name` prose only for human-facing routing. Directly applicable to every Armature
  "hand off to X" line.
- `writing-for-agents` + `SKILL-MECHANICS.md`: adopt as the house style for editing Armature's
  own skills (no-op hunting, completion-criterion sharpening, leading words, the two loads).
  The repo dogfoods it — its own `CONTEXT.md` and `.agents/adr/` are live examples.

## Suggested absorption order

1. **grilling mechanics** into concept/spec/plan (highest-traffic surface, pure upgrade)
2. **domain-modeling**: `_Avoid_` lines + inline glossary challenge + three-gate ADR tier
3. **AGENT-BRIEF rules** into red-team/inventor/librarian dispatches and plan tasks (cheap)
4. **invocation.md convention** across hand-off sections (mechanical)
5. **diagnosing-bugs adaptation** + shared human-loop script primitive (new debug capability)
6. **wizard pattern** for bring-up/test runners (builds on 5's primitive)
7. **handoff checkpointing + phase-boundary reference** (continuity hardening)
8. **to-questionnaire adaptation** for machinist/vendor queries
9. **writing-for-agents house style + README routing table** (maintenance/onboarding)
10. Later: **prototype LOGIC** when a behavior/firmware stage exists; **teach** learning records
