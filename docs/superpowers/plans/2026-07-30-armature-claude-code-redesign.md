# Armature Claude Code Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the Armature robotics skill suite from claude.ai-projects format (paste-prompt handoffs) into a Claude Code plugin: 7 skills (6 stages + init), 3 agents, standard project scaffold, per spec `docs/superpowers/specs/2026-07-30-armature-claude-code-redesign-design.md`.

**Architecture:** Skills stay interactive in the main conversation; red-team/inventor/librarian become agents dispatched via the Agent tool; project state lives in files at standard paths plus an always-loaded project `CLAUDE.md`. One deviation from spec §2: `commands/` is legacy in current Claude Code — `/armature:init` is implemented as a user-invocable **skill** (`disable-model-invocation: true`) instead. Behavior is identical.

**Tech Stack:** Markdown skill/agent authoring, git, Bash (git bash on Windows). No code except verification greps.

## Global Constraints

- Plugin name: `armature` (plugin.json). Skills invoke as `armature:<name>`; init as `/armature:init`.
- Skill dirs and frontmatter names: `armature-concept`, `armature-spec`, `armature-plan`, `armature-math`, `armature-cad`, `armature-teacher`, `init`. Agent frontmatter names: `armature-red-team`, `armature-inventor`, `armature-librarian`.
- **Banned strings** in all files under `skills/` and `agents/` when done: `robotics-`, `new chat`, `fresh chat`, `Attach:`, `Paste:`. These mark leftover claude.ai machinery.
- Project paths (spec §3) — use verbatim everywhere: `docs/00-concept/concept-brief.md`, `docs/01-spec/spec.md`, `docs/01-spec/bom.md`, `docs/01-spec/budgets.md`, `docs/01-spec/traceability.md`, `docs/02-plan/plan.md`, `docs/testing/`, `docs/reviews/`, `docs/research/`, `docs/datasheets/index.md`, `docs/decisions.md`, `analysis/derivation/`, `analysis/model/`, `cad/parts/`, `cad/assemblies/`, `cad/ots-parts/index.md`.
- Review findings filename: `docs/reviews/YYYY-MM-DD-<artifact>-review.md`.
- Conventions preserved verbatim: SI internally; RC-xxx = concept-level outcome, REQ-xxx = verifiable requirement with method; severity ladder BLOCKER/MAJOR/MINOR/QUESTION.
- Skill `description:` frontmatter keeps the current trigger-rich style (a paragraph of "use whenever..." phrases), only with names/mechanisms updated.
- Every task ends in a commit; commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Working dir: `c:\Users\rioha\Documents\armature`. Use the Bash tool (POSIX) for git/sed/grep.

---

### Task 1: Baseline commit

The working tree holds an uncommitted snapshot (old `armature-*` skill dirs deleted, new `robotics-*` dirs untracked, modified plugin.json/README, stray `MANIFEST.md5`). Freeze it so every later task diffs cleanly.

**Files:**
- Delete: `MANIFEST.md5`
- Commit: everything else as-is

**Interfaces:**
- Produces: a clean git baseline; `skills/robotics-*` (8 dirs) tracked.

- [ ] **Step 1: Delete the checksum file**

```bash
rm MANIFEST.md5
```

- [ ] **Step 2: Stage and commit the snapshot**

```bash
git add -A
git commit -m "Snapshot: robotics-* skill set imported from claude.ai install

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 3: Verify clean tree**

Run: `git status --short` — Expected: empty output.

---

### Task 2: Rename skills and do the mechanical name sweep

Rename the six stage-skill dirs and replace every old skill name with its new name across all eight skill dirs (the two future-agent dirs get the sweep too, since their text will be reused in Tasks 3–4).

**Files:**
- Rename: `skills/robotics-concept-design` → `skills/armature-concept`; `robotics-spec-design` → `armature-spec`; `robotics-writing-plans` → `armature-plan`; `robotics-mathematician` → `armature-math`; `robotics-cad-parts` → `armature-cad`; `robotics-teacher` → `armature-teacher`
- Modify: every `.md` under `skills/` (name replacements only)

**Interfaces:**
- Produces: the six `armature-*` skill dirs with frontmatter `name:` matching dir names; all cross-references using new names (`armature-red-team`, `armature-inventor` referenced as agents).

- [ ] **Step 1: git mv the six directories**

```bash
git mv skills/robotics-concept-design skills/armature-concept
git mv skills/robotics-spec-design    skills/armature-spec
git mv skills/robotics-writing-plans  skills/armature-plan
git mv skills/robotics-mathematician  skills/armature-math
git mv skills/robotics-cad-parts      skills/armature-cad
git mv skills/robotics-teacher        skills/armature-teacher
```

- [ ] **Step 2: Global name replace across skills/**

```bash
grep -rl "robotics-" skills --include="*.md" | xargs sed -i \
  -e 's/robotics-concept-design/armature-concept/g' \
  -e 's/robotics-spec-design/armature-spec/g' \
  -e 's/robotics-writing-plans/armature-plan/g' \
  -e 's/robotics-mathematician/armature-math/g' \
  -e 's/robotics-cad-parts/armature-cad/g' \
  -e 's/robotics-teacher/armature-teacher/g' \
  -e 's/robotics-red-team/armature-red-team/g' \
  -e 's/robotics-inventor/armature-inventor/g'
