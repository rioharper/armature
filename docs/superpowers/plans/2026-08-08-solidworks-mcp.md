# Armature SolidWorks MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A verification-first SolidWorks MCP server (9 name-addressed tools) bundled in the armature plugin, per `docs/superpowers/specs/2026-08-08-solidworks-mcp-design.md`.

**Architecture:** `sw.py` holds all COM logic (pywin32, attach-never-launch, stateless per call); `server.py` is a thin FastMCP veneer over it; `smoke.py` exercises `sw.py` against a real SolidWorks 2026 session with a known-answer test part. No unit tests by design — mocking COM tests the mock; the smoke script is the test cycle.

**Tech Stack:** Python 3.11+, `uv` (PEP 723 inline script deps — no pyproject), `mcp[cli]` (FastMCP), `pywin32`.

## Global Constraints

- **Name-addressed only** — no face/edge selection, no persistent COM references between calls.
- **Attach, never launch** — `GetActiveObject("SldWorks.Application")`; if not running, return the actionable error, never boot SolidWorks.
- **Stateless per call** — every tool re-attaches and re-resolves its document by name.
- **Units labeled in every payload** — mass properties and dimensions in SI (`UseSystemUnits`/`SystemValue`); equation values are document-units by SolidWorks design, so payloads carry a `linear_units` field instead of pretending.
- **Errors** map to exactly three actionable shapes: SolidWorks not running / document not found (+ list of open docs) / name not found (+ available names).
- `sw_set_params` never creates variables; `sw_rebuild` never throws on model errors (broken features are its return value).
- Windows-only; deps exactly `mcp[cli]` + `pywin32; sys_platform == 'win32'`.
- **COM enum caveat:** a few `swConst` integer values in this plan (moment type, tolerance type, fit type) are written from API docs memory. Every one is covered by a smoke assertion that fails loudly if the value is wrong (parallel-axis check, set→read round-trips). If a smoke step fails with a plausibly-wrong-enum symptom, check the constant against help.solidworks.com for the named enum before touching logic.
- Work on the existing `solidworks-mcp` branch. Do not touch the pre-existing uncommitted edits to `skills/armature-cad/SKILL.md` and `references/documentation-standards.md`.

---

### Task 1: COM wrapper core + server scaffold + plugin registration

**Files:**
- Create: `mcp/solidworks/sw.py`
- Create: `mcp/solidworks/server.py`
- Create: `mcp/solidworks/smoke.py`
- Create: `.mcp.json` (repo root = plugin root)

**Interfaces:**
- Consumes: nothing.
- Produces (later tasks build on these exact names):
  - `sw.attach() -> ISldWorks` (raises `SwNotRunning`)
  - `sw.resolve_doc(app, doc: str) -> IModelDoc2` (raises `DocNotFound`)
  - `sw.SwError(Exception)`, `SwNotRunning(SwError)`, `DocNotFound(SwError)`, `NameNotFound(SwError)`
  - `sw.status(app) -> dict`, `sw.open_doc(app, path: str) -> dict`
  - `sw.linear_units(doc) -> str` ("mm"/"cm"/"m"/"in"/…)
  - smoke harness: `check(name: str, fn)` collects PASS/FAIL, exit code 1 on any FAIL

- [ ] **Step 1: Write `sw.py`**

