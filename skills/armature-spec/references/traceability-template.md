# Requirements traceability — <project>

One row per REQ. Spec creates rows; plan fills Test; math/testing update
Status. Status: open → analyzed → tested, failed, or waived (with a reason
in docs/decisions.md). A REQ reads `failed` when its analysis or test shows
it is not met, and a REQ a breached budget answers to reads `failed` as
soon as the breach is in the ledger (`budgets.md`, *Reserves*):
`py -m armature.ledger check` reports `trace.unfailed` while its Status
cell says anything else, so write the word `failed` first. A failed REQ
stays failed until the recovery lands or a decision relaxes it. A Must REQ
still `open` at integration is a wish.

| REQ | Requirement (short) | Design element | Analysis | Test | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | | | | | open |
