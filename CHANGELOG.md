# Changelog

## Unreleased

Two changes: the plan moves off disk onto GitHub Issues, and subagents stop inheriting the main session's model. Both are recorded as ADRs — [0001](docs/adr/0001-plan-as-a-parallel-issue-species.md) on why the plan is its own issue species rather than a wayfinder map, [0002](docs/adr/0002-github-is-a-hard-prerequisite.md) on why the local tracker was deleted.

### The derivation gets a truth model

Every `armature-derive` milestone is checked against an independent MuJoCo model of the mechanism, built from the same parameter block. The reviews on the first real project found derivations whose arithmetic was right and whose model was wrong — a frozen degree of freedom, a textbook formula outside its assumptions — and the checkpoint's self-consistency checks could not see any of it, because the assumption sat on both sides. [#48](https://github.com/rioharper/armature/issues/48) tracks the effort.

- `scripts/env-probe.sh` checks **MuJoCo** in the core tier, beside SymPy, SciPy and NumPy, with the same `absent` / `error: <Type>` / version reading. Core rather than a tier because a machine that cannot import it cannot pass a derivation checkpoint at all. `pinocchio` joins the named checks as an optional second backend for chain dynamics — never core, since it has no Windows pip wheel.
- `references/environment-record.md` documents both; `init` and `armature-plan` name a missing MuJoCo as Phase 0 work that the analysis phase waits on, not a footnote.
- The model template's **Lagrangian is built by `sympy.physics.mechanics`** — frames off the DH table, points given velocities by the one- and two-point theorems, a `RigidBody` per link, `LagrangesMethod` for the equations. The angular velocity read out of Ṙ Rᵀ and the hand Euler-Lagrange loop are gone, so an ω sign or a dropped Coriolis term is impossible by construction rather than caught later. M, C, g and V are unchanged to 1e-12 on the shipped 2R arm, now pinned by a self-test; `dynamics/` no longer imports `kinematics.py`, sharing only the parameter block. The derive skill's Milestone 2 calls symmetry, skew-symmetry and energy conservation **self-consistency** checks, which is all they ever were.

### The plan lives on the issue tracker

- `armature-plan` no longer writes `docs/02-plan/plan.md`. A plan is a **plan index** issue (`plan:index`) carrying scope-against-hours, the machine split, Must satisfiability, CAD process, and risks-and-hooks; `plan:phase` children carry exit criteria; `plan:leaf` grandchildren are the work. Parent tasks are flattened — a dependency that named one is wired to its last leaf.
- **T-ids are permanent.** `T3.2a` is assigned once, rides as the issue title's prefix, and is never renumbered; an insertion is `T3.2c`. The plan stops being "a rendering, never a memory" — a tracker needs a stable name.
- **Leaves materialise lazily**: issues for the current and next phase only, later phases kept as a task list in their phase issue. A 200-session plan is about 40 live issues.
- **Rollups are derived, never stored.** Phase hours, session and closed counts, and estimate-versus-actual are computed on read; `Est:` stays in the leaf body, `Actual:` is the first line of the closing comment.
- **The interview checkpoints to `docs/02-plan/draft.md`** — gitignored, resumed from, deleted when the issues are cut, and explicitly not the plan. Nothing reaches the tracker until the interview closes.
- **Sixteen labels**, created by `init`: the five `wayfinder:*`, three `plan:*`, and eight `executor:*`. `executor:*` is cross-cutting — a wayfinder ticket wears one as readily as a leaf, which is what lets a runner batch by who does the work.
- **GitHub is now a hard prerequisite.** `init` gates on `gh` and `gh auth status`, offers `gh repo create --private`, creates the labels, and writes `docs/agents/issue-tracker.md`; `armature-plan` re-checks. `skills/armature-wayfind/references/issue-tracker-github.md` is the single source for tracker operations and gains a **Plan operations** section.

### Removed

- `skills/armature-wayfind/references/issue-tracker-local.md` — the non-GitHub tracker. See ADR 0002.

### Subagents are tiered by difficulty

