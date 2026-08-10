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
3. **Real projected views** for the definition's *At a glance* section,
   from the actual geometry, so they can't drift from the recipe the way a
   hand-drawn ASCII sketch does. Front/top/right are exported true 1:1 and
   share one scale, so a feature measured off the page is the part's real
   millimetres; the iso view is for orientation only, since an isometric
   projection foreshortens every 3D length.
4. **Interference sweeps at the kinematics/planning stage**, before parts
   exist, when a self-collision is still a joint limit rather than a rebuild.
   Note the limit, beside rebuild_sweep's above: the sweep is a finite grid
   over the joint range, so it can only be GUARANTEED to catch a collision
   band wider than the grid's step — a genuine collision narrower than the
   step, sitting between two sampled postures, is invisible. `sweep.py`'s
   default resolution is sized to the worked example's own narrowest known
   band (11 deg); a mechanism with tighter geometry needs a finer grid, and
   `sweep.py`'s docstring says how to re-measure and pick one.

## Files

| File | Role |
|---|---|
| `check.py` | Library. Mass properties in SI, target comparison, parameter-rebuild sweeps, interference, SVG views. **Holds the unit contract — read its docstring first.** |
| `part.py` | Template for `cad/parts/<PART-ID>.py`. Worked example: the plate-with-a-boss from SKILL.md. Copy and edit. |
| `sweep.py` | Template for a planning-stage interference sweep. Worked example: planar 2R arm folding into its base housing. |
| `stubs.py` | COTS placeholders for when armature-librarian can't find a vendor STEP. Enforces datasheet provenance, and offers a release gate that is only as good as the process it runs in — `still_placeholder()` sees the stubs *this process built*, so an empty list from a process that built nothing is not a clean release. Read its docstring before gating on it. |

Each file runs its own self-tests via `demo()`:

```bash
uv run --with 'build123d~=0.11' python check.py  # units, parallel axis, containment
uv run --with 'build123d~=0.11' python stubs.py  # envelopes, provenance stamp
uv run --with 'build123d~=0.11' --with sympy python sweep.py  # self-tests, then the sweep
uv run --with 'build123d~=0.11' --with sympy python part.py   # mass props vs target + SVG views
```

**The exit code is the contract for the set: nonzero means a check failed**,
which is what makes these usable in a pre-commit hook or CI. Note that this
cuts against the worked examples too — `sweep.py`'s 2R arm genuinely folds
into its own base post, so `python sweep.py` runs its self-tests, prints the
colliding pairs, and **exits 1 by design**. That is the tool working, not the
tool broken; it goes to 0 once the joint limits in the swept range exclude
the collision. `check.py`, `stubs.py`, and `part.py` exit 0.

`part.py` and `sweep.py` both need `--with sympy`, since both import
`analysis/model/params.py`, which imports it. Both also locate that file
*relative to their own path* — `../../analysis/model/` — so keep them two
directories below the project root (`cad/parts/`, which is where `part.py`
tells you to put them). Put a copy anywhere else in the tree and it looks
for `params.py` in the wrong place — the path is resolved from the file's
own location, so the directory you happen to run from doesn't enter into it.

`sweep.py` is stricter than `part.py` about `params.py`: `part.py`'s mass
target can fall back to a budget row when there is no derivation yet, and
says so loudly in its printed provenance line; `sweep.py`'s link lengths
have no such fallback, because a guessed link length could hide a real
self-collision or invent one that isn't there. `import sweep` itself never
needs `params.py` (the resolve is deferred to `main()`/`demo()`, so the
module stays importable from anywhere), but actually *running* it — its
own `demo()` self-test included — does, and raises clearly if it's
missing: copy `params.py` in (or run the armature-math milestone that
produces it) first.

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
