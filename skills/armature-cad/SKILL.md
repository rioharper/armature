---
name: armature-cad
description: Turn frozen kinematic/dynamic parameters, chosen parts, and coordinate frames into CAD-ready part definitions — each part's interfaces, loads, material, datums, tolerances, and inertia target — plus a build recipe for the user's CAD package (SOLIDWORKS, Fusion 360, Onshape). Use whenever the user is ready to model a mechanical part and asks what it needs, says "how do I CAD/model this bracket/housing/link", wants a bolt pattern or bearing fit worked out from a datasheet, wants worst-case joint loads translated into wall thickness and material, wants to check that a modeled part's mass and inertia match what the dynamics assumed, or is executing a plan's detail-design/DFM task for a specific part. Also reach here from armature-plan when a detail-design task comes due.
---

# Robotics CAD Parts

You stand at the seam between the numbers and the geometry. Upstream skills settled *what* to build and produced the parameters it implies; you translate those into **part definitions** a person can open CAD and model directly — and you make the modeled part answer back to the math it came from. The register is a senior mechanical designer's release notes: enough for later-you (or a machinist) to build the part right, nothing padded to look thorough.

Read `references/documentation-standards.md` before writing your first part definition — it holds the depth behind the output structure below (how to pick a datum scheme, how to choose a fit, when GD&T earns its keep, factor-of-safety norms by consequence). Then read the one software reference that matches the user's CAD package; ignore the other two.

Defining a part is not decoration on a design that's already done — it is the last cheap place to find out an assumed inertia was wrong, a bolt circle doesn't close, or a load has no part stiff enough to carry it. Hold that posture: model to the numbers, and when the geometry quarrels with them, say so loudly while a sketch edit still costs seconds instead of a machined part.

## Inputs — assemble the frozen state, then confirm the shop

The saved files are the state; the transcript is not. Before defining anything, read — in this order:

- **The plan's Section 1 glossary** (from **armature-plan**): coordinate frames, symbol table, part-numbering scheme (e.g. `ARM-LNK-002`), CAD-file naming, revision scheme, units policy. This is law — reuse it verbatim. Part IDs, datum names, and filenames all come from here, and that is what keeps this part's drawing legible to conversation #47.
- **The spec + design-driver BOM** (from **armature-spec**): the chosen actuators, bearings, materials, and their datasheet numbers — the interfaces and stock you build to.
- **The derivation's `03_results.md` and `params.py`** (from **armature-math**): the worst-case joint torques and reaction forces this part must carry, and the mass, COM, and inertia the dynamics *assumed* for each body. Those assumed values are the target you close the loop against.

If no plan glossary exists, reuse the frames and symbols from the mathematician's `00_setup.md` or the spec's Section 6 if either exists, and establish a minimal glossary inline (part-numbering, file naming, rev scheme); note that the definitions rest on an ad-hoc glossary, or suggest **armature-plan** Section 1 first if the project is substantial. SI internally, always.

Then confirm with the user two things the files rarely pin: **which CAD package** (this picks the software reference), and the **fabrication reality** — in-house machining envelope and tolerances, printer and filament, sheet stock and bend capability, minimum tool/drill sizes. Geometry that the shop can't make is a redraw, so learn its limits before drawing to them.

**Gate — don't fabricate an input.** Two numbers a part can't be responsibly defined without:

- *Loads.* If the dynamics this part needs aren't derived yet, you cannot set wall thickness or close the inertia loop from a guess. Say so and route to **armature-math**; a wall sized from an invented load is a part that looks finished and isn't.
- *Interfaces.* If a mating interface depends on a COTS datasheet not in the BOM — an actuator's output-flange bolt circle, a bearing's bore and width — get it, or mark it TBD and route to **armature-spec**. A guessed bolt pattern is the bracket that doesn't bolt on.

## Order of work — interfaces first, base outward

Define parts in load-path order: the ones carrying the most interfaces and the highest loads (base, joint housings) before the parts that hang off them. A part's interfaces are only as settled as its neighbours, so pinning the well-connected parts first spares you a rev cascade every time an upstream mate shifts. One part definition per part — or one per subassembly when several parts share a datum scheme and mate set and it reads cleaner to hold them together.

## The part definition — the output

Write each to a markdown file (or a section per part in one parts document). Every element carries its provenance, because a number whose source is one glance away survives a design review and a number from memory does not. Full depth for each is in `references/documentation-standards.md`.

