"""
A drawing view's own coordinates, and the views that cut a part open: a
section through a line drawn in a view, a detail of a rectangle on a view
at a larger scale, and numbered flags on the cut's edges, each keyed to a
note of that number. For a turned part, where outside views can't show the
walls that carry its load.

A view maps the part's frame to the sheet by `ModelToViewTransform`
(rotation, translation, scale). A view's sketch takes coordinates in the
model's units, projected into the view and centred on the view's position
point. A section's cut edges come back from `GetVisibleEntities2` as edges
in the part's frame, so they are picked by geometry like any other edge.
Model points here are mm in the part's frame; sheet points are mm.
"""
from __future__ import annotations

from .com import C, EMPTY, MM, NOTHING, SwError, get


def xform(view):
    """A view's map from the part's frame (m) to the sheet (m): rotation, translation, scale."""
    a = list(get(get(view, "ModelToViewTransform"), "ArrayData"))
    return a[:9], a[9:12], a[12]


def to_sheet(view, p_mm):
    """Model point p (mm, the part's frame) to the sheet (mm)."""
    R, T, k = xform(view)
    p = [c * MM for c in p_mm]
    return tuple((T[j] + k * sum(p[i] * R[3 * i + j] for i in range(3))) / MM for j in range(2))


def to_sketch(view, p_mm):
    """Model point p (mm) in the view's own sketch (m, model units, centred on its position)."""
    x, y = (c * MM for c in to_sheet(view, p_mm))
    px, py = list(get(view, "Position"))[:2]
    k = view.ScaleDecimal
    return (x - px) / k, (y - py) / k


def edges(view):
    """(kind, edge, data) for each edge the view shows, a section's or detail's cut edges
    among them: a circle's centre and radius, a line's two ends (mm, the part's frame)."""
    out = []
    for e in (view.GetVisibleEntities2(NOTHING, C["swViewEntityType_Edge"]) or []):
        cv = get(e, "GetCurve")
        if get(cv, "IsCircle"):
            p = list(get(cv, "CircleParams"))
            out.append(("circle", e, ([v / MM for v in p[:3]], p[6] / MM)))
        elif get(cv, "IsLine"):
            cp = list(get(e, "GetCurveParams2"))
            out.append(("line", e, ([v / MM for v in cp[0:3]], [v / MM for v in cp[3:6]])))
    return out


def edge_through(view, p, tol=0.01, cache=None):
    """The edge the view shows that passes through model point p (mm): a line segment or a
    circle within `tol`. Selecting by a sheet point (`SelectByID2("", "EDGE", x, y)`) picks
    the view itself, not the edge under the point, so a cut edge is found by its geometry."""
    es = cache.setdefault(view.Name, edges(view)) if cache is not None else edges(view)
    best = None
    for kind, e, d in es:
        if kind == "line":
            a, b = d
            ab = [b[i] - a[i] for i in range(3)]
            L2 = sum(v * v for v in ab)
            s = 0.0 if L2 == 0 else max(0.0, min(1.0, sum((p[i] - a[i]) * ab[i] for i in range(3)) / L2))
            off = sum((p[i] - a[i] - s * ab[i]) ** 2 for i in range(3)) ** 0.5
        else:
            c, r = d
            off = abs(sum((p[i] - c[i]) ** 2 for i in range(3)) ** 0.5 - r)
        if off <= tol and (best is None or off < best[0]):
            best = (off, e)
    if best is None:
        raise SwError(f"{view.Name}: no edge through {tuple(p)} mm")
    return best[1]


def activate_sheet(drw):
    """The sheet active again after work in a view's sketch: a selection by sheet point, a
    note's or a datum's placing, reads the sheet."""
    drw.ActivateSheet(get(get(drw, "GetCurrentSheet"), "GetName"))


def section_view(drw, view, a, b, at, label="A"):
    """Section `label` through the line from model point a to b (mm) drawn in `view`, placed
    at sheet point `at` (mm). Draw the line past the part's outline at both ends."""
    drw.ActivateView(view.Name)
    (ua, wa), (ub, wb) = to_sketch(view, a), to_sketch(view, b)
    line = drw.SketchManager.CreateLine(ua, wa, 0, ub, wb, 0)
    if line is None or not line.Select4(False, NOTHING):
        raise SwError(f"section {label}: its line not drawn in {view.Name}")
    sec = drw.CreateSectionViewAt5(at[0] * MM, at[1] * MM, 0, label, 0, EMPTY, 0.0)
    if sec is None:
        raise SwError(f"section {label}-{label} not made")
    drw.ForceRebuild3(False)
    activate_sheet(drw)
    return sec


def detail_view(drw, view, a, b, at, scale, label="B"):
    """Detail `label` of the rectangle with model corners a and b (mm) on `view`, at `scale`
    (num, den), placed at sheet point `at` (mm), its boundary the rectangle itself."""
    drw.ActivateView(view.Name)
    ua, ub = to_sketch(view, a), to_sketch(view, b)
    segs = drw.SketchManager.CreateCornerRectangle(ua[0], ua[1], 0, ub[0], ub[1], 0)
    if not segs:
        raise SwError(f"detail {label}: its rectangle not drawn")
    drw.ClearSelection2(True)
    for i, seg in enumerate(segs):
        seg.Select4(i > 0, NOTHING)
    num, den = scale
    det = drw.CreateDetailViewAt4(at[0] * MM, at[1] * MM, 0, C["swDetViewSTANDARD"], num, den, label,
                                  C["swDetCirclePROFILE"], True, False, False, 5)
    if det is None:
        raise SwError(f"detail {label} not made")
    drw.ForceRebuild3(False)
    activate_sheet(drw)
    return det


def flags(drw, view, items):
    """Each flag a note of its number, its leader on the edge through its model point: items
    are (number, model point mm, (dx, dy) mm from that point to the flag on the sheet)."""
    cache = {}
    for n, p, (dx, dy) in items:
        x0, y0 = to_sheet(view, p)
        drw.ClearSelection2(True)
        if not view.SelectEntity(edge_through(view, p, cache=cache), False):
            raise SwError(f"flag {n}: the edge at {p} mm not selected")
        note = drw.InsertNote(str(n))
        ann = get(note, "GetAnnotation")
        if not get(ann, "GetLeaderCount"):
            raise SwError(f"flag {n}: no leader")
        ann.SetPosition2((x0 + dx) * MM, (y0 + dy) * MM, 0)
    drw.ClearSelection2(True)
