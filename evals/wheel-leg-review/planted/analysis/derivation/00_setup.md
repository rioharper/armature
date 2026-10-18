# Wheel-legged robot, one leg on its rig — Milestone 0: setup

Rev 1 — 2026-10-17 — accompanies `analysis/model/mechanism.py`, `params.py`, `mechanism_checks.py`; DR-01 reads the description with the knee's skid pad added, `skid.skidded`, no reduction

## The system

The torso rides an x-y carriage on the rig. Under it a five-bar leg, driven at the hips A and E by two geared motors, carries a hub-driven wheel at the pin C, and the wheel stands on a level floor. The knee B carries a skid pad there to take a fall: a rubber sphere of radius `R_SKID` = 90 mm, fixed to link l1 and centred on B. The description does not carry the pad; DR-01 adds it as a contact against the floor. Gravity is −y, 9.81 m/s², and every hinge turns about z.

The question the plan hands derive is R-5: with the tyre on the floor, the skid pad stays clear of the floor everywhere in the hips' working range, `WORKSPACE` in `params.py`, A ∈ [−1, 1] rad and E ∈ [−0.5, 2] rad. The measured quantity is the pad's clearance above the floor, the gap between the sphere and the floor plane, with the torso at the height that puts the tyre on the floor.

## Assumptions

| # | Assumption | Reduction | Released? |
|---|---|---|---|
| A1 | The floor is level and rigid, and the tyre is rigid: the hub stands one wheel radius above the floor. | none | Not released: the description gives the tyre and floor no compliance; the tyre's radial stiffness is not in hand, and a soft tyre would only lower the hub by its static deflection, a millimetre or so. |
| A2 | The carriage carries no weight but its own rail cart. | none | Not released: the description has the rail cart alone on the carriage, and the wheel carries the rest; `test_truth_the_tyre_carries_the_weight` confirms it at 49.05 N. |
| A3 | First contact is checked at α = 0, the leg straight under the hips. | none: a scope for the search | Not a reduction. DR-01 searches the clearance over every posture at α = 0 inside `WORKSPACE`, 81 of them from the shortest leg to the longest (`skid.straight()`, `SKID_AT_ALPHA_ZERO`): the least is 50.79 mm, clear. |

α is the leg's angle, from straight down, of the pin C seen from the midpoint of the hips. The leg is shortest and longest at α = 0, and the knee comes lowest relative to the wheel where the leg is shortest, so that is where the pad comes nearest the floor; A3 is the spec's own scope for that.

## Home posture and frames

Home is every coordinate at 0: the hips A = (−0.05, 0) and E = (0.05, 0) m in the torso's frame, the knee B at (−0.10, −0.10) m, D at (0.11, −0.09) m and the pin C at (0, −0.25) m, the hub one wheel radius, 60 mm, above the floor. One frame, the base, x along the rail and y up; the torso's frame is the base translated by the carriage.

## Parameters

From `params.py`: link masses l1 0.30, l2 0.45, l3 0.35, l4 0.50 kg; torso 3.0 kg, wheel 0.4 kg, rail cart 0.2 kg; wheel radius r = 60 mm; the pad's radius R_SKID = 90 mm; g = 9.81 m/s².

## The pad's clearance

With the tyre on the floor the pin C sits r above it, so the pad, a sphere of radius r_skid round B, clears the floor by

$$h = B_y - C_y + r - r_\text{skid}, \tag{1}$$

with B turned about A by the hip angle on l1 and C from the five-bar's loop. At home B is 150 mm above C, so h = 150 + 60 − 90 = 120 mm, and `test_truth_the_pad_clears_the_floor_by_the_closed_form_at_home` reads the engine's clearance there at 120.000 mm.

## The weight on the tyre

Everything but the rail cart stands on the tyre, so at home its normal load is

$$N = g\,(m_\text{torso} + m_\text{wheel} + m_{l1} + m_{l2} + m_{l3} + m_{l4}) = 49.05\ \text{N}, \tag{2}$$

which `test_truth_the_tyre_carries_the_weight` confirms against the truth model's `inverse` to 1e-9 N.

## The truth model

`mechanism.truth()` compiles the full description, the tyre against the floor. `uv run python run_all.py` runs both checks above, the skid's checks and margin in `skid_checks.py` and `skid.py`, and the gates.

## Revision note

Rev 1: first issue, with DR-01.
