# Part Documentation — Standards

The depth behind SKILL.md's part-definition structure: what each element is *for*, how to fill it well, and the handful of tables you'll reach for repeatedly. The governing idea is that a mechanical part is defined by its **interfaces, its loads, and the few dimensions that must be controlled** — everything else is consequence. Document those three precisely and the part almost draws itself; document them vaguely and no amount of modeling saves it.

Contents:
1. Function & load path
2. Interfaces — the contract
3. Loads, factor of safety, and first-pass sizing
4. Material & process → geometry rules
5. Datum scheme
6. Tolerances & fits
7. GD&T — when it earns its keep
8. Mass & inertia target — closing the loop
9. Envelope, clearance, service access
10. The manufacturing deliverable

*Which* fit or tolerance to choose lives here; *how* to call it out in a given CAD package lives in that package's reference file. Keep the split — one source of truth each.

## 1. Function & load path

One paragraph, but the one that governs the rest: what the part does, what it connects, and the path forces take through it. Naming the load path is not a formality — it tells you where the material has to be (along the path, at the corners where moment peaks) and where it can be removed (everywhere the path doesn't run). A bracket whose load path you can't state in a sentence is a bracket you're about to over-build in the wrong places.

## 2. Interfaces — the contract

The interface table is the highest-leverage part of the whole definition, because an interface error is invisible until parts meet and then unrecoverable without a remake. Treat every interface as a two-sided contract: it must be defined on *both* sides and the two sides must agree — the same failure family the red-team checklist calls out.

For each mating item capture the controlling geometry, straight from the datasheet or the adjacent part:

- **Bolted joint:** bolt circle diameter and hole count, thread spec and class (M4×0.7, clearance vs. tapped), head clearance and wrench access, edge distance (≥ ~1.5–2× hole Ø to the part edge so it doesn't tear out), and grip length.
- **Shaft / bore:** nominal diameter and the fit class (§6) — this is where press vs. slip is decided — plus bore depth, shoulder, and retention (circlip groove, set screw flat, shoulder + endcap).
- **Bearing seat:** bore or OD per the bearing datasheet, seat width, shoulder height (from the bearing's minimum-shoulder spec, not guessed), and which ring is the interference fit (rotating ring gets the tight fit).
- **Flange / mounting face:** the mating face's flatness needs, pilot/spigot diameter if it centers the joint, and the pattern that locates it.
- **Actuator output:** the output flange's bolt pattern, pilot diameter, and shaft interface *from the actuator datasheet* — this is the single interface most often modeled from memory and most often wrong.

Every row names its source. A bolt circle with no datasheet behind it is an open question wearing a dimension.

## 3. Loads, factor of safety, and first-pass sizing

Pull the worst-case force and moment this part carries from the mathematician's `03_results.md` — prefer the worst-case-over-workspace value to the load at one convenient posture — and state it at a named point in a named frame. A load without a point of application and a direction can't size anything.

**Factor of safety scales to consequence, not to habit.** A number picked by reflex is either wasting mass or hiding a risk:

| Consequence of this part failing | FoS on yield (ductile metal) | Notes |
|---|---|---|
| Cosmetic / non-structural | 1.25–1.5 | Bracket for a light sensor, a cover |
| Structural, failure loses the part or the run | 1.5–2.0 | Typical link, housing, mount |
| Failure drops a payload or damages the machine | 2.0–3.0 | Load-bearing joint structure |
| Failure can injure a person | 3.0+, and design so failure is graceful | Anything overhead or near hands; treat FEA/test as required, not optional |
| Printed polymer, any structural role | apply to a *measured* or derated strength, not the vendor's headline number | Layer adhesion is the weak axis; orient the part so the load isn't across the layers |

Fatigue (millions of cycles, or a joint that reverses load) is a different regime — the endurance limit sits well below yield, and stress concentrations dominate. If the part sees cyclic load, say so and flag fatigue analysis; a static FoS does not cover it.

**First-pass sizing** is hand-calc, not FEA. For a bracket or link loaded as a beam, bending stress σ = M·c / I with I the *section's* second moment (not to be confused with mass inertia) — size the section so σ·FoS stays under yield, then add material at the fixed end where M peaks and the corner where stress concentrates. For a bolted joint, check bolt shear/tension against its proof load and the part's bearing stress at the hole. These get the section into the right ballpark; hand off to FEA when a stress concentration, a buckling mode, or a fatigue life actually governs — and *name* that in the definition rather than modeling a wall you can't defend.

## 4. Material & process → geometry rules

The BOM chose the stock and process; that choice constrains the geometry, and the constraints belong in the definition so the model respects them from the first feature:

- **Machined (aluminium, steel):** internal corners carry a minimum fillet set by tool radius (you cannot machine a sharp internal corner); keep pockets shallow enough for tool reach and standard flute lengths; call out where a sharp *external* edge must be broken. Deep narrow pockets and tiny internal radii are cost, quoted per hour.
- **3D printed (PLA/PETG/PA-CF):** strength is anisotropic — weakest across layer lines, so orient the part (and say so) to put the load along layers, not across them. Respect minimum wall (≈ 3–4 perimeters), design in embedded-nut or heat-set-insert bosses where fasteners land (printed threads strip), and avoid unsupported overhangs beyond ~45° or design them to print without support.
- **Sheet metal:** every bend needs a radius (≈ material thickness as a starting inside radius) and a bend relief at the ends; holes and form features keep clear of the bend zone by a few thicknesses; the flat pattern must actually unfold (the CAD sheet-metal environment enforces this — use it rather than modeling bent geometry by hand).
- **Cast / molded:** draft on every face pulled from the mold, uniform wall thickness to avoid sink, generous fillets.

## 5. Datum scheme

The datum scheme is the part's skeleton: the primary, secondary, and tertiary references that everything else is measured, modeled, and inspected from. Choosing it well is what lets a change propagate cleanly and an inspector check the part against the same references the function cares about.

Pick datums by *function*, and tie them to the project's coordinate frames so the part sits correctly in the assembly:

- **Primary datum** — the face or axis that most constrains the part in use and seats it in the assembly (the mounting face against the actuator, the main bore axis). It removes the most degrees of freedom.
- **Secondary** — locates the next, usually orthogonal to the primary (a locating pin hole, a shoulder).
- **Tertiary** — pins down the last rotation/translation (an edge, a second hole).

Build the CAD feature tree on these same references (the software reference shows how): the model's base feature and datum planes *are* the datum scheme, so a well-chosen scheme and a clean feature tree are the same decision made once. A part modeled off arbitrary planes and then dimensioned off functional ones will fight you at every revision.

## 6. Tolerances & fits

Control only the dimensions with a function behind them; leave the rest at a general tolerance block. Over-tolerancing buys nothing and costs money — a ±0.01 mm callout on a face that mates nothing is pure waste, and it hides the dimensions that *do* matter in a sea of tight numbers.

The recurring decision is the **cylindrical fit** — how a shaft sits in a bore. Reach for standard ISO fits rather than inventing clearances (hole-basis shown; the hole stays at H and the shaft letter sets the fit):

| Fit | Class | Character | Use it for |
|---|---|---|---|
| Loose clearance | H9/d9 | Obvious play | Rough guides, non-critical pivots |
| Free running | H8/f7 | Turns freely, some slop | Bushings, lightly loaded rotating shafts |
| Close running / sliding | H7/g6 | Slides by hand, minimal play | Sliding parts, located but movable joints |
| Location (snug) | H7/h6 | Assembles by hand, well located | Dowels, precise location, no rotation |
| Location / transition | H7/k6 | Light tap to assemble | Located parts that must not shift |
| Press / interference | H7/p6 (light), H7/s6 (heavy) | Requires force or heat/cold | Bearing inner race on shaft, bushing in housing |

Rule of thumb for bearings: the ring that rotates relative to the load gets the interference fit; the stationary ring gets a location/transition fit so it can be assembled. Take the exact recommended shaft and housing tolerances from the bearing manufacturer's mounting table when precision matters — they publish them.

For the general (uncontrolled) dimensions, put a tolerance block on the drawing (e.g. one-place ±0.5 mm, two-place ±0.1 mm, angles ±1°) so "uncontrolled" still means *bounded*, and match it to what the shop actually holds.

## 7. GD&T — when it earns its keep

Geometric dimensioning and tolerancing (a datum-referenced language for controlling *form, orientation, and position* rather than just size) earns its keep exactly where a size tolerance can't express the real requirement:

- **Position** on a bolt pattern or bearing bores that must line up across parts — a ±size tolerance on each hole doesn't capture that the *pattern* must align, and position tolerance (with maximum material condition where a clearance bonus is fair) does, often loosening the individual holes.
- **Flatness / parallelism** on a mating face that has to seat without rocking or preload a bearing evenly.
- **Concentricity / runout** on rotating features where wobble becomes vibration.
- **Perpendicularity** of a bore to its mounting face when misalignment binds a shaft.

If a plain ±dimension fully captures the requirement, use it — GD&T on features that don't need it is noise the machinist has to price. The value is in saying the functional thing precisely, not in decorating the drawing with symbols.

## 8. Mass & inertia target — closing the loop

This element is what makes the part definition answer back to the math. Record two things: the **mass budget** for the part (from the spec's mass rollup), and the **mass, COM, and inertia the dynamics assumed** for this body — with the *point and axes* they were taken about (the mathematician's `params.py` and `00_setup.md` state these). The last detail is the one people drop: an inertia tensor is meaningless without the point (COM? joint origin?) and the frame it's expressed in, and a CAD mass-properties report taken about a different point will disagree with a correct derivation for a reason that has nothing to do with the part. State which, on both sides, so the comparison is real. SKILL.md's "close the loop" step is where this target gets checked against the modeled reality.

## 9. Envelope, clearance, service access

The space the part may occupy, and the space it must leave alone: the swept volumes of moving neighbours through the full range of motion, the keep-outs for wiring and connectors, and — the one that bites at assembly — **service access**. For every fastener, can a tool actually reach and turn it once the part is in place? For every sensor and bearing, can it be replaced without dismantling half the machine? Access is a design-time dimension, not something you discover with a wrench at 2 a.m.; the design-foundations doctrine (from armature-spec) is blunt about this and it's right.

## 10. The manufacturing deliverable

The definition ends in something the shop or printer can consume:

- **Machined / outsourced part → a drawing.** Even in a model-based world, a dimensioned, toleranced drawing with a title block (part number and rev per the project scheme, material, finish, general-tolerance block, quantity) is what most shops quote and inspect against. Dimension from the datum scheme, apply GD&T only where §7 says it earns its keep, and add notes for anything the geometry can't say (deburr, surface finish, heat treat).
- **Printed part → a critical-dimension callout.** The STL carries the geometry, but the few fits and interfaces that matter (a bearing bore, an insert boss) need called-out dimensions and the print settings (orientation, walls, infill) that make them come out right.
- **Sheet part → a flat pattern / DXF** with bend lines and the bend table (k-factor from the shop or a test bend), plus the folded drawing.
- **Export formats:** STEP (AP242 preferred, it carries PMI) for solid handoff to a shop or another CAD; STL (with a resolution fine enough that facets don't show on fit surfaces) for print; DXF for laser/waterjet/sheet. State the format and settings, because a default STL export that's too coarse on a bearing bore is a part that won't press together.
