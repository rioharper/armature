# Derivation Report DR-01: the bob's first mode against R-4

Rev 1 — 2026-10-17 — plan task DR-01, Executor: armature-derive

**Status:** complete. R-4 holds: on the derived variant the bob has no mode at all, so none sits under R-4's 10 Hz. A3, the inextensible cable, is released in the truth model and moves the bob 4.905 mm, a sag that changes no posture the rig works at, so the variant stands. No number in the spec moves.

## Purpose

The plan hands derive one decision: does the bob's first mode meet R-4, every mode at or above 10 Hz? The measured quantity is the frequency of the bob's free oscillation on the slide, read by the slide's encoder after a tap (00_setup.md, *The system*).

## Method

`analysis/model/first_mode.py` (rev 1) reads the variant `DERIVED`, the description with the cable rigid by A3, and linearises it at its rest with `linearise()`, which on a closed chain reports the modes on the constraint manifold. The tables below are printed by `uv run python report_dr01.py`; `uv run python run_all.py` runs every check behind them.

## The decision: R-4 holds, the bob has no mode under 10 Hz

The rigid cable holds the bob at its rest length, so the slide's one coordinate z is solved by the cable's closure and the variant has no independent coordinate (`test_the_derivation_accounts_for_the_variants_coordinates`). Its linearisation has nothing to oscillate in and returns no mode; the first mode is unbounded.

I expected exactly that: a bob hung on an inextensible cable on a vertical slide is held, not sprung. The one way the answer could move is A3 itself, so A3 is released in the truth model (`test_truth_release_a3_on_the_sag`): with the cable allowed to stretch, the bob settles 4.905 mm lower, m g / k, and the release passes its bound of a twentieth of the slide's travel. A3 is kept, and with it the decision.

> **R-4: met.** First mode on A3: unbounded, against a 10 Hz floor.

## Results

| Quantity | Value | From |
|---|---|---|
| first mode on A3 | ∞ Hz | first_mode.first_mode(), the variant's modes [] |
| R-4's floor | 10 Hz | spec R-4 |
| A3 released: the bob's static sag | -4.905 mm | test_truth_release_a3_on_the_sag |
| the cable's tension at rest | 4.905 N | the truth model, settled |

## The write-back

| Number | was | now | where it changed |
|---|---|---|---|
| R-4 status | open | met | `docs/01-spec/traceability.md` |

## Assumptions under strain

| Assumption | Direction and size | Closed by |
|---|---|---|
| A3, the cable inextensible | released: the bob sags 4.905 mm on the elastic cable, under a twentieth of the 200 mm travel | this report |
| A2, the anchor rigid | a compliant anchor softens the rig; not in the description | the frame's CAD |

## Items routed here, and where each closed

| Routed by | Item | Closed |
|---|---|---|
| plan, DR-01 | does the first mode meet R-4? | yes, above |

## Feeds

| Target | Update |
|---|---|
| `docs/01-spec/traceability.md` | R-4: analyzed, DR-01 |
| `docs/decisions.md` | R-4 met on A3; cable order unblocked |

## Revision History

| Rev | Date | Notes |
|---|---|---|
| 1 | 2026-10-17 | first issue |
