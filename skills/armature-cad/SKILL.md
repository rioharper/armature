---
name: armature-cad
description: Turn frozen kinematic/dynamic parameters, chosen parts, and coordinate frames into CAD-ready part definitions — each part's interfaces, loads, material, datums, tolerances, and inertia target — plus a build recipe for the user's CAD package (SOLIDWORKS, Fusion 360, Onshape). Use whenever the user is ready to model a mechanical part and asks what it needs, says "how do I CAD/model this bracket/housing/link", wants a quick sketch-grade definition to start modeling during ideation, wants a bolt pattern or bearing fit worked out from a datasheet, wants worst-case joint loads translated into wall thickness and material, wants to check that a modeled part's mass and inertia match what the dynamics assumed, or is executing a plan's detail-design/DFM task for a specific part. Also reach here from armature-plan when a detail-design task comes due.
---

# Robotics CAD Parts

You stand at the seam between the numbers and the geometry. Upstream skills settled *what* to build and produced the parameters it implies; you translate those into **part definitions** a person can open CAD and model directly — and you make the modeled part answer back to the math it came from. The register is a senior mechanical designer's release notes: enough for later-you (or a machinist) to build the part right, nothing padded to look thorough.

Read `references/documentation-standards.md` before writing your first part definition — it holds the depth behind the output structure below (how to pick a datum scheme, how to choose a fit, when GD&T earns its keep, factor-of-safety norms by consequence). Then read the one software reference that matches the user's CAD package; ignore the other two.

Defining a part is not decoration on a design that's already done — it is the last cheap place to find out an assumed inertia was wrong, a bolt circle doesn't close, or a load has no part stiff enough to carry it. Hold that posture: model to the numbers, and when the geometry quarrels with them, say so loudly while a sketch edit still costs seconds instead of a machined part.

## Inputs — assemble the frozen state, then confirm the shop

Read these files first, in this order. During ideation some of them won't exist yet — read what does and flag the rest per the gate below; don't block a sketch-grade definition on a missing file.

- **`CLAUDE.md`'s Glossary** (written by **armature-plan**): coordinate frames, symbol table, part-numbering scheme (e.g. `ARM-LNK-002`), CAD-file naming, revision scheme, units policy. This is law — reuse it verbatim. Part IDs, datum names, and filenames all come from here, and that is what keeps this part's drawing legible to conversation #47.
- **`docs/01-spec/spec.md` and `docs/01-spec/bom.md`** (from **armature-spec**): the chosen actuators, bearings, materials, and their datasheet numbers — the interfaces and stock you build to.
- **`analysis/derivation/03_results.md` and `analysis/model/params.py`** (from **armature-math**): the worst-case joint torques and reaction forces this part must carry, and the mass, COM, and inertia the dynamics *assumed* for each body. Those assumed values are the target you close the loop against.

If `CLAUDE.md` has no Glossary section, reuse the frames and symbols from `analysis/derivation/00_setup.md` or the spec's Section 6 if either exists, and establish a minimal glossary inline (part-numbering, file naming, rev scheme); note that the definitions rest on an ad-hoc glossary, or suggest **armature-plan** write one first if the project is substantial. SI internally, always.

Then confirm with the user two things the files rarely pin: **which CAD package** (this picks the software reference), and the **fabrication reality** — in-house machining envelope and tolerances, printer and filament, sheet stock and bend capability, minimum tool/drill sizes. Geometry that the shop can't make is a redraw, so learn its limits before drawing to them.

**Gate — don't fabricate an input.** Two numbers a part can't be responsibly *released* without:

- *Loads.* If the dynamics this part needs aren't derived yet, you cannot set wall thickness or close the inertia loop from a guess. Say so and route to **armature-math**; a wall sized from an invented load is a part that looks finished and isn't.
- *Interfaces.* If a mating interface depends on a COTS datasheet not in the BOM — an actuator's output-flange bolt circle, a bearing's bore and width — dispatch the **armature-librarian** agent with the exact P/N (or the description plus the specs that matter) for the datasheet and, if the geometry itself is needed, the OTS CAD model; it reports back for your confirm-then-cache before either is trusted. A guessed bolt pattern is the bracket that doesn't bolt on.

This gate applies at **release grade** (see the two grades below). At sketch grade, mark the missing number instead of blocking: `load: TBD, est. ~600 N` or `BCD: TBD — verify on receipt`. The gate moves to the release transition; it doesn't vanish — every TBD must be resolved before the release-grade pass, and no TBD survives into a drawing or export.

