"""Thin COM wrapper for the armature SolidWorks MCP. All COM lives here."""
import itertools
import os
import pythoncom
import win32com.client
from win32com.client import VARIANT


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
    return win32com.client.Dispatch(disp)


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


def _com_call(op_desc, fn):
    """Run a raw COM call and turn any failure into an actionable SwError —
    the generic fallback shape for COM errors outside attach/resolve_doc."""
    try:
        return fn()
    except pythoncom.com_error as e:
        raise SwError(
            f"SolidWorks COM call failed during {op_desc}: {e}. "
            "Check for a blocking dialog in SolidWorks."
        )


def status(app) -> dict:
    def _read():
        active = app.ActiveDoc
        return {
            "solidworks_version": app.RevisionNumber,
            "open_documents": [
                {"title": d.GetTitle, "path": d.GetPathName} for d in _docs(app)
            ],
            "active_document": active.GetTitle if active else None,
        }
    return _com_call("status", _read)


_DOC_TYPES = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}  # swDocumentTypes_e

def open_doc(app, path: str) -> dict:
    ext = os.path.splitext(path)[1].lower()
    if ext not in _DOC_TYPES:
        raise SwError(f"Unsupported extension '{ext}' — expected .SLDPRT/.SLDASM/.SLDDRW")
    if not os.path.isfile(path):
        raise SwError(f"File not found: {path}")
    # OpenDoc6's [in/out] error/warning args — dynamic dispatch needs explicit byref VARIANTs,
    # a plain int raises "Type mismatch"; we don't read the values back.
    errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    # swOpenDocOptions_Silent = 1
    d = _com_call(
        f"OpenDoc6('{path}')",
        lambda: app.OpenDoc6(path, _DOC_TYPES[ext], 1, "", errors, warnings),
    )
    if d is None:
        d = resolve_doc(app, os.path.basename(path))  # already open → activate
    # swRebuildOnActivation_e 2 = don't rebuild; Errors is an [out] byref long, same VARIANT need as above
    activate_errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    _com_call(
        f"ActivateDoc3('{d.GetTitle}')",
        lambda: app.ActivateDoc3(d.GetTitle, False, 2, activate_errors),
    )
    return {"opened": d.GetTitle, "path": d.GetPathName, "linear_units": linear_units(d)}


def _eq_name(text: str) -> str | None:
    # global variable equations look like: "block_len" = 40
    if text.startswith('"'):
        return text[1 : text.index('"', 1)]
    return None


def get_params(doc) -> dict:
    def _read():
        eq = doc.GetEquationMgr  # niladic accessor -> property under dynamic dispatch, no ()
        out = {}
        for i in range(eq.GetCount):  # same: property, not a method call
            text = eq.Equation(i)  # parameterized-property get form
            name = _eq_name(text)
            if name:
                out[name] = {
                    "equation": text,
                    "value": eq.Value(i),  # document units — hence linear_units field
                    "global": bool(eq.GlobalVariable(i)),
                }
        return {"linear_units": linear_units(doc), "params": out}
    return _com_call("get_params", _read)


def _put_equation(eq, index: int, text: str):
    # This SolidWorks build exposes no GetEquation/SetEquation methods and no
    # Equation[i]= item-assignment under dynamic dispatch (verified against the
    # live COM object) — only the parameterized-property get eq.Equation(i).
    # The property "put" side isn't reachable through normal attribute
    # assignment either, since __setattr__ has nowhere to carry the index arg.
    # Fall back to a raw DISPATCH_PROPERTYPUT invoke: args are (index, value).
    dispid = eq._oleobj_.GetIDsOfNames(0, "Equation")
    eq._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_PROPERTYPUT, 0, index, text)


def rebuild(doc) -> dict:
    """Force-rebuild; model errors/warnings are RETURN DATA, never exceptions.
    Only a raw COM failure (e.g. blocking dialog) raises."""
    def _do():
        doc.ForceRebuild3(False)  # False = rebuild all, not just top level
        # IModelDocExtension::GetWhatsWrong's three [out] params are declared
        # [in/out] in the typelib, so under dynamic dispatch they must be
        # passed as byref VARIANTs (plain VT_VARIANT, not VT_ARRAY — VT_ARRAY
        # raises "Type mismatch"; omitting them raises "Parameter not
        # optional") — verified live. The return bool is call-success, not
        # "model is clean"; features/errors/warnings stay None when clean.
        feats = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
        error_codes = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
        warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
        doc.Extension.GetWhatsWrong(feats, error_codes, warnings)
        problems = []
        # zip_longest + defensive .Name: a malformed/short entry must degrade
        # to a labeled row, never crash the tool call the user needs most.
        for feat, warn in itertools.zip_longest(feats.value or (), warnings.value or ()):
            try:
                name = feat.Name
            except Exception:
                name = str(feat) if feat is not None else "<unknown feature>"
            problems.append({"feature": name, "kind": "warning" if warn else "error"})
        return {"rebuilt": True, "problems": problems}
    return _com_call("rebuild", _do)


