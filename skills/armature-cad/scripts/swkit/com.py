"""
COM plumbing for driving SOLIDWORKS from Python through pywin32: its
constants, attaching, the argument shapes its members want, preferences set
for a block and put back, documents, custom properties, features and their
errors, equations, and a restart.

Every quirk here cost a failed run once. The ones worth knowing before
writing a call:

- **A member with no arguments** comes back either as a value or as a
  bound method, depending on how pywin32 bound it: `doc.GetTitle`,
  `doc.EditRebuild3` and `comp.GetModelDoc2` run on access, while
  `body.GetBodyBox()` and `doc.ViewZoomtofit2()` need the call. `get()`
  reads either. `callable()` can't tell them apart, since a COM object is
  callable too.
- **A typed member** (known to the type library) takes plain values for its
  out-arguments and returns a tuple: `body.GetExtremePoint(dx, dy, dz, 0.0,
  0.0, 0.0)` gives `(ok, x, y, z)`. A null object there is `None`.
- **An untyped member** wants its out-arguments as by-reference VARIANTs
  (`byref_long()` and its siblings) and a null object as `NOTHING`, a null
  VT_DISPATCH; a bare `None` is a type mismatch. `SelectByID2`'s callout and
  `SaveAs3`'s export data are two.
- **A type library with stale dispatch ids** (Simulation's cosworks.tlb):
  call by runtime name with `call`, `put` and `read`, never through gencache.
- **An indexed property put** has no Python spelling: `set_equation` invokes
  the property put by its dispatch id.
"""
from __future__ import annotations

import contextlib
import inspect
import os
import re
import subprocess
import time

import pythoncom
import win32com.client
from win32com.client import VARIANT

MM = 1e-3
DEFAULT_DIR = r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS"


class SwError(RuntimeError):
    """A SOLIDWORKS call that did not do what it was asked; the message says what to do."""


# --- where SOLIDWORKS is installed, and its constants ---------------------------------------
def install_dir():
    """SOLIDWORKS's program folder: `SWKIT_SOLIDWORKS_DIR` if set, else the folder of the
    executable registered for `SldWorks.Application`, else the default install path."""
    env = os.environ.get("SWKIT_SOLIDWORKS_DIR")
    if env:
        return env
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"SldWorks.Application\CLSID") as k:
            clsid = winreg.QueryValue(k, None)
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32") as k:
            exe = winreg.QueryValue(k, None)
        exe = exe.strip().strip('"').split('" ')[0].split(" /")[0]
        try:
            import win32api
            exe = win32api.GetLongPathName(exe)
        except Exception:
            pass
        if os.path.isfile(exe):
            return os.path.dirname(exe)
    except OSError:
        pass
    return DEFAULT_DIR


class _Constants:
    """Every enum value in swconst.tlb by its name, `C["swDocPART"]`, read on first use."""

    def __init__(self):
        self._v = None

    def _load(self):
        path = os.environ.get("SWKIT_SWCONST") or os.path.join(install_dir(), "swconst.tlb")
        if not os.path.isfile(path):
            raise SwError(f"no swconst.tlb at {path}: set SWKIT_SOLIDWORKS_DIR to SOLIDWORKS's folder")
        tlb = pythoncom.LoadTypeLib(path)
        out = {}
        for i in range(tlb.GetTypeInfoCount()):
            ti = tlb.GetTypeInfo(i)
            ta = ti.GetTypeAttr()
            if ta.typekind != pythoncom.TKIND_ENUM:
                continue
            for j in range(ta.cVars):
                vd = ti.GetVarDesc(j)
                out[ti.GetNames(vd.memid)[0]] = vd.value
        self._v = out

    def __getitem__(self, name):
        if self._v is None:
            self._load()
        try:
            return self._v[name]
        except KeyError:
            raise KeyError(f"no SOLIDWORKS constant {name!r}") from None

    def __contains__(self, name):
        if self._v is None:
            self._load()
        return name in self._v


C = _Constants()