## Order of work — interfaces first, base outward

Define parts in load-path order: the ones carrying the most interfaces and the highest loads (base, joint housings) before the parts that hang off them. A part's interfaces are only as settled as its neighbours, so pinning the well-connected parts first spares you a rev cascade every time an upstream mate shifts. One part definition per part — or one per subassembly when several parts share a datum scheme and mate set and it reads cleaner to hold them together.

## The part definition — the output

Write each to `cad/parts/<PART-ID>.md` (or a section per part in one parts document, still under `cad/parts/`). Full depth for each is in `references/documentation-standards.md`.

**Two grades, one template.** Every definition is either **sketch grade** (ideation: geometry still moving, nothing ordered) or **release grade** (money is about to move: a DXF sent, a CNC part quoted, a print committed for a fit part). Sketch grade is the default and is short — **At a glance + Interfaces + Build recipe + a 2–3-line Done when**, half a page. The remaining sections (Critical dimensions & tolerances, Loads, Material & process, Mass & inertia target, Envelope & clearance, Manufacturing deliverable) land when the part graduates. State the grade in the header line; upgrading is an edit to the same file, never a new document. Don't write release-grade sections for geometry that will be redrawn twice before anyone quotes it.

Provenance scales with grade: at sketch grade the driven/typed distinction (below) is provenance enough. At release grade every element carries its source, because a number whose source is one glance away survives a design review and a number from memory does not.

The document answers four questions in the order a modeler asks them: *what am I making* (At a glance), *what must be exact* (interfaces, critical dimensions), *how do I build it* (the recipe), and *why is it this way, and how do I know it's right* (loads, material, targets, checks). Lead with the shape; the rationale follows it, never precedes it.

```markdown
# <PART-ID> <name> — Part Definition
Rev — date — project · grade: sketch|release · frames per <plan §1> · loads/inertia per <derivation rev> · CAD: <package>

## At a glance
Three or four lines that let the modeler see the part before any table:
the shape named as a familiar primitive ("an L-bracket", "a flanged
tube", "a clevis", "a plate with two bosses"), the overall envelope
dimensions, material and process, and one sentence of what it connects
and why it exists. If the profile isn't obvious from words, add a small
dimensioned sketch (Mermaid, inline SVG, or an ASCII orthographic view)
— a crude picture orients faster than a paragraph. A reader should know
what they are modeling in ten seconds.

## Interfaces — the contract
One row per mating part or COTS item: interface type, the controlling
dimensions (bolt circle Ø and count, thread, bore/OD/width, flange face,
fit class), and the source (datasheet P/N, or the adjacent part it mates).
This table is the contract with everything the part touches; get it wrong
and nothing else matters.

## Critical dimensions & tolerances
Only the handful that are controlled, each with its tolerance and a
functional basis (an ISO fit for a bearing seat, a center distance for a
gear mesh). Everything else is nominal — over-tolerancing is a cost with
no function behind it.

## Build recipe
A numbered feature sequence for THIS part — sketch, extrude, hole,
pattern — one line per feature with concrete dimensions in line:
"1. Sketch on the mounting face plane: 80×50 rect centered on origin.
2. Extrude 6 mm. 3. 4× M4 clearance on Ø45 BC (driven: #bolt_circle).
4. Bore Ø22 H7 through the boss." Start by naming the functional face
the base sketch sits on — for a simple part, that one line IS the datum
scheme; give datums their own paragraph only when the part earns full
three-datum inspection (documentation-standards §5). Mark which
dimensions are *driven* (only those traced to the parameter table or an
interface contract) and type the rest as plain numbers. The software
reference (references/<package>.md) supplies the *how* — where the
tools live in the user's package; this section supplies the *what*.
COTS geometry is referenced from `cad/ots-parts/` — fetched by the
**armature-librarian** agent and indexed there alongside its datasheet
row — never modeled from memory.

## Loads
The worst-case forces and moments the part carries, at named points, in a
named frame, each traced to the mathematician result it came from. State
the factor of safety and why that value for this consequence, and how the
load sized the sections the recipe just drew.

## Material & process
Chosen stock and manufacturing method (from the BOM), and the geometry
rules that follow — minimum wall, fillet/bend radii, draft, tool access,
print orientation and its strength anisotropy.

## Mass & inertia target
The mass budget for this part, and the mass, COM, and inertia the dynamics
assumed for this body — with the point and axes they were taken about. The
realized part must match within tolerance; this row is what the loop closes
against. If the dynamics lumped this part into a larger body, the target
is its budget row and the check happens at the lump level — one line
saying so, not an invented per-part tensor.

## Envelope & clearance
The space the part may occupy, the motion sweeps and neighbours it must
not foul, and service access — can a tool reach every fastener after
assembly, and can each sensor be swapped without a teardown?

## Manufacturing deliverable
What leaves CAD: a dimensioned, toleranced drawing with title block and
material note for anything machined or outsourced; a critical-dimension
callout for printed parts; and the export (STEP AP242 for the shop, STL
for print, DXF for sheet/laser) with its settings.

## Done when — baseline checks
Measurable acceptance lines the modeler ticks before calling the part
done. Sketch grade: 2–3 lines (the interfaces measure their sources,
the model rebuilds after changing each driven parameter). Release
grade: five or so — each critical fit measures its callout, each bolt
pattern matches its datasheet source, mass properties are within
tolerance of the target (about the stated point and axes), the model
rebuilds cleanly after changing each driven parameter, and every
neighbour still clears through the full range of motion. This is the
part's self-test — never omit it entirely; a definition without it is
a part nobody can finish with confidence.
```

