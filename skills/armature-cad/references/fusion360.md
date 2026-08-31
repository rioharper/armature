# CAD Build Recipe — Fusion 360

How to realize a part definition in Fusion 360. The build recipe says *what* to model; this file says *where the tools live* and the habits that keep the model honest.

## 1. Component structure — a skeleton when SKILL.md's rule says one pays

Fusion mixes bodies and components in one file:

- Make every real part a **Component** (not a loose body), named per the project part scheme. Components get their own origin, joints, and eventually drawings.
- Model a part off its own component origin by default. When a skeleton pays (SKILL.md, "Skeleton and driven dimensions"): make a **base component** anchored at the world origin holding only the controlling sketches and construction geometry — nothing solid — and ground it. Represent the project frames as **construction planes/axes and a construction point** per joint (Construct menu), named for the `CONTEXT.md` frames.

## 2. Origin, base feature = datum scheme

The part's datum scheme (documentation-standards §5) is its component origin plus the first sketch plane. Put the primary datum on the origin plane matching the functional mounting face, sketch the base feature there, and extrude outward. Building on the component origin is what makes joints and drawing dimensions land cleanly.

## 3. Driven dimensions — the Parameters dialog

For the dimensions SKILL.md's rule marks driven:

- **Modify → Change Parameters**: add a **User Parameter** per driven dimension (`link_len = 200 mm`, `bolt_circle = 45 mm`) with units and an optional comment.
- In any sketch dimension or feature input, type the parameter name (or an expression like `bolt_circle/2`) instead of a raw number.
- Editing a User Parameter updates every reference on the next compute — the model-side echo of `params.py`. One parameter per real design driver, referenced everywhere, rather than the same number typed in three sketches.
- For size families, drive a **Configuration** from the parameters rather than saving copies.

## 4. Insert the COTS model and joint to it

- **Insert → Insert McMaster-Carr Component** drops in real fasteners, bearings, and hardware as components. For actuators and gearboxes, upload the supplier's STEP and insert it.
- Constrain your part to the COTS component's interface with **Joints** or **As-Built Joints** referencing the datasheet geometry — the output flange face and bolt circle, the bearing OD and shoulder.
- Reference the COTS mounting face directly for your mating face rather than re-typing dimensions from the PDF.

## 5. Physical properties — the loop-closing measurement

1. **Assign a Physical Material first** (right-click component → Physical Material, or the Modify menu); for stock not in the library (PA-CF, a specific alloy), create a custom material with the BOM's density.
2. Open the component's **Properties** (right-click component → Properties) or **Inspect → Physical Properties**.
3. Read *which point and axes* Fusion reports the **moments of inertia** about — it gives values at the origin and at the center of mass, and the panel labels which. Match the one `00_setup.md` used.
4. Compare per SKILL.md's Close the loop.

## 6. Fits and tolerances

*Which* fit is documentation-standards §6; apply it here:

- The **Hole** feature places standard holes and clearances; for a shaft/bore fit, add the tolerance to the dimension (edit the dimension → tolerance fields). Fusion's parametric tolerancing is lighter than SOLIDWORKS's, so fit intent usually lives on the drawing.
- Tolerance the functional dimensions only; the rest ride the drawing's general-tolerance block.
- Fusion's drawing GD&T covers the common controls (position, flatness, etc.); apply them where §7 says.

## 7. Sheet metal, and printed / machined parts

- **Sheet Metal** workspace: set a **Sheet Metal Rule** (material, thickness, bend radius, **k-factor** to what the shop holds) before flanging, so bends and reliefs are enforced and the flat pattern is true.
- **Printed parts:** apply documentation-standards §4; note the print orientation on the drawing.
- **Machining in-house:** the **Manufacture (CAM)** workspace generates toolpaths from the same model; keep the design's minimum internal radii ≥ your smallest end mill.

## 8. Drawing and export

- **Drawing:** switch to the **Drawing** workspace from the component, dimension from the datum scheme (baseline/ordinate off the primary datum, not stacked chains), add GD&T where §7 warrants, fill the title block (part number and rev per the project scheme, material, finish, tolerance block), and add notes the geometry can't carry.
- **Export:** right-click the component → Save As Mesh for **STL** (refinement High) for print; **Export** → **STEP** for a shop or another CAD; **DXF** from the flat pattern for laser/sheet. State format and settings in the definition (documentation-standards §10).