```python
"""Thin COM wrapper for the armature SolidWorks MCP. All COM lives here."""
import os
import pythoncom
import win32com.client


class SwError(Exception):
    """Base — message is always actionable, shown to the model verbatim."""

class SwNotRunning(SwError):
    pass

class DocNotFound(SwError):
    pass

class NameNotFound(SwError):
    pass


def attach():
    pythoncom.CoInitialize()  # MCP tool calls may land on fresh threads
    try:
        disp = win32com.client.GetActiveObject("SldWorks.Application")
    except pythoncom.com_error:
        raise SwNotRunning(
            "SolidWorks is not running. Start SolidWorks, open the document, then retry."
        )
    return win32com.client.gencache.EnsureDispatch(disp)


def _docs(app):
    return list(app.GetDocuments) if app.GetDocuments else []


def resolve_doc(app, doc: str):
    """Match by title or path basename, case-insensitive."""
    want = doc.lower()
    for d in _docs(app):
        title = (d.GetTitle or "").lower()
        base = os.path.basename(d.GetPathName or "").lower()
        if want in (title, base, os.path.splitext(base)[0], os.path.splitext(title)[0]):
            return d
    raise DocNotFound(
        f"No open document matches '{doc}'. Open documents: "
        + (", ".join(d.GetTitle for d in _docs(app)) or "(none)")
    )


# swUserPreferenceIntegerValue swUnitsLinear=0 on the doc; enum swLengthUnit_e
_UNITS = {0: "mm", 1: "cm", 2: "m", 3: "in", 4: "ft", 5: "ft-in", 6: "angstrom", 7: "nm", 8: "micron", 9: "mil", 10: "uin"}

def linear_units(doc) -> str:
    return _UNITS.get(doc.GetUserPreferenceIntegerValue(0), "unknown")


def status(app) -> dict:
    active = app.ActiveDoc
    return {
        "solidworks_version": app.RevisionNumber,
        "open_documents": [
            {"title": d.GetTitle, "path": d.GetPathName} for d in _docs(app)
        ],
        "active_document": active.GetTitle if active else None,
    }


_DOC_TYPES = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}  # swDocumentTypes_e

def open_doc(app, path: str) -> dict:
    ext = os.path.splitext(path)[1].lower()
    if ext not in _DOC_TYPES:
        raise SwError(f"Unsupported extension '{ext}' — expected .SLDPRT/.SLDASM/.SLDDRW")
    if not os.path.isfile(path):
        raise SwError(f"File not found: {path}")
    errors, warnings = 0, 0
    # swOpenDocOptions_Silent = 1
    d = app.OpenDoc6(path, _DOC_TYPES[ext], 1, "", errors, warnings)
    if d is None:
        d = resolve_doc(app, os.path.basename(path))  # already open → activate
    app.ActivateDoc3(d.GetTitle, False, 2, 0)  # swRebuildOnActivation_e 2 = don't rebuild
    return {"opened": d.GetTitle, "path": d.GetPathName, "linear_units": linear_units(d)}
```

- [ ] **Step 2: Write `server.py`**

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp[cli]", "pywin32; sys_platform == 'win32'"]
# ///
"""Armature SolidWorks MCP — verification-first, name-addressed. Spec:
docs/superpowers/specs/2026-08-08-solidworks-mcp-design.md"""
from mcp.server.fastmcp import FastMCP
import sw

mcp = FastMCP("solidworks")


@mcp.tool()
def sw_status() -> dict:
    """SolidWorks version, open documents, and active document. Call first."""
    return sw.status(sw.attach())


@mcp.tool()
def sw_open(path: str) -> dict:
    """Open a part/assembly/drawing by absolute path, or activate it if already open."""
    return sw.open_doc(sw.attach(), path)


if __name__ == "__main__":
    mcp.run()
```

(FastMCP surfaces raised exceptions as tool errors — `SwError` messages are already the actionable text, so no per-tool try/except.)

- [ ] **Step 3: Write the smoke harness with checks for status/open**

```python
"""Manual smoke test. Prereq: SolidWorks 2026 running.
From mcp/solidworks/: uv run --with pywin32 smoke.py
Tasks 2+ additionally require test-part.SLDPRT (same folder) to exist."""
import os
import sys
import sw

RESULTS = []

def check(name, fn):
    try:
        fn()
        RESULTS.append((name, None))
        print(f"PASS {name}")
    except Exception as e:
        RESULTS.append((name, e))
        print(f"FAIL {name}: {e}")

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_PART = os.path.join(HERE, "test-part.SLDPRT")