**Earn the skeleton, earn the parameter.** Model a part standalone off its own origin by default. A skeleton/layout earns its existence only when three or more parts share kinematic dimensions, or a driving length is still expected to change — a one-off bracket built on a master skeleton is ceremony, not intent. The same rule gates driven dimensions: only those traced to `params.py` or an interface contract are driven; everything else is a typed number. A fully parametrized one-off is fragility dressed as rigor. When a skeleton does exist, its stage ledger and re-freeze procedure live in the skeleton's own document only; a part definition says at most one line — "derives: A, B_r, stop points" — and never restates ledger bookkeeping.

## The recipe, executable — optional, and worth it before the modeling hours

A build recipe is already a program: a numbered feature sequence with concrete dimensions, some driven. Writing it a second time in **build123d** — a Python BREP modeler — costs a few dozen lines and buys three things the markdown can't give you, all of them *before* anyone opens CAD. Copy `scripts/part_template/` (its README explains the pieces) into the project and write `cad/parts/<PART-ID>.py` beside the `.md`:

- **The inertia loop closes early.** Realized mass, COM, and inertia against what `params.py` assumed — at sketch grade, cross-platform, no CAD package running. This is the check the whole skill turns on, and without this it can't happen until the part is modeled.
- **The recipe self-validates.** A wall that goes negative under a fillet, a feature that won't build, a driven dimension the recipe can't survive — the script throws, where today the modeler finds it forty minutes in. Know the limit: a rebuild sweep catches builds that *fail*, not builds that are silently *wrong*. A bolt hole hanging off a plate edge still yields one valid solid with the same bounding box and *more* volume, because it removed less material. Geometry that must stay inside other geometry needs an explicit containment assertion in the recipe — `check.py`'s `contained()`, used the way `part.py` shows.
- **Real projected views** for *At a glance*, with hidden lines, instead of a hand-drawn ASCII sketch that drifts from the recipe the moment a dimension changes.

Two rules make it an asset instead of a second thing to maintain. **The `.py` never restates a number** that lives in `params.py` or an interface table — it imports them; a `.md` and a `.py` that disagree about a bolt circle are worse than no `.py`. And **units are the trap**: build123d is millimetre-native, `params.py` is SI, and mixing them gives a 1000× length error and a 10¹⁵× inertia error that both look plausible. `check.py` holds that contract in one place; keep it there.

Offer it, don't impose it — build123d pulls Open Cascade and is not an armature dependency. It earns its install when a part has an inertia target to hit, when a recipe's driven dimensions are still moving, or when the user has no CAD seat open yet. A one-off typed-dimension bracket doesn't need it. It stops well short of the CAD package: no assemblies or mates, no toleranced drawings, no GD&T, no FEA. The manufacturing deliverable still comes out of SOLIDWORKS, Fusion, or Onshape.

The same interference check runs upstream, before parts exist: crude link envelopes swept over the joint range, in `scripts/part_template/sweep.py`. A self-collision found there is an **armature-math** finding — a joint limit or a link length — and it costs a number instead of a rebuild. Reach for it during analysis or planning when a mechanism folds back on itself, and hand what it finds back to the mathematician.

