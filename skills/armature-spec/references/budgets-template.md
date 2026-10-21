# Budgets — <project>

Living document. Debit at every phase gate: math and CAD update estimates
as they harden; any change to a mass, power draw, or cost updates its
ledger entry. Each table below is a view of `ledger.toml` (ADR 0010): edit
the entries, then run `py -m armature.ledger render`, which rewrites every
table between its `<!-- ledger:budget.<kind> -->` and `<!-- /ledger -->`
markers, and `py -m armature.ledger check`, which fails a table edited by
hand. The prose around the tables is yours.

A budget is the section `budget.<kind>`: one entry named `allocation`, the
most its lines may sum to, citing its REQ (`of = "req.REQ-xxx"`, or
`source = { kind = "chosen", ref = "REQ-xxx" }`), and one entry per line
item. A line that is a part's number is `of = "part.<pn>.<field>"` with a
`qty`, never a copy of it. A row's prose is its entry's `note`. The total
and the margin are worked out on every render and stored nowhere.

**Margin is slack**: the allocation less the lines' total, how far the
estimates can still move the wrong way before the budget fails. Negative
means breached.

## Source

Every entry carries one of the ledger's six kinds, with the citation the
kind requires: `chosen` (the spec section or REQ id), `standard` (the
reference), `estimate` (what it rests on, and a band), `datasheet` (the
`docs/datasheets/index.md` row's P/N, and `retrieved`), `cad` (the part
file and its rev), `measured` (the test report). Trust rises estimate →
datasheet → cad → measured. Separately, a `status` says whether the user
has confirmed the number: `candidate` or `confirmed`.

A **cost** line is a `datasheet` entry in USD when a vendor publishes the
price: its `retrieved` is the price's date, the only thing that says the
price has gone stale, and `check` warns (`price.old`) once it is more than
90 days old. A part whose index row reads `quote only` publishes no price,
so a cost resting on it is an `estimate`, with a band, however carefully
the number was arrived at; it becomes a `datasheet` entry when a human asks
a vendor, not before.

## Reserves

A reserve, headroom held back for a named future change, is a line of its
own: a `chosen` entry holding the headroom its requirement demands, citing
that REQ in `source.ref`. Nothing debits it directly. A debit anywhere else
shrinks the margin it sits in, so the reserve is spent the moment the lines
around it outgrow the allocation.

When the lines, the reserve among them, sum past the allocation the budget
is **breached**, and `check` reports `budget.breach`. Each requirement the
budget answers to has failed: the REQ its allocation reads or cites, and
the REQ each of its lines cites, a reserve's among them. Each reads
`failed` in `docs/01-spec/traceability.md`, where `check` fails it as
`trace.unfailed` until it does, and stays failed until the recovery lands
or a decision in `docs/decisions.md` relaxes the requirement. A sentence
above the table saying so instead leaves the row reading healthy, which is
how a breach survives a review.

## Mass

<!-- ledger:budget.mass -->
| Line item | Entry | Budget | Current estimate | Margin | Source | Status |
| --- | --- | --- | --- | --- | --- | --- |
<!-- /ledger -->

## Power

An actuator's or the bus's power is a drive margin's worst-case row, not a
budget line (armature-derive's `references/derivation-standards.md`,
*Actuators and the bus*): `run_all.py` prints it (`bus: source power`,
`bus: brake power`) against the source's `drive.p_source`, and a derived
number is never a ledger entry. The other lines (compute, sensors) are
debited as usual, and the hotel load `drive.py` carries is the line
`of = "drive.hotel"`.

<!-- ledger:budget.power -->
| Line item | Entry | Budget | Current estimate | Margin | Source | Status |
| --- | --- | --- | --- | --- | --- | --- |
<!-- /ledger -->

## Cost

<!-- ledger:budget.cost -->
| Line item | Entry | Budget | Current estimate | Margin | Source | Status |
| --- | --- | --- | --- | --- | --- | --- |
<!-- /ledger -->
