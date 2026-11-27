"""
Files in and out: STEP copies checked by the schema they wrote, drawing and
flat exports, STEP imports, and a light part of a heavy vendor model.

- **AP242 needs SOLIDWORKS MBD.** Without its licence `PublishSTEP242File`
  returns 4 (MBDLicenseNotAvailable), and `swStepAP` reads back any integer
  but writes AP203 for anything but 214. So `export_step` reads the file's
  FILE_SCHEMA back rather than trusting the preference.
- **2D sketches never reach a STEP,** whatever the export toggles say.
- **A DXF won't overwrite an earlier one** (error 1), and after a drawing's
  native save its DXF export fails the same way: export first, then save.
- **An imported part keeps its whole import,** even in a light
  configuration (a 77 MB vendor STEP made a 132 MB part). A part
  re-imported from a STEP of only the bodies kept holds only them.
- **A STEP import with the screen asleep or locked** hung (3D Interconnect
  on) or crashed SOLIDWORKS (off) on one seat while a native open worked:
  wake the screen before an import.
- **Export time** runs about 3 s a body: a 1,393-body model took 71 min.
"""
from __future__ import annotations

import os
import tempfile

from .com import (C, MM, NOTHING, SwError, byref_long, close, open_doc, preference, save_as,
                  set_props)
from .measure import DIRS, extreme, reach, solid_bodies, volume

# the protocols the exporter writes, each by the FILE_SCHEMA it puts in the file's head
STEP_SCHEMA = {203: "CONFIG_CONTROL_DESIGN", 214: "AUTOMOTIVE_DESIGN"}


def step_schema(path):
    head = open(path, "rb").read(4000).decode("ascii", "replace")
    return next((ln.strip() for ln in head.splitlines() if ln.startswith("FILE_SCHEMA")), "")


def export_copy(doc, path):
    """A copy of the open document in the format its extension names (.pdf, .dxf, .stl,
    .step, .x_t, ...), the document unchanged. An earlier file is removed first."""
    if os.path.exists(path):
        os.remove(path)
    save_as(doc, path, copy=True)
    if not os.path.exists(path):
        raise SwError(f"{path}: SOLIDWORKS reported success and wrote nothing")
    return path


def export_step(app, doc, out, ap=214, config=None):
    """A STEP copy of `doc` (an open document, or a native file's path, opened and closed
    unsaved) at protocol `ap`, in configuration `config` if given; its schema read back.
    Returns (bytes, schema)."""
    if ap not in STEP_SCHEMA:
        raise SwError(f"AP{ap}: this exporter writes {sorted(STEP_SCHEMA)}; AP242 needs SOLIDWORKS MBD")
    own = isinstance(doc, str)
    d = open_doc(app, doc) if own else doc
    try:
        before = d.ConfigurationManager.ActiveConfiguration.Name
        if config and config != before:
            d.ShowConfiguration2(config)
            d.ForceRebuild3(False)
        with preference(app, "swStepAP", ap):
            export_copy(d, out)
        if config and config != before and not own:
            d.ShowConfiguration2(before)
    finally:
        if own:
            close(app, d)
    schema = step_schema(out)
    if STEP_SCHEMA[ap] not in schema.upper():
        raise SwError(f"{out}: not AP{ap}: {schema!r}")
    return os.path.getsize(out), schema


def import_step(app, step, multibody=True):
    """A STEP imported whole, unsaved; with `multibody` an assembly STEP comes in as one
    multibody part rather than an assembly of parts."""
    want = C["swImportNeutralAssemblyStructureMapping_MultibodyPart"] if multibody else None
    err = byref_long()
    if want is None:
        doc = app.LoadFile4(os.path.abspath(step), "r", NOTHING, err)
    else:
        with preference(app, "swImportNeutralAssemblyStructureMapping", want):
            doc = app.LoadFile4(os.path.abspath(step), "r", NOTHING, err)
    if doc is None:
        raise SwError(f"import of {step} failed: error {err.value} (is the screen awake?)")
    if multibody and doc.GetType != C["swDocPART"]:
        raise SwError(f"{step} came in as document type {doc.GetType}, not a part")
    return doc


