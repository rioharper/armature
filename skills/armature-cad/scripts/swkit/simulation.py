"""
Linear static studies in SOLIDWORKS Simulation through its COM API, for a
check a hand calculation can't make: a fitting's stress away from its
fixtures. Validate the setup on `validate_bar` before trusting a number.

What its API needs (Simulation 2026):
- **cosworks.tlb's dispatch ids are stale** (PressureBeginEdit is 8 there,
  11 at run time). Never use gencache or a CastTo wrapper; call by runtime
  name (`com.call`, `com.put`, `com.read`).
- **Entities are plain Python lists** of faces; a VT_ARRAY VARIANT throws. A
  null reference is `NOTHING`.
- **A load's edits take only between its BeginEdit and EndEdit.** Unit 0 is
  SI (Pa, N, N m); a pressure left unset is 1 Pa.
- **Results land beside the document,** and a solve that meets an earlier
  study's results fails (code 24), after which every solve in that session
  fails until SOLIDWORKS restarts: study a copy in a fresh folder
  (`study_copy`), under a unique study name, and after a 24 restart before
  trusting another solve (`com.restart(addins=[com.SIMULATION])`, the user's
  call while they keep their work out of the seat).
- **A study body dies when Python releases its component,** so `Study`
  holds it. The API can't exclude a body from a multibody study: delete the
  other bodies in memory (`keep_body`).
- **Sharp re-entrant corners read singular** at any load: round them first,
  and read the stress clear of fixtures (`nodal`, `stresses`), not the
  model's own maximum, which sits at a fixture's edge.
- **A load on part of a face** needs the face split: draw a line on a plane
  across the face and `InsertSplitLineProject(False, False)` with the sketch
  at mark 4 and the face at mark 1 (`InsertSplitLineIntersect` returned
  nothing for every mark). Check the loaded area against the footprint.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time

from .com import C, NOTHING, SwError, byref_long, call, disp, install_dir, open_doc, put, read

STUDY_STATIC = 0


def library():
    """SOLIDWORKS's own material library, for `Study.material`."""
    return os.path.join(install_dir(), "lang", "english", "sldmaterials", "solidworks materials.sldmat")


def study_copy(app, part, tmpdir=None):
    """A copy of `part` opened from a fresh scratch folder, where its results can land."""
    path = os.path.join(tmpdir or tempfile.mkdtemp(prefix="swkit_fea_"), os.path.basename(part))
    shutil.copyfile(part, path)
    return open_doc(app, path)


def keep_body(doc, name):
    """Every solid body but `name` deleted in memory, for a study of that body alone."""
    doc.ClearSelection2(True)
    others = [b.Name for b in (doc.GetBodies2(C["swSolidBody"], True) or []) if b.Name != name]
    if len(others) == len(doc.GetBodies2(C["swSolidBody"], True) or []):
        raise SwError(f"no body {name}")
    for n in others:
        if not doc.Extension.SelectByID2(n, "SOLIDBODY", 0, 0, 0, True, 0, NOTHING, 0):
            raise SwError(f"body {n} not selected")
    if others and doc.FeatureManager.InsertDeleteBody2(False) is None:
        raise SwError("the other bodies not deleted")
    return doc.GetBodies2(C["swSolidBody"], True)[0]


