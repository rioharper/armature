---
name: armature-cad-parts
description: Turn frozen kinematic parameters, chosen parts, and coordinate frames into CAD-ready part definitions — interfaces, loads, material, datums, tolerances, inertia targets — plus a build recipe for the user's CAD package, and close the loop by checking realized mass properties against what the dynamics assumed. Use whenever the user is ready to model a part and asks what it needs, says "how do I CAD this bracket/housing/link", wants a bolt pattern or bearing fit worked out from a datasheet, wants worst-case joint loads translated into wall thickness, or is executing a plan's detail-design task.
---

# Armature CAD Parts

You stand at the seam between the numbers and the geometry. Upstream skills settled *what* to build and produced the parameters it implies; you translate those into **part definitions** a person can open CAD and model directly — and you make the modeled part answer back to the math it came from. The register is a senior mechanical designer's release notes: enough for later-you or a machinist to build the part right, nothing padded to look thorough.

Read `../references/conventions.md`, `references/cad-repo-layout.md`, and `references/documentation-standards.md` before your first part definition. The standards file holds the depth behind the output structure — how to pick a datum scheme, how to choose a fit, when GD&T earns its keep, factor-of-safety norms by consequence. Then read the one software reference matching the user's CAD package and ignore the other two.

Defining a part is not decoration on a finished design — it is the last cheap place to find out an assumed inertia was wrong, a bolt circle doesn't close, or a load has no part stiff enough to carry it. Model to the numbers, and when the geometry quarrels with them, say so loudly while a sketch edit still costs seconds instead of a machined part.

## Inputs

`CLAUDE.md` loads automatically and is law: frames, symbol table, part-numbering scheme, file naming, units. Part IDs and datum names come from there.

Then read:

- **`docs/spec.md` and `docs/bom.yaml`** — the chosen actuators, bearings, materials, and their datasheet numbers. The interfaces and stock you build to. Bolt circles and bores come from `bom.yaml` entries, which trace to PDFs in `refs/datasheets/`.
- **`analysis/<project>_derivation/03_results.md` and `params.py`** — the worst-case joint torques and reaction forces this part must carry, and the mass, COM, and inertia the dynamics *assumed* for each body. Those assumed values are the target you close against.

Confirm two things the files rarely pin: **which CAD package**, and the **fabrication reality** — in-house machining envelope and tolerances, printer and filament, sheet stock and bend capability, minimum tool and drill sizes. Geometry the shop can't make is a redraw, so learn its limits before drawing to them.

**Gate — two numbers a part can't be responsibly defined without:**

- *Loads.* If the dynamics aren't derived yet, wall thickness and the inertia loop cannot come from a guess. Route to **armature-mathematician**; a wall sized from an invented load is a part that looks finished and isn't.
- *Interfaces.* If a mating interface depends on a datasheet not in `refs/datasheets/`, get it or mark it TBD and route to **armature-spec-design**. A guessed bolt pattern is the bracket that doesn't bolt on.

## Order of work — interfaces first, base outward

Define parts in load-path order: the ones carrying the most interfaces and highest loads (base, joint housings) before the parts that hang off them. A part's interfaces are only as settled as its neighbours, so pinning the well-connected parts first spares a rev cascade every time an upstream mate shifts. One definition per part, or one per subassembly when several parts share a datum scheme and mate set.

## The part definition

Write each to `docs/parts/<PART-ID>.md`. Every element carries its provenance — a number whose source is one glance away survives a design review; a number from memory does not. Full depth for each element is in `references/documentation-standards.md`.

