# Camera arm — Milestone 0: setup

Rev 1 — 2026-10-17 — accompanies `analysis/model/mechanism.py`, `params.py`, `mechanism_checks.py`, with `drive.py` and `missions.py` from the spec stage; DR-02 reads the full description, no variant

## The system

A balanced parallelogram arm in a vertical plane, gravity −y. The upper arm turns about O on J1 and carries the forearm at its far end P; the forearm's direction is set by a crank on J2, also at O, through a coupler parallel to the upper arm, so O, P, Q and C stay a parallelogram and the forearm turns with the crank. Counterweights on the upper arm and the crank put the arm's moment of mass at zero. Each joint has a geared motor (N1 = 50, N2 = 30) and its own driver; both drivers share a DC bus with 1 mF of capacitance, fed by a 24 V, 120 W PSU behind a diode.

The question the plan hands derive is DR-02: the PSU and the bus, against R-7, the bus never reaching a driver's 44 V overvoltage trip. The measured quantity is the bus voltage at the drivers' terminals, which is what each driver trips on.

## Assumptions

| # | Assumption | Reduction | Released? |
|---|---|---|---|
| A1 | The arm is balanced: no gravity torque at any posture. | none: a claim about `params.py`'s counterweights | Not a reduction. Checked in the truth model by `test_truth_the_balanced_arm_needs_no_holding_torque`: the largest holding torque is 8.6e-15 N m over n = 24 postures, seed 20260915. |
| A2 | The gearboxes and drivers are lossless. | none | Not released: neither efficiency is published for these parts, so both are 1.0 in `params.DRIVE`. Lossless returns the most energy to the bus, so A2 errs high on regeneration. |
| A3 | The PSU is sized for the static current, with no regeneration path. | none: a sizing claim | Not a reduction. DR-02 checks it on the e-stop at jog speed: the bus peaks at 28.99 V, under the 44 V trip. |

## Home posture and frames

Home is θ1 = 0, the upper arm along +x, and φ = π/2, the crank along +y, so O = (0, 0), P = (a, 0), C = (0, c) and Q = (a, c). J2's coordinate is φ − π/2. Every hinge is about z.

## Parameters

From `params.py`: a = 0.40 m, b = 0.35 m, c = 0.08 m, r2 = −0.15 m, r4 = 0.20 m, m1 = 3.0 kg, m2 = 1.0 kg, m3 = 2.0 kg, m4 = 0.3 kg, I = 2e-3 kg m² per body, J_m = 2e-5 kg m² per rotor, N1 = 50, N2 = 30, g = 9.81 m/s². The counterweights' COMs, r1 and r3, are solved from the balance below. The drive's numbers are `params.DRIVE`, each with its basis.

## The balance

Every body's COM moves with u(θ1), the upper arm's direction, or u(φ), the crank's, so the arm's moment of mass is B1 u(θ1) + B2 u(φ) with

$$B_1 = m_1 r_1 + m_4 r_4 + m_2 a = 0, \qquad B_2 = m_3 r_3 + m_4 c + m_2 r_2 = 0. \tag{1}$$

Solving (1) for r1 and r3 leaves no gravity torque anywhere, which I expected to hold to rounding, and the truth check confirms it: 8.6e-15 N m at worst. The static current is therefore zero, which is what A3 sizes the PSU against.

## Revision note

Rev 1: first issue, with DR-02.