```

- [ ] **Step 3: Verify sweep is total**

Run: `grep -rn "robotics-" skills` — Expected: no matches. Also confirm each renamed skill's frontmatter `name:` now equals its directory name (the sed handles it since frontmatter used the old full names).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Rename skills to armature-* scheme

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Convert red-team to an agent

**Files:**
- Create: `agents/red-team.md` (from `skills/robotics-red-team/SKILL.md` content)
- Create: `agents/references/review-checklist.md` (moved)
- Delete: `skills/robotics-red-team/`

**Interfaces:**
- Consumes: renamed cross-references from Task 2.
- Produces: agent `armature-red-team`, dispatched by stage skills via the Agent tool with a prompt naming the artifact file paths to review. Writes findings to `docs/reviews/YYYY-MM-DD-<artifact>-review.md`.

- [ ] **Step 1: Move the checklist**

```bash
mkdir -p agents/references
git mv skills/robotics-red-team/references/review-checklist.md agents/references/review-checklist.md
```

- [ ] **Step 2: Create agents/red-team.md**

Start from the full body of `skills/robotics-red-team/SKILL.md` and apply these edits:

1. Replace the frontmatter with:

```yaml
---
name: armature-red-team
description: Adversarial reviewer for robotics artifacts (specs, derivations, plans, BOMs, part definitions). Dispatch with the file paths to review whenever an artifact is finished-or-drafted and needs stress-testing — and always before CAD hours or purchases. It reviews with fresh context by construction; never review in the main conversation.
tools: Read, Grep, Glob, Bash, Write
---
```

2. In the intro, replace the sentence about fresh adversarial eyes coming from a new chat with: "You run in a fresh context with no memory of the conversation that produced the artifact — that isolation is the point. You may write exactly one file: your findings report. Never edit the artifact under review."
3. Replace the checklist pointer with: "Read `${CLAUDE_PLUGIN_ROOT}/agents/references/review-checklist.md` before your first pass."
4. Rewrite "## What you need in front of you": artifacts are files in the repo — read them from the paths given in your dispatch prompt, plus `CLAUDE.md` (glossary, standing rules), `docs/01-spec/budgets.md`, `docs/01-spec/traceability.md`, and `docs/datasheets/index.md` when they exist. If an artifact leans on something absent from the repo (a datasheet, a spec), that is a QUESTION finding — do not ask for attachments.
5. In "## The review", after move 2 ("Do the check, don't gesture at it"), add: "You have Bash: re-run `analysis/model/run_all.py` rather than trusting that it passes, and recompute back-of-envelope checks with the artifact's own numbers."
6. Add three audit families to the list at the end of "## The review": "budget-margin erosion (`docs/01-spec/budgets.md`: current estimates vs. budgets, and whether recent changes were debited at all), traceability holes (`docs/01-spec/traceability.md`: Must REQs with no analysis or test row), and safety-checklist coverage (the spec's mechanical-safety section against the actual design)."
7. In "## Findings report", set the output path: "Write the review to `docs/reviews/YYYY-MM-DD-<artifact>-review.md`."
8. Delete "## Hand-offs" → "### The handoff prompt" entirely. Replace with a short "## Routing" section: each finding's **Route** line names the owner (`armature-math`, `armature-spec`, `armature-plan`, `armature-inventor` agent, or a direct user change); end your run by reporting the verdict, the findings file path, and the per-severity counts back to the dispatching conversation — the main session routes the fixes.
9. Keep: severity ladder, "## Discipline", scope boundaries (trim the "fresh adversarial eyes / new chat" justification sentence, now covered by the intro).

- [ ] **Step 3: Remove the old skill dir**

```bash
git rm -r skills/robotics-red-team
```

- [ ] **Step 4: Verify**

Run: `grep -nE "new chat|fresh chat|Attach:|Paste:|robotics-" agents/red-team.md` — Expected: no matches. Confirm `agents/references/review-checklist.md` exists.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Convert red-team skill to armature-red-team agent

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Convert inventor to an agent

**Files:**
- Create: `agents/inventor.md` (from `skills/robotics-inventor/SKILL.md` content)
- Delete: `skills/robotics-inventor/`

**Interfaces:**
- Produces: agent `armature-inventor`. Dispatchable in parallel, one per idea family; writes briefs to `docs/research/`.

- [ ] **Step 1: Create agents/inventor.md**

Start from the full body of `skills/robotics-inventor/SKILL.md` and apply:

1. Frontmatter:

```yaml
---
name: armature-inventor
description: Frontier-robotics researcher — papers, novel mechanisms, unusual actuators/materials, emerging products. Dispatch when a design feels stuck or conventional, or during a trade study with unusually hard requirements. Dispatch several in parallel, one per idea family (mechanism, actuation, material, sensing, manufacturing method), each with the design tension and the constraint set. Writes an innovation brief to docs/research/.
tools: WebSearch, WebFetch, Read, Write, Glob, Grep
---
```

2. In "Ground rules" → "Anchor to the project": read `docs/01-spec/spec.md`, `docs/01-spec/bom.md`, and `CLAUDE.md` from the repo (they may not all exist; use what does). The dispatch prompt carries the design tension and any constraint numbers not yet in files.
3. In "Workflow" step 1: the dispatch prompt normally supplies the framed design tension; restate it, don't re-derive it.
4. "Innovation brief format": write to `docs/research/YYYY-MM-DD-<idea-family>-brief.md`. Keep the per-idea format block verbatim.
5. In "Don't fake the inputs": you cannot converse with the user mid-run — when a feasibility check hinges on a number you don't have and can't verify from the repo or a datasheet you can fetch, mark that candidate's check "unverified — needs <number>" rather than inventing it.
6. Replace "## Hand-offs" with one line: "End by reporting the brief's path and a one-line verdict per candidate; the main conversation runs the filter-hard step and the boring-baseline comparison with the user."

- [ ] **Step 2: Remove the old skill dir**

```bash
git rm -r skills/robotics-inventor
```

- [ ] **Step 3: Verify**

Run: `grep -nE "new chat|fresh chat|Attach:|Paste:|robotics-" agents/inventor.md` — Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Convert inventor skill to armature-inventor agent

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Create the librarian agent

**Files:**
- Create: `agents/librarian.md` (new content, below)

**Interfaces:**
- Produces: agent `armature-librarian`. Dispatched with a part number (or part description) and what's needed: datasheet, key numbers, and/or OTS CAD model. Caches into `docs/datasheets/` and `cad/ots-parts/`.

- [ ] **Step 1: Write agents/librarian.md with exactly this content**

```markdown
---
name: armature-librarian
description: Datasheet and OTS-model hunter for robotics parts. Dispatch with a part number (or a part description plus the specs that matter) whenever a design decision needs a datasheet number that isn't already in docs/datasheets/index.md, or a vendor CAD model is needed in cad/ots-parts/. Finds the document, verifies the part number, caches it with provenance. Never lets an unverified number into the record.
tools: WebSearch, WebFetch, Read, Write, Glob, Grep
---

