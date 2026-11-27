"""
A drawing's critical features dimensioned on its views: diameters, radii
and distances with their tolerances or fit classes, datum features, feature
control frames and leader notes (ISO 129-1, ISO 1101, ISO 286; ASME Y14.5
reads the same). A tolerance belongs on the view, not in a note.

A spec is one of:

    dia(view, pick, at, tol=None, pre="", post="", below="")   a diameter
    rad(view, pick, at, tol=None, pre="")                       a radius
    dist(view, pick, pick, at, tol=None, orient=None)           a distance
    datum(view, pick or index, label, at)                       a datum feature
    frame(sym, value, datums, at, on=index or (view, pick))     a feature control frame
    callout(view, pick, text, at)                               a leader note

A **pick** names an edge or face the view shows by its model geometry, in
the part's own frame (mm), so a drawing script never depends on SOLIDWORKS's
entity order: `circle(r, x=, y=, z=)` by its radius and any of its centre's
coordinates; `line(axis, x=, y=, z=)` the longest line along `axis` at those
coordinates; `face(normal, at)` the largest plane normal to an axis at a
coordinate. `spot(p)` is the edge passing through model point p, a
section's or detail's cut edges among them; `sharp(p)` places a sketch
point in the view (a virtual sharp) to dimension to. `survey(views)` prints
what each view shows, for writing the picks.

`at` places the text off the view's outline: a side ("left", "right", "top",
"bottom"), how far along it (0-1), and how far out (mm on the sheet; None
stacks it past what is already on that side, a lane at a time); ("in", u, v)
inside the outline by fractions; `model_at(p)` at a model point. A tolerance
is `fit("H7")` (upper case a hole, lower a shaft), `pm(0.1)` or `lim(+0.2, 0)`.

What it took to make these calls behave (SOLIDWORKS 2026):
- With a placed sketch point among the picks, the view must stay active
  while the dimension is made, or it measures at the sheet's scale rather
  than the view's (4x off at a 2:1 detail on a 1:2 sheet).
- A dimension between placed points is a driving one: its Modify box would
  block COM, so the value prompt is off meanwhile (`com.no_value_prompt`).
- `InsertDatumTag2` and `InsertGtol` bind as properties: read them with
  `get()`. A datum moves with `SetPosition`, not `SetPosition2`, and a datum
  on a dimension won't move at all: put it on the edge.
- A frame's symbol is `SetFrameSymbols2(1, "<IGTOL-PERP>", ...)`; read it back
  with `GetFrameSymbols3`, since a wrong code is silently dropped.
- A prefix replaces the Ø: write "4X <MOD-DIAM>" (`dia` does). The
  `<HOLE-CBORE>` code prints literally: write C'BORE and CSK.
"""
from __future__ import annotations

from .com import C, MM, NOTHING, SwError, get, no_value_prompt
from .section import activate_sheet, edge_through, edges, to_sheet, to_sketch

TOL_R, TOL_C = 0.005, 0.05     # mm: a pick's radius and coordinate match
BLACK = 0
_AX = {"x": 0, "y": 1, "z": 2}


# --- picks ----------------------------------------------------------------------------------
def circle(r, **at):
    return ("circle", r, at)


def line(axis, **at):
    return ("line", axis, at)


def face(normal, at):
    return ("face", normal, at)


def spot(p):
    """The edge the view shows through model point p (mm), a cut edge of a section or detail
    among them. Not by sheet point: `SelectByID2` there selects the view, not the edge."""
    return ("spot", tuple(p))


def sharp(p):
    """A virtual sharp at model point p (mm): a sketch point placed there in the view."""
    return ("sharp", tuple(p))


def model_at(p):
    """An `at` that places the text at model point p (mm), as the view shows it."""
    return ("model", tuple(p), None)


# --- tolerances -----------------------------------------------------------------------------
def fit(code):
    return ("fit", code)


def pm(v):
    return ("pm", v)


def lim(up, down):
    return ("lim", up, down)


