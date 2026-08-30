# Context

Glossary for the Armature plugin itself (not for user projects — their glossary lives in their own `CLAUDE.md`).

## Terms

- **Stage**: one step of the per-project pipeline (pitch → spec → plan → derive → CAD → build), recorded as the `Stage:` line in a user project's `CLAUDE.md`. A stage is session-sized work.
- **Effort**: a unit of work too big for one agent session, coordinated across sessions by a wayfinder map. An effort overlays the pipeline; it is not a stage and never moves the `Stage:` line.
- **Map**: the canonical artifact of an effort — destination, notes, decisions index, and fog — with decision tickets as children. Lives on the project's issue tracker.
- **Overlay**: the relationship between wayfinding and the pipeline: stages stay intact and become the means of resolving a map's tickets, rather than being absorbed or wrapped.
- **Executor**: who resolves a ticket or task — a stage skill, an agent (inventor / librarian / red-team), or the user. Ticket *types* (research / prototype / grilling / task) say what kind of question it is; the executor says who works it. Agents are executors, never ticket types.
