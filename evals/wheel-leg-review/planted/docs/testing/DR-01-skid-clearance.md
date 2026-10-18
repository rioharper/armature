# Derivation Report DR-01: the skid pad's clearance against R-5

Rev 1 — 2026-10-17 — plan task DR-01, Executor: armature-derive

**Status:** complete. R-5 holds: searched over every posture at α = 0 in the hips' working range, the skid pad never comes nearer the floor than 50.79 mm, with the tyre on it. No number in the spec moves.

## Purpose

The plan hands derive one decision: does the knee's skid pad stay clear of the floor everywhere in the hips' working range, `WORKSPACE`, with the tyre on the floor? The measured quantity is the pad's clearance, the gap between its sphere and the floor plane (00_setup.md, *The system*).

## Method

`analysis/model/skid.py` (rev 1) adds the skid pad to the description as a contact, a sphere of radius `R_SKID` round the knee B on l1 against the floor, and stands the leg on its tyre at each posture by lowering the torso by the tyre's gap. By A3 the first contact is checked at α = 0: `skid.straight()` walks hip A out from home to each end of its range in 40 steps, solving at each for the E that puts the pin C straight under the hips, and keeps the 81 postures inside `WORKSPACE`. `SKID_AT_ALPHA_ZERO` is the clearance margin over them, which `run_all.py` searches; its truth is (1) of 00_setup.md at the worst posture, and it agrees to 1e-3 mm. The tables below are printed by `uv run python report_dr01.py`; `uv run python run_all.py` runs every check behind them.

## The decision: R-5 holds

Over the leg's lengths at α = 0 the pad comes nearest the floor with the leg shortest, A = −1 rad: the knee folds down toward the wheel there, and the pad still clears the floor by 50.79 mm. I expected the shortest leg to be the worst, and it is; the margin passes at every posture searched (`test_r5_holds_at_alpha_zero`).

> **R-5: met.** Least skid clearance at α = 0: 50.79 mm, the tyre on the floor.

## Results

| Quantity | Value | From |
|---|---|---|
| least skid clearance at α = 0 | 50.79 mm | skid.SKID_AT_ALPHA_ZERO, searched |
| where it falls | A = −1.000, E = 1.201 rad | the same |
| postures searched at α = 0 | 81 | skid.straight() |
| clearance at home | 120.00 mm | skid.skid_mm(), (1) |

## The write-back

| Number | was | now | where it changed |
|---|---|---|---|
| R-5 status | open | met | `docs/01-spec/traceability.md` |

## Assumptions under strain

| Assumption | Direction and size | Closed by |
|---|---|---|
| A3, first contact at α = 0 | the scope of the search: 81 postures, every leg length in `WORKSPACE` | this report |
| A1, a rigid tyre | a soft tyre lowers the hub, and with it the pad, by its deflection, about a millimetre | the tyre's datasheet |

## Items routed here, and where each closed

| Routed by | Item | Closed |
|---|---|---|
| plan, DR-01 | does the skid pad clear the floor over the working range? | yes, above |

## Feeds

| Target | Update |
|---|---|
| `docs/01-spec/traceability.md` | R-5: analyzed, DR-01 |
| `docs/decisions.md` | skid pad R 90 mm kept |

## Revision History

| Rev | Date | Notes |
|---|---|---|
| 1 | 2026-10-17 | first issue |
