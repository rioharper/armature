---
name: armature-plan
description: Convert a robotics engineering spec into a phased implementation plan — analysis, CAD, prototyping, fabrication, integration — and write the project's shared vocabulary (frames, symbols, naming) into CONTEXT.md. Use when the user has a spec or design document and wants an implementation plan for building it, or asks to plan a robotics build with no spec behind it.
---

# Robotics Implementation Planning

You take a finished (or finished-enough) engineering spec and turn it into a plan someone can execute — phase by phase, task by task, with exit criteria — and write the project's shared language into `CONTEXT.md`.

## Inputs

Read `docs/01-spec/spec.md`, `docs/01-spec/bom.md`, `CLAUDE.md`, and `CONTEXT.md` (if present) from disk — the spec is normally produced by **armature-spec**. If no spec exists, do a compressed requirements capture (mission, constraints, chosen architecture, builder capability) and note in the plan that it rests on an informal spec — or, for a substantial project, offer armature-spec: on yes, call the Skill tool with "armature-spec". If the spec is still foggy — more open decisions than one session can settle — call the Skill tool with "armature-wayfind" to chart the way first. Audience and differentiation are settled upstream, in **armature-pitch**'s concept brief if one exists; take them as given.

**The tracker must exist before you plan.** The plan is issues, not a file. Confirm three things: `gh auth status` passes, `git remote -v` names a remote, and `docs/agents/issue-tracker.md` is present. `init` establishes all three; a project scaffolded before it did will be missing them. Where any is absent, stop and say which — the repair is `gh auth login`, `gh repo create <name> --private --source=. --remote=origin --push`, and copying **armature-wayfind**'s `references/issue-tracker-github.md` into `docs/agents/` plus creating the sixteen labels from its table. Planning into a markdown file that nothing downstream reads is the failure this check exists to prevent.

## Before writing

Three checks, then the rounds. Each is cheap, and each is something the plan
rests on silently when it is skipped.

**Probe the machine.** Run the plugin's environment probe, passing the tools
this spec actually names as arguments:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/env-probe.sh" ros2 gazebo cuda
```

Re-probe on **every** invocation, a re-plan at a phase gate included, and
rewrite this machine's section of `docs/environment.md` with today's date, so
the record is never older than the last plan written against it. Format and the
one-section-per-machine rule: `references/environment-record.md`, two levels
above this skill. An absence the plan depends on becomes explicit Phase 0 work
with hours against it rather than a footnote — a missing ROS 2 and Gazebo are
that phase's first tasks, and a machine with no CUDA is a dependency on some
other machine, not a slower schedule. **A missing MuJoCo is Phase 0 before the
analysis phase can start at all**: `armature-derive` builds its truth model on
MuJoCo, so a machine that reads `MUJOCO=absent` cannot pass a derivation
milestone checkpoint, and the analysis phase's first leaf waits on that install.

**Split the work across machines.** The spec's §8.1 `Runtime host` column
already answers what the robot runs on in the field, so ask only for the
superset: the development machines that never ship — a sim host, a GPU box, a
bench laptop, a target board on somebody else's desk. One machine that does all
of it needs no section. The moment one cannot do another's work, the plan index
carries a `## Machine split` section:

```markdown
## Machine split

Default machine: **sim host**; a leaf that runs elsewhere says so.

| Role | Machine | Probed | What runs there |
|---|---|---|---|
| Sim host | this laptop, WSL2 Ubuntu 24.04, ROS 2 Jazzy | 2026-09-10 | physics, controller iteration, Phases 1–3 |
| Render host | 64 GB / RTX 4090 box | not probed — T0.4 | splat training, image scoring |
| Target | Jetson Orin Nano Super | not probed — T0.5 | the REQ-034 parity check |
```

`Probed` cites that machine's dated section of `docs/environment.md`. **A role
the project needs that nobody has probed is the gap this prompt exists to
surface**: probing it is a Phase 0 leaf with hours against it, because a machine
assumed and never seen is an estimate resting on nothing, and access somebody
still has to arrange is a dependency the schedule owes a date. Say what forces
the split in a sentence under the table — a laptop with no CUDA cannot train
what the spec asked for, whatever the calendar says.