- `agents/*.md` carry a `model:` pin: **librarian `sonnet`**, **inventor `sonnet`**, **red-team `inherit`**. Previously every subagent silently inherited the main session's model, so a fleet of librarians hunting part numbers ran on whatever was chosen for the hard thinking.
- `references/subagent-dispatch.md` gains an **Agent tier** section (the table, that a pin is a default rather than a guarantee, and the rule that overrides go upward and say why) and a **Splitting a red-team review** section.
- **Split reviews.** Above ~40k tokens of source or three substantial artifacts, a red-team run splits **by input partition** — not by checklist family, which cannot reduce context because families 1, 2, 3 and 7 each need the whole set. Passes run sequentially and unchained, each staging its findings; a final merge pass reads the staging files, dedupes, writes the one report, and deletes what it merged. Routing stays in the dispatching session.
- The two anonymous "dispatch a subagent" sites are addressed: `armature-pitch` names the **librarian**; `armature-spec`'s parallel-exploration worktrees stay generic subagents but now name a tier, since frontmatter cannot pin one.
- `CONTEXT.md` gains **Agent tier** (with `_Avoid_: model`, which in this repo means the SymPy, CAD, OTS or MuJoCo model), **Ticket**, **Plan index**, and **Draft**; **Leaf** is rewritten, **Staging file** generalised to any agent run's ledger, and **Machine split** and **Executor** re-pointed.
- `scripts/run-wayfinder-afk.sh` — pointed at `armature:armature-wayfind` (it invoked a skill that does not exist), repo and map discovered instead of hardcoded, HITL ticket types skipped, an `EXECUTOR=` filter added, and `--dangerously-skip-permissions` demoted to an explicit `YOLO=1` opt-in.

## 1.3.0 — 2026-09-11

