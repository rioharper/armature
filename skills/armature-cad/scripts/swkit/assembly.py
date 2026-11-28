"""
Assemblies by script: components inserted in a chosen configuration, mated
by named reference geometry with each mate's alignment computed rather
than tried, and vendor models given named interface references once.

- `AddComponent5` places a component by its box and fixes the first one
  inserted: to mate a skeleton, unfix it and mate its three planes.
- `AddMate5`'s error 1 is no error; 0 is unknown.
- `IComponent2.Select4` takes three arguments.
- A component's suppression in a list of configurations, through
  `SetSuppression2`, silently does nothing: activate the configuration and
  use `swThisConfiguration`.
- An assembly opened from one folder loads a component from an open
  document of the same name first, wherever that one lives.
"""
from __future__ import annotations

import os

from .com import (C, MM, NOTHING, SwError, byref_long, close, get, new_doc, open_doc, require_closed,
                  save, save_as, set_props)
from .exchange import import_step, light_part
from .measure import find_face


class Asm:
    """A new assembly from `template`, saved at `path`. Redraw is off while mates come and
    go: a big vendor model redraws slowly at every one."""

    def __init__(self, app, template, path):
        self.app = app
        self.doc = new_doc(app, template)
        save_as(self.doc, path)
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.ext = self.doc.Extension
        self.view = self.doc.ActiveView
        self.view.EnableGraphicsUpdate = False

    def insert(self, path, at=(0, 0, 0), config=""):
        """A component of the part at `path` (mm placement), in configuration `config` (its
        last-saved one when empty), opened in that configuration only."""
        require_closed(self.app, path)
        err, warn = byref_long(), byref_long()
        part = self.app.OpenDoc6(os.path.abspath(path), C["swDocPART"], C["swOpenDocOptions_Silent"],
                                 config, err, warn)
        self.app.ActivateDoc3(self.doc.GetTitle, False, 0, byref_long())
        comp = self.doc.AddComponent5(os.path.abspath(path), C["swAddComponentConfigOptions_CurrentSelectedConfig"],
                                      "", False, config, at[0] * MM, at[1] * MM, at[2] * MM)
        if part is not None:
            self.app.CloseDoc(part.GetTitle)
        if comp is None:
            raise SwError(f"{path} not inserted")
        if config and get(comp, "ReferencedConfiguration") != config:
            comp.ReferencedConfiguration = config
            if get(comp, "ReferencedConfiguration") != config:
                raise SwError(f"{comp.Name2} won't take configuration {config}")
        return comp

    def ref(self, comp, feature):
        """A component's feature by its selection name in this assembly."""
        return f"{feature}@{comp.Name2}@{self.name}"

    def mate(self, kind, a, b, align):
        """Mate `kind` ("swMateCOINCIDENT", "swMateCONCENTRIC", ...) between a and b, each a
        (selection name, type) pair, aligned `align` ("swMateAlignALIGNED", ...)."""
        self.doc.ClearSelection2(True)
        for i, (name, typ) in enumerate((a, b)):
            if not self.ext.SelectByID2(name, typ, 0, 0, 0, i > 0, 1, NOTHING, 0):
                raise SwError(f"could not select {typ} {name}")
        err = byref_long()
        m = self.doc.AddMate5(C[kind], C[align], False, 0, 0, 0, 1, 1, 0, 0, 0, False, False, 0, err)
        self.doc.ClearSelection2(True)
        if m is None or err.value != C["swAddMateError_NoError"]:
            raise SwError(f"mate {kind} {a[0]} / {b[0]} failed: error {err.value}")
        return m

    def remove(self, feat):
        self.doc.ClearSelection2(True)
        feat.Select2(False, 0)
        self.doc.EditDelete()
        self.doc.ClearSelection2(True)

    def finish(self):
        self.view.EnableGraphicsUpdate = True
        self.doc.ForceRebuild3(False)
        save(self.doc)


def to_assembly(comp, p_mm):
    """A point in a component's own axes (mm) to the assembly's (mm), through its transform."""
    a = list(comp.Transform2.ArrayData)
    R, t, s = [a[0:3], a[3:6], a[6:9]], a[9:12], a[12]
    return tuple((sum(p_mm[j] * MM * R[j][i] for j in range(3)) * s + t[i]) / MM for i in range(3))


def direction(comp, name):
    """A reference plane's normal or a reference axis's direction in its own document's axes,
    read from that document, not through the component."""
    feat = get(comp, "GetModelDoc2").FeatureByName(name)
    if feat is None:
        raise SwError(f"{comp.Name2} has no feature {name}")
    spec = get(feat, "GetSpecificFeature2")
    if get(feat, "GetTypeName2") != "RefAxis":
        return list(get(spec, "Transform").ArrayData)[6:9]
    q = get(spec, "GetRefAxisParams")
    d = [q[3] - q[0], q[4] - q[1], q[5] - q[2]]
    n = sum(v * v for v in d) ** 0.5
    return [v / n for v in d]


def turn(cols, v):
    """Direction v through the rotation whose columns are where the component's X, Y and Z
    go in the assembly's axes."""
    return [sum(cols[j][i] * v[j] for j in range(3)) for i in range(3)]


def mated(asm, comp, target, cols, mates):
    """Each mate made once, aligned where the component's reference, turned by `cols`, points
    with the target's, anti-aligned where against: no mate tried and undone. `mates` are
    (kind, component feature, its type, target feature, its type)."""
    for kind, cf, ctype, tf, ttype in mates:
        dot = sum(a * b for a, b in zip(turn(cols, direction(comp, cf)), direction(target, tf)))
        if abs(dot) < 0.99:
            raise SwError(f"{comp.Name2}: {cf} would not lie along {tf} ({dot:.3f})")
        asm.mate(kind, (asm.ref(comp, cf), ctype), (asm.ref(target, tf), ttype),
                 "swMateAlignALIGNED" if dot > 0 else "swMateAlignANTI_ALIGNED")


def vendor_native(app, step, native, refs=(), light_mm=None, body_box=None, props=None, force=False):
    """A vendor's STEP as a native part beside it, imported once (as one multibody part, or as
    its light part of bodies `light_mm` long and longer), with its interface geometry named so
    mates can cite it: `refs` are (name, "cyl", radius mm), an axis on the cylinder of most
    area of that radius, or (name, "plane", (axis, position mm, normal sign)), a plane on that
    face; `body_box` limits the search to one body. Returns the native path."""
    made = []
    if force or not os.path.exists(native):
        if light_mm:
            doc, kept, total, box = light_part(app, step, light_mm)
            made.append(f"light part of {kept} of {total} bodies")
        else:
            doc = import_step(app, step)
        set_props(doc, dict({"Source": os.path.basename(step)}, **(props or {})))
        save_as(doc, native)
    else:
        doc = open_doc(app, native)
    try:
        for name, kind, spec in refs:
            if doc.FeatureByName(name) is not None:
                continue
            f = find_face(doc, kind, spec, body_box)
            doc.ClearSelection2(True)
            f.Select4(False, doc.SelectionManager.CreateSelectData)
            if kind == "cyl":
                if not doc.InsertAxis2(True):
                    raise SwError(f"{native}: axis {name} not made")
                feat = doc.FeatureByPositionReverse(0)
            else:
                feat = doc.FeatureManager.InsertRefPlane(C["swRefPlaneReferenceConstraint_Coincident"], 0, 0, 0, 0, 0)
                if feat is None:
                    raise SwError(f"{native}: plane {name} not made")
            feat.Name = name
            doc.ClearSelection2(True)
            made.append(name)
        if made:
            save(doc)
    finally:
        close(app, doc)
    return native