# --- argument shapes ------------------------------------------------------------------------
NOTHING = VARIANT(pythoncom.VT_DISPATCH, None)
EMPTY = VARIANT(pythoncom.VT_EMPTY, None)


def byref_long(v=0):
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, v)


def byref_bool(v=False):
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, v)


def byref_bstr(v=""):
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, v)


def byref_variant():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)


def doubles(values):
    """An array of doubles. A Python tuple put on a property lands as (0, its first)."""
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, tuple(float(v) for v in values))


def objects(values):
    """An array of COM objects, as a feature definition's `Edges` wants them."""
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(values))


def disp(x):
    """A raw PyIDispatch, as some calls hand back, wrapped for attribute access."""
    return x if hasattr(x, "_oleobj_") else win32com.client.Dispatch(x)


# --- members --------------------------------------------------------------------------------
def get(obj, name):
    """A member's value whether pywin32 binds it as a property or as a method."""
    v = getattr(obj, name)
    return v() if inspect.ismethod(v) else v


def _ole(x):
    return x._oleobj_ if hasattr(x, "_oleobj_") else x


def call(x, name, *args):
    """A method called by its runtime name, past a stale type library."""
    o = _ole(x)
    return o.Invoke(o.GetIDsOfNames(name), 0, pythoncom.DISPATCH_METHOD, True, *args)


def put(x, name, value):
    """A property set by its runtime name."""
    o = _ole(x)
    return o.Invoke(o.GetIDsOfNames(name), 0, pythoncom.DISPATCH_PROPERTYPUT, False, value)


def read(x, name):
    """A property read by its runtime name."""
    o = _ole(x)
    return o.Invoke(o.GetIDsOfNames(name), 0, pythoncom.DISPATCH_PROPERTYGET, True)


# --- the application ------------------------------------------------------------------------
def attach():
    """The running SOLIDWORKS. The kit never starts one: it drives the user's seat."""
    try:
        return win32com.client.Dispatch(win32com.client.GetActiveObject("SldWorks.Application"))
    except pythoncom.com_error:
        raise SwError("SOLIDWORKS is not running: start it, then rerun") from None


def titles(app):
    return [d.GetTitle for d in (app.GetDocuments or [])]


def require_empty(app):
    """Refuse to run while SOLIDWORKS holds documents: a script that closes everything it
    opened, or restarts the seat, must not take the user's unsaved work with it."""
    open_ = titles(app)
    if open_:
        raise SwError(f"SOLIDWORKS holds open documents, {open_}: save and close them first")


@contextlib.contextmanager
def preference(app, name, value):
    """An application preference set for the block and put back after it: a toggle when
    `value` is a bool, else an integer. Yields the value it replaced."""
    if isinstance(value, bool):
        old = app.GetUserPreferenceToggle(C[name])
        app.SetUserPreferenceToggle(C[name], value)
    else:
        old = app.GetUserPreferenceIntegerValue(C[name])
        app.SetUserPreferenceIntegerValue(C[name], value)
    try:
        yield old
    finally:
        if isinstance(value, bool):
            app.SetUserPreferenceToggle(C[name], old)
        else:
            app.SetUserPreferenceIntegerValue(C[name], old)


def no_value_prompt(app):
    """A new dimension opens SOLIDWORKS's Modify box unless `swInputDimValOnCreate` is off,
    and the box blocks every later COM call until a hand reaches the keyboard. A dimension in
    a drawing view's sketch is a driving one, so drawings need it off too."""
    return preference(app, "swInputDimValOnCreate", False)


# --- documents ------------------------------------------------------------------------------
DOC_TYPES = {".sldprt": "swDocPART", ".sldasm": "swDocASSEMBLY", ".slddrw": "swDocDRAWING"}


def require_closed(app, path):
    """Refuse a file SOLIDWORKS already holds in a window, or another folder's file of the same
    name. OpenDoc6 hands back an open document of that file name, whatever its folder, so a
    script would read the wrong file, or close the user's window unsaved when done. A hidden
    one, a reference an earlier view or open loaded, passes."""
    path = os.path.abspath(path)
    for d in app.GetDocuments or []:
        held = d.GetPathName or ""
        if os.path.basename(held).lower() != os.path.basename(path).lower():
            continue
        if os.path.normcase(held) != os.path.normcase(path):
            raise SwError(f"SOLIDWORKS holds {held}, of the same name as {path}: close it first")
        if d.Visible:
            raise SwError(f"{path} is open in SOLIDWORKS: save and close it first")


