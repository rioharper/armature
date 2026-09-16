# Issue tracker: GitHub

<!-- Generated from skills/armature-wayfind/references/issue-tracker-github.md,
     which is the single source. Re-copy it when it changes; everything below
     "## Local to this repo" is the only part that belongs to this file alone. -->

Issues and specs for this repo live as GitHub issues on `rioharper/armature`. Use the
`gh` CLI for all operations; it infers the repo from the clone. On this dev machine `gh`
lives at `C:\Program Files\GitHub CLI\gh.exe` when it is not on PATH.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`
- **Sub-issue**: `gh api --method POST repos/<owner>/<repo>/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>`, where `<child-db-id>` is the child's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). Where sub-issues aren't enabled, add the child to a task list in the parent body and put `Part of #<parent>` at the top of the child body.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>` (database id again). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. An issue is unblocked when every blocker is closed.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write. (In PowerShell, quote it: `--add-assignee "@me"`.) Assignee means *claimed by a working session* — never use it to record who an item is for; that is the `executor:` label.

## Labels

Sixteen, created by `init` with `gh label create <name> --color <hex> --description "..."`.
Nothing else creates labels; a missing one is an un-bootstrapped project.

| Label | Colour | Description |
|---|---|---|
| `wayfinder:map` | `5319E7` | Wayfinder map (the effort's index) |
| `wayfinder:research` | `1D76DB` | Wayfinder ticket: fact-finding (AFK) |
| `wayfinder:grilling` | `0E8A16` | Wayfinder ticket: decision by conversation (HITL) |
| `wayfinder:prototype` | `FBCA04` | Wayfinder ticket: artifact to react to (HITL) |
| `wayfinder:task` | `D93F0B` | Wayfinder ticket: work that gates a decision |
| `plan:index` | `0052CC` | Plan index (the build's narrative) |
| `plan:phase` | `006B75` | Plan phase (exit criterion for a block of leaves) |
| `plan:leaf` | `BFD4F2` | Plan leaf (one session of known work) |
| `executor:armature-derive` | `D4C5F9` | Executor: kinematics, dynamics, sizing math |
| `executor:armature-cad` | `D4C5F9` | Executor: part definitions and build recipes |
| `executor:armature-test` | `D4C5F9` | Executor: robot software, test-first |
| `executor:armature-bringup` | `D4C5F9` | Executor: bench procedures and their measurements |
| `executor:armature-librarian` | `D4C5F9` | Executor: datasheets and OTS models (agent) |
| `executor:armature-red-team` | `D4C5F9` | Executor: adversarial review (agent) |
| `executor:armature-inventor` | `D4C5F9` | Executor: frontier research (agent) |
| `executor:user` | `D4C5F9` | Executor: hands-on work no skill performs |

`executor:*` is **cross-cutting**: a wayfinder ticket wears one as readily as a plan leaf,
and an item with two executors wears both. `gh issue list --label executor:armature-librarian --state open`
is how a runner batches work by who does it.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

Used by armature-wayfind. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Destination / Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`. Find the active map with `gh issue list --label wayfinder:map --state open`.
- **Child ticket**: a sub-issue of the map, labelled `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`) plus its `executor:<who>`.
- **Frontier query**: list the map's open children, drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; **first in map order wins**.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.

## Plan operations

Used by armature-plan. The **plan index** is a single issue; phases are its children and
leaves are theirs — three levels. Parent tasks get no issue of their own.

- **Plan index**: a single issue labelled `plan:index`, holding scope-against-hours, `## Machine split`, Must satisfiability, CAD process, risks and their plan hooks, and the line `Glossary: see CONTEXT.md`. `gh issue create --label plan:index`. Find it with `gh issue list --label plan:index --state open`. It is an index, not a store: it carries no task and no rollup.
- **Phase**: a sub-issue of the index, labelled `plan:phase`, titled `Phase 1 — Analysis and simulation`. Body holds the phase's `Exit:` criterion, and — for phases not yet materialised — its leaves as an unchecked task list.
- **Leaf**: a sub-issue of its phase, labelled `plan:leaf` plus one `executor:<who>` per executor. Title is `<T-id> <name>`, e.g. `T3.2a Pulley set and load-cell fixture`. **T-ids are permanent**: assigned once, never renumbered, an insertion becoming `T3.2c`. The issue number is the machine identity; the T-id is the name humans and reports cite.
- **Materialise lazily**: cut leaf issues for the **current and next phase only**. Later phases keep their leaves as a task list in the phase body until the phase before them closes, then get cut. A plan of 200 sessions is ~40 live issues.
- **Frontier query**: open `plan:leaf` issues, minus any with an open blocker or an assignee; **first in T-id order wins**. T-id order is not issue-number order — leaves are cut a phase at a time, so sort on the title prefix, not on `number`.
- **Close a leaf**: `gh issue close <n> --comment "Actual: <time> · <what landed, one line>"`. The closing comment's **first line must begin `Actual:`** — that is what the estimate-versus-actual rollup reads. `Est:` stays in the body where planning put it; never edit it to match.
- **Rollups are derived, never stored.** A phase's hours, session count and closed count are computed on read from its child leaves (`gh issue list --label plan:leaf --state all --json number,title,state,body` scoped to that phase's sub-issues: sum each body's `Est:`, count `state == "CLOSED"`). Estimate-versus-actual pairs each closed leaf's body `Est:` with the `Actual:` line of its closing comment (`gh issue view <n> --comments`). Writing either number into a title or body makes it stale at the very next close.

## Local to this repo

This repo is the Armature plugin itself, not an Armature project: it has no `plan:*`
issues and no `executor:*` labels, and the sections above that describe them are
carried verbatim so a diff against the reference shows drift rather than hiding it.

### Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either: resolve with `gh pr view 42` and fall back to `gh issue view 42`.

### `ready-for-agent`

A label of this repo only, not part of the plugin taxonomy: a spec issue whose body is
complete enough for an agent to implement without further interview.
