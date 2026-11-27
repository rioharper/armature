"""
A project's part and assembly templates, made from the seat's stock ones:
its units, its drafting standard and the custom properties its title block
reads, left empty but for the part's Material, linked to the material the
part is given. A drawing template's sheet format is easier made by hand
once; `Drawing` takes any.
"""
from __future__ import annotations

import os

from .com import C, SwError, default_template, new_doc, save_as, set_props, titles

PART_PROPS = ("PartNo", "Revision", "Description", "Material", "Finish", "GenTol")
ASM_PROPS = ("PartNo", "Revision", "Description", "Finish", "GenTol")


def set_units_and_standard(doc, units="MMGS", standard="ISO"):
    """A document's unit system (MMGS, IPS, ...) and drafting standard (ISO, ANSI, DIN, ...)."""
    ext = doc.Extension
    u, s = C[f"swUnitSystem_{units}"], C[f"swDetailingStandard{standard}"]
    ext.SetUserPreferenceInteger(C["swUnitSystem"], 0, u)
    ext.SetUserPreferenceInteger(C["swDetailingDimensionStandard"], 0, s)
    if (ext.GetUserPreferenceInteger(C["swUnitSystem"], 0) != u
            or ext.GetUserPreferenceInteger(C["swDetailingDimensionStandard"], 0) != s):
        raise SwError(f"units {units} or standard {standard} did not take")


def make_template(app, out, kind="part", props=None, stock=None, units="MMGS", standard="ISO", force=False):
    """A template at `out` (.PRTDOT or .ASMDOT) from `stock` (the seat's default template of
    that kind if None), with `units`, `standard` and empty `props`, a part's Material linked to
    its assigned material. Refuses to overwrite unless `force`."""
    if os.path.exists(out) and not force:
        raise SwError(f"{out} exists: pass force=True to overwrite it")
    if os.path.basename(out).lower() in [t.lower() for t in titles(app)]:
        raise SwError(f"a document titled {os.path.basename(out)} is open: close it first")
    props = props or (PART_PROPS if kind == "part" else ASM_PROPS)
    doc = new_doc(app, stock or default_template(app, kind))
    try:
        set_units_and_standard(doc, units, standard)
        save_as(doc, out)                 # the first save names the file the Material links to
        name = os.path.basename(out)
        set_props(doc, {p: (f'"SW-Material@{name}"' if p == "Material" and kind == "part" else " ")
                        for p in props})
        save_as(doc, out)
    finally:
        app.CloseDoc(doc.GetTitle)
    return out