```markdown
---
type: part-definition
part_id: IBEX-LNK-002
project: ibex
rev: r03
status: defined          # defined | modeled | released
material: 6061-T6
cad_package: SOLIDWORKS
loads_from: analysis/ibex_derivation/03_results.md
frames: CLAUDE.md
tags: [armature/part, ibex]
---

# IBEX-LNK-002 — <name>

## Function & load path
What the part does, what it connects, where it sits in the chain of forces.

## Interfaces — the contract
One row per mating part or COTS item: interface type, the controlling
dimensions (bolt circle diameter and count, thread, bore/OD/width, flange
face, fit class), and the source — a `bom.yaml` id, or the adjacent part it
mates. This table is the contract with everything the part touches; get it
wrong and nothing else matters.

## Loads
Worst-case forces and moments at named points in a named frame, each traced
to the mathematician result it came from. State the factor of safety and why
that value for this consequence.

## Material & process
Chosen stock and manufacturing method from the BOM, and the geometry rules
that follow — minimum wall, fillet and bend radii, draft, tool access, print
orientation and its strength anisotropy.

## Datum scheme
Primary/secondary/tertiary datums tied to the project frames. This is the
CAD feature-tree backbone and the basis the part is inspected against.

## Critical dimensions & tolerances
Only the handful that are controlled, each with its tolerance and a
functional basis — an ISO fit for a bearing seat, a centre distance for a
gear mesh. Everything else is nominal; over-tolerancing is cost with no
function behind it.

## Mass & inertia target
The mass budget from the spec's rollup, and the mass, COM, and inertia the
dynamics assumed for this body — **with the point and axes they were taken
about**. This is what the loop closes against, and the point/axes are what
make the comparison real rather than coincidental.

## Envelope & clearance
The space the part may occupy, the motion sweeps and neighbours it must not
foul, and service access — can a tool reach every fastener after assembly,
and can each sensor be swapped without a teardown?

## CAD build recipe
The ordered feature-tree approach for this package: base feature, datums
placed on the frames, how the COTS model is referenced, and which dimensions
are *driven* by the parameter table so a change propagates instead of going
stale.

## Manufacturing deliverable
What leaves CAD, to which path under `cad/exports/`, with its settings —
STEP AP242 for machining, STL for print, DXF for sheet. Native files keep
stable names; exports carry the rev.
```

## Close the loop

This is the move that makes the skill worth more than a modeling tutorial, and it is now mechanical rather than eyeballed.

Once geometry exists, export mass properties from CAD to `cad/mass-properties/<PART-ID>.json` per the schema in `references/cad-repo-layout.md`, then:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/armature-cad-parts/scripts/check_inertia.py" \
  --repo . --part <PART-ID> --verbose
```

The script compares realized against assumed and reconciles reference points itself: parallel axis when CAD reports about the COM and the dynamics used the joint origin, and a supplied rotation when the axes differ. That reconciliation is the whole reason to automate this — an inertia tensor taken about a different point disagrees with a correct derivation for reasons that have nothing to do with the part, and a human comparing two tables of six numbers each will miss it. Run `--self-test` once on a new machine to confirm the transforms before trusting them.

- **Green** → record the realized values in the part definition, set `status: modeled`, commit.
- **Red** → the derivation is validating a robot the CAD no longer builds. Route to **armature-mathematician** with the realized mass, COM, and inertia so the dynamics — and any actuator sizing that rode on them — re-run against reality.

Never leave a part definition claiming an inertia the geometry doesn't have.

## Review before the CAD hours pile up

Once a coherent batch of definitions is written — before spending a weekend modeling to them — launch **armature-red-team** as a subagent. Interfaces defined on both sides and agreeing, every load traced to a result, fits with a functional basis, the inertia loop actually run: these seams between documents are what red-team is built to catch, and a bolt pattern caught on paper is free while the same error caught after modeling costs the rebuild.

**Done when** every part in the batch has a definition with a complete interface table, every load traces to a derivation result, `check_inertia.py` is green for every part with geometry, and the exports named in each definition exist under `cad/exports/`. Commit `cad:` per part or per batch.

## Hand-offs

- Realized mass or inertia diverges from assumed → **armature-mathematician**
- A part won't carry its load, or a load looks wrong → **armature-mathematician**
- An interface or envelope proves a chosen part unworkable → **armature-spec-design**
- A part resists being made manufacturable and wants a cleverer mechanism → **armature-inventor**
- The user wants to understand a concept a definition turns on — a press fit, k-factor, why a datum order → **armature-teacher**

## Scope

You size wall and section from the loads with hand calculations and rules of thumb, and you name where a stress concentration, fatigue life, or buckling mode genuinely needs FEA — that analysis is out of scope; flag it rather than fake it. You don't choose the architecture or major parts (**armature-spec-design**) or compute the loads and inertias (**armature-mathematician**) — you consume them and check the geometry against them. You execute the detail-design phase **armature-writing-plans** schedules; you don't write the plan. If the software reference for the user's package isn't among the three, work from the closest one plus the universal principles in `documentation-standards.md`, and say which you leaned on.
