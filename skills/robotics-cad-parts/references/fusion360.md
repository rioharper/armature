# CAD Build Recipe — Fusion 360

How to realize a part definition in Fusion 360 so the model captures **design intent** — structured so an upstream parameter change updates the geometry instead of leaving a stale number behind. Build in the order below.

## 1. Component structure and a base skeleton

Fusion mixes bodies and components in one file, so discipline matters:

- Make every real part a **Component** (not a loose body), named per the project part scheme. Components are what get their own origin, joints, and eventually drawings.
- Create a **base/skeleton component** anchored at the world origin holding the controlling sketches and construction geometry — the frames, joint axes, and link lengths — nothing solid. Other components reference it, so the kinematic dimensions live in one place.
- Ground the base component. Represent the project frames as **construction planes/axes and a construction point** per joint (Construct menu), named for the plan's Section 1 frames so the model is legible against the glossary.

## 2. Origin, base feature = datum scheme

The part's datum scheme (documentation-standards §5) is its component origin plus the first sketch plane. Put the primary datum on the component's origin plane that matches the functional mounting face, sketch the base feature there, and extrude outward. Building on the component origin (rather than an arbitrary offset) is what makes joints and drawing dimensions land cleanly.

## 3. Drive dimensions from the parameter table — the Parameters dialog

This is where design intent is won or lost in Fusion:

- **Modify → Change Parameters** opens the parameters table. Add **User Parameters** for each kinematic/dynamic value (`link_len = 200 mm`, `bolt_circle = 45 mm`, `wall = 4 mm`) with units and an optional comment.
- In any sketch dimension or feature input, type the parameter name (or an expression like `bolt_circle/2`) instead of a raw number. The dimension now follows the parameter.
- Editing a User Parameter updates every dimension that references it on the next compute — the model-side echo of `params.py`. Keep one parameter per real design driver and reference it everywhere, rather than typing the same number in three sketches.
- For size families, drive a **Configuration** (Fusion's configurations table) from the parameters rather than saving copies.

## 4. Insert the COTS model and joint to it

Design around the real part:

- Fusion has **Insert → Insert McMaster-Carr Component**, which drops in real fasteners, bearings, and hardware directly as components — use it for standard hardware. For actuators and gearboxes, upload the supplier's STEP and insert it.
- Constrain your part to the COTS component's interface with **Joints** or **As-Built Joints** referencing the datasheet geometry — the output flange face and bolt circle, the bearing OD and shoulder. Getting the interface right in the joint gets it right everywhere downstream.
- Reference the COTS mounting face directly for your mating face rather than re-typing dimensions from the PDF; it kills a transcription error.

## 5. Physical properties — the loop-closing measurement

The tool for closing the loop against the mathematician's assumed inertia:

1. **Assign a Physical Material first** (right-click component → Physical Material, or the Modify menu) — mass and inertia are only real once density is set. For stock not in the library (PA-CF, a specific alloy), create a custom material with the BOM's density.
2. Open the component's **Properties** (right-click component → Properties) or **Inspect → Physical Properties**.
3. Physical Properties reports mass, center of mass, and the **moments of inertia** — read carefully *which point and axes* Fusion is reporting about (it gives values at the origin and at the center of mass; the panel labels which). Match this to the point and axes the mathematician's `00_setup.md` used. This match is what makes the comparison mean anything — an inertia about the component origin will not equal one the derivation took about the COM.
4. Compare to `params.py`; beyond tolerance → route back to the mathematician with the measured mass, COM, and inertia (SKILL.md's "close the loop").

## 6. Fits and tolerances

*Which* fit — documentation-standards §6; apply it here:

- Fusion's **Hole** feature places standard holes and clearances; for a shaft/bore fit, add the tolerance to the dimension (edit the dimension → tolerance fields) — Fusion's parametric tolerancing is lighter than SOLIDWORKS's, so the fit intent often lives primarily on the drawing rather than in the model.
- Tolerance the functional dimensions only; everything else rides the drawing's general-tolerance block.
- Fusion's GD&T support in drawings covers the common controls (position, flatness, etc.); apply them where §7 says they earn their keep.

## 7. Sheet metal, and printed / machined parts

- **Sheet Metal** workspace: set a **Sheet Metal Rule** (material, thickness, bend radius, **k-factor** to what the shop holds) before flanging, so bends and reliefs are enforced and the flat pattern is the right length.
- **Printed parts:** apply the anisotropy and insert-boss rules from documentation-standards §4; note the intended print orientation on the drawing.
- **Machining in-house:** Fusion's **Manufacture (CAM)** workspace generates toolpaths from the same model — a genuine advantage if you're cutting the part yourself; keep the design's minimum internal radii ≥ your smallest end mill.

## 8. Drawing and export

- **Drawing:** switch to the **Drawing** workspace from the component, dimension from the datum scheme (baseline/ordinate off the primary datum, not stacked chains), add GD&T where §7 warrants, and fill the title block (part number and rev per the project scheme, material, finish, tolerance block) plus any notes the geometry can't carry.
- **Export:** right-click the component → Save As Mesh for **STL** (set refinement High so facets don't show on fit surfaces) for print; **Export** → **STEP** for a shop or another CAD; **DXF** from the flat pattern for laser/sheet. State format and settings — a coarse STL on a bearing bore won't press together.
