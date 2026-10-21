# [Project] — Recheck of docs/reviews/YYYY-MM-DD-<artifact>-review.md
Reviewed <full SHA> — date — fix diff <from>..<to>

## F1: holds
**Fix:** what the diff changed for this finding, by file and section.
**Judgment:** the finding's recomputation re-run on the fixed artifact
and where it lands now, or, for a judgment finding, why it no longer
stands.

## F2: reopened
**Fix:** what the diff changed for this finding.
**Judgment:** what still stands, as specifically as the finding was
written: the number, the requirement, the two documents.

```toml
reviewed = "826056014b0f7a8e1ab8e7922c9e208e60b99264"
rechecks = "docs/reviews/2026-10-21-spec-review.md"

[[finding]]
id = "F1"
status = "holds"

[[finding]]
id = "F2"
status = "reopened"
```
