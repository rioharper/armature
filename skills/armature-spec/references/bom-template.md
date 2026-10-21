# Design-Driver BOM Template

This captures the *major* items whose specifications constrain the design — actuators, gearboxes, bearings, drive electronics, power source, and the structural materials — together with the datasheet each number came from. It is intentionally short. The exhaustive procurement BOM (every fastener, standoff, and connector, with quantities and costs against budget) belongs to detail design in **armature-plan**.

The one job of this file: when the kinematics math, the CAD, or a design review later trips over "wait, what's the rotor inertia?" or "can this bracket take that moment?", the answer and its source are one glance away — not reconstructed from memory.

## Rules

- **The numbers live in the ledger, and the table is its view.** Each design-driving number is an entry `part.<pn>.<field>` in `ledger.toml` (ADR 0010), and the table between `<!-- ledger:bom -->` and `<!-- /ledger -->` is one row per entry, which `py -m armature.ledger render` rewrites and `check` fails when edited by hand. A part's entry that reads another's is `of = "part.<pn>.<field>"`, never a copy. The prose around the table (the section's design notes, the open questions) is yours.
- **One part per design driver, not per SKU.** Include an item only if at least one of its numbers actually shapes a decision. A shoulder actuator belongs here; the M3 screws holding its cover do not.
- **List only the parameters that drive the design**, each in SI with the quantity as the datasheet printed it in `as_written`, which `check` converts and holds to the value — not every field the datasheet prints. For a motor, driver, gearbox and the bus, that is what `drive.py` reads, each with its basis in `basis` (armature-derive's `references/derivation-standards.md`, *Actuators and the bus*); yield, modulus, and density for a metal; not the full electrical schematic.
- **Every number has a source and a status.** Its source is one of the ledger's six kinds: `datasheet` (the index row's P/N and `retrieved`, for a vendor PDF or a distributor page), `standard` (a handbook or standard, cited to its table), `estimate` (a placeholder used to keep moving, its `ref` saying what it rests on, with a band, and flagged as risk), `cad`, `measured`, or `chosen`. Its status is `candidate` until the user agrees it is the right part and the right number, then `confirmed`. A number needed and not yet sourced has no entry yet: it is an open question, below and in the spec's Open Questions.
- **Tie drivers back to requirements.** If a number exists because a requirement demands it (REQ-014 wants ≥2 N·m at the wrist), name the requirement in the entry's `note`; the Drives column adds every entry that reads the number and the REQ each budget among them answers to.

## Structure

```markdown
# [Project Name] — Design-Driver BOM
Rev 0.1 — [date] — companion to [spec file], Rev [x]

## 1. Design drivers
Item is the entry's note: name the item there ("shoulder actuator", "link
stock") and the requirement that wants the number.

<!-- ledger:bom -->
| Item | Part / spec | Parameter | Value | As written | Source | Status | Drives |
| --- | --- | --- | --- | --- | --- | --- | --- |
<!-- /ledger -->

What each kind of item carries:
- **Actuator:** Kt (motor side), Ke (with its basis, line or phase, rms or
  peak), R (line, at 25 °C), wye or delta, continuous and peak current,
  R_th, C_th, T_max, rotor J, mass.
- **Gearbox:** ratio, rated τ, backlash, efficiency forward and backward,
  mass.
- **Battery or PSU:** whether it **sinks** (a pack) or **cannot sink** (a
  PSU, a PSU behind a diode), V band, max power, overvoltage trip, capacity,
  mass.
- **Motor driver:** peak and continuous current, over- and undervoltage
  trips, efficiency, flux brake (I_d, onset V), on-board bus capacitance,
  comms.
- **Brake resistor:** R, switching threshold, pulse energy, continuous
  power.
- **Bus capacitance:** capacitance and its tolerance band, voltage rating.
- **Structure and bearings:** yield, E and ρ for a stock; practical
  layer-adhesion strength and Tg for a print (an `estimate` until a test
  print measures it); bore, dynamic load rating C and max speed for a
  bearing.

## 2. Open sourcing questions
Every number still needed and not yet entered, and every `candidate` row
above, restated with a plan to resolve (request from user, vendor query,
test print, measurement) and a date/gate by which it must close. Mirror
these into the spec's Open Questions section so nothing falls between the
two documents.

## Revision History
| Rev | Date | Notes |
```
