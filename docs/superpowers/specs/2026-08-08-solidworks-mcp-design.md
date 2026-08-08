# Armature SolidWorks MCP — Design Spec

2026-08-08 · approved via brainstorming session

## Problem

Armature's CAD stage ends with checks the user runs by hand: read mass properties out of SolidWorks and compare to `params.py`, re-key parameter changes, eyeball bolt-circle dimensions against the interface contract. Existing SolidWorks MCPs (alisamsam/solidworks-mcp, eyfel/SolidPilot, andrewbartels1/SolidworksMCP-python) all target *authoring* — LLM-driven geometry creation — which lives in the brittle half of the COM API (persistent face/edge references that break on rebuild; SolidPilot itself names its reference resolver "the make-or-break module still ahead").

## Niche

A **verification-first** MCP: the human models, Claude verifies the model against armature's frozen numbers. All operations are **name-addressed** (document names, coordinate-system names, dimension/global-variable names, feature names) — the half of the COM API where reference resolution is a non-problem and the API has been stable for a decade. Nobody has built "pytest for CAD"; armature part definitions already contain the acceptance criteria (`Done when` sections) to make it meaningful.

## Goals

1. Automate the close-the-loop check: mass/COM/inertia about the mathematician's coordinate system vs `params.py`.
2. Sync driven parameters from the project into SolidWorks global variables; rebuild and read back feature errors (enables the "perturb each driven parameter" check).
3. Verify interface dimensions (named model dimensions, incl. tolerance/fit) against the part definition's interface contract.
4. Set dimension tolerances/fit classes and title-block custom properties by name.
5. Ship inside the armature plugin — installing armature installs the MCP.

## Non-goals

- **No geometry authoring.** No sketches, features, mates, or selections by geometry. That is the crowded, brittle territory this project exists to avoid.
- **No drawing generation** (view creation, dimension placement). v2 may add a read-side *drawing audit* (see Roadmap).
- **No parsing of armature documents in the server.** The MCP measures; Claude reads `params.py` and the part definition and judges pass/fail. The server never knows what armature is.
- No assembly checks in v1 (interference, clearance, mate errors) — deferred, see Roadmap.

## Architecture

```
armature repo
  mcp/solidworks/
    server.py          FastMCP stdio server (~300 lines)
    sw.py              thin pywin32 COM wrapper: attach, doc lookup, unit handling
    smoke.py           manual smoke test (see Testing)
    test-part.SLDPRT   known-answer target for smoke test
    pyproject.toml     deps: mcp[cli], pywin32
  .mcp.json            registers the server; ships with the plugin
```

- **Attach, never launch.** `GetActiveObject("SldWorks.Application")`. If SolidWorks isn't running, tools return an actionable error ("start SolidWorks and open the part") — no COM boot attempts.
- **Name-addressed only.** No face/edge selection anywhere in the tool surface.
- **SI always.** COM returns SI (m, kg, kg·m²) regardless of document units; the server passes SI through and labels it. Armature is SI-internal, so no conversion layer.
- **Stateless per call.** Documents are resolved by name at call time; no COM pointers cached between calls. SolidWorks can restart mid-session without dangling state.
- Windows-only, tested against SolidWorks 2026; the APIs used are stable back to at least 2018.

## Tool surface (9 tools)

| Tool | Behavior |
|---|---|
| `sw_status()` | SolidWorks version, open documents, active document |
| `sw_open(path)` | Open a part/assembly, or activate it if already open |
| `sw_mass_properties(doc, coord_system?)` | Mass, COM, inertia tensor about the named coordinate system (COM axes if omitted). The loop-closer. |
| `sw_get_params(doc)` | All global variables + equations, name → value |
| `sw_set_params(doc, {name: value})` | Write existing global variables; returns new values. Never creates variables implicitly. |
| `sw_rebuild(doc)` | Force-rebuild; returns features in error/warning state (name + status). Errors are data, not exceptions. |
| `sw_get_dimensions(doc, names)` | Named model dimensions (`d@Sketch`/`d@Feature`) with value and tolerance settings (fit class if set) |
| `sw_set_tolerance(doc, dim_name, type, values_or_fit)` | Set a dimension's tolerance: plus/minus values or ISO fit class (H7, p6, …). Drawing inherits it from the model. |
| `sw_custom_props(doc, get \| set, {name: value}?)` | Read/write custom properties (part number, rev, material, finish — i.e. the title block) |

Composite checks are Claude-side composition, not tools: the perturbation check is `sw_set_params` → `sw_rebuild` → restore, looped over driven parameters; the mass loop is `sw_mass_properties` vs `params.py` judged in-conversation.

## Integration with armature-cad

- `skills/armature-cad/references/solidworks.md` gains one final section — "With the armature SolidWorks MCP connected" — mapping each Done-when check to its tool sequence. Without the MCP the skill reads exactly as today; the section is additive.
- Consequences of a failed check flow through existing armature machinery (update `params.py` + budgets, or route to armature-math). No new documents or file formats.
- The naming discipline the MCP depends on (coordinate systems named after project frames, driven dimensions named after glossary symbols) is already mandated by the skill. Those names are the API contract.

## Error handling

Every COM failure maps to one of three actionable messages:

1. **SolidWorks not running** — tells the user to start it.
2. **Document not open/found** — includes the list of documents that *are* open.
3. **Name not found** (coordinate system, variable, dimension, property) — includes the available names, so Claude self-corrects `link_len` vs `link_length` without a user round-trip.

`sw_set_params` validates existence before writing. `sw_rebuild` never throws on model errors — broken features are its return value.

## Testing

- No unit tests: the server is a thin COM pass-through; mocking COM tests the mock.
- `smoke.py`: run manually with SolidWorks 2026 open against `test-part.SLDPRT` (a block with one global variable, one named coordinate system, one toleranced dimension). Exercises every tool; asserts sane shapes: mass > 0, inertia tensor symmetric, params round-trip (set → read → restore), tolerance readback matches what was set. Run before tagging a release.

## Roadmap (v2, explicitly out of v1)

- **Drawing audit** (read-side): read every dimension present on a drawing; Claude checks each critical dimension from the part definition appears with the right tolerance. Verification, name-addressed, novel.
- **Assembly checks**: interference detection, clearance vs the envelope section, mate error readback.
- Hole Wizard readback for richer interface verification.