def main():
    app = sw.attach()

    def t_status():
        s = sw.status(app)
        assert s["solidworks_version"], "no version string"
        assert isinstance(s["open_documents"], list)
    check("status", t_status)

    def t_bad_doc():
        try:
            sw.resolve_doc(app, "no-such-doc-xyz")
        except sw.DocNotFound as e:
            assert "Open documents" in str(e)
            return
        raise AssertionError("DocNotFound not raised")
    check("doc-not-found lists open docs", t_bad_doc)

    if os.path.isfile(TEST_PART):
        check("open test part", lambda: sw.open_doc(app, TEST_PART))
        # later tasks append their sections here, guarded by the same if

    failed = [n for n, e in RESULTS if e]
    print(f"\n{len(RESULTS) - len(failed)} passed, {len(failed)} failed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the smoke test (SolidWorks must be running — ask the user to start it if it isn't)**

Run: `cd mcp/solidworks; uv run --with pywin32 smoke.py`
Expected: `status` and `doc-not-found` PASS; test-part section skipped (file doesn't exist yet); exit 0.

- [ ] **Step 5: Write `.mcp.json` at repo root**

```json
{
  "mcpServers": {
    "solidworks": {
      "command": "uv",
      "args": ["run", "${CLAUDE_PLUGIN_ROOT}/mcp/solidworks/server.py"]
    }
  }
}
```

- [ ] **Step 6: Verify the server starts and lists tools**

Run: `cd mcp/solidworks; uv run server.py` — should start silently on stdio (Ctrl-C after 2s without a traceback). Then `uv run --with "mcp[cli]" mcp dev server.py` is available for interactive checking if needed; a clean silent start is sufficient here.

- [ ] **Step 7: Commit**

```bash
git add mcp/solidworks/sw.py mcp/solidworks/server.py mcp/solidworks/smoke.py .mcp.json
git commit -m "Add SolidWorks MCP scaffold: attach/resolve core, status+open tools, smoke harness, plugin registration"
```

---

### Task 2: Known-answer test part (user-assisted — requires a human at SolidWorks)

**Files:**
- Create: `mcp/solidworks/test-part.SLDPRT` (binary, built by the user in the GUI)
- Modify: `mcp/solidworks/smoke.py` (known-answer constants)

**Interfaces:**
- Produces: a part every later smoke section targets, with exactly these names:
  - Global variable `block_len` = 40 (mm), driving the block's length
  - A boss-extrude block **40 × 20 × 10 mm** of **1060 Alloy** (ρ = 2700 kg/m³; with the hole below, mass ≈ 19.48 g)
  - Coordinate system **`CS_corner`** at a corner of the block, axes parallel to the origin planes
  - A through-hole Ø10 mm whose diameter dimension is renamed **`bore`** (full name `bore@Sketch2`)

- [ ] **Step 1: Ask the user to build the part with this exact recipe** (2–5 min; do not attempt COM authoring — that is the swamp the spec forbids):

> 1. New Part, units MMGS. Tools → Equations → add global variable `block_len` = 40.
> 2. Sketch on Front plane: corner rectangle from origin; horizontal dimension → set `= "block_len"` (shows Σ); vertical 20 mm. Extrude 10 mm (Boss-Extrude1).
> 3. Sketch on the large front face (Sketch2): circle roughly centered, Ø10 mm. Rename the diameter dimension to `bore` (select dim → rename in the dimension PropertyManager or Feature tree). Extruded Cut, Through All.
> 4. Insert → Reference Geometry → Coordinate System: pick the block corner vertex at the origin-diagonal corner (the corner farthest from the origin), axes along the block edges. Rename it `CS_corner`.
> 5. Right-click Material → 1060 Alloy. Rebuild (Ctrl-B), confirm no errors.
> 6. Save as `mcp/solidworks/test-part.SLDPRT` (File → Save As into the repo folder).

- [ ] **Step 2: Add known-answer constants to `smoke.py`** (top of file, after `TEST_PART`):

```python
# Known answers for test-part.SLDPRT: 40x20x10 mm block, 1060 Alloy (2700 kg/m3),
# minus a 10 mm through-hole (10 mm deep): 8000 - pi*25*10 = 7214.6 mm^3 -> 19.48 g.
import math
BLOCK_MASS_KG = (40 * 20 * 10 - math.pi * 5**2 * 10) * 1e-9 * 2700  # ≈ 0.01948
```

- [ ] **Step 3: Run smoke, verify the part opens**

Run: `cd mcp/solidworks; uv run --with pywin32 smoke.py`
Expected: `open test part` PASS.

- [ ] **Step 4: Commit** (the binary is a test fixture; committing it is the point)

```bash
git add mcp/solidworks/test-part.SLDPRT mcp/solidworks/smoke.py
git commit -m "Add known-answer test part for SolidWorks MCP smoke suite"
```

---

### Task 3: Parameters — `sw_get_params` / `sw_set_params`

**Files:**
- Modify: `mcp/solidworks/sw.py`
- Modify: `mcp/solidworks/server.py`
- Modify: `mcp/solidworks/smoke.py`

**Interfaces:**
- Consumes: `attach`, `resolve_doc`, `linear_units`, `NameNotFound` from Task 1.
- Produces:
  - `sw.get_params(doc) -> dict` — `{"linear_units": str, "params": {name: {"equation": str, "value": float, "global": bool}}}`
  - `sw.set_params(doc, values: dict[str, float]) -> dict` — same shape, only the touched names; raises `NameNotFound` listing available globals

- [ ] **Step 1: Add smoke section first** (inside the `if os.path.isfile(TEST_PART):` block; get the doc once: `doc = sw.resolve_doc(app, "test-part")` after the open check):

```python
        def t_params_roundtrip():
            p = sw.get_params(doc)["params"]
            assert "block_len" in p, f"block_len missing; got {list(p)}"
            assert abs(p["block_len"]["value"] - 40) < 1e-6
            sw.set_params(doc, {"block_len": 50})
            assert abs(sw.get_params(doc)["params"]["block_len"]["value"] - 50) < 1e-6
            sw.set_params(doc, {"block_len": 40})  # restore
        check("params round-trip", t_params_roundtrip)

        def t_params_no_create():
            try:
                sw.set_params(doc, {"not_a_var": 1})
            except sw.NameNotFound as e:
                assert "block_len" in str(e)
                return
            raise AssertionError("NameNotFound not raised")
        check("set_params refuses unknown names", t_params_no_create)
```

- [ ] **Step 2: Run smoke — verify the new sections FAIL** (`AttributeError: module 'sw' has no attribute 'get_params'`)

- [ ] **Step 3: Implement in `sw.py`**

```python
def _eq_name(text: str) -> str | None:
    # global variable equations look like: "block_len" = 40
    if text.startswith('"'):
        return text[1 : text.index('"', 1)]
    return None


def get_params(doc) -> dict:
    eq = doc.GetEquationMgr()
    out = {}
    for i in range(eq.GetCount):
        text = eq.GetEquation(i)
        name = _eq_name(text)
        if name:
            out[name] = {
                "equation": text,
                "value": eq.GetValue(i),  # document units — hence linear_units field
                "global": bool(eq.GetGlobalVariable(i)),
            }
    return {"linear_units": linear_units(doc), "params": out}


def set_params(doc, values: dict) -> dict:
    eq = doc.GetEquationMgr()
    index = {}
    for i in range(eq.GetCount):
        name = _eq_name(eq.GetEquation(i))
        if name:
            index[name] = i
    missing = [n for n in values if n not in index]
    if missing:
        raise NameNotFound(
            f"No global variable(s) {missing}. Available: {sorted(index)}. "
            "set_params never creates variables — fix the name or add it in SolidWorks."
        )
    for name, val in values.items():
        eq.SetEquation(index[name], f'"{name}" = {val}')
    doc.EditRebuild3()
    fresh = get_params(doc)
    return {"linear_units": fresh["linear_units"],
            "params": {n: fresh["params"][n] for n in values}}
```

(`EnsureDispatch` in `attach()` generates the makepy `GetEquation/SetEquation/GetValue/GetGlobalVariable` accessors for the parameterized properties; if any is missing at runtime, the property-call forms `eq.Equation(i)` / `eq.Value(i)` are the dynamic-dispatch equivalents — swap accessor style only, keep logic.)

- [ ] **Step 4: Run smoke — both new sections PASS. Step 5: add the two thin tools to `server.py`:**

```python
@mcp.tool()
def sw_get_params(doc: str) -> dict:
    """All global variables/equations of the named open document (values in document units)."""
    app = sw.attach()
    return sw.get_params(sw.resolve_doc(app, doc))


@mcp.tool()
def sw_set_params(doc: str, values: dict[str, float]) -> dict:
    """Set existing global variables (document units), rebuild, return new values. Never creates variables."""
    app = sw.attach()
    return sw.set_params(sw.resolve_doc(app, doc), values)
```

- [ ] **Step 6: Commit**

```bash
git add mcp/solidworks/sw.py mcp/solidworks/server.py mcp/solidworks/smoke.py
git commit -m "Add global-variable read/write tools with round-trip smoke checks"
```

---

### Task 4: Rebuild + feature-error readback — `sw_rebuild`

**Files:**
- Modify: `mcp/solidworks/sw.py`, `mcp/solidworks/server.py`, `mcp/solidworks/smoke.py`

**Interfaces:**
- Consumes: Task 1 core; Task 3 `set_params` (smoke uses it to perturb).
- Produces: `sw.rebuild(doc) -> dict` — `{"rebuilt": True, "problems": [{"feature": str, "kind": "error"|"warning"}]}`. Model errors are data; only COM failure raises.

- [ ] **Step 1: Smoke section first** (perturb → rebuild clean → restore; this IS the Done-when perturbation check the skill will run):

```python
        def t_rebuild_perturb():
            sw.set_params(doc, {"block_len": 60})
            r = sw.rebuild(doc)
            assert r["problems"] == [], f"unexpected problems: {r['problems']}"
            sw.set_params(doc, {"block_len": 40})
            assert sw.rebuild(doc)["problems"] == []
        check("perturb+rebuild clean", t_rebuild_perturb)
```

- [ ] **Step 2: Run smoke → FAIL (no `sw.rebuild`). Step 3: implement:**

```python
def rebuild(doc) -> dict:
    doc.ForceRebuild3(False)  # False = rebuild all, not just top level
    problems = []
    # IModelDocExtension::GetWhatsWrong — [out] arrays come back as a tuple under makepy
    features, error_codes, warnings = doc.Extension.GetWhatsWrong()
    for feat, warn in zip(features or [], warnings or []):
        problems.append({"feature": feat.Name, "kind": "warning" if warn else "error"})
    return {"rebuilt": True, "problems": problems}
```

- [ ] **Step 4: Run smoke → PASS. Step 5: tool veneer:**

```python
@mcp.tool()
def sw_rebuild(doc: str) -> dict:
    """Force-rebuild the named document; returns features in error/warning state (empty list = clean)."""
    app = sw.attach()
    return sw.rebuild(sw.resolve_doc(app, doc))
```

- [ ] **Step 6: Commit** — `git add -u; git commit -m "Add force-rebuild tool with feature error readback"`

---

### Task 5: Mass properties about a named coordinate system — `sw_mass_properties`

**Files:**
- Modify: `mcp/solidworks/sw.py`, `mcp/solidworks/server.py`, `mcp/solidworks/smoke.py`

**Interfaces:**
- Consumes: Task 1 core.
- Produces:
  - `sw.feature_by_name(doc, name, type_filter=None) -> IFeature` — raises `NameNotFound` listing available features (of the filtered type)
  - `sw.mass_properties(doc, coord_system: str | None) -> dict` — `{"units": "SI (kg, m, kg*m^2)", "about": name-or-"center_of_mass", "mass": float, "center_of_mass": [x,y,z], "inertia_tensor": [[...3x3...]]}`

- [ ] **Step 1: Smoke first** — mass known-answer, tensor symmetry, and the parallel-axis check that catches a wrong moment-type enum:

```python
        def t_mass_props():
            m = sw.mass_properties(doc, None)
            assert abs(m["mass"] - BLOCK_MASS_KG) / BLOCK_MASS_KG < 0.01, m["mass"]
            t = m["inertia_tensor"]
            for i in range(3):
                for j in range(3):
                    assert abs(t[i][j] - t[j][i]) < 1e-12, "tensor not symmetric"
            mc = sw.mass_properties(doc, "CS_corner")
            assert mc["about"] == "CS_corner"
            # parallel axis: every diagonal moment about the corner CS must be >= about COM
            for i in range(3):
                assert mc["inertia_tensor"][i][i] > t[i][i], (
                    "corner moments not larger than COM moments — moment-type enum is wrong")
        check("mass properties + parallel-axis", t_mass_props)

        def t_mass_bad_cs():
            try:
                sw.mass_properties(doc, "CS_nope")
            except sw.NameNotFound as e:
                assert "CS_corner" in str(e)
                return
            raise AssertionError("NameNotFound not raised")
        check("mass props lists coordinate systems on bad name", t_mass_bad_cs)
```

- [ ] **Step 2: Run smoke → FAIL. Step 3: implement:**

```python
def feature_by_name(doc, name: str, type_filter: str | None = None):
    names = []
    feat = doc.FirstFeature()
    while feat:
        for f in _with_subfeatures(feat):
            if type_filter is None or f.GetTypeName2() == type_filter:
                if f.Name == name:
                    return f
                names.append(f.Name)
        feat = feat.GetNextFeature()
    kind = f" of type {type_filter}" if type_filter else ""
    raise NameNotFound(f"No feature '{name}'{kind}. Available: {names}")


def _with_subfeatures(feat):
    yield feat
    sub = feat.GetFirstSubFeature()
    while sub:
        yield sub
        sub = sub.GetNextSubFeature()


# swMassPropertyMoment_e — verified by the smoke parallel-axis assertion
_MOMENT_ABOUT_COM = 0
_MOMENT_ABOUT_COORD_SYS = 1

def mass_properties(doc, coord_system: str | None) -> dict:
    mp = doc.Extension.CreateMassProperty()
    mp.UseSystemUnits = True  # kg, m, kg*m^2 regardless of document units
    about = "center_of_mass"
    moment_kind = _MOMENT_ABOUT_COM
    if coord_system:
        feat = feature_by_name(doc, coord_system, type_filter="CoordSys")
        xform = feat.GetDefinition().Transform  # ICoordinateSystemFeatureData
        if not mp.SetCoordinateSystem(xform):
            raise SwError(f"SetCoordinateSystem failed for '{coord_system}'")
        about = coord_system
        moment_kind = _MOMENT_ABOUT_COORD_SYS
    ixx, ixy, ixz, iyx, iyy, iyz, izx, izy, izz = mp.GetMomentOfInertia(moment_kind)
    return {
        "units": "SI (kg, m, kg*m^2)",
        "about": about,
        "mass": mp.Mass,
        "center_of_mass": list(mp.CenterOfMass),
        "inertia_tensor": [[ixx, ixy, ixz], [iyx, iyy, iyz], [izx, izy, izz]],
    }
```

- [ ] **Step 4: Run smoke → PASS** (if the parallel-axis check fails, swap `_MOMENT_ABOUT_COORD_SYS` per `swMassPropertyMoment_e` on help.solidworks.com — that assertion exists precisely to catch this).

- [ ] **Step 5: Tool veneer:**

```python
@mcp.tool()
def sw_mass_properties(doc: str, coord_system: str | None = None) -> dict:
    """Mass, COM, and inertia tensor in SI, about the named coordinate system
    (or about the center of mass if omitted). The armature loop-closer:
    compare against params.py assumed values."""
    app = sw.attach()
    return sw.mass_properties(sw.resolve_doc(app, doc), coord_system)
```

- [ ] **Step 6: Commit** — `git add -u; git commit -m "Add mass-properties tool about named coordinate systems, parallel-axis-verified"`

---

### Task 6: Dimensions + tolerances — `sw_get_dimensions` / `sw_set_tolerance`

**Files:**
- Modify: `mcp/solidworks/sw.py`, `mcp/solidworks/server.py`, `mcp/solidworks/smoke.py`

**Interfaces:**
- Consumes: Task 1 core.
- Produces:
  - `sw.get_dimensions(doc, names: list[str]) -> dict` — `{"units": "SI (m, rad)", "dimensions": {full_name: {"value": float, "tolerance": {"type": str, "max": float, "min": float} | None}}}`; raises `NameNotFound` per missing name
  - `sw.set_tolerance(doc, dim_name, tol_type: "bilateral"|"symmetric"|"fit", values: dict) -> dict` — `values` is `{"max": m, "min": m}` (SI meters) for bilateral/symmetric or `{"hole": "H7", "shaft": ""}` for fit; returns the dimension's new `get_dimensions` entry

- [ ] **Step 1: Smoke first** — read `bore`, set H7 fit, read it back; set bilateral, read back:

```python
        def t_dimensions():
            d = sw.get_dimensions(doc, ["bore@Sketch2"])["dimensions"]["bore@Sketch2"]
            assert abs(d["value"] - 0.010) < 1e-9, d  # SystemValue is meters
        check("read named dimension in SI", t_dimensions)

        def t_tolerance_roundtrip():
            sw.set_tolerance(doc, "bore@Sketch2", "fit", {"hole": "H7", "shaft": ""})
            d = sw.get_dimensions(doc, ["bore@Sketch2"])["dimensions"]["bore@Sketch2"]
            assert d["tolerance"] and d["tolerance"]["type"] == "fit", d
            sw.set_tolerance(doc, "bore@Sketch2", "bilateral",
                             {"max": 0.0001, "min": -0.0001})
            d = sw.get_dimensions(doc, ["bore@Sketch2"])["dimensions"]["bore@Sketch2"]
            assert d["tolerance"]["type"] == "bilateral"
            assert abs(d["tolerance"]["max"] - 0.0001) < 1e-9
        check("tolerance set/read round-trip", t_tolerance_roundtrip)
```

- [ ] **Step 2: Run smoke → FAIL. Step 3: implement:**

```python
# swTolType_e values — verified by the smoke set→read round-trip
_TOL_TYPES = {"none": 0, "bilateral": 2, "symmetric": 5, "fit": 9}
_TOL_NAMES = {v: k for k, v in _TOL_TYPES.items()}


def _dimension(doc, full_name: str):
    dim = doc.Parameter(full_name)
    if dim is None:
        raise NameNotFound(
            f"No dimension '{full_name}'. Use the full form 'name@Sketch1' / 'name@Feature'; "
            "check the name in the SolidWorks dimension PropertyManager."
        )
    return dim


def _tol_entry(dim) -> dict | None:
    tol = dim.Tolerance
    t = _TOL_NAMES.get(tol.Type, f"swTolType_{tol.Type}")
    if t == "none":
        return None
    return {"type": t, "max": tol.GetMaxValue2(), "min": tol.GetMinValue2()}


def get_dimensions(doc, names: list) -> dict:
    out = {}
    for full_name in names:
        dim = _dimension(doc, full_name)
        out[full_name] = {"value": dim.SystemValue, "tolerance": _tol_entry(dim)}
    return {"units": "SI (m, rad)", "dimensions": out}


def set_tolerance(doc, dim_name: str, tol_type: str, values: dict) -> dict:
    if tol_type not in ("bilateral", "symmetric", "fit"):
        raise SwError(f"tol_type must be bilateral|symmetric|fit, got '{tol_type}'")
    dim = _dimension(doc, dim_name)
    tol = dim.Tolerance
    tol.Type = _TOL_TYPES[tol_type]
    if tol_type == "fit":
        # ITolerance fit: hole class like "H7", shaft class like "p6" ("" = unused side)
        tol.SetFitValues(values.get("hole", ""), values.get("shaft", ""))
    else:
        tol.SetValues(values["min"], values["max"])  # SI meters
    doc.EditRebuild3()
    return get_dimensions(doc, [dim_name])["dimensions"][dim_name]
```

- [ ] **Step 4: Run smoke → PASS** (wrong `swTolType_e` constants or `SetFitValues` arity show up here; correct against the `IDimensionTolerance` page on help.solidworks.com, logic unchanged).

- [ ] **Step 5: Tool veneers:**

```python
@mcp.tool()
def sw_get_dimensions(doc: str, names: list[str]) -> dict:
    """Named model dimensions ('d1@Sketch1') with SI values and tolerance settings —
    verify against the part definition's interface contract."""
    app = sw.attach()
    return sw.get_dimensions(sw.resolve_doc(app, doc), names)


@mcp.tool()
def sw_set_tolerance(doc: str, dim_name: str, tol_type: str, values: dict) -> dict:
    """Set a dimension tolerance. tol_type: bilateral|symmetric|fit.
    values: {"max": m, "min": m} in SI meters, or {"hole": "H7", "shaft": "p6"} for fit.
    The drawing inherits it from the model."""
    app = sw.attach()
    return sw.set_tolerance(sw.resolve_doc(app, doc), dim_name, tol_type, values)
```

- [ ] **Step 6: Commit** — `git add -u; git commit -m "Add dimension readback and tolerance/fit tools with round-trip smoke checks"`

---

### Task 7: Custom properties — `sw_custom_props`

**Files:**
- Modify: `mcp/solidworks/sw.py`, `mcp/solidworks/server.py`, `mcp/solidworks/smoke.py`

**Interfaces:**
- Consumes: Task 1 core.
- Produces: `sw.custom_props_get(doc) -> dict[str, str]` (resolved values); `sw.custom_props_set(doc, values: dict[str, str]) -> dict[str, str]` (creates-or-overwrites — properties are metadata, so unlike `set_params`, creating here is the desired behavior).

- [ ] **Step 1: Smoke first:**

```python
        def t_custom_props():
            sw.custom_props_set(doc, {"PartNo": "ARM-TST-001", "Material": "1060 Alloy"})
            got = sw.custom_props_get(doc)
            assert got.get("PartNo") == "ARM-TST-001", got
        check("custom props set/get", t_custom_props)
```

- [ ] **Step 2: Run smoke → FAIL. Step 3: implement:**

```python
def _cpm(doc):
    return doc.Extension.CustomPropertyManager("")  # "" = document-level (not config)


def custom_props_get(doc) -> dict:
    cpm = _cpm(doc)
    out = {}
    for name in cpm.GetNames() or []:
        # Get6 [out] params under makepy: (status, ValOut, ResolvedValOut, WasResolved, LinkToProperty)
        _, raw, resolved, _, _ = cpm.Get6(name, False)
        out[name] = resolved or raw
    return out


def custom_props_set(doc, values: dict) -> dict:
    cpm = _cpm(doc)
    for name, val in values.items():
        # 30 = swCustomInfoText, 1 = swCustomPropertyReplaceValue
        cpm.Add3(name, 30, str(val), 1)
    got = custom_props_get(doc)
    return {k: got.get(k, "") for k in values}
```

- [ ] **Step 4: Run smoke → PASS. Step 5: tool veneer (one tool, mode by argument, per spec):**

```python
@mcp.tool()
def sw_custom_props(doc: str, values: dict[str, str] | None = None) -> dict:
    """Custom properties (title block: part number, rev, material, finish).
    Omit values to read all; pass values to create/overwrite those keys."""
    app = sw.attach()
    d = sw.resolve_doc(app, doc)
    if values:
        return sw.custom_props_set(d, values)
    return sw.custom_props_get(d)
```

- [ ] **Step 6: Full smoke run** — `uv run --with pywin32 smoke.py` → every section PASS, exit 0.

- [ ] **Step 7: Commit** — `git add -u; git commit -m "Add custom-properties tool; full smoke suite green"`

---

### Task 8: armature-cad integration docs + release checks

**Files:**
- Modify: `skills/armature-cad/references/solidworks.md` (append one section — do NOT touch the user's uncommitted edits elsewhere in the skill)
- Modify: `README.md` (one short paragraph)

- [ ] **Step 1: Append to `skills/armature-cad/references/solidworks.md`:**

```markdown
## 9. With the armature SolidWorks MCP connected

If the `solidworks` MCP server is connected (ships with this plugin; needs
SolidWorks running on Windows), run the Done-when checks against the live
model instead of asking the user to transcribe numbers. The server measures;
you judge — pass/fail lives in this conversation, against `params.py` and
the part definition.

- **Mass loop (§5):** `sw_mass_properties(doc, coord_system=<the frame from
  00_setup.md>)` → compare mass/COM/inertia to the `params.py` block, in SI,
  about the same point and axes. Route divergence per SKILL.md's close-the-loop.
- **Perturbation check:** for each driven parameter: `sw_set_params` to a
  ±10% value → `sw_rebuild` (must return no problems) → `sw_set_params` back
  → final `sw_rebuild`. Any feature in the problems list fails the check.
- **Interface verification:** `sw_get_dimensions` on each controlling
  dimension named in the interface contract table; compare value and
  tolerance against the table's source column.
- **Release metadata:** `sw_set_tolerance` for the fits documentation-
  standards §6 chose; `sw_custom_props` to stamp part number, rev, material
  before the drawing.

Parameter names, coordinate-system names, and dimension names are the whole
API contract — they must match the glossary and the part definition exactly,
which §1–§3 already require. If a name lookup fails, the error lists what
exists; fix the model's names rather than adapting to typos.
```

- [ ] **Step 2: Add to `README.md`** after the cross-cutting skills table:

```markdown
## SolidWorks MCP (bundled)

Armature ships a verification-first SolidWorks MCP server (Windows +
SolidWorks required; attaches to your running session). It does not model
for you — it measures: mass properties about your project's frames,
parameter sync and rebuild checks, interface dimensions, tolerances, and
title-block properties, so the armature-cad Done-when checks run against
the live model. See `mcp/solidworks/`.
```

- [ ] **Step 3: Full smoke run one last time** (`cd mcp/solidworks; uv run --with pywin32 smoke.py` → exit 0), and verify the MCP registers: restart the Claude Code session or run `claude mcp list` — `solidworks` should appear.

- [ ] **Step 4: Commit**

```bash
git add skills/armature-cad/references/solidworks.md README.md
git commit -m "Document the bundled SolidWorks MCP in armature-cad reference and README"
```

- [ ] **Step 5: Offer the user a rebase onto main** (branch was cut from `ab22347`; main is at `058ffcb`) and merge via the repo's normal flow.
