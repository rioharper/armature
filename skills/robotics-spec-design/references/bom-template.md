# Design-Driver BOM Template

This captures the *major* items whose specifications constrain the design — actuators, gearboxes, bearings, drive electronics, power source, and the structural materials — together with the datasheet each number came from. It is intentionally short. The exhaustive procurement BOM (every fastener, standoff, and connector, with quantities and costs against budget) belongs to detail design in **robotics-writing-plans**; do not try to make this that.

The one job of this file: when the kinematics math, the CAD, or a design review later trips over "wait, what's the rotor inertia?" or "can this bracket take that moment?", the answer and its source are one glance away — not reconstructed from memory.

## Rules

- **One row per design driver, not per SKU.** Include an item only if at least one of its numbers actually shapes a decision. A shoulder actuator belongs here; the M3 screws holding its cover do not.
- **List only the parameters that drive the design**, each with units and the value straight off the datasheet — not every field the datasheet prints. Stall torque, continuous torque, rotor inertia, mass, and max current for a motor; yield, modulus, and density for a metal; not the full electrical schematic.
- **Every number has a source and a status.** Source is the exact part number and where the datasheet came from (vendor PDF, distributor page). Status is one of: **Confirmed** (datasheet in hand, user agrees it's the right part), **TBD** (needed, not yet sourced — must also appear in the spec's Open Questions), or **Assumed** (a placeholder value used to keep moving, flagged as risk). No fourth option; a bare number with no status is the exact failure this file prevents.
- **Tie drivers back to requirements.** If a number exists because a requirement demands it (REQ-014 wants ≥2 N·m at the wrist), name the requirement so the link survives.

## Structure

```markdown
# [Project Name] — Design-Driver BOM
Rev 0.1 — [date] — companion to [spec file], Rev [x]

## 1. Actuation & drive
| Item | Part / spec | Design-driving parameters | Source | Status | Drives |
|------|-------------|---------------------------|--------|--------|--------|
| Shoulder actuator | [vendor + P/N] | stall τ = X N·m, cont. τ = Y N·m, rotor J = Z kg·m², mass = M kg, max I = A A @ V V | [datasheet, P/N] | Confirmed | REQ-0xx |
| Gearbox | ... | ratio, rated τ, backlash (arcmin), efficiency, mass | ... | ... | ... |

## 2. Power & electronics
| Item | Part / spec | Design-driving parameters | Source | Status | Drives |
| Battery | ... | chemistry, V nominal, capacity Wh, max continuous discharge A, mass | ... | ... | ... |
| Motor driver | ... | max continuous/peak current, bus voltage range, comms | ... | ... | ... |

## 3. Structure & bearings
| Item | Part / spec | Design-driving parameters | Source | Status | Drives |
| Link stock | 6061-T6, 3 mm plate | yield 276 MPa, E 68.9 GPa, ρ 2700 kg/m³ | [matweb / mill cert] | Confirmed | REQ-0xx |
| Printed bracket | PETG, 0.2 mm, 4 walls | practical layer-adhesion strength, Tg ~80 °C | [test print / vendor] | Assumed | REQ-0xx |
| Main bearing | ... | bore, dynamic load rating C, max speed | ... | ... | ... |

## 4. Open sourcing questions
Every TBD row above, restated with a plan to resolve (request from user,
vendor query, test print, measurement) and a date/gate by which it must
close. Mirror these into the spec's Open Questions section so nothing
falls between the two documents.

## Revision History
| Rev | Date | Notes |
```