def import_solid(app, step, out, name=None, material=None, props=None, bodies=1):
    """A STEP from another tool (an executable recipe's, say) brought in as a dumb solid and
    saved native at `out`, so it can be drawn from the project's template: `bodies` expected,
    the one body named `name`, a library `material` (library path, material name) for its
    mass, the title block's `props`. Returns its volume (mm^3) to check against the recipe's."""
    doc = import_step(app, step)
    try:
        got = solid_bodies(doc)
        if len(got) != bodies:
            raise SwError(f"{step}: {len(got)} bodies imported, not {bodies}")
        if name and bodies == 1:
            got[0].Name = name
        if material:
            doc.SetMaterialPropertyName2("", *material)
        if props:
            set_props(doc, props)
        doc.ForceRebuild3(False)
        v = sum(volume(b) for b in got)
        save_as(doc, out)
        return v
    finally:
        close(app, doc)


def light_part(app, step, min_mm, tmpdir=None):
    """A heavy vendor model as its larger bodies alone, a part that holds no import of the
    rest, unsaved: the model imported whole; its bodies at least `min_mm` long, and the one
    reaching each face of its box, kept by a Delete/Keep Body feature; those exported to a
    temporary STEP and the whole model closed; that STEP imported as a part of its own.
    Each stage is checked to reach the whole model's box exactly. Returns (the part, bodies
    kept, of how many, the box mm)."""
    doc = import_step(app, step)
    tmp = os.path.join(tmpdir or tempfile.mkdtemp(prefix="swkit_light_"), "light_" + os.path.basename(step))
    try:
        bodies = solid_bodies(doc)
        boxes = [[v / MM for v in b.GetBodyBox()] for b in bodies]
        keep = {b.Name for b, x in zip(bodies, boxes) if max(x[3] - x[0], x[4] - x[1], x[5] - x[2]) >= min_mm}
        full = []
        for d in DIRS:
            # GetBodyBox isn't exact: the exact extremes of those within 2 mm of the most
            i = d.index(1) if 1 in d else d.index(-1)
            side = [x[i + 3] if sum(d) > 0 else -x[i] for x in boxes]
            top = max(side)
            cand = [b for b, s in zip(bodies, side) if s >= top - 2.0]
            best = max(cand, key=lambda b: extreme(b, d))
            keep.add(best.Name)
            full.append(extreme(best, d))
        full = (-full[1], -full[3], -full[5], full[0], full[2], full[4])
        doc.ClearSelection2(True)
        for b in bodies:
            if b.Name in keep:
                b.Select2(True, None)    # typed: None, not NOTHING
        picked = doc.SelectionManager.GetSelectedObjectCount2(-1)
        if picked != len(keep):
            raise SwError(f"{picked} bodies selected of {len(keep)} to keep")
        if doc.FeatureManager.InsertDeleteBody2(True) is None:
            raise SwError("the Delete/Keep Body feature wasn't made")
        doc.ClearSelection2(True)
        kept = solid_bodies(doc)
        got = reach(kept)
        if len(kept) != len(keep) or max(abs(a - b) for a, b in zip(got, full)) > 1e-3:
            raise SwError(f"kept {len(kept)} of {len(keep)}, reaching {got}, not {full}")
        with preference(app, "swStepAP", 214):
            export_copy(doc, tmp)
    finally:
        close(app, doc)
    try:
        light = import_step(app, tmp)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    lb = solid_bodies(light)
    got = reach(lb)
    if len(lb) != len(keep) or max(abs(a - b) for a, b in zip(got, full)) > 1e-3:
        close(app, light)
        raise SwError(f"the light part holds {len(lb)} of {len(keep)}, reaching {got}, not {full}")
    return light, len(keep), len(bodies), full
