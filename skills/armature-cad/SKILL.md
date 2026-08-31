---
name: armature-cad
description: Turn frozen parameters, chosen parts, and coordinate frames into CAD-ready part definitions (interfaces, loads, material, datums, tolerances, inertia target) with a build recipe for SOLIDWORKS, Fusion 360, or Onshape, then check the modeled part back against the dynamics. Use when the user is ready to model a mechanical part, wants a bolt pattern or bearing fit worked out from a datasheet, wants worst-case loads sized into wall thickness and material, wants a modeled part's mass and inertia checked against what the dynamics assumed, needs DFM questions drafted for an outside shop, or a plan's detail-design task comes due.
---

# Robotics CAD Parts

You translate the upstream numbers into **part definitions** a person opens CAD and models directly, and you make the modeled part answer back to the math it came from. Register: a senior mechanical designer's release notes.

Read `references/documentation-standards.md` before writing the first part definition, then the one software reference matching the user's CAD package (`references/solidworks.md`, `fusion360.md`, or `onshape.md`).

## Inputs

Read in this order; during ideation read what exists and carry the rest as TBDs per the gate below:

- **`CONTEXT.md`** (written by **armature-plan**): coordinate frames, symbol table, part-numbering scheme, CAD-file naming, revision scheme, units policy. Reuse verbatim — part IDs, datum names, and filenames all come from here.
- **`docs/01-spec/spec.md` and `docs/01-spec/bom.md`**: the chosen actuators, bearings, materials, and their datasheet numbers.
- **`analysis/derivation/03_results.md` and `analysis/model/params.py`**: the worst-case joint torques and reaction forces each part carries, and the mass, COM, and inertia the dynamics *assumed* per body — the target the loop closes against.

Without `CONTEXT.md`, reuse the frames and symbols from `analysis/derivation/00_setup.md` or the spec's Section 6, establish a minimal glossary inline (part-numbering, file naming, rev scheme), and note that the definitions rest on it; for a substantial project, suggest **armature-plan** write one first. SI internally. If the design itself is still open — more undecided architecture than one session settles — call the Skill tool with "armature-wayfind" to chart the way first; a sketch-grade definition can serve one of its prototype tickets.

Then confirm two things the files rarely pin: **which CAD package**, and the **fabrication reality** — in-house machining envelope and tolerances, printer and filament, sheet stock and bend capability, minimum tool and drill sizes. When the shop is outside and the user can't speak for its limits, offer a **questionnaire** built per the plugin's `references/questionnaire.template.md` (two levels above this skill), written to `cad/questionnaire-<shop>.md`, sent with a sketch or drawing for the questions to point at. Its answers are release-grade inputs; until they return, they ride the affected parts as TBDs.

**Gate.** Release grade requires two sourced numbers:

- *Loads*, from the derivation. Not derived yet → call the Skill tool with "armature-derive" for them.
- *Interfaces*, from the datasheet. A mating interface on a COTS datasheet not in the BOM (an actuator's output-flange bolt circle, a bearing's bore and width) → dispatch the **armature-librarian** agent with the exact P/N (or the description plus the specs that matter) for the datasheet and, if the geometry itself is needed, the OTS CAD model; confirm what it reports before either is trusted.

At sketch grade, mark the missing number (`load: TBD, est. ~600 N`; `BCD: TBD — verify on receipt`) and continue. Every TBD resolves before the release-grade pass, and none survives into a drawing or export.

## Order of work

Define parts in load-path order: those carrying the most interfaces and the highest loads (base, joint housings) before the parts that hang off them. One part definition per part, or one per subassembly when several parts share a datum scheme and mate set.

## The part definition

Write each to `cad/parts/<PART-ID>.md` (or a section per part in one document under `cad/parts/`). Section depth is in `references/documentation-standards.md`.

**Two grades, one template.** **Sketch grade** (geometry still moving, nothing ordered) is the default: At a glance + Interfaces + Build recipe + Done when, half a page. **Release grade** (money about to move: a DXF sent, a CNC part quoted, a fit part printed) adds the remaining sections and a source on every element. State the grade in the header line; upgrading is an edit to the same file.

Sections run in the order a modeler asks: *what am I making* → *what must be exact* → *how do I build it* → *why, and how do I know it's right*.

```markdown
# <PART-ID> <name> — Part Definition
Rev — date — project · grade: sketch|release · frames per <CONTEXT.md> · loads/inertia per <derivation rev> · CAD: <package>

## At a glance
Three or four lines: the shape as a familiar primitive ("an L-bracket",
"a flanged tube", "a clevis"), overall envelope, material and process,
one sentence of what it connects and why. Add a small dimensioned sketch
(Mermaid, inline SVG, ASCII orthographic, or `write_views` output from an
executable recipe) when words don't carry the profile.

## Interfaces — the contract
One row per mating part or COTS item: interface type, controlling
dimensions (bolt circle Ø and count, thread, bore/OD/width, flange face,
fit class), and source (datasheet P/N, or the adjacent part it mates).

## Critical dimensions & tolerances
Only the controlled handful, each with its tolerance and functional basis
(an ISO fit for a bearing seat, a center distance for a gear mesh).
Everything else is nominal.

## Build recipe
A numbered feature sequence for THIS part, concrete dimensions in line:
"1. Sketch on the mounting face plane: 80×75 rect centered on origin.
2. Extrude 6 mm. 3. 4× M4 clearance on Ø45 BC (driven: #bolt_circle).
4. Bore Ø22 H7 through the boss." Line 1 names the functional face the
base sketch sits on — for a simple part that line IS the datum scheme;
datums get their own paragraph only when the part earns three-datum
inspection (documentation-standards §5). Mark *driven* dimensions per
the rule below; the rest are typed numbers. The software reference
supplies where the tools live; this section supplies the what. COTS
geometry is referenced from `cad/ots-parts/` (fetched by the
**armature-librarian** agent, indexed beside its datasheet row).

## Loads
Worst-case forces and moments at named points in a named frame, each
traced to the derivation result; the factor of safety and why that value
for this consequence; how the load sized the sections the recipe drew.

## Material & process
Stock and method from the BOM, and the geometry rules that follow —
minimum wall, fillet/bend radii, draft, tool access, print orientation.

## Mass & inertia target
The mass budget row, and the mass, COM, and inertia the dynamics assumed
for this body, with the point and axes they were taken about. Granularity
follows the dynamics (see Close the loop).

## Envelope & clearance
Space the part may occupy, motion sweeps and neighbours it must clear,
and service access: every fastener reachable with a tool after assembly,
every sensor swappable without teardown.

## Manufacturing deliverable
What leaves CAD: drawing, critical-dimension callout, or flat pattern,
plus the export (STEP AP242 / STL / DXF) with its settings.

## Done when — baseline checks
Sketch grade: 2–3 lines (interfaces measure their sources; the model
rebuilds after changing each driven parameter). Release grade: the five
checks in documentation-standards §11, each written concretely for this
part with the numbers to measure.
```

