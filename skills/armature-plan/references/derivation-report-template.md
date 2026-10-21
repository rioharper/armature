# Derivation Report <ID>: <name>

Rev <n> — <date> — plan task <T-id> (issue #<n>), Executor: armature-derive

**Status:** complete, or blocked on what. Then the decision itself in three or
four sentences, with every number it moves, old → new. A reader who stops here
knows what changed and what it cost.

**Review:** `docs/reviews/<review file>`, and how its findings closed: fixed
here, accepted with the reason, or open and blocking. A report that skipped its
review says why in the Status line instead (armature-derive, *When a plan task
lands as a report*).

## Purpose
The decision this task was handed and who handed it — the milestone, review
finding, or requirement dispute that ended in a decision rather than a number.
Name the REQ-xxx being sized to and the **measured quantity** it bounds
(armature-derive Step 0).

## Method
Which module and rev printed these numbers, how it was run, and what changed in
the model since the milestone that shipped it. A number that disagrees with an
earlier milestone's says why, and how the earlier one reproduces.

## The decision: <state the decision in the heading>
The heading is the decision, not the topic. Then the argument: the readings or
options on the table, the evidence for the one taken, and each lever rejected
with the number that rejects it. Box the result and its margin.

## <Results>
The tables the decision rests on — sweeps over the envelope, acceptance bands,
tolerance corners. One section per result, headed by what it shows. Every table
is printed from `analysis/model/`; a number typed in by hand goes stale in
silence.

## The write-back
| Number | was | now | where it changed |

Every number this report moves and every file that carries it. An input is its
ledger entry, edited once, then `render` and `check`, which carry it into the
budgets, the BOM, the requirements table and `CONTEXT.md`'s symbols; the
rows after it are the prose that quotes it, the milestone notes and the spec's
text. A derived number, such as a margin, has no entry, and its row names the
note that quotes it. This table is the propagation checklist.

## Assumptions under strain
Each assumption one number away from moving a result, with the **direction and
size** the model gives: sweep it and quote what the result reads at each end,
then name the task that closes it. An assumption that moves nothing does not
belong here.

## Items routed here, and where each closed
| Routed by | Item | Closed |

Every finding, question, and TBD earlier work sent to this task, each with its
resolution or the reason it stays open. An item with no row is an item lost.

## Feeds
| Target | Update |

Where each number goes: its ledger entry, the milestone notes, the spec's
prose and `docs/01-spec/traceability.md`, `docs/decisions.md`, and any skill
this report hands work to.

## Revision History
| Rev | Date | Notes |