Lands the feedback log from running every stage on a demo project: each change below is a shape that project had to invent by hand, or a failure it hit. Charted and decided on the map [Land the armature-demo feedback log (1.3.0)](https://github.com/rioharper/armature/issues/26); each decision's ticket holds its reasoning. Ruled out along the way, with reasons on the map: Onshape live checks by API, an HTML rendering of briefs and reports, an electronics scaffold, and a quotable specification, RFQ, and quote register for custom parts.

### New references, templates, and scripts

- `references/model-layout.md` — one layout standard for generated analysis and CAD modules. A module's decomposition mirrors its note's sections (a package from the start once the note passes about three), self-tests sit one file over in a `<module>_checks.py`, tables print from `report_*.py`, and every module carries a hard **250-code-line budget**, counted by a stdlib-only `layout.py` that both templates ship and enforced by the full `run_all.py` and `pytest`. The one exception is `LAYOUT_EXEMPT = "<reason>"`, and the red team challenges it.
- `references/subagent-dispatch.md` — subagents go out **two or three at a time**, each wave landing before the next, because a subagent spends the dispatching session's context and share of the session limit whether it succeeds or dies. Name the cost first, size a run to one part or one slice, prefer the agent that writes as it goes. Every fan-out paragraph in spec, derive, plan, cad, and wayfind points here.
- `scripts/env-probe.sh` and `references/environment-record.md` — the probe prints `KEY=VALUE` and exits 0 whatever it finds, reporting the python invocation that works and telling a module that is `absent` from one that is `error: <Type>`. A spec's own tools arrive as arguments (`ros2 gazebo cuda`), with a `command -v` fallback for names the script does not know. Results land in the project's **environment record**, `docs/environment.md`: one dated section per machine, replaced by a re-probe and never hand-edited.
- `armature-plan`'s `references/derivation-report-template.md` — the report for an analysis task `armature-derive` runs, beside the bench test template: the decision as a heading, a write-back table for every number it moves, the assumptions under strain with the direction and size the model gives each, and a row per item routed to the task.
- The spec template's **§8 Software & Compute Architecture** — compute units with their runtime host; links with medium, protocol, a rate/latency/loss budget citing its REQ, and a seam-level verification (`unit`/`sim`/`bench`); data artifacts with schemas; relocation; and a ROS 2 graph only when there is a graph. Always answered, scaled to consequence.

### Changed

- `init` — the scaffolded `CLAUDE.md` opens with a `## Purpose` section (why *this builder* is building it, which the one-line description does not carry), and the builder profile asks once for **related work**. A core probe seeds `docs/environment.md`, and gaps are reported at hand-off. The datasheet index is seeded with `Clauses read` and `Price` cells; standing rules gain the reserve debit rule, a cost estimate citing the `Price` it read, and a CANDIDATE row carrying no decision.
- `armature-pitch` — the envelope question reads init's related-work line instead of re-asking and presses on the relationship: conceptual sibling, shared code, or this one supersedes it. The concept brief's §5 records it.
- `armature-spec` — gains §8 (above): §7's Interfaces column narrows to mechanical and electrical, and old §8–§11 become §9–§12. Phase 1 gains question 7, **Compute & software**. §6 gains a platform mapping (apex and ground range, stride and step height, turning radius, touchdown speed, attitude envelope) and `F` for a free body, and `design-foundations.md` reads its examples for mobile, legged, and aerial machines. The budgets template carries a **reserve** as a line item nothing debits directly, so a negative margin is a failed REQ; cost gains a `list price` rung citing the index row's `Price`, and a `quote only` part has no rung above `guess`.
- `armature-plan` — the leaf task is one session and one commit under a numbered parent, cut at every third-party wait; `Est:` is sessions plus wall-clock from a starting table, closed leaves carry `Actual:`, and each phase gate re-cuts from same-kind actuals. A **Before writing** step runs the environment probe on every invocation, the **machine split** (starting from spec §8.1; a role nobody has probed becomes Phase 0 work), and a satisfiability pass over every Must. §3 carries the table of all eight executors plus `armature-bringup + user`; the glossary's convention family follows the topology, floating base included. The header is rendered from the Revision History table on every save.
- `armature-derive` — self-tests are discovered by shape: `test_*` callables, ordered by each module's `MILESTONE = (order, title)`, run by `python run_all.py`, by `pytest` through `test_derivation.py`, or one milestone at a time with `python run_all.py <milestone>`; a discovery that finds nothing fails. `model_template` demonstrates the model layout (9 checks). Step 0 writes the measured-quantity reading of every requirement sized against into `00_setup.md`. `derivation-standards.md` gains the book-data rule (book, edition, and table; a second independent source; design to the conservative fit) and gives each sentence one layer, note or docstring. Milestone 3 owns the **corner sweep** and dispatches two red teams split by question. A plan's analysis task lands as a decision report.
- `armature-cad` — the part template adopts the model layout: `check/` and `sweep/` become packages (`from check import mass_properties` unchanged; `python -m sweep`), every `demo()` becomes a checks module, and `python cad/parts/run_all.py` runs all 29 self-tests and the budget. The release transition runs the corner sweep before it dispatches the red team. A project emitting `params.toml` is read there, `params.py` only for provenance.
- `armature-librarian` — gains Bash and writes as it goes: a named-part run ledgers into `docs/datasheets/staging/<task>-<subject>.md`, deleted at merge; a survey run writes the permanent `docs/datasheets/<task>-<subject>-<slice>.md`. Index rows gain **Clauses read** and **Price** (`quote only` where the vendor publishes none), and the `File` cell names the source kind. A long-lead part gets the **stand-in** question, answered either way. The librarian and `armature-inventor` descriptions carry the dispatch cap.
- `armature-red-team`'s checklist — probes for a breached reserve, a Must whose own clauses contradict each other, a routed item with no row, a report number no module prints, book data without its second source, an assumption without direction and size, a stale price (Minor at six months unre-read, Major when a cost margin closes on an old price, Blocker on a purchase), a §8 link with no budget or verification, and a layout exemption. Its inputs name each requirement's reading and the survey records.
- `armature-test` — seam agreement starts from the spec's §8.2 links.
- SolidWorks MCP server — connects per project (below). `sw.py` imports COM inside `attach()`, so a non-Windows host starts the server and reads a per-tool message instead of failing at import; a failed connection now means `uv` is not on PATH. Tools are `mcp__solidworks__sw_*`.
- `CONTEXT.md` gains Session, Leaf, Staging file, Survey file, Environment record, Corner sweep, Stand-in, Reserve, Link, Runtime host, Machine split, Milestone module, and Checks module; Executor points at `armature-plan`'s table.

### Removed

- The plugin-root `.mcp.json`: the SolidWorks server no longer starts in every session. `/armature:init` asks a SOLIDWORKS project whether to connect it and writes that project's `.mcp.json` on a yes, gitignored because it holds an absolute path into this machine's plugin install. Re-running init repoints a path a plugin update stranded.
### Upgrading a 1.2.x project

`/armature:init` stops on an existing project, so a project scaffolded under 1.2.x re-adopts by hand:

- `CLAUDE.md` — add the `## Purpose` section, the related-work bullet, and the new standing rules from `init`'s template.
- `docs/datasheets/index.md` — add the `Clauses read` and `Price` columns.
- `docs/environment.md` — written by the next `armature-plan` run, which probes on every invocation.
- `docs/01-spec/spec.md` — at its next revision, insert §8 and renumber §8–§11 to §9–§12, with every reference to them.
- `docs/01-spec/budgets.md` — carry each reserve as a line item.
- `analysis/model/` — copying in the new `run_all.py`, `layout.py`, and `test_derivation.py` turns the budget on, so an oversized module fails until it is split or declares `LAYOUT_EXEMPT`.
- A SOLIDWORKS project that relied on the bundled server has none after the update, and init's re-run will not add one: write `.mcp.json` in the shape `init`'s step 4 gives and add it to `.gitignore`.

## 1.2.1 — 2026-09-08

`init` hardening:

- The scaffolded `CLAUDE.md`'s Stage comment now maps each stage to the skill that works it (`concept (armature-pitch) → … → build (armature-bringup, armature-test)`), so a fresh session routes without the plugin README.
- A pre-existing non-Armature `CLAUDE.md` triggers a merge-or-replace question instead of being overwritten.
- The scaffold commit stages only the files init created or changed, keeping unrelated untracked files out in pre-existing repos.
- Standing rules annotate `docs/01-spec/budgets.md` as created by `armature-spec`; the CAD-package question mentions the bundled SolidWorks MCP server when the answer is SOLIDWORKS.

## 1.2.0 — 2026-08-30

Absorbs and adapts material from [Matt Pocock's skills](https://github.com/mattpocock/skills) (MIT, see `NOTICE.md`) and brings every agent-facing doc to one writing standard.

### New skills

- `armature-wayfind` — multi-session efforts charted as a map of decision tickets on the project's issue tracker (GitHub Issues or local markdown, auto-detected), resolved one ticket per session by the stage skills and agents.
- `armature-test` — test-driven development for robot software, default-on in Armature projects: red → green at unit and simulation level, bench seams handed to `docs/testing/bench-seams.md`.
- `armature-debug` — user-invoked bench debugging: a red-capable feedback loop before any hypothesis, then one variable at a time. Ships `scripts/human-loop.template.sh`, the shared step/confirm/capture primitive.
- `armature-bringup` — a plan's bring-up or verification test as an executable bash procedure, measurements recorded into its `docs/testing/` report.

### Renames

- `armature-concept` → `armature-pitch`, `armature-math` → `armature-derive`, `armature-teacher` → `armature-teach`. Every skill name now reads as a verb; agents keep their noun personas. Artifact paths (`docs/00-concept/`, `analysis/`) are unchanged.

### Changed

- Pitch, spec, and plan interviews run in frontier rounds via `AskUserQuestion` (recommended answer first), checkpoint each round, and send lookups to `armature-librarian` mid-interview.
- Project glossaries move from `docs/02-plan/` to the user project's `CONTEXT.md`; `init`'s `CLAUDE.md` template carries the inline-challenge rule and a three-gate ADR tier over `docs/decisions.md`.
- `armature-spec` and `armature-cad` draft questionnaires (`references/questionnaire.template.md`) for unknowns a third party holds.
- `armature-derive` gains `references/phase-boundaries.md`, the five-option context-boundary tree.
- Every `SKILL.md`, agent, and reference rewritten to the writing standard: duplicated rules single-sourced, one trigger per description branch, checkable done-conditions, hand-offs as Skill-tool calls. Agent descriptions carry their dispatch contracts.
- Repo-level `CLAUDE.md`, `docs/agents/issue-tracker.md`, and `docs/agents/domain.md` formalize the GitHub tracker and single-context domain docs.
- README gains a routing table and credits; `NOTICE.md` carries the MIT attribution.

## 1.1.0

- `armature-cad` executable build recipes (build123d): part definitions run as programs that check realized mass, COM, and inertia against `analysis/model/params.py`, self-validate features, render projected views, and sweep link envelopes for interference.
- SolidWorks MCP server (`mcp/solidworks/`): nine verification tools attached to a running session.

## 1.0.0

- First plugin release: `/armature:init`, the concept → spec → plan → math → CAD pipeline, the teacher skill, and the red-team, inventor, and librarian agents.