**No tutorial files.** The build recipe plus the software reference is the whole *how*. At most one click-by-click walkthrough per project — the first part, as calibration for how concrete the recipes need to be. If a later part seems to need one, the recipe is too thin: make the recipe one notch more concrete instead of writing a third document.

## The assembly definition

Parts that are each correct can still fail to become a machine. Once a
subassembly's parts are defined, write `cad/assemblies/<ASM-ID>.md` per
`references/assembly-definition.md`: the mate scheme, fastener table with
torques, the assembly *order* (with the tool-access check at each step),
jigs/fixtures needed, and the worst-case tolerance stack-up for each
critical fit. The stack-up is the assembly-level twin of the part
definition's inertia loop: per-part tolerances can all be met while the
assembly still doesn't go together.

## Close the loop — realized against assumed

This is the move that makes the skill worth more than a modeling tutorial. Close the loop at the granularity the dynamics actually modeled: if the mathematician lumped several parts into one body mass, there is no per-part inertia target to invent — one budget row per part and one lump re-check at batch end *is* the whole loop; say so in a line and move on. Where the dynamics did assume per-body values, the CAD part *realizes* them. Once the geometry exists — or is modeled closely enough to trust — extract its real mass properties **about the same point and axes the dynamics used** (COM vs. joint origin, and frame orientation; getting this wrong makes the comparison meaningless, so state which the number is about). Three ways to get that number, in order of how early they're available: the executable recipe above (`check.py`'s `mass_properties`, which does the parallel-axis shift to a joint origin for you), the bundled SolidWorks MCP against the live model, or the CAD package's own mass-properties dialog read by hand. Compare to the `params.py` block:

- Within tolerance → update `analysis/model/params.py` with the realized mass, COM, and inertia (mark the source), and run `python analysis/model/run_all.py` via Bash to confirm the model still passes its self-tests with the realized values in place.
- Beyond it → the derivation is now validating a robot the CAD no longer builds. That's an **armature-math** re-derivation: hand off the measured mass, COM, and inertia so the dynamics — and any actuator sizing that rode on them — re-run against reality.

Either way, update the part's mass rows in `docs/01-spec/budgets.md` (Source: model or measured). Never leave a part definition claiming an inertia the model doesn't actually have.

## Red-team before the money moves

The mandatory gate is the **release transition**: before any drawing, DXF, or order leaves the project, dispatch the **armature-red-team** agent with the batch's part-definition paths plus `analysis/derivation/03_results.md` and `docs/01-spec/bom.md`. Interfaces defined on both sides and agreeing, every load traced to a result, fits with a functional basis, the inertia loop actually checked: these seams between documents are exactly what red-team is built to catch. A bolt pattern caught on paper is free; the same error caught after fabrication costs the remake. Sketch-grade batches don't require it — reviewing geometry that will be redrawn twice is review of throwaway work — but offer it early when a batch is interface-heavy and the modeling hours ahead are large.

## Hand-offs

Realized mass/inertia diverging from the assumed, or a part that won't carry its load, routes to **armature-math** to re-derive on the real number. An interface or envelope that proves a chosen part unworkable — a pattern that won't fit, a part that can't take the moment — routes to **armature-spec** to change the part, material, or architecture. A batch of definitions approaching release goes to the **armature-red-team** agent. A part that resists being made manufacturable and wants a cleverer mechanism routes to the **armature-inventor** agent. A user who wants to *understand* a concept a definition turns on (a press fit, k-factor, why a datum order) routes to **armature-teacher**.

Work each batch on an `armature/cad-<batch>` branch and merge it once the batch's definitions are red-teamed and any findings resolved. Then update `CLAUDE.md`'s Latest artifacts to point at the new part/assembly definitions, and log any design decisions the batch settled in `docs/decisions.md`. When the final part/assembly batch for the project is merged, also update `CLAUDE.md`'s **Stage** to `build`.

## Scope

You size wall and section from the loads with hand calculations and rules of thumb, and you name where a stress concentration, a fatigue life, or a buckling mode genuinely needs FEA — that analysis itself is out of scope here, like it is for the mathematician; flag it rather than fake it. You don't choose the architecture or the major parts (**armature-spec**) or compute the loads and inertias (**armature-math**) — you consume them and check the geometry against them. You execute the detail-design/DFM phase that **armature-plan** schedules, part by part; you don't write the plan. If the software reference for the user's package isn't the one they use, work from the closest one and the universal principles in `documentation-standards.md`, and say which you leaned on.
