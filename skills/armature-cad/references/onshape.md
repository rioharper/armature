# CAD Build Recipe — Onshape

How to realize a part definition in Onshape. The build recipe says *what* to model; this file says *where the tools live* and the habits that keep the model honest.

## 1. Part Studio scope — shared sketches when SKILL.md's rule says they pay

A Part Studio holds *multiple parts built from shared sketches*; scope it to what shares geometry:

- A part that shares nothing gets its own Part Studio, built off the origin planes.
- When driving sketches pay (SKILL.md, "Skeleton and driven dimensions"): lay the controlling geometry — frames, joint axes, link lengths — as sketches in the Part Studio, then build each part from that shared geometry. The kinematic dimensions live once, in those sketches.
- Carry the project frames as **mate connectors** placed at each joint origin and named for the `CONTEXT.md` frames. Mate connectors define a point *and* an orientation, are what the Assembly mates against, and map one-to-one onto the derivation's coordinate frames.
- Keep separate assemblies of parts in their own Part Studios and bring them together in an Assembly via those mate connectors.

## 2. Origin, base feature = datum scheme

The part's datum scheme (documentation-standards §5) is its base sketch plane and the mate connector that seats it. Sketch the base feature on the plane matching the functional mounting face and build outward; anchor the part's locating mate connector on the primary datum so the Assembly seats it the way the function does.

## 3. Driven dimensions — Variables

For the dimensions SKILL.md's rule marks driven:

- Declare a **Variable** per driven dimension, `#` prefix and units — `#link_len = 200 mm`, `#bolt_circle = 45 mm` — via the Variable feature at the top of the feature list, or a shared **Variable Studio** when several Part Studios need the same values (the cloud-native echo of one `params.py`).
- Reference the variable in any dimension or field by name or expression (`#bolt_circle / 2`); editing the variable updates every reference on regen.
- For size families, use **Configurations** driven off variables rather than copies.
- Onshape has real version control: branch and merge design changes rather than saving alternate files.

## 4. Insert the COTS model and mate to it

- Import the supplier's STEP for each actuator, bearing, and gearbox (Import into the document; it lands as its own tab). For standard hardware, **Standard Content** supplies parametric fasteners and some bearings.
- In the Assembly, mate your part to the COTS component using **mate connectors on its interface geometry** — the output flange face and bolt circle, the bearing OD and shoulder.
- Reference the COTS geometry directly rather than re-typing datasheet dimensions.

## 5. Mass properties — the loop-closing measurement

1. **Assign a material first** — right-click the part → Assign material (or Part properties); for stock not in the library (PA-CF, a specific alloy), add a custom material with the BOM's density.
2. Use the **Measure** tool with the part selected, or open **Part properties**, for mass, center of mass, and the inertia tensor.
3. **Report the inertia about the derivation's reference.** Measure reports about the part's origin by default; measure relative to the mate connector you placed at the frame `00_setup.md` names (joint origin or COM).
4. Compare per SKILL.md's Close the loop.

## 6. Fits and tolerances

*Which* fit is documentation-standards §6; apply it here:

- The **Hole** feature for standard holes and clearances; for a shaft/bore fit, add the tolerance to the dimension. Onshape's in-model tolerancing is lightweight, so fit intent usually lives on the drawing.
- Tolerance the functional dimensions only; the rest ride the drawing's general-tolerance block.
- Onshape drawings support the common GD&T controls; apply them where §7 says.

## 7. Sheet metal and printed parts

- **Sheet Metal:** Onshape maintains a synchronized flat pattern and folded model together; set the bend radius and **k-factor / bend table** to what the shop holds.
- **Printed parts:** apply documentation-standards §4; note the print orientation on the drawing.

## 8. Drawing and export

- **Drawing:** create a Drawing from the Part Studio/Assembly, dimension from the datum scheme (baseline/ordinate off the primary datum, not stacked chains), add GD&T where §7 warrants, complete the title block (part number and rev per the project scheme, material, finish, tolerance block), and add notes the geometry can't state.
- **Export:** right-click the part/tab → Export → **STEP** for a shop or another CAD; **STL** with a fine chord/angle tolerance for print; **DXF/DWG** from the flat pattern for laser/sheet. State format and settings in the definition (documentation-standards §10).
