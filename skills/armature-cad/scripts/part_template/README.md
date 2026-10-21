# Executable build recipes (build123d)

Optional companion to a part definition. The `.md` stays the part
definition — the contract, the loads, the rationale. These files make its
**Build recipe** section runnable, so the checks in **Done when** are
things a machine confirms.

What that buys, in order of value:

1. **The inertia loop closes before anyone opens CAD.** Realized mass, COM,
   and inertia against the values the ledger says the dynamics assumed —
   cross-platform, at sketch grade, no SolidWorks needed — and written
   back into the ledger with `set --from-part` (below).
2. **The recipe self-validates.** A wall that goes negative under a fillet,
   a feature that fails to build, a driven dimension the recipe can't
   survive — found in a second. `rebuild_sweep` catches builds that
   *fail*, not builds that are silently *wrong*; geometry that must stay
   inside other geometry needs `contained()` (its docstring says what it
   catches and how to probe; `part.py` shows the pattern).
3. **Real projected views** for the definition's *At a glance* section,
   from the actual geometry, so they can't drift from the recipe.
   Front/top/right export true 1:1; the iso is orientation only.
4. **Interference sweeps at the kinematics/planning stage**, before parts
   exist, when a self-collision is still a joint limit rather than a
   rebuild. The sweep is a finite grid: it can only be guaranteed to catch
   a collision band wider than its step, and the first interfering sample
   can sit up to one step past the true onset, so a joint limit read off
   it goes at least one step inside. `joint_limits_and_interior`'s
   docstring says how to size the grid; `sweep_clearance`'s says which
   pairs an `ignore` threshold fits and what each kind of excuse hides.

## Files

| File | Role |
|---|---|
| `check/` | Library package. Mass properties in SI, target comparison, parameter-rebuild sweeps, interference, SVG views, and the ledger's reader (`check/ledger.py`, standard library only), one submodule each. **Holds the unit contract — read `check/__init__.py`'s docstring first.** |
| `part.py` | Template for `cad/parts/<PART-ID>.py`. Worked example: the plate-with-a-boss from SKILL.md. Copy and edit. |
| `ledger.toml` | The worked example's numbers, for this template's own self-run: the stock's density and the bracket's mass budget line. **Never copy it into a project**: a part file reads the nearest ledger at or above its folder, and this one beside it would shadow the project's. |
| `sweep/` | Template for a planning-stage interference sweep. Worked example: planar 2R arm folding into its base housing. Replace the envelopes and `CARRIERS` in `sweep/bodies.py`. |
| `stubs.py` | COTS placeholders for when armature-librarian can't find a vendor STEP. Enforces datasheet provenance; its release gate `still_placeholder()` only sees stubs *this process built* — read its docstring before gating on it. |
| `run_all.py`, `layout.py`, `layout_checks.py` | The runner and the code-line budget, the same files armature-derive's model template ships. |

The files follow the plugin's `references/model-layout.md`: each module's
self-tests live one file over in its `*_checks.py` (`part.py` →
`part_checks.py`, copied as `<PART-ID>_checks.py`; `check/mass.py` →
`check/mass_checks.py`), and no module passes 250 code lines. One command
runs every self-test and the budget; the other two run the things
themselves:

```bash
uv run --project ../../analysis/model --with 'build123d~=0.11' python run_all.py  # every self-test, then the budget
uv run --project ../../analysis/model --with 'build123d~=0.11' python -m sweep    # the sweep
uv run --with 'build123d~=0.11' python run_all.py check   # one module or package's self-tests
uv run --with 'build123d~=0.11' python part.py            # mass props vs target + SVG views
python layout.py                                          # the size table, stdlib only
```

Run them from `cad/parts/`. The full run and the sweep need the model's environment,
`analysis/model/pyproject.toml`, because the sweep's postures come from the engine;
a part file and `check/` need only build123d.