def open_doc(app, path, config=""):
    """A native document opened silently, in configuration `config` (its last saved if empty).
    Refuses one the user has open, or a namesake (`require_closed`)."""
    path = os.path.abspath(path)
    require_closed(app, path)
    kind = DOC_TYPES.get(os.path.splitext(path)[1].lower())
    if kind is None:
        raise SwError(f"{path}: not a SOLIDWORKS part, assembly or drawing")
    err, warn = byref_long(), byref_long()
    doc = app.OpenDoc6(path, C[kind], C["swOpenDocOptions_Silent"], config, err, warn)
    if doc is None:
        raise SwError(f"could not open {path}: error {err.value}, warning {warn.value}")
    return doc


def close(app, doc):
    app.CloseDoc(doc.GetTitle)


@contextlib.contextmanager
def opened(app, path, config=""):
    """A document open for the block and closed unsaved after it."""
    doc = open_doc(app, path, config)
    try:
        yield doc
    finally:
        close(app, doc)


def new_doc(app, template):
    doc = app.NewDocument(os.path.abspath(template), 0, 0, 0)
    if doc is None:
        raise SwError(f"NewDocument failed from {template}")
    return doc


def default_template(app, kind="part"):
    """The seat's default template for a part, an assembly or a drawing."""
    key = {"part": "swDefaultTemplatePart", "assembly": "swDefaultTemplateAssembly",
           "drawing": "swDefaultTemplateDrawing"}[kind]
    path = app.GetUserPreferenceStringValue(C[key])
    if not path or not os.path.isfile(path):
        raise SwError(f"no default {kind} template set on this seat ({path!r}): pass one")
    return path


def save(doc):
    err, warn = byref_long(), byref_long()
    if not doc.Save3(C["swSaveAsOptions_Silent"], err, warn):
        raise SwError(f"Save3 failed for {doc.GetTitle}: error {err.value}, warning {warn.value}")


def save_as(doc, path, copy=False):
    """Save under a new name, or write a copy (`copy=True`) and keep the document as it was.
    The extension picks the format: .STEP, .PDF, .DXF, .STL and the rest go through here."""
    opts = C["swSaveAsOptions_Silent"] | (C["swSaveAsOptions_Copy"] if copy else 0)
    err, warn = byref_long(), byref_long()
    ok = doc.Extension.SaveAs3(os.path.abspath(path), C["swSaveAsCurrentVersion"], opts,
                               NOTHING, NOTHING, err, warn)
    if not ok or err.value:
        raise SwError(f"SaveAs3 failed for {path}: error {err.value}, warning {warn.value}")


# --- custom properties ----------------------------------------------------------------------
def set_props(doc, values, config=""):
    """Text custom properties, each replaced if present: the title block reads them."""
    cpm = doc.Extension.CustomPropertyManager(config)
    for name, value in values.items():
        cpm.Add3(name, C["swCustomInfoText"], str(value), C["swCustomPropertyReplaceValue"])


def prop(doc, name, config=""):
    """A custom property's resolved value. The property manager comes back untyped, so its
    out-arguments go by reference."""
    val, res = byref_bstr(), byref_bstr()
    was, link = byref_bool(), byref_bool()
    doc.Extension.CustomPropertyManager(config).Get6(name, False, val, res, was, link)
    if not (res.value or val.value):
        raise SwError(f"no property {name} on {doc.GetTitle}")
    return res.value or val.value


def props(doc, config=""):
    names = doc.Extension.CustomPropertyManager(config).GetNames or []
    return {n: prop(doc, n, config) for n in names}


