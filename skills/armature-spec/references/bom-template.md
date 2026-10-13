# Design-Driver BOM Template

This captures the *major* items whose specifications constrain the design — actuators, gearboxes, bearings, drive electronics, power source, and the structural materials — together with the datasheet each number came from. It is intentionally short. The exhaustive procurement BOM (every fastener, standoff, and connector, with quantities and costs against budget) belongs to detail design in **armature-plan**.

The one job of this file: when the kinematics math, the CAD, or a design review later trips over "wait, what's the rotor inertia?" or "can this bracket take that moment?", the answer and its source are one glance away — not reconstructed from memory.

## Rules

- **One row per design driver, not per SKU.** Include an item only if at least one of its numbers actually shapes a decision. A shoulder actuator belongs here; the M3 screws holding its cover do not.
- **List only the parameters that drive the design**, each with units and the value straight off the datasheet — not every field the datasheet prints. For a motor, driver, gearbox and the bus, that is what `drive.py` reads, each with its basis (armature-derive's `references/derivation-standards.md`, *Actuators and the bus*); yield, modulus, and density for a metal; not the full electrical schematic.
- **Every number has a source and a status.** Source is the exact part number and where the datasheet came from (vendor PDF, distributor page). Status is one of: **Confirmed** (datasheet in hand, user agrees it's the right part), **TBD** (needed, not yet sourced — must also appear in the spec's Open Questions), or **Assumed** (a placeholder value used to keep moving, flagged as risk). No fourth option.
- **Tie drivers back to requirements.** If a number exists because a requirement demands it (REQ-014 wants ≥2 N·m at the wrist), name the requirement so the link survives.

## Structure

```markdown
# [Project Name] — Design-Driver BOM
Rev 0.1 — [date] — companion to [spec file], Rev [x]

## 1. Actuation & drive
| Item | Part / spec | Design-driving parameters | Source | Status | Drives |
|------|-------------|---------------------------|--------|--------|--------|
| Shoulder actuator | [vendor + P/N] | Kt = X N·m/A_rms (motor side), Ke = Y V_rms/krpm (line), R = Z Ω (line, 25 °C), wye, cont./peak I = A A_rms / B A_peak, R_th = K/W, C_th = J/K, T_max = °C, rotor J = kg·m², mass = M kg | [datasheet, P/N] | Confirmed | REQ-0xx |
| Gearbox | ... | ratio, rated τ, backlash (arcmin), efficiency forward and backward, mass | ... | ... | ... |

## 2. Power & electronics
| Item | Part / spec | Design-driving parameters | Source | Status | Drives |
| Battery or PSU | ... | source type: **sinks** (a pack) or **cannot sink** (a PSU, a PSU behind a diode); V band, max power W, overvoltage trip, capacity Wh, mass | ... | ... | ... |
| Motor driver | ... | peak and continuous current (A_rms or A_peak), over- and undervoltage trips, efficiency, flux brake (I_d, onset V), on-board bus capacitance, comms | ... | ... | ... |
| Brake resistor | ... | R Ω, switching threshold V, pulse energy J, continuous power W | ... | ... | ... |
| Bus capacitance | ... | capacitance and its tolerance band, voltage rating | ... | ... | ... |

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