**Skeleton and driven dimensions.** Model a part standalone off its own origin. A skeleton/layout earns its existence when three or more parts share kinematic dimensions or a driving length is still expected to change. Driven dimensions are only those traced to `params.py` or an interface contract; everything else is a typed number. When a skeleton exists, its stage ledger and re-freeze procedure live in the skeleton's own document; a part definition says at most "derives: A, B_r, stop points".

**One walkthrough per project at most.** The build recipe plus the software reference is the whole *how*; a click-by-click walkthrough is written once, for the first part, as calibration. A later part that seems to need one gets a more concrete recipe instead.

## The recipe, executable — optional

A build recipe is a numbered feature sequence with concrete dimensions, so it can also be written in **build123d** as `cad/parts/<PART-ID>.py` from `scripts/part_template/` (its README holds what it buys, the unit contract, and where it stops). Offer it when a part has an inertia target to hit, its driven dimensions are still moving, or no CAD seat is open yet: it closes the inertia loop and validates the recipe at sketch grade, before the modeling hours. A one-off typed-dimension bracket doesn't need it, and build123d is not an armature dependency.

`scripts/part_template/sweep.py` is the planning-stage cousin: crude link envelopes swept over the joint range, before parts exist. A self-collision it finds is a joint limit or a link length — an **armature-derive** finding; hand it back with the printed rows.

## The assembly definition

Once a subassembly's parts are defined, write `cad/assemblies/<ASM-ID>.md` per `references/assembly-definition.md`: mate scheme, fastener table with torques, assembly order with a tool-access check at each step, jigs/fixtures, and the worst-case tolerance stack-up for each critical fit — the assembly-level twin of the inertia loop.

## Close the loop — realized against assumed

Close at the granularity the dynamics modeled: where it assumed per-body values, the part realizes them; where it lumped several parts into one body, the target is each part's budget row plus one re-check of the lump at batch end — say so in a line. Once the geometry exists, extract its mass properties **about the same point and axes the dynamics used** (COM vs. joint origin, and frame orientation — state which). Three sources, earliest first: the executable recipe (`check.py`'s `mass_properties` does the parallel-axis shift), the bundled SolidWorks MCP against the live model, or the CAD package's own mass-properties dialog. Compare to the `params.py` block:

- Within tolerance → update `analysis/model/params.py` with the realized mass, COM, and inertia (mark the source) and run `python analysis/model/run_all.py` via Bash: the self-tests must pass with the realized values in place.
- Beyond it → call the Skill tool with "armature-derive", handing off the measured mass, COM, and inertia, so the dynamics and any actuator sizing that rode on them re-run against reality.

Either way, update the part's mass rows in `docs/01-spec/budgets.md` (Source: model or measured). Done when every part definition's inertia claim matches the model.

## Red-team before the money moves

The **release transition** is the gate: before any drawing, DXF, or order leaves the project, dispatch the **armature-red-team** agent with the batch's part-definition paths plus `analysis/derivation/03_results.md` and `docs/01-spec/bom.md` — interfaces defined on both sides and agreeing, every load traced to a result, fits with a functional basis, the inertia loop checked. Sketch-grade batches skip it; offer it early when a batch is interface-heavy and the modeling hours ahead are large.

## Hand-offs

- A part that won't carry its load, or realized mass/inertia diverging from assumed → call the Skill tool with "armature-derive" with the real number.
- An interface or envelope that proves a chosen part unworkable — a pattern that won't fit, a part that can't take the moment → call the Skill tool with "armature-spec" to change the part, material, or architecture.
- A part that resists being made manufacturable and wants a cleverer mechanism → dispatch the **armature-inventor** agent.
- A user who wants to *understand* a concept a definition turns on (a press fit, k-factor, datum order) → call the Skill tool with "armature-teach".

Work each batch on an `armature/cad-<batch>` branch; merge once its definitions are red-teamed and findings resolved. Then point `CLAUDE.md`'s Latest artifacts at the new part/assembly definitions and log the batch's design decisions in `docs/decisions.md`. When the project's final batch merges, set `CLAUDE.md`'s **Stage** to `build`.

## Scope

Wall and section sizing by hand calculation and rules of thumb; name where a stress concentration, fatigue life, or buckling mode needs FEA and flag it rather than fake it. Architecture and major parts belong to **armature-spec**, loads and inertias to **armature-derive**, the schedule to **armature-plan**: consume them and check the geometry against them. If none of the software references matches the user's package, work from the closest one plus `documentation-standards.md`, and say which.