# --- features -------------------------------------------------------------------------------
def features(doc):
    """Every feature, each followed by its sub-features (a sketch under its extrusion)."""
    f = doc.FirstFeature
    while f is not None:
        yield f
        sub = f.GetFirstSubFeature
        while sub is not None:
            yield sub
            sub = sub.GetNextSubFeature
        f = f.GetNextFeature


def errors(doc):
    """Every feature in error or warning after a rebuild: (name, code, "error" | "warning")."""
    out = []
    for f in features(doc):
        warn = byref_bool()
        code = f.GetErrorCode2(warn)
        if code:
            out.append((f.Name, code, "warning" if warn.value else "error"))
    return out


# --- equations ------------------------------------------------------------------------------
def equation_index(em, name):
    """The index of global `name`'s equation in the equation manager."""
    for i in range(em.GetCount):
        if em.Equation(i).split("=")[0].strip().strip('"') == name:
            return i
    raise KeyError(f"no equation for {name!r}")


def global_value(em, name):
    """A global's value, in the document's units (mm, deg on an MMGS part)."""
    return em.Value(equation_index(em, name))


def set_equation(em, i, text):
    """Equation i's text, put through the property itself. `SetEquationAndConfigurationOption`
    returns -1 and changes nothing, and deleting a global and adding it back leaves its
    dependents reading 0 (SOLIDWORKS 2026)."""
    o = em._oleobj_
    o.Invoke(o.GetIDsOfNames("Equation"), 0, pythoncom.DISPATCH_PROPERTYPUT, 0, i, text)
    if em.Equation(i).replace(" ", "") != text.replace(" ", ""):
        raise SwError(f"equation {i} kept {em.Equation(i)!r}, not {text!r}")


_NUMBER = re.compile(r'^\s*("[^"]+"\s*=\s*)(-?[\d.]+(?:[eE][-+]?\d+)?)(\s*[A-Za-z]*)(.*)$')


def scale_global(em, name, factor):
    """A typed global's number times `factor`, its unit and comment kept. Returns its old text.
    A global takes a new value only from the configuration it was written in: from a mirrored
    configuration the put leaves it as it was, so show the first configuration before this."""
    i = equation_index(em, name)
    text = em.Equation(i)
    m = _NUMBER.match(text)
    if not m:
        raise SwError(f"{name}'s equation is not a typed number: {text!r}")
    set_equation(em, i, f"{m.group(1)}{float(m.group(2)) * factor:.9g}{m.group(3)}{m.group(4)}")
    return text


# --- restarting the seat --------------------------------------------------------------------
SIMULATION = ("SldWorks.Simulation", os.path.join("Simulation", "cosworks.dll"))


def restart(addins=(), timeout=300):
    """End SOLIDWORKS and start it again, only while it holds no document, then load each
    add-in, (prog id, dll path relative to the install folder). For a seat a failed call has
    left in a state no later call recovers from, such as Simulation after a failed solve.
    Ending the user's SOLIDWORKS is their call: ask first. Returns the new application."""
    try:
        app = win32com.client.Dispatch(win32com.client.GetActiveObject("SldWorks.Application"))
    except pythoncom.com_error:
        app = None
    if app is not None:
        require_empty(app)
        app = None
        subprocess.run(["taskkill", "/IM", "SLDWORKS.exe", "/F"], capture_output=True)
        for _ in range(60):
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe"], capture_output=True, text=True)
            if "SLDWORKS.exe" not in r.stdout:
                break
            time.sleep(1)
    subprocess.Popen([os.path.join(install_dir(), "SLDWORKS.exe")], creationflags=subprocess.DETACHED_PROCESS)
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(5)
        try:
            app = win32com.client.Dispatch(win32com.client.GetActiveObject("SldWorks.Application"))
            for progid, dll in addins:
                if app.GetAddInObject(progid) is None:
                    app.LoadAddIn(os.path.join(install_dir(), dll))
                if app.GetAddInObject(progid) is None:
                    raise pythoncom.com_error
            return app
        except pythoncom.com_error:
            continue
    raise SwError(f"SOLIDWORKS did not come up{' with its add-ins' if addins else ''} in {timeout} s")
