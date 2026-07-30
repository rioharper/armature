# Concept Brief Template

Short, on purpose. A concept brief that runs past a page or two has let
technical detail creep in — push that content to **robotics-spec-design**
instead of padding this file. Omit a section only if genuinely
inapplicable, and say so rather than silently dropping it.

```markdown
# [Project Name] — Concept Brief
Rev 0.1 — [date] — Status: Draft

## 1. The Problem
What's broken, missing, slow, or annoying, for whom, right now. One or two
paragraphs. No mechanisms.

## 2. Audience
Who has this problem, specifically enough to go find three of them. What
they do today instead. Size of the audience, roughly. Willingness to pay
or adopt, if known.

## 3. Differentiation
The actual alternative (named), and what this idea does better, cheaper,
faster, or more accessibly. An honest "no real differentiation, it's a
hobby project" is acceptable — just say so plainly.

## 4. Abstract Requirements & Success Criteria
| ID | Requirement (outcome-level) | Threshold | Priority |
|----|------------------------------|-----------|----------|
| RC-001 | ... | ... | Must/Should/Could |

Outcome-level only: what must be true when it works, not how it works.
"Sorts 95% of recyclables correctly" belongs here; "uses a CNN classifier"
does not.

## 5. Envelope (rough)
Budget order of magnitude, timeline order of magnitude, who's building it
(solo hobbyist, student team, company). A sanity check on ambition, not a
detailed constraint.

## 6. The Pitch
One paragraph, written to sell the idea to someone who hasn't heard it —
the sentence a funder, judge, or teammate would repeat afterward.

## 7. Open Questions
Anything genuinely unresolved at the concept level (audience uncertainty,
unverified differentiation claim). Technical open questions belong in the
spec, not here.

## Revision History
| Rev | Date | Notes |
```
