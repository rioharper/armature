# CAD Build Recipe — SOLIDWORKS

How to realize a part definition in SOLIDWORKS. The part definition's build recipe says *what* to model — the feature sequence and its dimensions; this file says *how* — where the tools live and the habits that keep the model honest.

## 1. Standalone by default — a skeleton only when it pays

Model a part off its own origin planes unless shared geometry earns more. A skeleton earns its existence only when **three or more parts share kinematic dimensions** (link lengths, joint spacing) or a driving length is still expected to move; for a one-off bracket it's ceremony — sketch on the part's own origin and go. When it does pay:

- Create a **skeleton part** (or a layout sketch in the assembly): sketches and reference geometry that carry the frames, joint locations, and key link lengths — nothing solid. This is the single place the kinematic dimensions live.
- Bring frames in as **coordinate systems** and **reference planes/axes** (Insert → Reference Geometry), named for the project frames (`{B}_base`, `{2}_hip`, …) so the assembly's geometry is legible against the plan's Section 1.
- Individual parts reference the skeleton (derived sketch, or in-context references to skeleton geometry). Change a link length in the skeleton and every part built on it updates. Use in-context references deliberately and sparingly — they're powerful and they're also the classic source of circular-reference headaches; a shared skeleton the parts *read from* is safer than parts referencing each other.

## 2. Datums and the base feature = the datum scheme

The part's datum scheme (documentation-standards §5) becomes its opening feature tree. Put the part's primary datum on its Front/Top/Right or a created plane that matches the functional mounting face, sketch the base feature on it, and build outward so the feature tree reads in the same order a machinist would set up the part. A model rooted on functional datums dimensions cleanly onto a drawing later; one rooted on arbitrary planes fights every revision.

## 3. Drive dimensions from the parameter table

This is where design intent is won or lost. Any dimension that traces to a kinematic/dynamic parameter or an interface contract must be *driven*, not typed as a loose number that goes stale the moment the math updates. Every other dimension is a plain typed number — parametrizing a wall thickness nothing else depends on adds fragility, not intent:

- Open **Tools → Equations** and create **global variables** for the parameters — link length, bolt-circle diameter, bore, wall thickness (`"link_len" = 200mm`).
- Drive sketch dimensions from them: double-click the dimension, enter `= "link_len"`. The dimension now shows a Σ and follows the variable.
- For a table of parameters, either keep them in the Equations dialog or **link to an external text/Excel file** (Equations → link to file) so the same parameter file can feed several parts and one edit updates them all. This is the model-side echo of the project's `params.py`: change the number in one place, rebuild, done.
- Where a part comes in several sizes, use a **Design Table** (configurations driven by a spreadsheet) rather than saving copies.

Name your dimensions and features (not `D1@Sketch3`) — a named dimension referenced in an equation is a model someone can read.

## 4. Bring in the COTS model and mate to it

Design around the real part, not a placeholder box:

- Download the supplier's STEP (or SOLIDWORKS) model of each actuator, bearing, and gearbox. Insert it into the assembly as a component.
- Mate your part to *its* interface geometry — the actuator's output-flange face and its bolt-circle, the bearing's OD and shoulder face — so your part's mounting features are constrained by the datasheet geometry directly. When the interface is right in the mate, it's right in the drawing.
- Use the COTS model's mounting face as the reference for your part's mating face rather than re-keying dimensions from the PDF; it removes a transcription error.
- For fasteners and standard hardware, SOLIDWORKS **Toolbox** supplies parametric COTS models — use it for bolts, washers, and retaining rings rather than modeling them.

## 5. Mass properties — the loop-closing measurement

This is the tool that lets you close the loop against the mathematician's assumed inertia:

1. **Assign the material first** (right-click the part → Material) — the mass and inertia are only real once density is set. If the stock isn't in the library (PA-CF, a specific alloy), create a custom material with the density from the BOM.
2. **Tools → Evaluate → Mass Properties.**
3. **Set the output coordinate system to match the mathematician's**, using the "Output coordinate system" dropdown — pick the coordinate system you placed at the joint origin (or ask for it about the COM, depending on which the derivation used). This is the step that makes the comparison meaningful: the reported inertia tensor is *about that coordinate system*, and the mathematician's `00_setup.md` states the point and axes theirs is about. Match them or the numbers disagree for no physical reason.
4. Read mass, center of mass, and the inertia tensor; compare to `params.py`. Beyond tolerance → route back to the mathematician with these measured values (SKILL.md's "close the loop").

Mass Properties updates live as the model changes, so it doubles as a running check against the mass budget through detailing.

## 6. Fits and tolerances

*Which* fit to use is decided in documentation-standards §6; apply it here:

- On a hole, the **Hole Wizard** places standard-sized holes with correct clearances and can carry a fit; on a bore/shaft, add the fit as a **dimension tolerance** (double-click the dimension → Tolerance/Precision → choose Fit, then the ISO class like H7/p6). SOLIDWORKS will show the resulting limits.
- Apply tolerances to the *functional* dimensions only; leave the rest to the drawing's general-tolerance block (§10).
- For model-based tolerancing, **DimXpert** applies dimensions and GD&T to the solid and can drive an MBD (model-based definition) — useful if the shop consumes STEP AP242 with PMI rather than a 2D drawing.

## 7. Sheet metal, weldments, and printed parts

- **Sheet metal:** model in the Sheet Metal environment (Base Flange, Edge Flange, sketched bends) so SOLIDWORKS enforces bend radii and reliefs and can produce a true flat pattern. Set the **k-factor / bend table** to what your shop actually holds — a guessed k-factor gives a flat pattern that's the wrong length.
- **Weldments:** use Weldment structural members with standard profiles for extruded-tube structure; cut lists generate automatically.
- **Printed parts:** design the anisotropy and insert bosses in per documentation-standards §4; there's no special environment, but keep the intended print orientation in mind and note it on the drawing.

## 8. Drawing and export

- **Drawing:** create a drawing from the part, dimension **from the datum scheme** (use ordinate or baseline dimensioning off the primary datum, not chained dimensions that stack tolerance), place GD&T where §7 warrants, and fill the title block (part number and rev per the project scheme, material, finish, general-tolerance block). Add notes the geometry can't state.
- **Export:** File → Save As → **STEP AP242** for a shop or another CAD (AP242 carries PMI if you did MBD); **STL** for printing — set the resolution fine (Options → higher deviation/angle settings) so facets don't show on a bearing bore; **DXF** from the flat pattern for laser/waterjet. State the format and settings in the definition — a coarse default STL on a fit surface is a part that won't assemble.