# --- specs ----------------------------------------------------------------------------------
def dia(view, pick, at, tol=None, pre="", post="", below="", prec=None):
    """A diameter; `pre` goes before its Ø ("3X "), which is kept."""
    return dict(kind="dia", view=view, picks=[pick], at=at, tol=tol, pre=pre + "<MOD-DIAM>" if pre else "",
                post=post, below=below, prec=prec)


def rad(view, pick, at, tol=None, pre="", prec=None):
    return dict(kind="rad", view=view, picks=[pick], at=at, tol=tol, pre=pre, post="", below="", prec=prec)


def dist(view, a, b, at, tol=None, pre="", post="", orient=None, prec=None):
    """A distance; `orient` "h" or "v" holds it level or upright on the sheet."""
    return dict(kind="dist", view=view, picks=[a, b], at=at, tol=tol, pre=pre, post=post, below="",
                orient=orient, prec=prec)


def datum(view, pick, label, at):
    """On an edge or face (a pick), or on an earlier annotation (its index): its axis."""
    return dict(kind="datum", view=view, picks=[pick], label=label, at=at)


def frame(sym, value, datums, at, on, dia=False):
    """`on`: an earlier annotation's index, placed off that one's view; or (view, pick)."""
    return dict(kind="frame", sym=sym, value=value, datums=datums, at=at, on=on, dia=dia)


def callout(view, pick, text, at):
    return dict(kind="callout", view=view, picks=[pick], text=text, at=at)


SYMBOLS = {"perp": "<IGTOL-PERP>", "flat": "<IGTOL-FLAT>", "pos": "<IGTOL-POSITION>", "surf": "<IGTOL-SPROF>",
           "line": "<IGTOL-LPROF>", "par": "<IGTOL-PARALLEL>", "conc": "<IGTOL-CONC>", "circ": "<IGTOL-CIRC>",
           "cyl": "<IGTOL-CYL>", "runout": "<IGTOL-CRUNOUT>", "total": "<IGTOL-TRUNOUT>", "angle": "<IGTOL-ANGULAR>",
           "sym": "<IGTOL-SYMMETRY>", "straight": "<IGTOL-STRAIGHT>"}


# --- what a view shows (edges() is section.edges) --------------------------------------------
def _faces(view):
    out = []
    for f in (view.GetVisibleEntities2(NOTHING, C["swViewEntityType_Face"]) or []):
        srf = get(f, "GetSurface")
        if get(srf, "IsPlane"):
            p = list(get(srf, "PlaneParams"))
            out.append((f, p[:3], [v / MM for v in p[3:6]], get(f, "GetArea")))
    return out


def find(view, pick, cache):
    """The entity a pick names on `view`."""
    if pick[0] == "face":
        _, normal, at = pick
        i = _AX[normal]
        fs = [(a, f) for f, n, r, a in cache.setdefault(("faces", view.Name), _faces(view))
              if abs(abs(n[i]) - 1) < 1e-6 and abs(r[i] - at) < TOL_C]
        if not fs:
            raise SwError(f"{view.Name}: no face for {pick}")
        return max(fs, key=lambda t: t[0])[1]
    es = cache.setdefault(view.Name, edges(view))
    if pick[0] == "circle":
        _, r, at = pick
        hits = [e for k, e, (c, rr) in es if k == "circle" and abs(rr - r) < TOL_R
                and all(abs(c[_AX[a]] - v) < TOL_C for a, v in at.items())]
    else:
        _, axis, at = pick
        i = _AX[axis]
        cands = []
        for k, e, d in es:
            if k != "line":
                continue
            a, b = d
            if any(abs(a[j] - b[j]) > 1e-4 for j in range(3) if j != i):
                continue
            if all(abs(a[_AX[ax]] - v) < TOL_C for ax, v in at.items()):
                cands.append((abs(b[i] - a[i]), e))
        hits = [e for _, e in sorted(cands, key=lambda t: -t[0])]
    if not hits:
        raise SwError(f"{view.Name}: no edge for {pick}")
    return hits[0]


