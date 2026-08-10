# Executable build recipes (build123d)

Optional companion to a part definition. The `.md` is still the part
definition — the contract, the loads, the rationale. These files make its
**Build recipe** section runnable, so the checks in **Done when** are
things a machine confirms instead of things a human promises.

What that buys, in order of value:

1. **The inertia loop closes before anyone opens CAD.** Realized mass, COM,
   and inertia against the values `analysis/model/params.py` assumed —
   cross-platform, at sketch grade, no SolidWorks needed.
2. **The recipe self-validates.** A wall that goes negative under a fillet,
   a feature that fails to build, a driven dimension the recipe can't
   actually survive — found in a second instead of forty minutes in.
   Note the limit: `rebuild_sweep` catches builds that *fail*, not builds
   that are silently *wrong*. A bolt hole hanging off a plate edge still
   makes one valid solid with the same bounding box (and more volume, since
   it removed less material). That class needs an explicit `contained()`
   assertion in the recipe — `part.py` shows the pattern.
3. **Real orthographic views** for the definition's *At a glance* section,
   projected from the actual geometry, so they can't drift from the recipe
   the way a hand-drawn ASCII sketch does.
4. **Interference sweeps at the kinematics/planning stage**, before parts
   exist, when a self-collision is still a joint limit rather than a rebuild.

## Files

| File | Role |
|---|---|
| `check.py` | Library. Mass properties in SI, target comparison, parameter-rebuild sweeps, interference, SVG views. **Holds the unit contract — read its docstring first.** |
| `part.py` | Template for `cad/parts/<PART-ID>.py`. Worked example: the plate-with-a-boss from SKILL.md. Copy and edit. |
| `sweep.py` | Template for a planning-stage interference sweep. Worked example: planar 2R arm folding into its base housing. |
| `stubs.py` | COTS placeholders for when armature-librarian can't find a vendor STEP. Enforces datasheet provenance and a release gate. |

Each file runs its own self-tests via `demo()`:

```bash
uv run --with 'build123d~=0.11' python check.py  # units, parallel axis, containment
uv run --with 'build123d~=0.11' python stubs.py  # envelopes, provenance stamp
uv run --with 'build123d~=0.11' python sweep.py  # self-tests, then the sweep
uv run --with 'build123d~=0.11' python part.py   # mass props vs target + SVG views
```

`part.py` also needs `--with sympy` once `analysis/model/params.py` exists,
since that module imports it.

## Prerequisite

build123d, which pulls Open Cascade (~hundreds of MB). It is **not** a
plugin dependency — nothing in armature requires it. `uv run --with` fetches
it on demand and caches it, same pattern as the bundled SolidWorks MCP.

**Written and tested against build123d 0.11.1.** The version bound is
deliberate: this code depends on API details that have moved before —
`matrix_of_inertia` is about the COM in mm⁵ (volumetric, density = 1),
`center_of_mass` does not exist (it is `center(CenterOf.MASS)`), and
`intersect` returns `None` rather than an empty result for disjoint shapes.
Before relaxing the bound, re-run all four `demo()` self-tests; they are
written to fail loudly if any of those change.

To install into a project properly:

```bash
uv add 'build123d~=0.11'      # or: pip install 'build123d~=0.11'
```

## The two rules

**Units.** build123d is millimetre-native; `params.py` is SI. `mm()` in
`check.py` is the only place a factor of 1000 may appear, and everything
`check.py` returns is SI, because that is the derivation's unit system and
the comparison has to happen there. Getting this wrong gives a 1000x length
error and a 1e15x inertia error, both of which look plausible.

**One source of truth.** The `.py` never restates a dimension that lives in
`params.py` or an interface table — it imports them. A `.md` and a `.py`
that disagree about a bolt circle are worse than having no `.py` at all.

## Where this stops

Not a replacement for the CAD package. No assemblies or mates, no
toleranced drawings, no GD&T, no title blocks, no FEA. Release-grade
drawings and the manufacturing deliverable come out of SOLIDWORKS, Fusion,
or Onshape as they always did. This is the check that runs before you get
there, and the picture that goes in the definition.
