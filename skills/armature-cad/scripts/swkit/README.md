# swkit: SOLIDWORKS by script

Python helpers for driving a running SOLIDWORKS through its COM API (pywin32): building a part from its build recipe with the design intent a person would give it, checking it against the numbers it was built from, drawing it to its critical features, and exporting it. Every rule in here cost a failed run once on a real project; the module docstrings say which call it guards.

Use it when the project's CAD package is SOLIDWORKS and a part is worth building by script: its driven dimensions are still moving, it has a mirrored hand, it will be rebuilt as the ledger moves, or its drawing will be redone at every revision. A one-off bracket is faster by hand. For reading a live model from the conversation (mass properties, a dimension, a rebuild), the plugin's SolidWorks MCP server is the lighter tool; swkit is for scripts a project keeps.

## Running it

Windows, SOLIDWORKS running, `uv` on the path. Copy this folder into the project, conventionally `cad/tools/swkit/`, so its version is pinned with the project's commit, and keep the project's own scripts beside it:

```
cad/tools/
  swkit/                 this folder
  build_bracket.py       from swkit.part import Part ...
```

Run a script from `cad/tools/`, so `swkit` imports:

```
uv run --no-project --with pywin32 python -u build_bracket.py
uv run --no-project --with pywin32 python -m swkit audit ../parts/BRK-001/BRK-001.SLDPRT
```

Check the copy on the seat once, with SOLIDWORKS holding no document (about two minutes; `--fea` adds Simulation's bar, `--import` a STEP read back in):

```
uv run --no-project --with pywin32 python -u -m swkit.smoke
uv run --no-project --with pytest python -m pytest swkit/tests -q      # the pure modules, anywhere
```

The kit finds SOLIDWORKS through the executable registered for `SldWorks.Application`; set `SWKIT_SOLIDWORKS_DIR` to its folder if that fails.

## The contract

- **Lengths a caller passes are mm, angles degrees,** on the model and on the sheet alike; the API's metres stay inside the kit. Mass properties come out SI (kg, m, kg m²), ready for a `cad` ledger entry.
- **A part's frame is its own origin planes:** Front is XY (normal +Z), Top XZ (+Y), Right YZ (+X). Name the planes the project's frames need (`Part.plane`), not one per feature. The standard planes' names are an English-language seat's.
- **Every driven dimension is an equation of the part's globals** (`expr.X` carries a value and its equation text together), so the model moves when a global does. Globals are written unlinked; `part.set_globals` pushes a moved ledger number in.
- **A sketch is fully defined or the build stops.** Relations carry the intent (a centre on the origin, a rectangle symmetric about its centreline, equal fillets); a dimension appears only for a number that is a design input.

## The modules

| Module | What it does |
|---|---|
| `com` | Constants, attaching, argument shapes (`NOTHING`, `byref_*`, `doubles`), `get` for a member bound either way, calls by runtime name, preferences set for a block and put back, documents, custom properties, features and their errors, equations, `restart` |
| `expr` | `X`: an expression's nominal value and its SOLIDWORKS text, with `sin`, `cos`, `sqrt`, `arccos`, `rot`; pure |
| `part` | `Part`: from a template, typed globals, named planes and axes, `extrude` that keeps the side asked for and refuses a faceless boss, `revolve`, `pattern`, feature `fillet`, `name_body`, `mirror_config`; `Sketch`: circles, rings, rectangles, polygons, arcs, angles, a flanged ring, each held fully defined |
| `measure` | Exact extents (`reach`), faces by geometry, mass properties at a density, `faceless_bosses`, `rebuild_test` at globals ±10 % |
| `inertia` | SOLIDWORKS's mass properties to (m, COM, I), the parallel-axis sum; pure |
| `exchange` | STEP copies checked by the schema they wrote, PDF/DXF/STL copies, STEP import, a dumb solid from another tool's STEP, a light part of a heavy vendor model |
| `assembly` | `Asm`: components in a chosen configuration, mates by named references with computed alignments, a vendor model's interface geometry named once |
| `drawing` | `Drawing` and `draw_part`: views at the largest standard scale that fits, arranged for the sheet's projection, notes, exports |
| `annotate` | Diameters, radii, distances with fits or tolerances, datums, feature control frames and leader notes, each on an edge picked by its model geometry; `survey` prints what a view shows |
| `section` | A view's own coordinates, section and detail views, numbered flags on cut edges |
| `layout` | The scale series, view arrangement for third and first angle, numbered notes; pure |
| `simulation` | Linear static studies: restraints, remote loads, pressures, mesh, results by node; `validate_bar` against beam theory |
| `templates` | A project's part and assembly templates: units, drafting standard, title-block properties |

## A build, end to end

1. **Script the recipe** with `Part` and `Sketch`, one function per part, its globals from the ledger (`expr.globals_mm`).
2. **Audit it:** `python -m swkit audit` rebuilds every configuration and lists errors and faceless bosses. A boss that went the wrong way into material already there owns no faces, adds nothing, and looks right in the viewport.
3. **Rebuild it** at its driven globals ±10 % (`python -m swkit rebuild`), the usual *Done when* for a parametric part.
4. **Measure it back** (`measure.reach`, `mass_props`, `find_face`) and write the measurement to the ledger as `cad` entries, per armature-cad's *Close the loop*. Never put a number in a part definition that was not read off the model.
5. **Draw it** (`draw_part`): the critical features dimensioned on the views, the STEP governing the rest, three to five terse notes. Rationale goes in the part definition, never on the sheet.
6. **Export it** (`exchange.export_step` at AP214, the drawing's PDF and DXF), each copy read back.

## Working on the user's seat

The seat is the user's, often with their unsaved work in it. The rules that keep it so:

- **Require an empty seat** for any script that opens and closes documents (`com.require_empty`), and close only what the script opened. Never `CloseAllDocuments`.
- **Build in visible documents.** A hidden part holding any equation fails every save, and a seat crashed after about fifteen hidden scratch parts and took an unsaved drawing with it.
- **Restarting SOLIDWORKS is the user's call** (`com.restart`, `python -m swkit restart`), even with no document open; ask each session.
- **One script at a time on a seat.** Two clients interleave selections.
- **Run long scripts with `python -u` and no short timeout,** and watch memory: killing the client doesn't cancel a call SOLIDWORKS is already running, and a hung call can leave the seat at tens of GB. Each open of a model with thousands of bodies leaves about 1 GB behind.
- **Wake the screen before a STEP import:** with the monitors asleep an import hung or crashed the seat while native opens worked.
- **Compile a script before running it** (`python -m compileall`), and try an untested mode on a copy of the part.

## Where it stops

- Tested on SOLIDWORKS 2026 SP4.1 (Student Premium). Another release may bind a member differently; `com.get` absorbs the commonest change.
- STEP AP242 needs SOLIDWORKS MBD; the kit writes AP214 and AP203.
- Simulation needs its licence and the add-in loaded; after a failed solve, restart before trusting another.
- A drawing template's sheet format is easier made by hand once; `Drawing` takes any template and keeps its paper and projection.