# --- placing --------------------------------------------------------------------------------
def place(view, at, lanes=None):
    """The text's sheet point (m) for `at`."""
    side, k, gap = at
    if side == "model":
        x, y = to_sheet(view, k)
        return x * MM, y * MM
    if gap is None and side != "in":
        key = (view.Name, side)
        n = lanes.get(key, 0) if lanes is not None else 0
        if lanes is not None:
            lanes[key] = n + 1
        gap = 8 + 9 * n
    a, b, c, d = list(get(view, "GetOutline"))
    if side == "in":
        return a + k * (c - a), b + gap * (d - b)
    g = (gap or 0) * MM
    return {"left": (a - g, b + k * (d - b)), "right": (c + g, b + k * (d - b)),
            "top": (a + k * (c - a), d + g), "bottom": (a + k * (c - a), b - g)}[side]


def _select(drw, view, picks, cache):
    """Select the picks; with a placed point among them the view stays active, so the
    dimension is measured at the view's own scale. Returns whether it is."""
    points = []
    in_view = any(p[0] == "sharp" for p in picks)
    if in_view:
        drw.ActivateView(view.Name)
        sm = drw.SketchManager
        for p in picks:
            if p[0] == "sharp":
                u, w = to_sketch(view, p[1])
                sm.AddToDB = True               # no snapping onto the edges round it
                pt = sm.CreatePoint(u, w, 0)
                sm.AddToDB = False
                if pt is None:
                    raise SwError(f"{view.Name}: no sketch point at {p}")
                points.append(pt)
    drw.ClearSelection2(True)
    for i, p in enumerate(picks):
        if p[0] == "spot":
            ok = view.SelectEntity(edge_through(view, p[1], cache=cache), i > 0)
        elif p[0] == "sharp":
            ok = points.pop(0).Select4(i > 0, NOTHING)
        else:
            ok = view.SelectEntity(find(view, p, cache), i > 0)
        if not ok:
            raise SwError(f"{view.Name}: {p} not selected")
    return in_view


_sheet = activate_sheet


def _tolerance(dim, tol):
    if tol is None:
        return
    t = dim.Tolerance
    if tol[0] == "fit":
        t.Type = C["swTolFIT"]
        hole, shaft = (tol[1], "") if tol[1][0].isupper() else ("", tol[1])
        if not t.SetFitValues(hole, shaft):
            raise SwError(f"fit {tol[1]} not set")
    elif tol[0] == "pm":
        t.Type = C["swTolSYMMETRIC"]
        if not t.SetValues(-tol[1] * MM, tol[1] * MM):
            raise SwError(f"± {tol[1]} not set")
    else:
        t.Type = C["swTolBILAT"]
        if not t.SetValues(tol[2] * MM, tol[1] * MM):
            raise SwError(f"{tol} not set")


def _black(ann):
    try:
        ann.Color = BLACK
    except Exception:
        pass


def annotate(app, drw, views, specs, broken_leaders=True, black=True):
    """Every spec placed on its view, `views` {name: view}; returns the annotations in order,
    for a later spec to cite by index. `broken_leaders` sets the drawing's diameter, radius
    and hole callouts to a bent leader with level text. `black` colours each annotation."""
    with no_value_prompt(app):
        return _annotate(drw, views, specs, broken_leaders, black)


