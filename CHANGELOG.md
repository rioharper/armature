# Changelog

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