def feature_by_name(doc, name: str, type_filter: str | None = None):
    # FirstFeature/GetNextFeature/GetFirstSubFeature/GetNextSubFeature/GetTypeName2
    # are niladic under dynamic dispatch (no gencache) -> bare attribute access,
    # calling them with () raises "Member not found" (verified live).
    names = []
    feat = doc.FirstFeature
    while feat:
        for f in _with_subfeatures(feat):
            if type_filter is None or f.GetTypeName2 == type_filter:
                if f.Name == name:
                    return f
                names.append(f.Name)
        feat = feat.GetNextFeature
    kind = f" of type {type_filter}" if type_filter else ""
    raise NameNotFound(f"No feature '{name}'{kind}. Available: {names}")


def _with_subfeatures(feat):
    yield feat
    sub = feat.GetFirstSubFeature
    while sub:
        yield sub
        sub = sub.GetNextSubFeature


# swMassPropertyMoment_e — verified by the smoke parallel-axis assertion
_MOMENT_ABOUT_COM = 0
_MOMENT_ABOUT_COORD_SYS = 1

def mass_properties(doc, coord_system: str | None) -> dict:
    def _read():
        # CreateMassProperty and GetDefinition are also niladic -> bare attribute
        # access (same "Member not found" trap as the feature-traversal accessors).
        mp = doc.Extension.CreateMassProperty
        mp.UseSystemUnits = True  # kg, m, kg*m^2 regardless of document units
        about = "center_of_mass"
        moment_kind = _MOMENT_ABOUT_COM
        if coord_system:
            feat = feature_by_name(doc, coord_system, type_filter="CoordSys")
            xform = feat.GetDefinition.Transform  # ICoordinateSystemFeatureData
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
    return _com_call("mass_properties", _read)


# swTolType_e values — verified by the smoke set->read round-trip
_TOL_TYPES = {"none": 0, "bilateral": 2, "symmetric": 5, "fit": 9}
_TOL_NAMES = {v: k for k, v in _TOL_TYPES.items()}


def _dimension(doc, full_name: str):
    # doc.Parameter(name) is a parameterized-property get -> callable under
    # dynamic dispatch (unlike the niladic accessors elsewhere in this file);
    # returns None rather than raising for an unknown name.
    dim = doc.Parameter(full_name)
    if dim is None:
        raise NameNotFound(
            f"No dimension '{full_name}'. Use the full form 'name@Sketch1' / 'name@Feature'; "
            "check the name in the SolidWorks dimension PropertyManager."
        )
    return dim


def _tol_entry(dim) -> dict | None:
    tol = dim.Tolerance  # bare attribute -> ITolerance
    t = _TOL_NAMES.get(tol.Type, f"swTolType_{tol.Type}")
    if t == "none":
        return None
    # GetMaxValue2()/GetMinValue2() (brief's guess) both raise "Parameter not
    # optional" here -- verified live they're niladic properties under this
    # build's dynamic dispatch (the "2"-less GetMaxValue/GetMinValue), same
    # bare-attribute trap as elsewhere in this file.
    return {"type": t, "max": tol.GetMaxValue, "min": tol.GetMinValue}


def get_dimensions(doc, names: list) -> dict:
    def _read():
        out = {}
        for full_name in names:
            dim = _dimension(doc, full_name)
            out[full_name] = {"value": dim.SystemValue, "tolerance": _tol_entry(dim)}
        return {"units": "SI (m, rad)", "dimensions": out}
    return _com_call("get_dimensions", _read)


def set_tolerance(doc, dim_name: str, tol_type: str, values: dict) -> dict:
    # "none" isn't in the brief's public contract but is needed to restore a
    # dimension to its un-toleranced state (smoke suite idempotency).
    if tol_type not in ("none", "bilateral", "symmetric", "fit"):
        raise SwError(f"tol_type must be bilateral|symmetric|fit, got '{tol_type}'")
    def _write():
        dim = _dimension(doc, dim_name)
        tol = dim.Tolerance
        # Unlike IEquationMgr::Equation (_put_equation), ITolerance::Type's
        # property PUT *is* reachable via plain attribute assignment under
        # this build's dynamic dispatch -- verified live, no raw invoke needed.
        tol.Type = _TOL_TYPES[tol_type]
        if tol_type == "fit":
            # ITolerance fit: hole class like "H7", shaft class like "p6" ("" = unused side)
            tol.SetFitValues(values.get("hole", ""), values.get("shaft", ""))
        elif tol_type in ("bilateral", "symmetric"):
            tol.SetValues(values["min"], values["max"])  # SI meters
        doc.EditRebuild3
        return get_dimensions(doc, [dim_name])["dimensions"][dim_name]
    return _com_call("set_tolerance", _write)


def set_params(doc, values: dict) -> dict:
    def _write():
        eq = doc.GetEquationMgr
        index = {}
        for i in range(eq.GetCount):
            name = _eq_name(eq.Equation(i))
            if name and eq.GlobalVariable(i):  # writes are global-vars-only, never feature dims
                index[name] = i
        missing = [n for n in values if n not in index]
        if missing:
            raise NameNotFound(
                f"No global variable(s) {missing}. Available: {sorted(index)}. "
                "set_params never creates variables — fix the name or add it in SolidWorks."
            )
        for name, val in values.items():
            _put_equation(eq, index[name], f'"{name}"= {val}')
        doc.EditRebuild3  # also niladic -> property access triggers the rebuild
        fresh = get_params(doc)
        return {"linear_units": fresh["linear_units"],
                "params": {n: fresh["params"][n] for n in values}}
    return _com_call("set_params", _write)