def _annotate(drw, views, specs, broken_leaders, black):
    cache, made, lanes = {}, [], {}
    ext = drw.Extension
    if broken_leaders:
        for kind in ("swDetailingDiameterDimension", "swDetailingRadiusDimension", "swDetailingHoleDimension"):
            ext.SetUserPreferenceInteger(C["swDetailingDimensionTextAndLeaderStyle"], C[kind],
                                         C["swBrokenLeaderHorizontalText"])
    for s in specs:
        kind = s["kind"]
        if kind == "frame":
            made.append(_frame(drw, views, s, made, cache, black))
            continue
        v = views[s["view"]]
        in_view = False
        if isinstance(s["picks"][0], int):          # on an earlier annotation
            drw.ClearSelection2(True)
            if not made[s["picks"][0]][0].Select2(False, 0):
                raise SwError(f"annotation {s['picks'][0]} not selected")
        else:
            in_view = _select(drw, v, s["picks"], cache)
        x, y = place(v, s["at"], lanes)
        if kind in ("dia", "rad", "dist"):
            fn = {"dia": "AddDiameterDimension2", "rad": "AddRadialDimension2", "dist": "AddDimension2"}[kind]
            fn = {"h": "AddHorizontalDimension2", "v": "AddVerticalDimension2"}.get(s.get("orient"), fn)
            dd = getattr(drw, fn)(x, y, 0)
            if dd is None:
                raise SwError(f"{v.Name}: {kind} {s['picks']} not made")
            _tolerance(dd.GetDimension2(0), s.get("tol"))
            prec = s.get("prec")
            if prec is None and s.get("tol") and s["tol"][0] == "fit":
                prec = 0                                # Ø20 H7, not Ø20.00 H7
            if prec is not None:
                try:
                    dd.SetPrecision3(prec, -1, -1, -1)
                except Exception:
                    pass
            for which, text in ((C["swDimensionTextPrefix"], s["pre"]), (C["swDimensionTextSuffix"], s["post"]),
                                (C["swDimensionTextCalloutBelow"], s["below"])):
                if text:
                    dd.SetText(which, text)
            ann = get(dd, "GetAnnotation")
            if in_view:
                _sheet(drw)
        elif kind == "datum":
            dt = get(drw, "InsertDatumTag2")
            if dt is None:
                raise SwError(f"{v.Name}: datum {s['label']} not made")
            dt.SetLabel(s["label"])
            ann = get(dt, "GetAnnotation")
        else:
            note = drw.InsertNote(s["text"])
            if note is None:
                raise SwError(f"{v.Name}: callout not made")
            ann = get(note, "GetAnnotation")
        if kind in ("datum", "callout") and in_view:
            _sheet(drw)
        ann.SetPosition2(x, y, 0)
        if kind == "datum":
            ann.SetPosition(x, y, 0)
        if black:
            _black(ann)
        made.append((ann, s["view"]))
        drw.ClearSelection2(True)
    return [a for a, _ in made]


def _frame(drw, views, s, made, cache, black):
    """A feature control frame on an earlier annotation (an index) or on an edge (view, pick),
    placed by its `at` off that view."""
    drw.ClearSelection2(True)
    on = s["on"]
    if isinstance(on, int):
        target, vname = made[on]
        if not target.Select2(False, 0):
            raise SwError(f"frame: annotation {on} not selected")
    else:
        vname = on[0]
        _select(drw, views[vname], [on[1]], cache)
    g = get(drw, "InsertGtol")
    if g is None:
        raise SwError("frame not made")
    d = list(s["datums"]) + ["", "", ""]
    g.SetFrameValues2(1, s["value"], "", d[0], d[1], d[2])
    sym = SYMBOLS[s["sym"]]
    g.SetFrameSymbols2(1, sym, s["dia"], "", False, "", "", "", "")
    if g.GetFrameSymbols3(1)[0] != sym:
        raise SwError(f"frame symbol {sym} not set")
    ann = get(g, "GetAnnotation")
    if s.get("at"):
        ann.SetPosition2(*place(views[vname], s["at"]), 0)
    if black:
        _black(ann)
    drw.ClearSelection2(True)
    return ann, vname


def survey(views):
    """Print what each view shows, for writing its picks: its circles (r; x, y, z) and its
    lines along each axis by their other two coordinates with the longest length (mm)."""
    for name, view in views.items():
        es = edges(view)
        circ = sorted({(round(r, 3), *(round(v, 2) for v in c)) for k, _, (c, r) in es if k == "circle"})
        print(f"  {name}: circles (r; x, y, z) {circ}")
        for ax, i in _AX.items():
            seen = {}
            for k, _, d in es:
                if k != "line":
                    continue
                a, b = d
                if any(abs(a[j] - b[j]) > 1e-4 for j in range(3) if j != i):
                    continue
                key = tuple(round(a[j], 2) for j in range(3) if j != i)
                seen[key] = max(seen.get(key, 0), round(abs(b[i] - a[i]), 1))
            if seen:
                print(f"    along {ax}: " + ", ".join(f"{k}:{v}" for k, v in sorted(seen.items())))
