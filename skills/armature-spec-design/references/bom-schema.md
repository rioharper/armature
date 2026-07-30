# Design-driver BOM — schema

`docs/bom.yaml` captures the *major* items whose specifications constrain the design — actuators, gearboxes, bearings, drive electronics, power source, structural materials — with the datasheet each number came from. It is intentionally short. The exhaustive procurement BOM (every fastener and standoff, with quantities and costs) belongs to detail design in **armature-writing-plans**.

Its one job: when the math, the CAD, or a review later trips over "wait, what's the rotor inertia?", the answer and its source are one glance away rather than reconstructed from memory.

It is YAML rather than a table because three consumers read it mechanically:

- **armature-mathematician** pulls inertias, torque limits, and material properties into `params.py`
- **armature-cad-parts** pulls bolt circles, bores, and widths into interface tables
- **armature-red-team**'s consistency checker asserts that the numbers in `params.py` still match the ones here

## Rules

- **One entry per design driver, not per SKU.** Include an item only if at least one of its numbers shapes a decision. A shoulder actuator belongs here; the M3 screws holding its cover do not.
- **Only the parameters that drive the design**, each with units and the value straight off the datasheet — not every field the datasheet prints.
- **Every number has a source and a status.** `confirmed` (datasheet retrieved, user agrees it's the right part), `tbd` (needed, not yet sourced — must also appear in the spec's open questions and `.armature/state.md`), or `assumed` (placeholder to keep moving, flagged as risk). There is no fourth option; a bare number with no status is the exact failure this file prevents.
- **Tie drivers back to requirements** via `drives`, so the link survives.
- **`params_key` is the drift guard.** When a value is also consumed by the model, name the `params.py` key that holds it. The consistency checker compares them and fails when they disagree — which is how a motor swap that never reached the derivation gets caught.

## Schema

```yaml
project: ibex
rev: 0.3
spec: docs/spec.md
frozen_at: freeze/ibex-bom        # tag, once locked

actuation:
  - id: hip-actuator
    part: CubeMars AK60-6
    datasheet: refs/datasheets/cubemars-ak60-6.pdf
    status: confirmed
    drives: [REQ-004, REQ-011]
    params:
      stall_torque:      { value: 9.0,     unit: "N*m" }
      cont_torque:       { value: 3.0,     unit: "N*m",     params_key: tau_hip_max }
      rotor_inertia:     { value: 6.4e-5,  unit: "kg*m^2",  params_key: J_rotor_hip }
      mass:              { value: 0.32,    unit: "kg",      params_key: m_hip_actuator }
      max_current:       { value: 12.0,    unit: "A" }
      bus_voltage:       { value: 24.0,    unit: "V" }

  - id: hip-gearbox
    part: integrated 6:1 planetary
    datasheet: refs/datasheets/cubemars-ak60-6.pdf
    status: confirmed
    drives: [REQ-004]
    params:
      ratio:       { value: 6.0,   unit: "-",      params_key: n_hip }
      backlash:    { value: 15.0,  unit: "arcmin" }
      efficiency:  { value: 0.85,  unit: "-",      params_key: eta_hip }

power:
  - id: battery
    part: <vendor + P/N>
    datasheet: refs/datasheets/<file>.pdf
    status: tbd
    drives: [REQ-018]
    params:
      nominal_voltage:  { value: 24.0, unit: "V" }
      capacity:         { value: null, unit: "W*h" }
      max_discharge:    { value: null, unit: "A" }
      mass:             { value: null, unit: "kg" }
    resolve: "vendor query — needs to close before T4.3 releases the tray drawing"

structure:
  - id: link-stock
    part: 6061-T6, 3 mm plate
    datasheet: refs/datasheets/matweb-6061-t6.pdf
    status: confirmed
    drives: [REQ-007]
    params:
      yield_strength: { value: 276.0,  unit: "MPa" }
      modulus:        { value: 68.9,   unit: "GPa" }
      density:        { value: 2700.0, unit: "kg/m^3", params_key: rho_link }

bearings:
  - id: main-bearing
    part: <P/N>
    datasheet: refs/datasheets/<file>.pdf
    status: confirmed
    drives: [REQ-009]
    params:
      bore:              { value: 12.0,  unit: "mm" }
      outer_diameter:    { value: 28.0,  unit: "mm" }
      width:             { value: 8.0,   unit: "mm" }
      dynamic_load_C:    { value: 6.8,   unit: "kN" }
```

## Notes on fields

- **Top-level keys** group by subsystem: `actuation`, `power`, `structure`, `bearings`, `sensing`, `electronics`. Add groups as the project needs; keep them stable once the checker is running against them.
- **`id`** is stable and referenced elsewhere (part definitions, findings). Rename it and you break the links.
- **`value: null`** is how a `tbd` entry holds its shape — the parameter is known to be needed, the number isn't known yet. The checker treats a null on a `confirmed` entry as an error.
- **`resolve`** on a `tbd` entry states the plan and the gate it must close before. Mirror it into `.armature/state.md` under Open.
- **`unit`** strings are SymPy/Pint-parseable ASCII (`N*m`, `kg*m^2`, `W*h`) so the checker can compare dimensions rather than just numbers.

Revision history lives in `git log`, not in the file.