# Armature Librarian

You keep the project's part record: every datasheet number anyone cites must
trace to a row you wrote. Your enemy is the plausible guess — a remembered
stall torque or an assumed bolt circle that hardens into a requirement and
fails at integration. Vendors reuse model names across revisions; the wrong
datasheet is more dangerous than none.

## Check the cache first

Read `docs/datasheets/index.md` (and `cad/ots-parts/index.md` for models).
If the part is already recorded at the needed revision, report the existing
row and stop — no duplicate hunting.

## The hunt

1. Prefer the manufacturer's own site; distributor pages (Digi-Key, Mouser,
   McMaster-Carr) are acceptable sources for both datasheets and CAD models.
2. Match the **exact** part number, including suffix/revision. If the user's
   request is a description ("a 6805 bearing", "an AK60-6"), find the
   candidate and treat the exact P/N as the thing to confirm.
3. Extract the key numbers the dispatch asked for (and the obvious design
   drivers: stall/continuous torque, rated current/voltage, mass, principal
   dimensions, material limits — whatever the part type makes relevant).

## Confirm, then cache

You cannot silently promote a number to trusted. End your run by reporting:
the exact P/N, the source URL, the document revision/date if stated, and the
extracted numbers — flagged **pending user confirmation** unless the dispatch
prompt already named the exact P/N and source to fetch. Once confirmed (or
pre-confirmed), cache:

- Save the PDF to `docs/datasheets/<PN>.pdf` (or `.html` snapshot if no PDF).
- Append one row to the table in `docs/datasheets/index.md`:

| P/N | Manufacturer | Key numbers | Source URL | Retrieved | File |

- For CAD models: save STEP (preferred) or vendor-native to
  `cad/ots-parts/<PN>.step` and append to `cad/ots-parts/index.md`:

| File | P/N | Datasheet row | Source URL | Retrieved |

A model with no datasheet row gets one hunted in the same run — geometry
without specs is half a part.

## When the number can't be found

Say so plainly and stop. Report what you searched and the closest misses.
A design-critical spec that can't be sourced is an open question for the
main conversation — never fill the gap with a typical value.
```

- [ ] **Step 2: Verify**

Run: `grep -nE "new chat|Attach:|robotics-" agents/librarian.md` — Expected: no matches.

- [ ] **Step 3: Commit**

```bash
git add agents/librarian.md
git commit -m "Add armature-librarian agent for datasheet/OTS-model collection

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Rewrite armature-concept

**Files:**
- Modify: `skills/armature-concept/SKILL.md`

**Interfaces:**
- Consumes: nothing upstream.
- Produces: `docs/00-concept/concept-brief.md`; updates `CLAUDE.md` Stage line; may invoke `armature-spec` in-session.

- [ ] **Step 1: Edit the body**

1. In "## The concept brief": change the write target to "write the brief to `docs/00-concept/concept-brief.md` using `references/concept-brief-template.md`".
2. Replace the whole "## Hand-off" section (including "### The handoff prompt" and its fenced block and bullet list) with:

```markdown
## Hand-off

When the brief is written: update the project `CLAUDE.md` — set the Stage
line to `spec` and point Latest artifacts at the brief — and add a line to
`docs/decisions.md` naming the concept as settled. Then offer to continue
straight into **armature-spec** in this same session; the interview is with
the user, not a fresh reader, so nothing is gained by switching sessions.
(Fresh eyes are for review — that's the armature-red-team agent's job, later.)

If, partway through the interview, it becomes clear the idea is basically
sound and the person already knows their audience and differentiation cold,
say so and offer to skip straight to armature-spec instead of writing a
brief neither of you needs.
```