**Read every Must for satisfiability.** A Must is a promise the whole plan is
cut to keep, so read each one as the conditions it actually imposes and ask what
could satisfy all of them at once. It fails two ways, and the second is the
quiet one: two Musts that cannot both hold (the mass budget against the
stiffness one), and a *single* Must whose own clauses contradict each other —
usually a term of art whose definition forbids the clause beside it ("open
source, non-commercial": the OSI definition forbids field-of-use restrictions,
so nothing satisfies both). Quantified and verifiable is not satisfiable, and a
review reading requirements against *each other* slides straight past the second
kind. Neither is yours to amend: name the requirement, say which reading you
would keep and what it costs, and route it to **armature-spec** as a spec
question — or carry the amendment as a Phase 0 leaf that closes by editing the
spec and its revision history.

Resolve with the user: available hours per week, hard deadlines, whether analysis (kinematics/dynamics) precedes or parallels CAD, and any gaps the spec left open. Their calendar is theirs to state, never yours to assume.

Work these questions in rounds. Each round, ask the **frontier** — the questions whose prerequisites are already settled (a phase-ordering question waits until the spec gap that drives it is resolved); recompute the frontier after each round. Deliver rounds through the AskUserQuestion tool, your recommended answer as the first option labeled "(Recommended)", so a single word can accept it; the tool takes 4 questions per call, so a larger frontier spans consecutive calls within the round. Facts are your job; decisions are the user's: send a lookupable (a lead time, a part's availability, a datasheet number) to the **armature-librarian** agent and keep asking the rest of the frontier while it runs — several at once go in waves of two or three per the plugin's `references/subagent-dispatch.md` (two levels above this skill).

**Checkpoint each round.** After each round, write the plan as it stands to `docs/02-plan/draft.md`, opening with a `> Draft — open questions: …` line carrying the live frontier. If that file exists on invocation, resume from it: settled answers stand, and its open questions seed the frontier.

The draft is **not** the plan and never becomes it. It is gitignored, it exists only while the interview runs, and cutting the issues is what ends it — delete it in the same step. Nothing is created on the tracker until the interview closes: a half-specified plan published as forty issues is worse than no plan, because the fog in it is now indistinguishable from work. A `draft.md` found on disk with no issues behind it is an abandoned interview; offer to resume it or delete it.

## The plan on the tracker

The plan is three levels of issues — a **plan index**, its **phase** children,
and their **leaf** grandchildren. Read the "Plan operations" section of
`docs/agents/issue-tracker.md` before the first write: it holds the labels, the
sub-issue and dependency commands, and the queries the shapes below assume.

### The index issue

Titled `<Project> — Implementation Plan`, labelled `plan:index`. It carries
everything in a plan that is not a task:

```markdown
Glossary: see CONTEXT.md
From spec Rev 1.3 (`docs/01-spec/spec.md`) and BOM Rev 0.4 (`docs/01-spec/bom.md`)

## Scope against hours
## Machine split
## Must satisfiability
## CAD process
## Risks and plan hooks
```

**That source line is a rendering, never a memory.** Re-read both revs from
those documents' own headers every time you rewrite the index, so there is
nothing to compare and nothing to drift — a line typed once and edited by hand
names a spec rev the plan has already been re-cut past.

**No rev number, no revision history.** The issue's own edit history is the
record, and a hand-maintained table beside it is a second source of truth: the
table is always the one that goes stale. What a revision used to carry — what
moved, which leaves closed with their actuals, which numbers changed in the
spec, BOM or budgets — is posted as a comment on the index when a phase gate
re-cuts the plan.

**The index carries no rollup.** Hours, session counts, closed counts and
estimate-versus-actual are derived on read from the leaf issues; writing any of
them into the index body or a phase title makes them wrong at the very next
close.

Structure:

### 1. Glossary & conventions — written into `CONTEXT.md`

This is the point of the skill — it's what makes conversation #47 about this robot as grounded as conversation #2. The shared language lives in `CONTEXT.md` at the project root: create the file if it doesn't exist (this is usually its first content), and confirm `CLAUDE.md`'s Glossary section points at it so every session auto-loads the pointer. The index issue keeps a one-line pointer: `Glossary: see CONTEXT.md`. `CONTEXT.md` stays a file in the repo — it is read by every session and every agent, including ones with no tracker access, and it belongs beside the code it names.

Each named term gets a tight definition (one or two sentences, what it IS) followed by an `_Avoid_:` line listing the synonyms it displaces — pick arm *or* link *or* boom, ban the rest. The `_Avoid_` lines are what the inline-challenge rule in `CLAUDE.md` enforces.

Content requirements, regardless of destination:

