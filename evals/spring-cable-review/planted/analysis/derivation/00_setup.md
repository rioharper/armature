# Bob-on-a-cable rig — Milestone 0: setup

Rev 1 — 2026-10-17 — accompanies `analysis/model/mechanism.py`, `params.py`, `mechanism_checks.py`; the variant DR-01 reads is `first_mode.DERIVED`

## The system

A 0.5 kg bob rides a vertical slide, z along +z, and hangs on a cable from an anchor 1.0 m above its home. The cable's rest length is 0.99 m and its stiffness EA / l₀ is k = 1000 N/m, so at home it is stretched 10 mm and pulls the bob up. Gravity is −z, 9.81 m/s². Nothing actuates the bob: the slide only guides it, and the position loop of the spec moves the anchor, which this derivation does not model.

The question the spec hands derive is R-4: every mode of the rig at or above 10 Hz, five times the position loop's 2 Hz crossover. The measured quantity is the frequency of a free oscillation of the bob on the slide, read by the slide's encoder after a tap.

## Assumptions

| # | Assumption | Reduction | Released? |
|---|---|---|---|
| A1 | The slide is frictionless. | none | Not released: the description gives the slide no friction; adding it means a `frictionloss` on z from the slide's datasheet, which is not in hand, scoped with the slide's purchase. Friction only damps the mode, it does not move it. |
| A2 | The anchor is rigid. | none | Not released: the anchor's compliance is not in the description; releasing it means a body for the anchor on a slide of its own with the frame's stiffness, which waits on the frame's CAD. |
| A3 | The cable is inextensible. | `rigid("hang", assumption="A3")` | `test_truth_release_a3_on_the_sag` — rigid hang (A3), −4.905 mm at rest. Sized and kept: under a twentieth of the slide's 200 mm travel. |

A3 is the one reduction the variant makes. Released in the truth model, the elastic cable lets the bob settle 4.905 mm lower than the rigid one holds it, which is m g / k, as (2) below predicts. That moves no posture the rig works at, so A3 stands.

## Home posture and frames

Home is the bob at z = 0 on the slide, the anchor at (0, 0, 1.0) m. One frame, the base, z up; the bob's frame is the base translated by z.

| Element | At home, base frame |
|---|---|
| slide z | axis (0, 0, 1) through the origin, range ±0.1 m |
| bob | mass 0.5 kg, COM at the origin, a 10 mm sphere's inertia |
| cable `hang` | from the world at (0, 0, 1.0) m to the bob's COM, rest length 0.99 m, EA = k l₀ |

## Parameters

| Symbol | Value | Unit | Source |
|---|---|---|---|
| m | 0.5 | kg | spec |
| k | 1000 | N/m | spec, EA / l₀ of the chosen cable |
| drop | 1.0 | m | spec |
| l₀ (rest) | 0.99 | m | spec |
| g | 9.81 | m/s² | the engine's default |

## The rest

The bob rests where the cable's tension carries its weight. While taut the cable pulls with

$$T = k\,(\text{drop} - z - l_0), \tag{1}$$

so T = m g puts the bob at

$$z_\text{rest} = \text{drop} - l_0 - \frac{m g}{k} = 5.095\ \text{mm}. \tag{2}$$

I expected the 10 mm pre-stretch to be mostly taken up by the weight, and it is: 4.905 mm of it. `test_truth_the_bob_hangs_where_the_cable_carries_its_weight` settles the truth model from home and finds the bob at 5.095 mm with the cable at 4.905 N, confirming (2) to 1e-6 m.

## The truth model

`mechanism.truth()` compiles the full description, the cable elastic. `uv run python run_all.py` runs both checks above, the A3 release in `first_mode_checks.py`, and the gates.

## Revision note

Rev 1: first issue, with DR-01.