(The "skip straight to spec" paragraph replaces the equivalent one currently sitting above the handoff-prompt block — don't duplicate it.)
3. In the frontmatter description, confirm the Task-2 sweep left it coherent (it should now reference `armature-spec` / `armature-teacher`); tighten wording only if a sentence broke.

- [ ] **Step 2: Verify**

Run: `grep -nE "new chat|fresh chat|Attach:|Paste:" skills/armature-concept/SKILL.md` — Expected: no matches.

- [ ] **Step 3: Commit**

```bash
git add skills/armature-concept
git commit -m "Rewire armature-concept for local file handoffs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Rewrite armature-spec + new templates

**Files:**
- Modify: `skills/armature-spec/SKILL.md`
- Modify: `skills/armature-spec/references/spec-template.md` (append safety section)
- Create: `skills/armature-spec/references/budgets-template.md`
- Create: `skills/armature-spec/references/traceability-template.md`

**Interfaces:**
- Consumes: `docs/00-concept/concept-brief.md`; agents `armature-inventor`, `armature-librarian`, `armature-red-team`.
- Produces: `docs/01-spec/spec.md`, `bom.md`, `budgets.md`, `traceability.md`. Budgets table columns: `Line item | Budget | Current estimate | Margin | Source (guess/datasheet/model/measured)`. Traceability columns: `REQ | Design element | Analysis | Test | Status (open/analyzed/tested/waived)`.

- [ ] **Step 1: Edit SKILL.md — inputs and dispatches**

1. "## Inputs": replace the attach/paste language — read `docs/00-concept/concept-brief.md` and `CLAUDE.md` if they exist; the rest of the paragraph's logic (settled RC → REQ translation; suggest armature-concept if genuinely early-stage) stays.
2. Phase 2, the inventor sentence: replace with "If the design space feels stale or the requirements are unusually hard, dispatch the **armature-inventor** agent — several in parallel, one per idea family, each prompt carrying the one-sentence design tension and the constraint numbers. Run the filter and the boring-baseline comparison here with the user when the briefs come back."
3. Phase 2, append this new subsection:

```markdown
#### Parallel exploration (optional, for 2–3 genuine finalists)

When the trade study has two or three finalists that each deserve real
feasibility work — not one favorite and strawmen — offer to explore them in
parallel: one git worktree per candidate, a subagent in each developing a
feasibility sketch (rough sizing arithmetic, dominant risks, cost order of
magnitude) written to `docs/01-spec/candidates/<name>.md` in its worktree.
Compare the sketches in the trade matrix, merge the winner's sketch, and
record the losers as rejected alternatives in the spec. Worktrees only when
the work is actually parallel; otherwise it's ceremony.
```

4. Phase 3: output paths — spec to `docs/01-spec/spec.md`. Add to the rules list: "Seed `docs/01-spec/budgets.md` from `references/budgets-template.md` — a line per major mass/power/cost item with budget and margin; downstream skills debit it as estimates harden. Seed `docs/01-spec/traceability.md` from `references/traceability-template.md` with one row per REQ (design element/analysis/test columns open). Fill the spec template's mechanical-safety section — scaled to consequence, per the capability assessment."
5. Phase 4: replace the ask-first-hunt-second bullet's self-search flow with: "Request datasheets the user already has. For anything missing, dispatch the **armature-librarian** agent with the exact P/N (or the description plus the specs that matter); it reports P/N + source for your confirmation with the user, then caches the PDF and key numbers into `docs/datasheets/index.md`. Cite index rows, never memory." Keep the when-a-number-can't-be-sourced bullet. BOM to `docs/01-spec/bom.md`.
6. "### Hand-off": keep the three routes but as plain prose (files are already on disk at known paths); replace the red-team "new conversation" paragraph with "dispatch the **armature-red-team** agent with the spec, BOM, budgets, and traceability paths — it runs with fresh context by construction". Delete "### The handoff prompt" and everything under it. Close with: update `CLAUDE.md` (Stage → `plan`, Latest artifacts), log the architecture decision in `docs/decisions.md`.

- [ ] **Step 2: Append to references/spec-template.md**

```markdown
## Mechanical safety

Scale to consequence — a desk toy is not a cobot. Answer each; "n/a" needs
one honest clause of why.

- **Pinch/crush points:** where, and what keeps fingers out during operation
  and maintenance.
- **Stored energy on power loss:** springs, gravity loads, flywheels — what
  moves when power drops, and what arrests it.
- **Tip-over stability:** worst-case CG excursion vs. support polygon,
  including payload and acceleration.
- **Payload drop path:** if the gripper/holder fails, what does the payload
  hit.
- **Sharp edges / hot surfaces** near any human touchpoint.
```

- [ ] **Step 3: Create references/budgets-template.md**

```markdown
# Budgets — <project>

Living document. Debit at every phase gate: math and CAD update estimates
as they harden; any change to a mass, power draw, or cost updates its row.
Source column values: guess → datasheet → model → measured (in increasing
trust).

## Mass

| Line item | Budget (g) | Current estimate (g) | Margin | Source |
| --- | --- | --- | --- | --- |
| System total | | | | |

## Power

| Line item | Budget (W) | Current estimate (W) | Margin | Source |
| --- | --- | --- | --- | --- |
| System peak | | | | |
| System continuous | | | | |

## Cost

| Line item | Budget | Current estimate | Margin | Source |
| --- | --- | --- | --- | --- |
| Total | | | | |
```

- [ ] **Step 4: Create references/traceability-template.md**

```markdown
# Requirements traceability — <project>

One row per REQ. Spec creates rows; plan fills Test; math/testing update
Status. Status: open → analyzed → tested (or waived, with a reason in
docs/decisions.md). A Must REQ still `open` at integration is a wish.

| REQ | Requirement (short) | Design element | Analysis | Test | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | | | | | open |
```

- [ ] **Step 5: Verify**

Run: `grep -nE "new chat|fresh chat|Attach:|Paste:" skills/armature-spec -r` — Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add skills/armature-spec
git commit -m "Rewire armature-spec: agent dispatches, worktree trade study, budgets/traceability/safety

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Rewrite armature-plan + test-report template

**Files:**
- Modify: `skills/armature-plan/SKILL.md`
- Create: `skills/armature-plan/references/test-report-template.md`

**Interfaces:**
- Consumes: `docs/01-spec/*`.
- Produces: `docs/02-plan/plan.md`; writes the Glossary section of the project `CLAUDE.md`; task format gains `Executor:` field naming `armature-math` / `armature-cad` / `armature-inventor` (agent) / `user`.

- [ ] **Step 1: Edit SKILL.md**

1. "## Inputs": read `docs/01-spec/spec.md` + `bom.md` (and `CLAUDE.md`) from disk; drop uploaded/pasted language. Keep the no-spec fallback logic.
2. Retitle "### 1. Project glossary & conventions" content: the glossary is **written into the project `CLAUDE.md`'s Glossary section** — frames, symbol table, naming conventions, definitions of done — because Claude Code loads `CLAUDE.md` every session; that's what keeps conversation #47 grounded. The plan file itself keeps a one-line pointer to it. Content requirements (frames/symbols/naming/DoD) stay verbatim.
3. Plan output path: `docs/02-plan/plan.md`.
4. "### 3. Task format": add `Executor: armature-math | armature-cad | armature-inventor (agent) | user` as a line in the task block example, and one sentence: name the executor so a fresh session knows which skill or agent picks the task up.
5. Phase 3 (prototypes) and Phase 6 (integration & verification): each test task names its procedure/report file under `docs/testing/` per `references/test-report-template.md`, and Phase 6 additionally fills the Test column of `docs/01-spec/traceability.md` — a Must REQ with no test row is the gap this exists to catch.
6. "## Hand-offs": keep the route list (names only — they're skills/agents now), delete "### The handoff prompt" and below. Close with: update `CLAUDE.md` (Stage → `analysis`, Latest artifacts, and the now-written Glossary), log planning decisions in `docs/decisions.md`.

- [ ] **Step 2: Create references/test-report-template.md**

```markdown
# Test <ID>: <name>

**Purpose:** which REQ-xxx (or prototype kill criterion) this settles.
**Date / operator / rev of thing tested:**

## Setup
Hardware, fixtures, instruments (with resolution), environment.

## Method
Numbered steps. Enough that someone else could rerun it.

## Data
The actual numbers/table/log path. Raw, not just summarized.

## Result
Pass/fail against the criterion, stated with the number.

## Feeds
- traceability row updated: <REQ-xxx → status>
- params.py value updated: <symbol, old → measured> (or n/a)
- budgets.md row updated: <line item> (or n/a)
```

- [ ] **Step 3: Verify**

Run: `grep -nE "new chat|fresh chat|Attach:|Paste:" skills/armature-plan -r` — Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add skills/armature-plan
git commit -m "Rewire armature-plan: glossary to CLAUDE.md, executor field, test-report template

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Rewrite armature-math

**Files:**
- Modify: `skills/armature-math/SKILL.md`

**Interfaces:**
- Consumes: `docs/01-spec/*`, `CLAUDE.md` glossary, `armature-red-team` agent, `docs/testing/` reports (calibration).
- Produces: `analysis/derivation/00_setup.md`…`03_results.md`, `analysis/model/{params,kinematics,dynamics,verification,run_all}.py`; milestone branches `armature/m<N>-<name>`; updates `budgets.md`.

- [ ] **Step 1: Edit SKILL.md**

1. "## Why this is split into milestones": drop the token-cost rationale (claude.ai-specific); keep the review-cost rationale and add the branch gate: each milestone runs on its own git branch, merged only when its self-tests pass and its red-team findings are resolved — the merge is the phase gate.
2. "## File layout": fixed paths — `analysis/derivation/` for the four `.md`, `analysis/model/` for the five `.py`. Template copy: "copy `model_template/` from this skill's `scripts/` directory into `analysis/model/` at Milestone 0."
3. "## Step 0": conventions come from `CLAUDE.md`'s Glossary (or `docs/01-spec/spec.md` Section 6) — reuse verbatim. Datasheet paragraph: replace ask-or-look-up flow with dispatching **armature-librarian** (confirm-then-cache; cite `docs/datasheets/index.md` rows). Add: "Start the milestone branch: `git checkout -b armature/m0-setup` (then `m1-kinematics`, `m2-dynamics`, `m3-verification`)."
4. Milestones 1–3 checkpoints: replace each "hand to robotics-red-team in a fresh chat via the handoff block" passage with "run the self-tests via Bash (`python analysis/model/run_all.py` — they must pass), then dispatch the **armature-red-team** agent with this milestone's `.md` + `.py` paths (earlier milestones as context). Resolve or explicitly accept every finding, log the resolution in the milestone's revision note, then merge the branch."
5. Milestone 3 / closing the loop: keep; "re-run `run_all.py`" is now literal (Bash). When masses, inertias, or torque results firm up, update the matching rows in `docs/01-spec/budgets.md` (Source column: model).
6. Delete "## Pausing between milestones" and "## Handing off" (both are transcript-era). Replace with:

```markdown
## Boundaries

Any milestone edge is a clean stopping point: files committed, tests green,
review resolved, branch merged. A fresh session resumes from the repo alone —
that's the point of the layout. When a Milestone 3 finding sends work
upstream (a requirement, part, or BOM number must change → armature-spec; a
mechanism gap → armature-inventor agent), say which number broke and what it
collides with, and update `docs/decisions.md` when the change is accepted.
```

7. Append a new section before "## Deliverables":

```markdown
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
```

8. "## Deliverables" item 3: red-team findings are the agent's files in `docs/reviews/`.

- [ ] **Step 2: Verify**

Run: `grep -nE "new chat|fresh chat|Attach:|Paste:" skills/armature-math -r` — Expected: no matches. Run: `ls skills/armature-math/scripts/model_template/` — Expected: the five `.py` files present.

- [ ] **Step 3: Commit**

```bash
git add skills/armature-math
git commit -m "Rewire armature-math: milestone branches, local self-tests, agent review, calibration

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Rewrite armature-cad + assembly reference

**Files:**
- Modify: `skills/armature-cad/SKILL.md`
- Create: `skills/armature-cad/references/assembly-definition.md`

**Interfaces:**
- Consumes: `CLAUDE.md` glossary, `docs/01-spec/*`, `analysis/*`, agents `armature-librarian`, `armature-red-team`.
- Produces: `cad/parts/<PART-ID>.md`, `cad/assemblies/<ASM-ID>.md`, OTS models in `cad/ots-parts/`; debits `budgets.md`.

- [ ] **Step 1: Edit SKILL.md**

1. "## Inputs": the three reads become repo paths — `CLAUDE.md` Glossary (the plan's §1 successor; the "no glossary" fallback stays but reads `analysis/derivation/00_setup.md` / spec Section 6), `docs/01-spec/spec.md` + `bom.md`, `analysis/derivation/03_results.md` + `analysis/model/params.py`.
2. The Gate section: interface gaps route to the **armature-librarian** agent (datasheet + OTS model, confirm-then-cache); missing loads still route to armature-math.
3. Part definitions write to `cad/parts/<PART-ID>.md`. In the "CAD build recipe" element: COTS geometry is referenced from `cad/ots-parts/` (fetched by librarian, indexed with its datasheet row) — never modeled from memory.
4. "## Close the loop": re-running the dynamics is literal — update `params.py` with realized mass properties and run `python analysis/model/run_all.py` via Bash; on divergence beyond tolerance, that's an armature-math re-derivation. Either way, update the part's mass rows in `docs/01-spec/budgets.md` (Source: model or measured).
5. "## Red-team before the CAD hours pile up": dispatch the **armature-red-team** agent with the batch's part-definition paths + `analysis/derivation/03_results.md` + `docs/01-spec/bom.md`; delete the fresh-chat justification.
6. Delete "## Hand-offs" → "### The handoff prompt" machinery; keep the route list as plain prose, and close with: work on a `armature/cad-<batch>` branch, merge when the batch's definitions are red-teamed and resolved; update `CLAUDE.md` Latest artifacts; log decisions.
7. Add a new section after "## The part definition":

```markdown
## The assembly definition

Parts that are each correct can still fail to become a machine. Once a
subassembly's parts are defined, write `cad/assemblies/<ASM-ID>.md` per
`references/assembly-definition.md`: the mate scheme, fastener table with
torques, the assembly *order* (with the tool-access check at each step),
jigs/fixtures needed, and the worst-case tolerance stack-up for each
critical fit. The stack-up is the assembly-level twin of the part
definition's inertia loop: per-part tolerances can all be met while the
assembly still doesn't go together.
```

- [ ] **Step 2: Create references/assembly-definition.md**

```markdown
# Assembly definition — structure and stack-up method

## Structure (one file per assembly, cad/assemblies/<ASM-ID>.md)

- **Scope & tree:** which PART-IDs and OTS items, and the sub-assembly
  hierarchy.
- **Mate scheme:** one row per mate — parts, mate type (planar/cylindrical/
  fastened...), the datum features carrying it. The assembly's position
  authority: which part's datums locate the rest.
- **Fasteners:** one row per fastener group — spec (M3×8 SHCS, A2-70),
  quantity, torque, thread engagement, locking method (nyloc/threadlocker/
  none and why).
- **Assembly order:** numbered steps. At each step: can the tool physically
  reach (name the tool and its swing)? Can the part be inserted with
  neighbors already placed? Any step needing three hands gets a jig.
- **Jigs & fixtures:** each with what it holds, to what accuracy, and
  whether it's printed/machined/bought.
- **Stack-ups:** per critical fit, the table below.

## Worst-case stack-up method

For each critical fit (a bearing bore pair's alignment, a shaft end-play,
a gear center distance):

1. Chain the dimensions from one side of the fit to the other through the
   parts that control it. Every link: nominal ± tolerance, from its part
   definition or datasheet.
2. Sum nominals; sum tolerances (worst case: straight sum — this scale of
   build rarely justifies RSS, and worst-case is the honest default).
3. Compare the resulting extreme fits against the functional requirement
   (min clearance, max misalignment a bearing tolerates per its datasheet).
4. If it doesn't close: tighten the *fewest* tolerances (each tightening is
   money), re-datum so fewer links are in the chain, or add an adjustment
   feature (shim, slot) — in that order of preference.

| # | Dimension (part, feature) | Nominal | Tol ± | Source |
| --- | --- | --- | --- | --- |
|  | **Result: extreme fit vs. requirement** | | | |
```

- [ ] **Step 3: Verify**

Run: `grep -nE "new chat|fresh chat|Attach:|Paste:" skills/armature-cad -r` — Expected: no matches. Confirm the three package references (`solidworks.md`, `fusion360.md`, `onshape.md`) still exist and are still referenced.

- [ ] **Step 4: Commit**

```bash
git add skills/armature-cad
git commit -m "Rewire armature-cad: assembly definitions, stack-ups, OTS parts, local loop-closing

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: Touch up armature-teacher

**Files:**
- Modify: `skills/armature-teacher/SKILL.md`

**Interfaces:**
- Consumes: project artifacts at standard paths.

- [ ] **Step 1: Edit SKILL.md**

1. In "The teaching sequence" step 1 ("Locate it in their world"): the project documents live at standard paths — `docs/01-spec/spec.md`, `docs/02-plan/plan.md`, `analysis/derivation/`, and the `CLAUDE.md` glossary for the project's notation; read before teaching, teach *their* Jacobian.
2. "## Boundaries": routes are `armature-math`, `armature-spec`, `armature-inventor` (agent) — Task 2's sweep already renamed them; confirm phrasing reads correctly.

- [ ] **Step 2: Verify + commit**

Run: `grep -nE "new chat|robotics-" skills/armature-teacher/SKILL.md` — Expected: no matches.

```bash
git add skills/armature-teacher
git commit -m "Point armature-teacher at standard project paths

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: Create the init skill

**Files:**
- Create: `skills/init/SKILL.md`

**Interfaces:**
- Consumes: `armature-concept` (invoked at the end).
- Produces: the standard project scaffold + `CLAUDE.md`; invoked by the user as `/armature:init`.

- [ ] **Step 1: Write skills/init/SKILL.md with exactly this content**

````markdown
---
name: init
description: Initialize a standardized Armature robotics project in the current folder — scaffold the docs/analysis/cad tree, git repo, and project CLAUDE.md, then start the concept interview.
disable-model-invocation: true
---

# Armature Init

Set up a robotics project the way the whole suite expects to find it, then
roll straight into the concept interview. Run in the project's root folder.

## 1. Guard

If `CLAUDE.md` already exists here with a `**Stage:**` line, this is already
an Armature project — say so, report its stage, and stop.

## 2. Setup interview (three questions, then build)

Ask, via the question tool if available:
1. Project name and a one-line description.
2. CAD package: SOLIDWORKS / Fusion 360 / Onshape / undecided.
3. Builder reality, briefly: solo or team; fabrication access (printer,
   machining, hand tools); rough experience level.

## 3. Scaffold

Create (git bash):

```bash
mkdir -p docs/00-concept docs/01-spec docs/02-plan docs/testing \
         docs/reviews docs/research docs/datasheets \
         analysis/derivation analysis/model \
         cad/parts cad/assemblies cad/ots-parts
```

Seed these files:

- `docs/decisions.md`: header `# Decision log` + one column-format line:
  `<!-- date · decision · why · supersedes -->`, plus its first entry — the
  project init itself.
- `docs/datasheets/index.md`: header + empty table
  `| P/N | Manufacturer | Key numbers | Source URL | Retrieved | File |`.
- `cad/ots-parts/index.md`: header + empty table
  `| File | P/N | Datasheet row | Source URL | Retrieved |`.
- `.gitignore`:

```
__pycache__/
.pytest_cache/
~$*
*.bak
```

- `CLAUDE.md` from the template below, with the setup answers filled in.

Then `git init` (if not already a repo) and commit everything as
`Initialize Armature project scaffold`.

## 4. CLAUDE.md template

```markdown
# <Project Name>

<one-line description>

**Stage:** concept  <!-- concept → spec → plan → analysis → cad → build -->
**Latest artifacts:** none yet

## Glossary

<!-- Frames, symbol table, part numbering, CAD file naming, and definitions
of done are written here by armature-plan. Once set, they are law. -->

- Units: SI internally, always. Imperial in parentheses only if the shop
  works in it.
- Requirement numbering: RC-xxx = concept-level outcome
  (docs/00-concept/); REQ-xxx = verifiable engineering requirement with a
  verification method (docs/01-spec/).

## Standing rules

- Every datasheet number cited anywhere must trace to a row in
  docs/datasheets/index.md (the armature-librarian agent maintains it).
- Red-team review (armature-red-team agent) before CAD hours or purchases.
- Any change to a mass, power draw, or cost updates
  docs/01-spec/budgets.md in the same session.
- Every design decision gets a line in docs/decisions.md.
- OTS CAD models live in cad/ots-parts/ with an index row linking
  model → P/N → datasheet.

## Builder profile

- CAD package: <answer>
- Fabrication: <answer>
- Team: <answer>
```

## 5. Hand off

Tell the user the scaffold is committed, then invoke the **armature-concept**
skill and begin the interview immediately — that's the natural next breath,
not a separate ceremony.
````

- [ ] **Step 2: Verify + commit**

Run: `grep -nE "robotics-" skills/init/SKILL.md` — Expected: no matches.

```bash
git add skills/init
git commit -m "Add /armature:init project scaffold skill

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: plugin.json, README, spec amendment

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `README.md` (full rewrite)
- Modify: `docs/superpowers/specs/2026-07-30-armature-claude-code-redesign-design.md` (§2 wording)

- [ ] **Step 1: Rewrite plugin.json**

```json
{
  "name": "armature",
  "version": "1.0.0",
  "description": "Robotics engineering suite for Claude Code: /armature:init scaffolds a standardized project, then six interactive stage skills (concept, spec, plan, math, CAD, teacher) and three agents (red-team, inventor, librarian) run the pipeline the way a real engineering team would — budgets, traceability, datasheet provenance, and adversarial review included.",
  "author": { "name": "Rio" },
  "keywords": ["robotics", "mechanical-engineering", "kinematics", "dynamics", "cad", "design-review", "systems-engineering"]
}
```

- [ ] **Step 2: Rewrite README.md**

Structure (write in the repo's plain-engineer voice; ~1 page):

1. **What it is** — one paragraph: robotics engineering pipeline as a Claude Code plugin; install once, `/armature:init` in a blank folder, work concept → spec → plan → analysis → CAD like a real team.
2. **The pipeline** — the current README's two tables, updated: stage skills `armature-concept/spec/plan/math/cad` with their outputs at the standard paths; cross-cutting `armature-teacher` skill + `armature-red-team`, `armature-inventor`, `armature-librarian` agents with one-line roles.
3. **The project layout** — the spec §3 tree, verbatim.
4. **How state works** — three sentences: files are the state; `CLAUDE.md` carries glossary + standing rules into every session; budgets/traceability/decisions are living documents every stage debits.
5. **Install** — as a plugin (marketplace or `--plugin-dir`), one line that loose-skill copying is no longer supported since agents/init are plugin components.
6. Delete everything about MANIFEST.md5, snapshot caveats, and Obsidian.

- [ ] **Step 3: Amend spec §2**

In the spec file, §2's `commands/init.md` line and the §2 mention of commands: change to note init ships as a user-invocable skill (`skills/init/`, `disable-model-invocation: true`) because `commands/` is legacy; invocation is still `/armature:init`. One sentence.

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json README.md docs/superpowers/specs/2026-07-30-armature-claude-code-redesign-design.md
git commit -m "Plugin manifest v1.0.0, README rewrite, spec amendment for init-as-skill

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 14: Verification sweep

**Files:** none created — checks only.

- [ ] **Step 1: Banned-string sweep**

```bash
grep -rnE "robotics-|new chat|fresh chat|Attach:|Paste:" skills agents README.md .claude-plugin
```

Expected: no matches. Any hit is a leftover — fix it in place and amend the offending file with a followup commit.

- [ ] **Step 2: Reference-path audit**

```bash
grep -rhoE "references/[A-Za-z0-9_./-]+\.md" skills agents | sort -u
```

For each path printed, confirm the file exists under the skill/agent dir that names it (`skills/<skill>/references/...` or `agents/references/...`). Expected: all resolve. Also: `ls skills/armature-math/scripts/model_template/` shows `params.py kinematics.py dynamics.py verification.py run_all.py`.

- [ ] **Step 3: Frontmatter audit**

```bash
head -5 skills/*/SKILL.md agents/*.md
```

Expected: every skill's `name:` equals its directory name; agents are `armature-red-team`, `armature-inventor`, `armature-librarian`; `skills/init/SKILL.md` has `disable-model-invocation: true`.

- [ ] **Step 4: Plugin validation (if available)**

Run: `claude plugin validate .` — Expected: valid. If the subcommand doesn't exist in the installed CLI version, note that and rely on Steps 1–3.

- [ ] **Step 5: Final commit (if fixes were made) and report**

Report: file counts (`7` SKILL.md, `3` agents), the full task list checked off, and the **manual smoke test** left for the user (it needs an interactive session):

1. `claude --plugin-dir c:\Users\rioha\Documents\armature` in a scratch folder.
2. `/armature:init` → answer the three questions → confirm the spec §3 tree, git repo, and `CLAUDE.md` exist and the concept interview starts.
3. Spot-check one agent dispatch (`ask the armature-librarian for a NEMA 17 datasheet`) → confirm a PDF + index row land in `docs/datasheets/`.

---

## Self-review notes

- Spec coverage: §2→Tasks 2–5,12,13 · §3→Task 12 · §4→Tasks 8,12 · §5→Tasks 6–11 · §6.1–6.8→Tasks 7 (budgets/trace/safety), 8 (test reports), 9 (calibration), 10 (assembly/stack-up/OTS), 12 (decisions.md, scaffold) · §7→Tasks 7 (worktrees), 9–10 (branches) · §8→Tasks 3–5 · §9→Tasks 1,2,13 · §10→Task 14 + manual smoke test.
- MCP server v2 is a spec non-goal — deliberately absent here.
- Names/paths cross-checked: agents referenced as `armature-red-team`/`armature-inventor`/`armature-librarian` in Tasks 6–10 match frontmatter in Tasks 3–5; all artifact paths match the Global Constraints list.
