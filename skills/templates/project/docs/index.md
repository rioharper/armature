---
type: index
project: <project>
tags: [armature/index]
---

# <project>

<one-line pitch>

This note is the human entry point. It is not a source of truth — every number lives in the document that owns it, and `.armature/state.md` is the authoritative answer to "where is this project right now."

## Documents

| | |
|---|---|
| Concept | [concept brief](concept-brief.md) |
| Engineering | [spec](spec.md) · [design-driver BOM](bom.yaml) |
| Execution | [plan](plan.md) · [state](../.armature/state.md) |
| Conventions | [glossary — frames, symbols, naming](../CLAUDE.md) |

## Analysis

| | |
|---|---|
| M0 setup | [assumptions & parameters](../analysis/<project>_derivation/00_setup.md) |
| M1 kinematics | [frames, FK, Jacobian](../analysis/<project>_derivation/01_kinematics.md) |
| M2 dynamics | [equations of motion](../analysis/<project>_derivation/02_dynamics.md) |
| M3 results | [worst case & collisions](../analysis/<project>_derivation/03_results.md) |

## Parts

Definitions live in [`docs/parts/`](parts/). Geometry lives in `cad/`, which is
excluded from this vault — Obsidian can't render a solid model, and the part
definition is the document about it that you actually want to read.

## Checks

```
cd analysis && pytest && cd ..        # the model is green or red
A=~/.claude/skills/armature/skills
python "$A/armature-red-team/scripts/consistency.py" --repo .
python "$A/armature-cad-parts/scripts/check_inertia.py" --repo .
```

## Open items

Findings and TBDs are tracked in [state](../.armature/state.md). With Dataview
installed, this pulls every review verdict instead:

```dataview
TABLE verdict, findings, reviewed_sha
FROM "reviews"
WHERE type = "review"
SORT file.name DESC
```

And every part not yet modeled:

```dataview
LIST
FROM "docs/parts"
WHERE type = "part-definition" AND status != "modeled"
```
