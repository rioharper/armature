# CAD repository layout

Where geometry lives, what leaves it, and how it stays traceable to the numbers it was built from.

```
cad/
  README.md                  which package, units, and the document link if cloud-based
  parts/                     native part files       IBEX-LNK-002.sldprt
  assemblies/                native assemblies       IBEX-ASM-001.sldasm
  drawings/                  native drawings         IBEX-LNK-002.slddrw
  cots/                      vendor models — never edited
  exports/
    step/                    IBEX-LNK-002_r03.step   AP242, for machining
    stl/                     IBEX-LNK-002_r03.stl    for printing
    dxf/                     IBEX-LNK-002_r03.dxf    flat patterns for sheet/laser
    pdf/                     IBEX-LNK-002_r03.pdf    dimensioned drawings for the shop
  mass-properties/           IBEX-LNK-002.json       extracted, for the inertia loop
  sim/
    visual/                  decimated meshes for URDF/USD rendering
    collision/               convex hulls or primitives for physics
```

Part definitions — the markdown documents this skill authors — stay in `docs/parts/`, not here. `cad/` holds geometry; `docs/` holds the reasoning about it.

## Native names are stable; exports carry the rev

This split matters more than it looks:

- **Native files never carry a revision in the filename.** `IBEX-LNK-002.sldprt`, not `IBEX-LNK-002_r03.sldprt`. Assemblies and drawings hold external references to part files by path, so renaming a part on every revision breaks every reference to it — the classic way a CAD tree quietly detaches from itself. Git already holds the revision history, better than a filename can.
- **Exports and drawings do carry the rev.** `IBEX-LNK-002_r03.step` leaves the repo and lands in a shop's inbox or a slicer, where there is no git history and no ambiguity budget. A machinist holding two files needs to know which is newer from the name alone.

The rev in an export filename matches the rev in the drawing's title block and the `rev` field of the part definition. Bump all three together or none.

## Binaries need LFS

Native CAD files, STEP, and meshes are binary and large; git stores a full copy of every version. Track them with LFS from the first commit — retrofitting means rewriting history.

`.gitattributes` at the repo root:

```gitattributes
*.sldprt  filter=lfs diff=lfs merge=lfs -text
*.sldasm  filter=lfs diff=lfs merge=lfs -text
*.slddrw  filter=lfs diff=lfs merge=lfs -text
*.f3d     filter=lfs diff=lfs merge=lfs -text
*.f3z     filter=lfs diff=lfs merge=lfs -text
*.step    filter=lfs diff=lfs merge=lfs -text
*.stp     filter=lfs diff=lfs merge=lfs -text
*.stl     filter=lfs diff=lfs merge=lfs -text
*.obj     filter=lfs diff=lfs merge=lfs -text
*.3mf     filter=lfs diff=lfs merge=lfs -text
*.pdf     filter=lfs diff=lfs merge=lfs -text
*.png     filter=lfs diff=lfs merge=lfs -text
*.jpg     filter=lfs diff=lfs merge=lfs -text

*.md      text eol=lf
*.py      text eol=lf
*.yaml    text eol=lf
*.json    text eol=lf
*.urdf    text eol=lf
*.dxf     text eol=lf
```

DXF stays text so its diffs are readable. STEP is nominally text too, but a solid model's STEP runs to megabytes of coordinates that no one reads — LFS it.

**What is not committed:** CAD package backup and lock files (`~$*`, `*.sldprt.bak`, `*.lck`), mesh caches, and thumbnail databases. They belong in `.gitignore`.

## Cloud CAD

Onshape holds no local native files, and Fusion's cloud documents are only exported copies. In that case `cad/parts/` and `cad/assemblies/` stay empty or absent, and `cad/README.md` carries the document URL, the workspace/version being worked in, and the export date of everything under `exports/`. Record the Onshape *version* name — not just the document link — or an export can't be traced to the state that produced it.

The consequence is worth stating plainly: with cloud CAD, git no longer holds the geometry's history, only its exports. Tag a version in Onshape at every freeze so the two systems have matching reference points.

## COTS models are read-only

Vendor models go in `cad/cots/` under their part number and are never edited — not to simplify, not to fix a mate. A modified vendor model that still carries the vendor's name is a part whose real dimensions nobody can check against the datasheet. If simplification is genuinely needed (a 400-face connector slowing an assembly), save the simplified version as a project part with a project ID and note what it stands in for.

Every file here should trace to a `datasheet` entry in `docs/bom.yaml`. A COTS model with no datasheet behind it is a set of dimensions from an unknown source.

## Simulation meshes

`cad/sim/` exists because URDF and USD need geometry, and the geometry they need is not the geometry the shop needs:

- **`visual/`** — decimated. Target a few thousand triangles per link; a full-fidelity export makes a sim that renders slowly for no benefit.
- **`collision/`** — convex hulls, or better, primitives (boxes, cylinders, spheres) hand-placed. Physics engines resolve contacts against these, and a concave mesh either gets silently convexified or tanks the step rate.

`armature-mathematician`'s `export.py` emits URDF referencing these paths and asserts that link masses and inertias in the emitted file match `params.py`. It generates from the parameter block rather than reading the meshes, so the meshes only supply shape — the physics comes from the same numbers the dynamics were derived from.

## Mass-properties export schema

`cad/mass-properties/<PART-ID>.json` is how CAD answers back to the dynamics. Export it whenever a part's geometry changes materially, then run `scripts/check_inertia.py`.

```json
{
  "part_id": "IBEX-LNK-002",
  "cad_package": "SOLIDWORKS",
  "exported": "2026-07-28",
  "rev": "r03",
  "material": "6061-T6",

  "mass_kg": 1.8,
  "com_m": [0.15, 0.0, 0.0],
  "inertia_kg_m2": { "Ixx": 0.0, "Iyy": 0.0135, "Izz": 0.0135,
                     "Ixy": 0.0, "Iyz": 0.0, "Ixz": 0.0 },

  "inertia_about": "com",
  "inertia_axes": "J2",
  "joint_to_com_m": [0.15, 0.0, 0.0],
  "dynamics_expects": { "about": "joint", "axes": "J2" },

  "params_keys": { "mass": "m_thigh", "com": "c_thigh", "inertia": "I_thigh" },
  "tolerances": { "mass_rel": 0.02, "inertia_rel": 0.05 }
}
```

**`inertia_about` and `inertia_axes` are the fields people drop, and dropping them is why a correct derivation and a correct model appear to disagree.** An inertia tensor means nothing without the point it was taken about and the frame it is expressed in. State both, state what the dynamics expect, and the checker transforms between them: parallel axis for the point, and `rotation_to_dynamics_axes` (a 3×3) for the frame. When it can't reconcile them it reports a finding rather than comparing incomparable numbers.

`inertia_kg_m2` also accepts a 3×3 nested list or a 6-vector `[Ixx, Iyy, Izz, Ixy, Iyz, Ixz]`, whichever your CAD package exports most cleanly. Set SI units in the mass-properties dialog before exporting; a report in g·mm² is off by 10⁹ and will read as a spectacular divergence.

`tolerances` is optional and per-part. Defaults are 2% on mass, 1 mm on COM, 5% on inertia — tighten them for a link whose inertia drives the dynamics, loosen them for a bracket that only has to be strong enough.