- **Coordinate frames:** define every frame the project will use ({W} world, {B} base, {E} end-effector, per-joint frames…), their origins, axis conventions (right-handed, z-up or z-along-joint — pick and state), and the convention family. Once chosen, these are law. Pick the family from the topology: a serial chain on a fixed base takes modified DH or product-of-exponentials; a platform whose own body moves — wheeled, legged, or flying — takes a **floating base plus joints**, the body's pose in {W} as a 6-DOF transform followed by each joint's axis and origin in its parent frame. State the one the machine has — a floating base is a convention in its own right, not a chain missing its DH table.
- **Symbol table:** q for joint positions, τ for torques, m_i, l_i, I_i for link properties, etc., with units. The **armature-derive** skill consumes this table verbatim, so make it complete.
- **Naming conventions:** part numbering scheme (e.g., `ARM-LNK-002`), CAD file naming, revision scheme, units policy (SI internally, always).
- **Definitions of done** for a task (its `Done when` literally true, checkable by a session that never saw the conversation, and every artifact it touched committed), a phase (every task done or killed with its kill criterion logged, the exit criterion held, budgets and traceability debited, the next phase re-cut per §3), and the project.

### 2. Phase breakdown

Decompose into phases where each phase ends in something *demonstrable or testable*. Each becomes a `plan:phase` issue, a sub-issue of the index, titled for the phase alone — `Phase 1 — Analysis and sizing`, with **no hours in the title**: the hours, session count and closed count are derived from its leaves whenever someone asks, and a title carrying them is wrong the moment a leaf closes. The body holds the phase's `Exit:` criterion.

**Cut the leaves, materialise them lazily.** Cut every phase's leaves during the interview — the plan is not finished until you have — but create issues only for the **current and next phase**. A later phase keeps its leaves as an unchecked task list in its own body until the phase before it closes, then they are cut into issues. A 200-session plan is about 40 live issues, and the leaves furthest out are the ones a prototype is most likely to rewrite before anyone reaches them.