**The exit code is the contract: nonzero means a check failed**, which is
what makes these usable in a pre-commit hook or CI. `sweep/`'s worked 2R
arm genuinely folds into its own base post, so `python -m sweep` prints the
colliding pairs and **exits 1 by design** until the swept range excludes the
collision. `run_all.py`, `part.py`, and `layout.py` exit 0.

`part.py` and `sweep/` both read the project's `ledger.toml` (ADR 0010).
A part file reads the nearest one at or above its own folder with the
standard library's `tomllib`: the stock's density, its body's mass, COM and
inertia targets, and its mass budget line. The sweep reads the ledger the
model reads, at or above `analysis/model/`, through the engine, and also
imports `mechanism.py` and compiles it: each envelope rides on a site of
the description, posed by the truth model, over the description's joint
ranges. It locates `analysis/model/` *relative to its own path* —
`../../analysis/model/` from `cad/parts/` — so keep it two directories
below the project root. `part.py`'s target falls back to its budget line
while `BODY` is still the placeholder, at sketch grade, and says so in its
printed provenance line; the sweep's link lengths have no fallback (a
guessed link length hides a real self-collision or invents one), and nor do
its postures (a hand-written pose is a second forward kinematics), so
running it — its self-tests included — needs the ledger's `mechanism`
section and `mechanism.py`: run the armature-derive milestone that produces
them first. Importing the package alone never needs them.

## Writing the measurement back

Once a part's numbers are worth the dynamics' re-run, write them into the
ledger from `cad/parts/`:

```bash
uv run --project ../../analysis/model --with 'build123d~=0.11' \
    python -m armature.ledger set part.<PART-ID> --from-part <PART-ID>.py
```

`set` runs `<PART-ID>.py --mass-properties`, which prints the measurement as
one JSON line, and writes `part.<PART-ID>.mass`, `.com` and `.inertia` with
`source = { kind = "cad", ref = "<file>@<rev>" }` and `status = "candidate"`;
the rev is the file's last commit, `+dirty` if it has changed since. The
tensor carries its `point` and `axes` and the COM its `point` (the origin it
is measured from) and `axes`, from the part file's `ABOUT`, `ORIGIN` and
`AXES`; `set` refuses a measurement without them. It writes through
tomlkit, so comments, order and the fields it doesn't own — a `note`, an
estimate's `band` — survive, and a new entry goes at the end of the file. A
re-run on an unchanged part changes nothing, a confirmation included. Then
point the description's body at the entries with `of` and re-run the model:
`ledger check` flags a `confirmed` body that reads a `candidate`, until you
confirm the measurement.

## Prerequisite

build123d, which pulls Open Cascade (~hundreds of MB). It is **not** a
plugin dependency. `uv run --with` fetches it on demand and caches it, same
pattern as the SolidWorks MCP server.

**Written and tested against build123d 0.11.1.** The version bound is
deliberate: this code depends on API details that have moved before —
`matrix_of_inertia` is about the COM in mm⁵ (volumetric, density = 1),
`center_of_mass` does not exist (it is `center(CenterOf.MASS)`), and
`intersect` returns `None` rather than an empty result for disjoint shapes.
Before relaxing the bound, re-run `run_all.py`; its self-tests fail loudly
if any of those change.

To install into a project properly:

```bash
uv add 'build123d~=0.11'      # or: pip install 'build123d~=0.11'
```

## The two rules

**Units.** build123d is millimetre-native; the ledger is SI. `mm()` in
`check/` is the only place a factor of 1000 may appear, and everything
`check/` returns is SI, because the comparison happens in the derivation's
units. The full contract is `check/__init__.py`'s docstring.

**One source of truth.** The `.py` never restates a dimension that lives in
the ledger or an interface table — it reads them. A `.md` and a `.py`
that disagree about a bolt circle are worse than having no `.py` at all.

## Where this stops

Not a replacement for the CAD package. No assemblies or mates, no
toleranced drawings, no GD&T, no title blocks, no FEA. Release-grade
drawings and the manufacturing deliverable come out of SOLIDWORKS, Fusion,
or Onshape. This is the check that runs before you get there, and the
picture that goes in the definition.
