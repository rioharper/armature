# Derivation Report DR-02: the 24 V PSU needs no regeneration path

Rev 1 — 2026-10-17 — plan task DR-02, Executor: armature-derive

**Status:** complete. The 24 V, 120 W PSU behind its diode, with the drivers' own 1 mF, needs no brake resistor and no extra capacitance. The balanced arm draws no static current, and the e-stop at jog speed lifts the bus to 28.99 V, 15.0 V under the drivers' 44 V trip. R-7 holds; no number in the spec moves.

## Purpose

The plan hands derive one decision: is the PSU that A3 sizes for the static current enough, with no regeneration path, or does the bus need a brake resistor or more capacitance? R-7 bounds the bus voltage at the drivers' terminals by their 44 V overvoltage trip (00_setup.md, *The system*).

## Method

`analysis/model/bus.py` (rev 1) declares the drive margins, `armature.drive.margins`, on `drive.py`'s PSU over the stop below, and `run_all.py` searches them; it also computes the bus's peak with nothing tripped, by `charge` on the stop's trace at 1 kHz. `uv run python report_dr02.py` prints every table here, and `uv run python run_all.py` runs every check behind them. The model reads the full description, with the drive and missions from the spec stage.

## The decision: no regeneration path is needed

The PSU sits behind a diode, so it cannot sink: whatever a stop returns lands on the bus capacitance alone. The static current is zero, because the arm is balanced (00_setup.md (1)), so the one load on the bus that matters is regeneration.

### Regeneration

The stop sized is the e-stop at jog speed: the operator stops the arm while jogging it, J1 braked from its 1 rad/s jog speed to rest in 0.1 s at constant deceleration, φ held (`bus.JOG_STOP`). With φ held the forearm translates and the coupler turns with θ1 about C, so J1 brakes the inertia

$$J_{11} = 2I + m_1 r_1^2 + m_4 r_4^2 + m_2 a^2 + N_1^2 J_m, \tag{1}$$

and gives up its kinetic energy

$$E = \tfrac{1}{2} J_{11} \omega_0^2. \tag{2}$$

If all of it reached the capacitance, the bus would rise to

$$V \le \sqrt{V_0^2 + J_{11}\omega_0^2 / C}, \tag{3}$$

an upper bound, since the windings' copper loss takes some of E first. I expected the jog stop to land well under the trip, and it does: `test_truth_j11_is_the_truth_models_inertia_about_j1` confirms (1) against the truth model's mass matrix, and `test_truth_the_jog_stop_lifts_the_bus_under_its_bound` finds the peak 1.9 % under (3).

> **The bus peaks at 28.99 V in the jog e-stop, 15.0 V under the 44 V trip. The PSU needs no regeneration path.**

## Results

| Quantity | Value | From |
|---|---|---|
| J11 | 0.2965 kg m² | bus.j11(), (1) |
| jog speed | 1 rad/s | bus.JOG_SPEED |
| ½ J11 ω0² | 0.1483 J | (2) |
| returned to the bus | 0.1322 J | ½ C (V² − V0²) at the peak |
| bus peak, nothing tripped | 28.99 V | bus.peak(JOG_STOP) |
| lossless bound | 29.54 V | bus.bound(), (3) |
| lowest trip | 44 V | each driver's max_voltage |
| capacitance needed | 0.194 mF, against 1 mF fitted | bus.needed() |

The drive margins, as `run_all.py` prints them: the bus's peak V passes by 15.01 V against every driver's 44 V, its minimum V by 14 V, the source's power by 119.8 W, and each driver's peak current and each motor's envelope pass. The two windings stand UNCHECKED under `DRIVE_EXEMPT`, each with its reason: no thermal RC is in hand, and a balanced arm carries no holding current.

## The write-back

| Number | was | now | where it changed |
|---|---|---|---|
| R-7 status | open | met | `docs/01-spec/traceability.md` |
| brake resistor | TBD | none | `docs/01-spec/bom.md` |

## Assumptions under strain

| Assumption | Direction and size | Closed by |
|---|---|---|
| A2, lossless gearboxes and drivers | losses only lower the peak; lossless is the high side | this report |
| the motors' thermal RC | not in hand; the windings stand exempt | librarian, before CAD |

## Items routed here, and where each closed

| Routed by | Item | Closed |
|---|---|---|
| plan, DR-02 | does A3's PSU need a regeneration path? | no, above |

## Feeds

| Target | Update |
|---|---|
| `docs/01-spec/traceability.md` | R-7: analyzed, DR-02 |
| `docs/decisions.md` | PSU: 24 V, 120 W behind a diode, no brake resistor |

## Revision History

| Rev | Date | Notes |
|---|---|---|
| 1 | 2026-10-17 | first issue |
