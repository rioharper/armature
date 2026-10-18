# Cable camera platform — Milestone 0: setup

Rev 1 — 2026-10-17 — accompanies `analysis/model/mechanism.py`, `params.py`, `mechanism_checks.py`; the variant DR-01 reads is `deck.DERIVED`

## The system

A 2 kg platform hangs from four cables, one from each top corner of a 4 m square frame at 2.4 m, and a winch on each cable sets its length. The platform's four attachment points are a 0.15 m square, a scaled copy of the anchor square, and its COM sits 0.10 m below their centre. Each cable is an elastic tie of axial stiffness EA = 44 kN that cannot push. Gravity is −z, 9.81 m/s².

The question the plan hands derive is R-2: the deck within 2° of level wherever the camera stops, the gimbal's correction range. The measured quantity is the deck's tilt, the angle between the platform's axis and the vertical, read by the gimbal's IMU at a stop. DR-01 decides it at the edge midpoint, `POSE` = (0.5, 2.0, 1.2) m, on the rest lengths in `params.py` that the tension law pays out there.

## Assumptions

| # | Assumption | Reduction | Released? |
|---|---|---|---|
| A1 | Each cable is a straight elastic tie that cannot push: no sag, no mass. | none | Not released: the description models each cable as exactly this; sag would need the cable's mass per metre, not in hand until the cable is chosen. At 2 kg on four cables the catenary sag is a few millimetres. |
| A2 | The frame and its anchors are rigid. | none | Not released: the frame's stiffness waits on its CAD; releasing it means bodies for the anchors on springs of the frame's stiffness. |
| A3 | The platform stays level: the cables only translate it. | `lock("hang:rx"/"hang:ry"/"hang:rz", 0.0, assumption="A3")` | `test_truth_release_a3_at_the_room_centre`: the full description, free to turn, hung at the room centre on the law's rest lengths there, turns the deck by under 1e-13°. Sized and kept: under a tenth of R-2's 2°. |

A3 is the one reduction the variant makes. The attachment square is a scaled copy of the anchor square, so with four cables pulling toward four anchors placed the same way the platform has no preferred turn, and the release confirms it: freed of the locks, the platform hangs exactly as level as the variant holds it. A3 stands.

## Home posture and frames

Home is the platform hung at the room centre, `HOME` = (2.0, 2.0, 1.2) m, level. One frame, the base, z up; the platform's frame is the base translated to its point, the attachment square's centre, and turned by the free joint `hang`.

| Element | At home, base frame |
|---|---|
| free joint `hang` | the platform's point at (2.0, 2.0, 1.2) m |
| platform | mass 2.0 kg, COM 0.10 m below the point, 0.02 kg m² about each axis |
| cable `c1`…`c4` | from the anchors (0, 0), (4, 0), (4, 4), (0, 4) at 2.4 m to the attachment corners (±0.075, ±0.075) m about the point |

## Parameters

| Symbol | Value | Unit | Source |
|---|---|---|---|
| m | 2.0 | kg | spec |
| EA | 44 000 | N | spec, the chosen cable |
| l0_1 … l0_4 | 2.3070, 4.1077, 4.1077, 2.3070 | m | `params.py`, the tension law at `POSE` |
| g | 9.81 | m/s² | the engine's default |

## The level-platform law at the room centre

The tension law balances the platform's weight on the cables' force rows, with the platform level. At the room centre the rig is symmetric, so the four cables share the weight equally: cable i, of length L from its corner to its anchor and rising h, pulls along its own direction with a vertical share h/L, so

$$4\,T\,\frac{h}{L} = m g, \qquad T = \frac{m g L}{4h}, \tag{1}$$

and the winch pays out the rest length that stretches it to T,

$$l_0 = \frac{L}{1 + T/EA}. \tag{2}$$

That is 12.161 N in each cable on a 2.9743 m rest length. I expected the truth model, hung there level, to stay put on these, and it does: `test_truth_the_centre_hangs_on_four_equal_tensions` settles it and reads each tension at (1) to 1e-6, the platform moved by under 1e-6 m.

## The truth model

`mechanism.truth()` compiles the full description, the platform free to turn. `uv run python run_all.py` runs the check above, the A3 release in `deck_checks.py`, and the gates.

## Revision note

Rev 1: first issue, with DR-01.
