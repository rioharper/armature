"""Thin COM wrapper for the armature SolidWorks MCP. All COM lives here."""
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
