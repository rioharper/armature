# CAD Build Recipe — SOLIDWORKS

How to realize a part definition in SOLIDWORKS. The build recipe says *what* to model; this file says *where the tools live* and the habits that keep the model honest.

## 1. Skeleton — when SKILL.md's rule says one pays

Model a part off its own origin planes by default. When a skeleton pays (SKILL.md, "Skeleton and driven dimensions"):

- Create a **skeleton part** (or a layout sketch in the assembly): sketches and reference geometry carrying the frames, joint locations, and key link lengths — nothing solid. The kinematic dimensions live here once.
- Bring frames in as **coordinate systems** and **reference planes/axes** (Insert → Reference Geometry), named for the project frames (`{B}_base`, `{2}_hip`, …) so the assembly reads against `CONTEXT.md`.
- Individual parts reference the skeleton (derived sketch, or in-context references to skeleton geometry). A shared skeleton the parts *read from* is safer than parts referencing each other — in-context references between parts are the classic source of circular-reference rebuild errors.

## 2. Datums and the base feature = the datum scheme

The part's datum scheme (documentation-standards §5) becomes its opening feature tree. Put the primary datum on Front/Top/Right or a created plane matching the functional mounting face, sketch the base feature on it, and build outward so the feature tree reads in the order a machinist would set up the part.

## 3. Driven dimensions — global variables

For the dimensions SKILL.md's rule marks driven:

- **Tools → Equations**: create **global variables** for them (`"link_len" = 200mm`).
- Drive sketch dimensions from them: double-click the dimension, enter `= "link_len"`. The dimension shows a Σ and follows the variable.
- For a table of parameters, **link to an external text/Excel file** (Equations → link to file) so one parameter file feeds several parts — the model-side echo of the project's ledger.
- Where a part comes in several sizes, use a **Design Table** (configurations driven by a spreadsheet) rather than saving copies.

Name dimensions and features (not `D1@Sketch3`); a named dimension referenced in an equation is a model someone can read.

## 4. Bring in the COTS model and mate to it

- Insert the supplier's STEP (or SOLIDWORKS) model of each actuator, bearing, and gearbox into the assembly as a component.
- Mate your part to *its* interface geometry — the actuator's output-flange face and bolt circle, the bearing's OD and shoulder face — so your mounting features are constrained by the datasheet geometry directly.
- Reference the COTS mounting face for your mating face rather than re-keying dimensions from the PDF.
- For fasteners and standard hardware, **Toolbox** supplies parametric COTS models.

## 5. Mass properties — the loop-closing measurement

1. **Assign the material first** (right-click the part → Material); if the stock isn't in the library (PA-CF, a specific alloy), create a custom material with the BOM's density.
2. **Tools → Evaluate → Mass Properties.**
3. **Set the output coordinate system to the derivation's**, via the "Output coordinate system" dropdown — the coordinate system you placed at the joint origin, or the COM, whichever `00_setup.md` states.
4. Read mass, center of mass, and the inertia tensor; compare per SKILL.md's Close the loop.

Mass Properties updates live as the model changes, so it doubles as a running check against the mass budget through detailing.

## 6. Fits and tolerances

*Which* fit is documentation-standards §6; apply it here:

- On a hole, the **Hole Wizard** places standard-sized holes with correct clearances and can carry a fit; on a bore/shaft, add the fit as a **dimension tolerance** (double-click the dimension → Tolerance/Precision → Fit → the ISO class, e.g. H7/p6). SOLIDWORKS shows the resulting limits.
- Tolerance the functional dimensions only; the rest ride the drawing's general-tolerance block (§10).
- For model-based tolerancing, **DimXpert** applies dimensions and GD&T to the solid and can drive an MBD, for a shop that consumes STEP AP242 with PMI rather than a 2D drawing.

## 7. Sheet metal, weldments, and printed parts