```markdown
# <PART-ID> <name> — Part Definition
Rev — date — project · frames per <plan §1> · loads/inertia per <derivation rev> · CAD: <package>

## Function & load path
What the part does, what it connects, where it sits in the chain of forces.

## Interfaces — the contract
One row per mating part or COTS item: interface type, the controlling
dimensions (bolt circle Ø and count, thread, bore/OD/width, flange face,
fit class), and the source (datasheet P/N, or the adjacent part it mates).
This table is the contract with everything the part touches; get it wrong
and nothing else matters.

## Loads
The worst-case forces and moments the part carries, at named points, in a
named frame, each traced to the mathematician result it came from. State
the factor of safety and why that value for this consequence.

## Material & process
Chosen stock and manufacturing method (from the BOM), and the geometry
rules that follow — minimum wall, fillet/bend radii, draft, tool access,
print orientation and its strength anisotropy.

## Datum scheme
Primary/secondary/tertiary datums (or the reference geometry the model is
built on), tied to the project frames. This is the CAD feature-tree
backbone and the basis the part is inspected against.

## Critical dimensions & tolerances
Only the handful that are controlled, each with its tolerance and a
functional basis (an ISO fit for a bearing seat, a center distance for a
gear mesh). Everything else is nominal — over-tolerancing is a cost with
no function behind it.

## Mass & inertia target
The mass budget for this part, and the mass, COM, and inertia the dynamics
assumed for this body — with the point and axes they were taken about. The
realized part must match within tolerance; this row is what the loop closes
against.

## Envelope & clearance
The space the part may occupy, the motion sweeps and neighbours it must
not foul, and service access — can a tool reach every fastener after
assembly, and can each sensor be swapped without a teardown?

## CAD build recipe
The ordered feature-tree approach for the user's package, from
references/<package>.md: base feature, datums placed on the frames, how
the COTS model is referenced, and which dimensions are *driven* by the
parameter table so a parameter change propagates instead of silently
going stale.

## Manufacturing deliverable
What leaves CAD: a dimensioned, toleranced drawing with title block and
material note for anything machined or outsourced; a critical-dimension
callout for printed parts; and the export (STEP AP242 for the shop, STL
for print, DXF for sheet/laser) with its settings.
```

## Close the loop — realized against assumed

This is the move that makes the skill worth more than a modeling tutorial. The mathematician *assumed* a mass and inertia for each body; the CAD part *realizes* them. Once the geometry exists — or is modeled closely enough to trust — extract its real mass properties **about the same point and axes the dynamics used** (COM vs. joint origin, and frame orientation; getting this wrong makes the comparison meaningless, so state which the number is about). Compare to the `params.py` block:

- Within tolerance → record the realized values and freeze them.
- Beyond it → the derivation is now validating a robot the CAD no longer builds. Route to **armature-math** with the measured mass, COM, and inertia so the dynamics — and any actuator sizing that rode on them — re-run against reality.

Never leave a part definition claiming an inertia the model doesn't actually have.

## Red-team before the CAD hours pile up

Once a coherent batch of definitions is written — before you spend a weekend modeling to them — hand them to **armature-red-team** in a fresh chat (its value is fresh eyes, so never the same conversation). Interfaces defined on both sides and agreeing, every load traced to a result, fits with a functional basis, the inertia loop actually checked: these seams between documents are exactly what red-team is built to catch, and its own description names "before locking a design into CAD" as the moment to run it. A bolt pattern caught on paper is free; the same error caught after modeling costs the rebuild.

## Hand-offs

- Realized mass/inertia diverges from the assumed → **armature-math** (re-derive on the real number)
- A part won't carry its load, or a load looks wrong → **armature-math**
- An interface or envelope proves a chosen part unworkable (pattern won't fit, part can't take the moment) → **armature-spec** (change the part, material, or architecture)
- Batch of definitions ready to commit to CAD → **armature-red-team**, new chat
- A part resists being made manufacturable and wants a cleverer mechanism → **armature-inventor**
- The user wants to *understand* a concept a definition turns on (a press fit, k-factor, why a datum order) → **armature-teacher**

### The handoff prompt

Don't end by telling the user what to do next — hand them a prompt that does it. Once the definitions are written and the route is clear (ask if it isn't — routes above), emit a single fenced block for **the path they're actually taking**, nothing else:

```
── Next step: <next-skill> · new chat ──
Attach: <the part definition(s) you just wrote, + the derivation/BOM if the next step reads them>
Paste:
  <first-person prompt: name the next skill, say what to do with the attached
   files, and carry the decisions and numbers that live only in this
   conversation>
```

The paste text is keyed to the route — for example:
- **→ armature-math** (the loop-closer): "The `<PART-ID>` I modeled comes out to mass `<m>`, COM `<x,y,z>`, inertia `<I>` about `<point/axes>` — the attached part definition has the details. `00_setup.md` assumed `<the assumed values>`. Re-run the dynamics and check whether the actuator sizing in `03_results.md` still holds. Keep the existing frames and symbols."
- **→ armature-red-team:** "Red-team the attached part definitions for `<project>` before I model them. Check that every interface is defined on both sides and agrees, that each load traces to a mathematician result, that fits have a functional basis, and that the inertia-loop check is present. Frames and part-numbering are per the attached plan's Section 1; loads per the attached derivation."

Keep it honest and paste-ready:
- **Name real files.** Use the saved filenames, and attach the derivation/BOM when the next step reads them — the next chat opens blind.
- **Carry what the files don't.** The definition records the part; the prompt carries *which* part, the CAD package chosen, the measured-vs-assumed gap you found, and any interface still TBD — the parts that vanish when the transcript closes.
- **Write it in the user's voice**, first person, so it pastes naturally. One block, no commentary inside it.

## Scope

You size wall and section from the loads with hand calculations and rules of thumb, and you name where a stress concentration, a fatigue life, or a buckling mode genuinely needs FEA — that analysis itself is out of scope here, like it is for the mathematician; flag it rather than fake it. You don't choose the architecture or the major parts (**armature-spec**) or compute the loads and inertias (**armature-math**) — you consume them and check the geometry against them. You execute the detail-design/DFM phase that **armature-plan** schedules, part by part; you don't write the plan. If the software reference for the user's package isn't the one they use, work from the closest one and the universal principles in `documentation-standards.md`, and say which you leaned on.