Typical arc (adapt, don't copy):

1. **Analysis & sizing** — kinematic model, workspace check, actuator sizing from dynamics, DOF/reachability verification. Derivation tasks say "derive FK/IK/Jacobian/dynamics" and carry `armature-derive` as Executor.
2. **Concept CAD & layout** — master sketch / skeleton model driving all subassemblies, envelope check, interference and service-access check, mass rollup vs. budget.
3. **Prototype the risky bits** — each prototype task carries the question it must answer and a kill criterion.
4. **Detail design & DFM** — part-by-part CAD, tolerance decisions, COTS selection with actual part numbers, drawings for anything outsourced, BOM with costs against budget. If the spec came with a **design-driver BOM** (from armature-spec), expand it into the full procurement BOM — the design drivers and their datasheets are settled; add quantities, fasteners, costs, and lead times. Any part still carrying a TBD or assumed spec gets a task to source and confirm its datasheet *before* its drawing is released.
5. **Fabrication & subsystem bring-up** — build order chosen so subsystems are testable standalone; electrical/wiring as first-class tasks.
6. **Integration & verification** — trace every Must requirement (REQ-xxx) to a test task and fill the Test column of `docs/01-spec/traceability.md`; a Must REQ with no test row is the gap this phase exists to catch.
7. **Iteration reserve** — an explicit phase: budget for revising the worst mechanism.

### 3. Leaf format

A leaf is one issue: title is its permanent T-id and name, labels are `plan:leaf`
plus one `executor:<who>` per executor, body is the contract.

```markdown
Title:  T3.2b 500-cycle tension test
Labels: plan:leaf, executor:user

Executor: user · Est: 1h · Machine: bench laptop
Depends on: T3.2a (#147)
Needs: printed pulley set, load cell
Answers: can 2mm Dyneema hold tension over 500 cycles at r=8mm?
Done when: 500 cycles logged in docs/testing/T3.2-wrist-cycles.md, elongation < 1%
Out of scope: the geared-wrist fallback (T3.3)
```

`Depends on:` carries the T-id for the reader and the issue number for the
machine, and the *same* edge is wired as a native dependency — the line is the
readable copy, the dependency is the gate the frontier query actually reads.
Wire the edges in a second pass, once the leaves exist and have numbers.

**`Est:` is written once and never edited.** `Actual:` never appears in the
body: it is the first line of the closing comment, `Actual: 30 min · <what
landed>`. That keeps the record append-only, and it is what the derived
estimate-versus-actual reads.

`Executor` names who picks the leaf up, so a fresh session knows where it goes.
Each row below is also a label:

| Executor | Picks up |
|---|---|
| `armature-derive` | kinematics, dynamics, sizing math |
| `armature-cad` | part definitions and build recipes |
| `armature-test` | robot software, test-first |
| `armature-bringup` | bench procedures and the measurements they record |
| `armature-librarian` | datasheets and OTS models (agent) |
| `armature-red-team` | adversarial review (agent) |
| `armature-inventor` | frontier research (agent) |
| `user` | hands-on work no skill performs: shop, bench, vendor contact, judgement calls |

A leaf the skill drafts and the user executes names both, written `armature-bringup + user`, and wears both labels. Dependencies explicit, exit criteria observable.

A leaf that runs somewhere other than the plan's default machine names it too, written `Machine: render host`, citing a row of the index's `## Machine split`. The default stays silent, so the field marks exactly the leaves that wait on access somebody has to arrange.

**The unit is the session.** A leaf task is one agent session, roughly 100k tokens: finished, committed, and re-runnable from the repo alone. Where the session boundary and the hour estimate disagree, the session boundary wins. Parent tasks are a planning convenience and nothing more: they group leaves while you cut a phase, and they get no issue. Leaves are lettered (`T1.1a`), and a dependency that named a parent is wired to that parent's **last leaf** when the issues are cut — a grouping cannot be a blocker, because nothing closes it.

**T-ids are permanent.** Assign once, never renumber: a leaf inserted after `T3.2b` is `T3.2c`, even where that leaves the order looking odd. Renumbering would mean editing every issue title in the phase and would still orphan the T-ids already cited by closed issues, `docs/decisions.md`, and every report written under `references/derivation-report-template.md`.

Three cuts a planner makes before a session discovers them:

- a review and its rework are separate leaves (the **armature-red-team** agent runs in its own context; resolving its findings costs a session);
- a report (re-run the model, tabulate the sweep, write back to the spec, `params.py`, `budgets.md`) is its own leaf;
- a change of executor is a cut.

User-executed leaves keep the older bound: under a day of hands-on work.

**Cut at every third-party wait.** Wherever a task waits on a party outside the project — a vendor's quote, a shipment, someone else's CI run, a reviewer's answer — cut it there. The agent-doable leaf's `Done when` ends at "ready to send" or "submitted"; the waiting leaf is `Executor: user` with `Done when: the reply is recorded as received, whatever it says`, so the only session that can close it is one holding the reply.

**Estimate in sessions and wall-clock.** A leaf's `Est:` is the wall-clock of its session; a phase's is the sum of its leaves', derived on read rather than written down. A closed leaf records `Actual:` in its closing comment, never beside `Est:`. User leaves are estimated in the user's own hours, which they state. The user's hours per week bound the sessions they drive, so the calendar follows from wall-clock. Starting table, until the project's own actuals replace it:

| Leaf kind | Wall-clock per session |
|---|---|
| Writing: documents, repository layout, configuration, a schema | 15–45 min |
| Checked outside the editor: a build, a real source tree at a tag, constants that must agree across documents | 1–2 h |
| Derivation milestone, three leaves | draft ~30 min · review ~0 for the driver · rework ~1 h |
| Report: re-run, tabulate, write back | 1–1.5 h |

Wall-clock tracks how much of the leaf is checked against something the executor does not control: a fast draft is fast because it defers the checking, and the checking is where the hours are.

**Re-cut at each phase gate.** Estimate-versus-actual is a **derived view**, not a stored table: pair each closed leaf's body `Est:` with the `Actual:` line of its closing comment, and take the ratio. At the gate, build that view, re-cut the next phase from the ratios of closed leaves *of the same kind*, and materialise the following phase's leaves into issues. A kind with no actual yet carries forward unchanged, and the gate comment on the index says so.

A task whose output is a report names that file under `docs/testing/`, and the filled-in file is what its `Done when` points to. Which shape it takes follows from what the task produces: a **test task** — prototype (phase 3) or verification (phase 6) — measures, and takes `references/test-report-template.md`; an **analysis task** run by `armature-derive` decides on numbers the model prints, and takes `references/derivation-report-template.md`.

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
- A concept the plan assumes the user knows: call the Skill tool with "armature-teach".
- Stress-testing the plan (or the spec under it) before committing: dispatch the **armature-red-team** agent.

Once the issues are cut: delete `docs/02-plan/draft.md`, update `CLAUDE.md` — Stage → `analysis`, Latest artifacts → the plan index issue by name and URL — and log the planning decisions (phases chosen, prototypes selected, hours assumed) in `docs/decisions.md`. Report the index issue, how many leaves were materialised and for which phases, and which phases are still task lists waiting to be cut.
