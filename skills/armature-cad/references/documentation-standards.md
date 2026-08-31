# Part Documentation — Standards

The depth behind SKILL.md's part-definition template: what each section is *for*, how to fill it, and the tables you reach for repeatedly. A mechanical part is defined by its **interfaces, its loads, and the few dimensions that must be controlled**; everything else is consequence.

*Which* fit or tolerance to choose lives here; *how* to call it out in a given CAD package lives in that package's reference file.

Sections 1–2 and 11 apply at both grades; sections 3–10 are **release-grade depth** — read them when the part graduates from sketch to release.

## 1. At a glance — shape, function, load path

Name the shape as a familiar primitive before any table, then one sentence for the **load path**: the route forces take through the part. The load path says where material has to be (along the path, at the corners where moment peaks) and where it can be removed (everywhere the path doesn't run). If the part has an executable recipe, `write_views` projects real front/top/right/iso views with hidden lines from the geometry; the three orthographic views export 1:1, so a feature measured off them is the part's real millimetres, while the iso is orientation only (an isometric projection foreshortens every 3D length).

## 2. Interfaces — the contract

Every interface is a two-sided contract: defined on *both* sides, and the two sides agree. For each mating item capture the controlling geometry from the datasheet or the adjacent part:

- **Bolted joint:** bolt circle diameter and hole count, thread spec and class (M4×0.7, clearance vs. tapped), head clearance and wrench access, edge distance (≥ ~1.5–2× hole Ø to the part edge), and grip length.
- **Shaft / bore:** nominal diameter and the fit class (§6), bore depth, shoulder, and retention (circlip groove, set screw flat, shoulder + endcap).
- **Bearing seat:** bore or OD per the bearing datasheet, seat width, shoulder height (from the bearing's minimum-shoulder spec), and which ring is the interference fit (the rotating ring).
- **Flange / mounting face:** the mating face's flatness needs, pilot/spigot diameter if it centers the joint, and the pattern that locates it.
- **Actuator output:** the output flange's bolt pattern, pilot diameter, and shaft interface *from the actuator datasheet* — the interface most often modeled from memory and most often wrong.

## 3. Loads, factor of safety, and first-pass sizing

Pull the worst-case force and moment this part carries from the derivation's `03_results.md` — the worst-case-over-workspace value, not the load at one convenient posture — and state it at a named point in a named frame.

**Factor of safety scales to consequence:**

| Consequence of this part failing | FoS on yield (ductile metal) | Notes |
|---|---|---|
| Cosmetic / non-structural | 1.25–1.5 | Bracket for a light sensor, a cover |
| Structural, failure loses the part or the run | 1.5–2.0 | Typical link, housing, mount |
| Failure drops a payload or damages the machine | 2.0–3.0 | Load-bearing joint structure |
| Failure can injure a person | 3.0+, and design so failure is graceful | Anything overhead or near hands; FEA/test required |
| Printed polymer, any structural role | apply to a *measured* or derated strength, not the vendor's headline number | Layer adhesion is the weak axis; orient the part so the load runs along the layers |

Fatigue (millions of cycles, or a joint that reverses load) is a different regime — the endurance limit sits well below yield, and stress concentrations dominate. If the part sees cyclic load, say so and flag fatigue analysis; a static FoS does not cover it.

**First-pass sizing** is hand-calc. For a bracket or link loaded as a beam, bending stress σ = M·c / I with I the *section's* second moment (not mass inertia) — size the section so σ·FoS stays under yield, then add material at the fixed end where M peaks and the corner where stress concentrates. For a bolted joint, check bolt shear/tension against its proof load and the part's bearing stress at the hole. Hand off to FEA when a stress concentration, a buckling mode, or a fatigue life governs, and *name* that in the definition.

## 4. Material & process → geometry rules

The BOM chose the stock and process; the geometry rules that follow belong in the definition so the model respects them from the first feature:

- **Machined (aluminium, steel):** internal corners carry a minimum fillet set by tool radius; keep pockets shallow enough for tool reach and standard flute lengths; call out where a sharp *external* edge must be broken. Deep narrow pockets and tiny internal radii are quoted per hour.
- **3D printed (PLA/PETG/PA-CF):** strength is anisotropic — weakest across layer lines — so orient the part (and say so) to put the load along layers. Respect minimum wall (≈ 3–4 perimeters), design in embedded-nut or heat-set-insert bosses where fasteners land (printed threads strip), and keep overhangs under ~45° or design them to print without support.
- **Sheet metal:** every bend needs a radius (≈ material thickness as a starting inside radius) and a bend relief at the ends; holes and form features keep clear of the bend zone by a few thicknesses; model in the CAD sheet-metal environment so the flat pattern unfolds.
- **Cast / molded:** draft on every face pulled from the mold, uniform wall thickness to avoid sink, generous fillets.

## 5. Datum scheme

The primary, secondary, and tertiary references everything else is measured, modeled, and inspected from. Pick them by *function*, tied to the project's coordinate frames so the part sits correctly in the assembly:

- **Primary datum** — the face or axis that most constrains the part in use and seats it in the assembly (the mounting face against the actuator, the main bore axis). It removes the most degrees of freedom.
- **Secondary** — locates the next, usually orthogonal to the primary (a locating pin hole, a shoulder).
- **Tertiary** — pins down the last rotation/translation (an edge, a second hole).

Build the CAD feature tree on these same references (the software reference shows how): the model's base feature and datum planes *are* the datum scheme, so a well-chosen scheme and a clean feature tree are one decision made once.

## 6. Tolerances & fits

Control only the dimensions with a function behind them; the rest ride a general tolerance block.

The recurring decision is the **cylindrical fit** — how a shaft sits in a bore. Use standard ISO fits (hole-basis: the hole stays at H and the shaft letter sets the fit):

| Fit | Class | Character | Use it for |
|---|---|---|---|
| Loose clearance | H9/d9 | Obvious play | Rough guides, non-critical pivots |
| Free running | H8/f7 | Turns freely, some slop | Bushings, lightly loaded rotating shafts |
| Close running / sliding | H7/g6 | Slides by hand, minimal play | Sliding parts, located but movable joints |
| Location (snug) | H7/h6 | Assembles by hand, well located | Dowels, precise location, no rotation |
| Location / transition | H7/k6 | Light tap to assemble | Located parts that must not shift |
| Press / interference | H7/p6 (light), H7/s6 (heavy) | Requires force or heat/cold | Bearing inner race on shaft, bushing in housing |

Bearings: the ring that rotates relative to the load gets the interference fit; the stationary ring gets a location/transition fit so it can be assembled. Take the exact shaft and housing tolerances from the bearing manufacturer's mounting table when precision matters.

For the general dimensions, put a tolerance block on the drawing (e.g. one-place ±0.5 mm, two-place ±0.1 mm, angles ±1°) matched to what the shop holds, so "uncontrolled" still means *bounded*.

## 7. GD&T — when it earns its keep

Geometric dimensioning and tolerancing (datum-referenced control of *form, orientation, and position*) earns its keep where a size tolerance can't express the requirement:

- **Position** on a bolt pattern or bearing bores that must line up across parts — a ±size tolerance per hole doesn't capture that the *pattern* must align; position tolerance (with maximum material condition where a clearance bonus is fair) does, often loosening the individual holes.
- **Flatness / parallelism** on a mating face that has to seat without rocking or preload a bearing evenly.
- **Concentricity / runout** on rotating features where wobble becomes vibration.
- **Perpendicularity** of a bore to its mounting face when misalignment binds a shaft.

If a plain ±dimension fully captures the requirement, use it.

## 8. Mass & inertia target — closing the loop

Record the **mass budget** row (from the spec's mass rollup) and the **mass, COM, and inertia the dynamics assumed** for this body, with the *point and axes* they were taken about — the derivation's `params.py` and `00_setup.md` state these. An inertia tensor without its point (COM? joint origin?) and frame is not comparable: a CAD mass-properties report taken about a different point disagrees with a correct derivation for a reason that has nothing to do with the part. State point and axes on both sides. Granularity (per-body vs. lump) and the comparison itself are SKILL.md's Close the loop.

## 9. Envelope, clearance, service access

The space the part may occupy, and the space it must leave alone: the swept volumes of moving neighbours through the full range of motion, keep-outs for wiring and connectors, and **service access** — for every fastener, a tool that reaches and turns it once the part is in place; for every sensor and bearing, a replacement path that doesn't dismantle half the machine.

## 10. The manufacturing deliverable

The definition ends in something the shop or printer consumes:

- **Machined / outsourced part → a drawing.** A dimensioned, toleranced drawing with a title block (part number and rev per the project scheme, material, finish, general-tolerance block, quantity) is what shops quote and inspect against. Dimension from the datum scheme, apply GD&T only where §7 says, and add notes for anything the geometry can't say (deburr, surface finish, heat treat).
- **Printed part → a critical-dimension callout.** The STL carries the geometry; the few fits and interfaces that matter (a bearing bore, an insert boss) need called-out dimensions and the print settings (orientation, walls, infill) that make them come out right.
- **Sheet part → a flat pattern / DXF** with bend lines and the bend table (k-factor from the shop or a test bend), plus the folded drawing.
- **Export formats:** STEP (AP242 preferred, it carries PMI) for solid handoff to a shop or another CAD; STL for print; DXF for laser/waterjet/sheet. State the format and settings: a default STL export is too coarse on a bearing bore and the part won't press together.

## 11. Done when — baseline checks

At release grade, five checks, each checkable in the CAD package in under a minute:

- Each **critical dimension** from §6 measures its callout in the model (measure the bore, don't trust the feature name).
- Each **interface** matches its source row — bolt circle diameter and count against the datasheet page, bore against the bearing table — checked against the *source*, not memory of it.
- **Mass properties** are within tolerance of the §8 target, taken about the stated point and axes.
- The model **rebuilds cleanly after changing each driven parameter** and the geometry follows.
- **Clearance holds**: neighbours and swept volumes from §9 still clear at the extremes of motion.

Write each check concretely for the part at hand ("bore measures 22.000–22.021", "4× holes on Ø45.0 ± 0.1 BC per iC-MU datasheet p.12"), not as generic reminders.