class Study:
    """A static study on the active part document, under a unique name."""

    def __init__(self, app, name=None):
        addin = app.GetAddInObject("SldWorks.Simulation")
        if addin is None:
            raise SwError("Simulation is not loaded: load the add-in first")
        self.cw = disp(addin).CosmosWorks
        self.err = byref_long()
        name = name or f"study-{int(time.time() * 1000) % 10 ** 8}"
        st = disp(self.cw.ActiveDoc).StudyManager.CreateNewStudy3(name, STUDY_STATIC, 0, self.err)
        if st is None:
            raise SwError(f"study {name} not made: {self.err.value}")
        self.st = disp(st)
        self.lrm = disp(self.st.LoadsAndRestraintsManager)
        self.res = None

    def bodies(self):
        """The study's solid bodies, in its own order."""
        self.comp = comp = disp(disp(self.st.SolidManager).GetComponentAt(0, self.err))
        return [disp(comp.GetSolidBodyAt(i, self.err)) for i in range(read(comp, "SolidBodyCount"))]

    def material(self, sbody, name, lib=None):
        """A library material by its name ("6061-T6 (SS)", "AISI 304", ...)."""
        if not sbody.SetLibraryMaterial(lib or library(), name):
            raise SwError(f"material {name} not set")

    def fix(self, faces):
        r = self.lrm.AddRestraint(0, list(faces), NOTHING, self.err)
        if r is None:
            raise SwError(f"restraint not made: {self.err.value}")
        return r

    def remote(self, faces, at_mm, force=(0.0, 0.0, 0.0), moment=(0.0, 0.0, 0.0)):
        """A remote load at model point `at_mm` on `faces`: a force (N) and a moment (N m) in
        the part's axes, carried to the faces with their own deformation (direct transfer)."""
        r = self.lrm.AddRemoteLoad(0, list(faces), 0, *at_mm, self.err)
        if r is None:
            raise SwError(f"remote load not made: {self.err.value}")
        call(r, "RemoteLoadBeginEdit")
        put(r, "ForceOrTranslationUnit", 0)
        put(r, "MomentOrRotationUnit", 0)
        call(r, "SetForceOrTranslationValues", 1, 1, float(force[0]), 1, float(force[1]), 1, float(force[2]))
        call(r, "SetMomentOrRotationValues", 1, 1, float(moment[0]), 1, float(moment[1]), 1, float(moment[2]))
        code = call(r, "RemoteLoadEndEdit")
        if code:
            raise SwError(f"remote load not edited: {code}")
        return r

    def pressure(self, faces, pa):
        """A uniform pressure (Pa) normal to `faces`."""
        r = self.lrm.AddPressure(0, list(faces), NOTHING, self.err)
        if r is None:
            raise SwError(f"pressure not made: {self.err.value}")
        call(r, "PressureBeginEdit")
        put(r, "Unit", 0)
        put(r, "Value", float(pa))
        code = call(r, "PressureEndEdit")
        if code:
            raise SwError(f"pressure not edited: {code}")
        return r

    def solve(self, size_mm, tol_mm=None):
        """Mesh (high quality, `size_mm` elements) and run. Code 24 is a results clash: see
        the module's note before solving again."""
        put(self.st.Mesh, "Quality", 1)
        code = self.st.CreateMesh(0, float(size_mm), float(tol_mm or size_mm / 20))
        if code:
            raise SwError(f"mesh failed: {code}")
        code = self.st.RunAnalysis
        if code:
            raise SwError(f"analysis failed: {code}" + (" (a results clash: restart before another solve)"
                                                       if code == 24 else ""))
        self.res = disp(self.st.Results)

    def von_mises(self):
        """(min, max) von Mises over the model (Pa)."""
        out = self.res.GetMinMaxStress(9, 0, 0, NOTHING, 0, self.err)
        return out[1], out[3]

    def displacement(self):
        """The largest resultant displacement (mm)."""
        return self.res.GetMinMaxDisplacement(3, 0, NOTHING, 0, self.err)[3]

    def nodal(self):
        """Every node's place (mm) and von Mises (Pa), for reading a zone clear of fixtures."""
        nodes = list(call(self.st.Mesh, "GetNodes") or [])
        where = {int(nodes[i]): (nodes[i + 1] * 1e3, nodes[i + 2] * 1e3, nodes[i + 3] * 1e3)
                 for i in range(0, len(nodes), 4)}
        s = list(self.res.GetStress(0, 0, NOTHING, 0, self.err) or [])
        return [(*where[int(s[i])], s[i + 10]) for i in range(0, len(s), 12)]

    def stresses(self, faces):
        """The von Mises at every node on `faces` (Pa)."""
        return list(self.res.GetStressForEntities2(True, 9, 0, NOTHING, list(faces), 0, self.err) or [])


def validate_bar(app, tmpdir=None, template=None, material="6061-T6 (SS)", e_pa=68.9e9):
    """A 10 x 10 x 100 mm bar built here, fixed at z 0, 10 N m about x at its free end: the tip
    moves M L^2 / (2 E I). Returns (tip mm, beam theory's mm); within 3 % is a working setup."""
    from .expr import ZERO
    from .measure import faces_where
    from .part import Part
    tmpdir = tmpdir or tempfile.mkdtemp(prefix="swkit_fea_")
    p = Part(app, os.path.join(tmpdir, "validate.SLDPRT"), template=template,
             globals_=[("a", 10.0, "mm", "section"), ("L", 100.0, "mm", "length")])
    try:
        s = p.sketch("Front Plane", "bar_sk")
        s.rect(-p["a"] / 2, p["a"] / 2, p["a"] / 2, ZERO)
        s.close()
        p.extrude("bar_sk", "bar", p["L"], toward=1)
        p.finish()
        body = p.doc.GetBodies2(C["swSolidBody"], True)[0]
        st = Study(app)
        st.material(st.bodies()[0], material)
        st.fix(faces_where(body, lambda b: abs(b[2]) < 1e-6 and abs(b[5]) < 1e-6))
        end = faces_where(body, lambda b: abs(b[2] - 100) < 1e-6 and abs(b[5] - 100) < 1e-6)
        st.remote(end, (0.0, 0.0, 100.0), moment=(10.0, 0.0, 0.0))
        st.solve(2.0)
        i = 0.010 ** 4 / 12
        return st.displacement(), 10.0 * 0.100 ** 2 / (2 * e_pa * i) * 1e3
    finally:
        p.close()
