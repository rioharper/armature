# CAD Build Recipe — Onshape

How to realize a part definition in Onshape so the model captures **design intent** — structured so an upstream parameter change updates the geometry rather than stranding a stale number. Onshape's Part Studio model makes top-down design the natural default; lean into it. Build in the order below.

## 1. Part Studio as the skeleton — top-down by default

A Part Studio holds *multiple parts built from shared sketches*, which is top-down design without extra ceremony:

- Lay the controlling geometry — frames, joint axes, link lengths — as sketches in the Part Studio, then build each part from that shared geometry. The kinematic dimensions live once, in those driving sketches, and every part follows them.
- Carry the project frames as **mate connectors** placed at each joint origin and named for the plan's Section 1 frames. Mate connectors are Onshape's idiomatic frame carriers: they define a point *and* an orientation, they're exactly what the Assembly mates against, and they map one-to-one onto the coordinate frames the derivation uses.
- Keep genuinely separate assemblies of parts in their own Part Studios and bring them together in an Assembly via those mate connectors.

## 2. Origin, base feature = datum scheme

The part's datum scheme (documentation-standards §5) is its base sketch plane and the mate connector that seats it. Sketch the base feature on the plane matching the functional mounting face and build outward; anchor the part's locating mate connector on the primary datum so the Assembly seats it the way the function does.

## 3. Drive dimensions from the parameter table — Variables

This is where design intent is won or lost in Onshape:

- Declare **Variables** for each kinematic/dynamic parameter with a `#` prefix and units — `#link_len = 200 mm`, `#bolt_circle = 45 mm`, `#wall = 4 mm` — using the Variable feature at the top of the feature list, or a shared **Variable Studio** if several Part Studios need the same values (the cloud-native echo of one `params.py` feeding everything).
- Reference the variable in any dimension or field by name or expression (`#bolt_circle / 2`). The dimension follows the variable; editing the variable updates every reference on regen.
- For size families, use **Configurations** driven off variables rather than copies.
- Because Onshape is cloud-native with real version control, the driving sketches and variables are the authoritative geometry — branch and merge design changes rather than saving alternate files.

## 4. Insert the COTS model and mate to it

Design around the real part:

- Import the supplier's STEP for each actuator, bearing, and gearbox (Import into the document; it lands as its own tab). For standard hardware, Onshape's **Standard Content** library supplies parametric fasteners and some bearings.
- In the Assembly, mate your part to the COTS component using **mate connectors on its interface geometry** — the output flange face and bolt circle, the bearing OD and shoulder. A correct interface mate is a correct interface everywhere downstream.
- Reference the COTS geometry directly rather than re-typing datasheet dimensions; it removes a transcription error.

## 5. Mass properties — the loop-closing measurement

The tool for closing the loop against the mathematician's assumed inertia:

1. **Assign a material first** — right-click the part → Assign material (or Part properties) — since mass and inertia need density. For stock not in the library (PA-CF, a specific alloy), add a custom material with the BOM's density.
2. Use the **Measure** tool with the part selected, or open **Part properties**, to get mass, center of mass, and the inertia tensor.
3. **Report the inertia about the right reference.** Measure reports about the part's origin by default; to compare against a derivation that used the joint origin or the COM, take the inertia about the matching mate connector / point and axes. Onshape lets you measure relative to a selected mate connector — use the one you placed at the frame the mathematician's `00_setup.md` names. Matching the point and axes is what makes the comparison physical rather than nonsense.
4. Compare to `params.py`; beyond tolerance → route back to the mathematician with the measured mass, COM, and inertia (SKILL.md's "close the loop").

## 6. Fits and tolerances

*Which* fit — documentation-standards §6; apply it here:

- Use the **Hole** feature for standard holes and clearances; for a shaft/bore fit, add the tolerance to the dimension. Onshape's in-model tolerancing is lightweight, so fit intent usually lives on the drawing.
- Tolerance functional dimensions only; the rest rides the drawing's general-tolerance block.
- Onshape drawings support the common GD&T controls; apply them where §7 says they earn their keep.

## 7. Sheet metal and printed parts

- **Sheet Metal:** Onshape's sheet-metal tools maintain a synchronized flat pattern and folded model together; set the bend radius and **k-factor / bend table** to what the shop holds so the flat pattern length is right.
- **Printed parts:** apply the anisotropy and insert-boss rules from documentation-standards §4; note intended print orientation on the drawing.

## 8. Drawing and export

- **Drawing:** create a Drawing from the Part Studio/Assembly, dimension from the datum scheme (baseline/ordinate off the primary datum, not stacked chains), add GD&T where §7 warrants, and complete the title block (part number and rev per the project scheme, material, finish, tolerance block) plus notes the geometry can't state.
- **Export:** right-click the part/tab → Export → **STEP** for a shop or another CAD; **STL** with a fine chord/angle tolerance so facets don't show on fit surfaces, for print; **DXF/DWG** from the flat pattern for laser/sheet. State format and settings — a coarse STL on a bearing bore won't press together.
