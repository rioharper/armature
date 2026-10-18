# Derivation Report DR-01: the deck's tilt at the edge midpoint against R-2

Rev 1 — 2026-10-17 — plan task DR-01, Executor: armature-derive

**Status:** complete. R-2 holds at the edge midpoint: on the rest lengths in `params.py` the cables carry the platform there level, so the deck's tilt is 0.000°, inside the gimbal's 2°. A3, the level platform, is released in the truth model and turns the deck by under 1e-13°, so the variant stands. No number in the spec moves.

## Purpose

The plan hands derive one decision: does the deck stay within R-2's 2° of level at the edge midpoint, `POSE` = (0.5, 2.0, 1.2) m, on the rest lengths in `params.py`? The measured quantity is the deck's tilt, the platform's axis against the vertical, read by the gimbal's IMU at a stop (00_setup.md, *The system*).

## Method

`analysis/model/deck.py` (rev 1) reads the variant `DERIVED`, the description with the platform's three turns locked level by A3, compiles it on `params.py`'s rest lengths, and settles it from `POSE`; the deck's tilt is read off the settled platform's `centre` site. The tables below are printed by `uv run python report_dr01.py`; `uv run python run_all.py` runs every check behind them.

## The decision: R-2 holds, the deck stays level

The tension law sets each cable's rest length so the four tensions carry the platform's weight with the platform level at `POSE`. Settled from there, the level platform stays: it moves by under 1e-6 m, every cable taut, c1 and c4 carrying 16.78 N and the far pair 3.71 N (`test_the_level_platform_holds_the_edge_midpoint`). Its tilt is the locks', 0.000°.

I expected exactly that: the attachment square is a scaled copy of the anchor square, so the cables only translate the platform. The one way the answer could move is A3 itself, so A3 is released in the truth model (`test_truth_release_a3_at_the_room_centre`): hung at the room centre on the law's own rest lengths, free to turn, the platform turns by under 1e-13° and settles as level as the variant holds it, well under the bound of a tenth of R-2's range. A3 is kept, and with it the decision.

> **R-2: met.** Deck tilt at the edge midpoint on A3: 0.000°, against a 2° limit.

## Results

| Quantity | Value | From |
|---|---|---|
| deck tilt at the edge midpoint, on A3 | 0.000° | deck.deck_tilt() |
| R-2's limit | 2° | spec R-2 |
| A3 released at the room centre: largest turn | 7.0e-14° | test_truth_release_a3_at_the_room_centre |
| the law's tension at the room centre, each cable | 12.161 N | deck.centre_law(), (1) |
| tensions at the edge midpoint, c1 to c4 | 16.78, 3.71, 3.71, 16.78 N | deck.at_the_edge() |

## The write-back

| Number | was | now | where it changed |
|---|---|---|---|
| R-2 status | open | met at the edge midpoint | `docs/01-spec/traceability.md` |

## Assumptions under strain

| Assumption | Direction and size | Closed by |
|---|---|---|
| A3, the platform level | released at the room centre: under 1e-13° | this report |
| A1, straight massless cables | sag of a few millimetres at 2 kg; moves no tension appreciably | the cable's choice |
| A2, a rigid frame | a compliant frame lowers the platform; not in the description | the frame's CAD |

## Items routed here, and where each closed

| Routed by | Item | Closed |
|---|---|---|
| plan, DR-01 | does R-2 hold at the edge midpoint? | yes, above |

## Feeds

| Target | Update |
|---|---|
| `docs/01-spec/traceability.md` | R-2: analyzed, DR-01 |
| `docs/decisions.md` | R-2 met on A3; gimbal order unblocked |

## Revision History

| Rev | Date | Notes |
|---|---|---|
| 1 | 2026-10-17 | first issue |
