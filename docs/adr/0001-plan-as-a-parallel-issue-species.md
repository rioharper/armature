# ADR 0001 — The plan is its own issue species, not a wayfinder map

2026-09-15 — Status: accepted

`armature-plan` no longer writes `docs/02-plan/plan.md`. The plan lives on the
project's issue tracker as a `plan:index` issue with `plan:phase` children and
`plan:leaf` grandchildren, alongside — not inside — `armature-wayfind`'s
`wayfinder:map` and its tickets. The obvious move was to reuse the map
machinery, which already had tickets, blocking, claiming and a frontier query
working on GitHub Issues; two issue species on one tracker looks like
duplication and a future reader will reach for the merge.

It is not duplication. `CONTEXT.md` separates an **Effort** (foggy, coordinated
across sessions, overlaying the pipeline, resolved by **decisions**) from a
**Stage**'s plan (known work, under one stage, executed as **leaves**), and the
two artifacts differ in every property that matters: a ticket's body is a
question and its answer is recorded on resolution, while a leaf's body is a
behavioural contract with a `Done when` fixed at planning time; a map is
charted breadth-first into fog, while a plan is cut into ordered phases with
exit criteria; a map's frontier is map order, a plan's is T-id order. Collapsing
them would delete the distinction the glossary exists to hold, and the pull to
merge them is exactly what this record is here to stop.

The cost accepted: moving off a single markdown file means a session that read
the whole plan with one `cat` now runs a list query plus per-issue views, and
that can raise per-session tokens rather than lower them. Two choices hold that
down — leaves are materialised lazily (current and next phase only, roughly 40
issues instead of 200) and rollups are derived on read rather than stored.
Revisit if the read cost shows up as real context pressure in a planned
session, or if the two species start growing the same fields.