- **Sheet metal:** model in the Sheet Metal environment (Base Flange, Edge Flange, sketched bends) so bend radii and reliefs are enforced and the flat pattern is true. Set the **k-factor / bend table** to what the shop holds.
- **Weldments:** Weldment structural members with standard profiles for extruded-tube structure; cut lists generate automatically.
- **Printed parts:** no special environment; apply documentation-standards §4 and note the print orientation on the drawing.

## 8. Drawing and export

- **Drawing:** create a drawing from the part, dimension **from the datum scheme** (ordinate or baseline off the primary datum, not chained dimensions that stack tolerance), place GD&T where §7 warrants, fill the title block (part number and rev per the project scheme, material, finish, general-tolerance block), and add notes the geometry can't state.
- **Export:** File → Save As → **STEP AP242** for a shop or another CAD (carries PMI if you did MBD); **STL** for printing, with Options → deviation/angle set fine; **DXF** from the flat pattern for laser/waterjet. State format and settings in the definition (documentation-standards §10).

## 9. With the armature SolidWorks MCP connected

If the `solidworks` MCP server is connected (`/armature:init` writes it into a SolidWorks project's `.mcp.json`; needs SolidWorks running on Windows), run the Done-when checks against the live model instead of asking the user to transcribe numbers. The server measures; you judge — pass/fail lives in this conversation, against the ledger and the part definition.

- **Mass loop (§5):** `sw_mass_properties(doc, coord_system=<the frame from 00_setup.md>)` → compare mass/COM/inertia to the body's ledger entries (`CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" bash "${CLAUDE_PLUGIN_ROOT}/scripts/armature.sh" ledger show mechanism`), in SI, about the same point and axes. The write-back and any divergence go per SKILL.md's Close the loop.
- **Perturbation check:** for each driven parameter: `sw_set_params` to a ±10% value → `sw_rebuild` (must return no problems) → `sw_set_params` back → final `sw_rebuild`. Any feature in the problems list fails the check.
- **Interface verification:** `sw_get_dimensions` on each controlling dimension named in the interface contract table; compare value and tolerance against the table's source column.
- **Release metadata:** `sw_set_tolerance` for the fits documentation-standards §6 chose; `sw_custom_props` to stamp part number, rev, material before the drawing.

Parameter names, coordinate-system names, and dimension names are the whole API contract — they must match the glossary and the part definition exactly, which §1–§3 already require. If a name lookup fails, the error lists what exists; fix the model's names rather than adapting to typos.

## 10. Building and drawing by script — swkit

When a part is worth scripting (its driven dimensions are still moving, it has a mirrored hand, it is rebuilt each time the ledger moves, or its drawing is redone at every revision), build it in SOLIDWORKS itself with `${CLAUDE_PLUGIN_ROOT}/skills/armature-cad/scripts/swkit/`. Copy it into the project as `cad/tools/swkit/` and keep the project's build scripts beside it. Its README covers how to run it, its units and frames, and the rules that keep the user's seat safe. It does §1–§8 by script:

- **§1–§3:** `part.Part` and `Sketch` make named planes and typed globals. Every driven dimension is an equation of the globals, and the build stops on any sketch that is not fully defined. `extrude` keeps the side it was asked for and refuses a boss that merged away with no faces.
- **§5 and *Close the loop*:** `measure.mass_props`, `reach` and `find_face` read the model back, the mass properties in SI, ready for the `cad` entries. `python -m swkit audit` lists each configuration's rebuild errors and faceless bosses. `python -m swkit rebuild` rebuilds the part with its driven globals at ±10 %. Together they are a scripted part's *Done when* checks.
- **§6 and §8:** `drawing.draw_part` with `annotate` puts fits, tolerances, datums and feature control frames on the views, picking each edge by its model geometry, plus three to five terse notes. `exchange.export_step` writes AP214 and reads its schema back; AP242 needs SOLIDWORKS MBD. The drawing's PDF and DXF are exported before its native save.

Run `python -m swkit.smoke` once on a new seat or release, with SOLIDWORKS holding no document, before trusting the kit's numbers. A script that opens and closes documents needs an empty seat. Restarting SOLIDWORKS is the user's call. Wake the screen before a STEP import.
