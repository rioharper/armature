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
