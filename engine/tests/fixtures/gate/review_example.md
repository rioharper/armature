# [Project] — Design Review Findings
Reviewed <full SHA> — date — artifacts reviewed (name each)

## Verdict
One paragraph: proceed, proceed-with-fixes, or go-back-and-rework.
Commit to one.

## What's solid
The load-bearing things that are right, so the user knows what to
build on.

## Findings
Ordered by severity. For each:

### [BLOCKER | MAJOR | MINOR | QUESTION] F<n>: short title
**Where:** artifact, section / equation / REQ-id.
**Finding:** what is wrong or missing, as a fact with its evidence —
the recomputed number, the untraceable requirement, the two documents
that disagree.
**Consequence:** what it costs if it ships as-is, in the worst case.
**Route:** the fix and its owner — re-derive (armature-derive),
re-spec (armature-spec), re-plan (armature-plan), a new approach
(armature-inventor agent), or a change the user makes directly.

```toml
reviewed = "51dfa1dbdf37aed365503690302b677c827c64fd"
artifacts = ["docs/01-spec/spec.md", "docs/01-spec/budgets.md", "ledger.toml"]

[[finding]]
id = "F1"
severity = "BLOCKER"
status = "open"

[[finding]]
id = "F2"
severity = "MAJOR"
status = "open"

[[finding]]
id = "F3"
severity = "MINOR"
status = "open"

[[finding]]
id = "F4"
severity = "QUESTION"
status = "open"
```
