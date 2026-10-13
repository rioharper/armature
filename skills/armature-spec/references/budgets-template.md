# Budgets — <project>

Living document. Debit at every phase gate: math and CAD update estimates
as they harden; any change to a mass, power draw, or cost updates its row.

**Margin is slack** — how far the estimate can still move the wrong way
before the row fails. A line item that consumes the budget fails from above,
so its slack is budget − estimate; a **reserve** fails from below, so its
slack is estimate − budget. Negative either way means failed.

## Source

Increasing trust: `guess` → `datasheet` → `model` → `measured`. A `datasheet`
value cites its row in `docs/datasheets/index.md`.

A **cost** row reads one more rung, `list price`, where `datasheet` sits: cite
the `docs/datasheets/index.md` row whose `Price` cell you read, and take that
row's `Retrieved` as the price's date. The price goes stale on its own and
that date is the only thing that says so. A row reading `quote only` publishes
no price, so a cost resting on it is a `guess` and says `guess`, however
carefully the number was arrived at; it climbs the ladder when a human asks a
vendor, not before.

## Reserves

A reserve — headroom held back for a named future change — is a line item in
whichever table holds it, with one difference: **nothing debits it directly**.
Its current estimate is the ceiling minus every other line's current estimate,
so a debit anywhere else debits the reserve in the same edit. Its budget is
the number its requirement demands; name that REQ in the Source cell.

When that arithmetic drives the margin negative the reserve is **breached**,
and a Must requirement has failed. It fails where a failure is read — the
row's margin, and the requirement's row in `docs/01-spec/traceability.md` —
and stays failed until the recovery lands or a decision in `docs/decisions.md`
relaxes the requirement. A sentence above the table saying so instead leaves
the row reading healthy, which is how a breach survives a review.

## Mass

| Line item | Budget (g) | Current estimate (g) | Margin | Source |
| --- | --- | --- | --- | --- |
| Reserve for <named future change> | | | | REQ-xxx |
| System total | | | | |

## Power

An actuator's or the bus's power row is a drive margin's worst-case row, not
arithmetic (armature-derive's `references/derivation-standards.md`, *Actuators
and the bus*): its Source reads `model` and names the row `run_all.py` prints
(`bus: source power`, `bus: brake power`). The other lines
(compute, sensors, the hotel load `drive.py` carries) are debited as usual.

| Line item | Budget (W) | Current estimate (W) | Margin | Source |
| --- | --- | --- | --- | --- |
| System peak | | | | |
| System continuous | | | | |

## Cost

| Line item | Budget | Current estimate | Margin | Source |
| --- | --- | --- | --- | --- |
| Total | | | | |
