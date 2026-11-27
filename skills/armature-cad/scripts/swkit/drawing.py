"""
A part's drawing by script: from the project's drawing template, the
front, its projections and an isometric at the largest standard scale that
fits, the critical features dimensioned on the views (`annotate`), a few
terse numbered notes for what geometry can't say, and its PDF and DXF.

Let the STEP govern every dimension not shown, and keep a drawing to its
critical features: fits, datums, positions, and what a shop must hold.
Rationale belongs in the part definition, not on the sheet: a note is
imperative and short ("BREAK SHARP EDGES 0.2 MAX."), three to five lines.

    from swkit import annotate as A
    from swkit.drawing import draw_part

    draw_part(app, r"C:\\work\\bracket.SLDPRT", r"C:\\work\\bracket_A",
              template=r"C:\\work\\templates\\A3.DRWDOT",
              dims=[A.dia("*Front", A.circle(4.0, z=0), ("right", 0.8, None), A.fit("H7"))],
              notes=["MATERIAL: AL 6061-T6.", "DIMENSIONS NOT SHOWN PER bracket_A.STEP.",
                     "BREAK SHARP EDGES 0.2 MAX."])

Sheet positions are mm. What the calls needed (SOLIDWORKS 2026):
- A template saved while editing its sheet format hides every view placed
  on it: `Drawing` calls `EditSheet` before the views go in.
- A view's position is its model origin's point, not its outline's centre:
  `place` moves a view by its outline. Its `Position` takes an array of
  doubles; a Python tuple lands as (0, its first value).
- A detail view's `GetOutline` is taller than what it shows: place a
  detail by a model point (`section.to_sheet`), not by its outline.
- Export PDF and DXF before the native save, and remove an earlier DXF.
"""
from __future__ import annotations

import os

from .annotate import annotate
from .com import MM, NOTHING, SwError, close, default_template, doubles, get, new_doc, open_doc, save_as
from .exchange import export_copy
from .layout import SERIES, Rooms, arrangement, first_scale, iso_scale, numbered
from .measure import reach, solid_bodies


def part_box(app, part):
    """The part's exact (x, y, z) spans (mm), all its solid bodies together: the front view
    shows X by Y, the top X by Z, the right Z by Y."""
    doc = open_doc(app, part)
    try:
        r = reach(solid_bodies(doc))
        return r[3] - r[0], r[4] - r[1], r[5] - r[2]
    finally:
        close(app, doc)


def outline(view):
    """A view's outline on the sheet (mm): x0, y0, x1, y1."""
    return tuple(v / MM for v in list(get(view, "GetOutline"))[:4])


def place(view, cx, cy):
    """Move a view so its outline's centre lands at sheet point (cx, cy) mm."""
    a, b, c, d = outline(view)
    px, py = list(get(view, "Position"))[:2]
    view.Position = doubles((px + (cx - (a + c) / 2) * MM, py + (cy - (b + d) / 2) * MM))


class Drawing:
    """A new drawing from `template` (the seat's default if None), its sheet in edit."""

    def __init__(self, app, template=None):
        self.app = app
        self.doc = new_doc(app, template or default_template(app, "drawing"))
        self.doc.EditSheet()
        self.sheet = get(self.doc, "GetCurrentSheet")
        p = list(get(self.sheet, "GetProperties2"))
        self._paper, self._templ = int(p[0]), int(p[1])
        self.first_angle = bool(p[4])
        self.size = (p[5] / MM, p[6] / MM)
        self.views = {}

    def scale(self, num, den):
        """The sheet's scale; the paper, format and projection kept."""
        self.sheet.SetProperties2(self._paper, self._templ, num, den, self.first_angle,
                                  self.size[0] * MM, self.size[1] * MM, True)

    def model_view(self, part, name, at=(100.0, 100.0)):
        """A named model view of `part` ("*Front", "*Back", "*Isometric", ...) at `at` mm."""
        v = self.doc.CreateDrawViewFromModelView3(os.path.abspath(part), name, at[0] * MM, at[1] * MM, 0)
        if v is None:
            raise SwError(f"view {name} of {part} not made")
        self.views[name] = v
        return v

    def projected(self, base, name, at):
        """A view projected from view `base`, the way its direction from `base` says: "*Top"
        placed above a third-angle front, below a first-angle one; "*Right" likewise."""
        self.doc.ClearSelection2(True)
        self.doc.Extension.SelectByID2(self.views[base].Name, "DRAWINGVIEW", 0, 0, 0, False, 0, NOTHING, 0)
        v = self.doc.CreateUnfoldedViewAt3(at[0] * MM, at[1] * MM, 0, False)
        if v is None:
            raise SwError(f"view {name} not projected from {base}")
        self.views[name] = v
        return v

    def standard_views(self, part, show=("*Top", "*Right"), main=None, iso=True):
        """The front (or `main`, a named view of the part's to draw as the front) and the
        projections in `show` and an isometric. With `main` the others are projected from it."""
        w, h = self.size
        if main:
            self.model_view(part, main, (0.3 * w, 0.6 * h))
            self.views["*Front"] = self.views.pop(main)
            for name in show:
                above = (name == "*Top") != self.first_angle
                right = (name == "*Right") != self.first_angle
                at = (0.3 * w, 0.85 * h if above else 0.35 * h) if name == "*Top" else \
                     (0.55 * w if right else 0.1 * w, 0.6 * h)
                self.projected("*Front", name, at)
        else:
            for i, name in enumerate(("*Front",) + tuple(show)):
                self.model_view(part, name, (0.25 * w + 0.2 * w * i, 0.65 * h))
        if iso:
            self.model_view(part, "*Isometric", (0.85 * w, 0.7 * h))
        return self.views

    def fit(self, box, rooms, show=("*Top", "*Right"), start=None):
        """Scale the sheet down the series from the first guess until the orthographic views
        fit their room by their real outlines, arranged for the sheet's projection; the
        isometric at its own scale in its own room. Returns the scale (num, den)."""
        iso = iso_scale(box, rooms.iso[2])
        i0 = first_scale(box, rooms.views, rooms.gap, show) if start is None else start
        for i in range(i0, len(SERIES)):
            num, den = SERIES[i]
            self.scale(num, den)
            for name, v in self.views.items():
                v.UseSheetScale = name != "*Isometric"
                if name == "*Isometric":
                    v.ScaleDecimal = iso
            self.doc.ForceRebuild3(False)
            ortho = {n: outline(v) for n, v in self.views.items() if n in ("*Front", "*Top", "*Right")}
            at, fits = arrangement(ortho, rooms.views, rooms.gap, self.first_angle)
            for name, (cx, cy) in at.items():
                place(self.views[name], cx, cy)
            if "*Isometric" in self.views:
                place(self.views["*Isometric"], *rooms.iso[:2])
            if fits:
                return num, den
        raise SwError(f"the views don't fit their room {rooms.views} even at {SERIES[-1]}")

    def notes(self, lines, at, pitch=4.2):
        """Notes numbered (a line opening with a space continues the last), from sheet point
        `at` (mm) down, `pitch` mm a line."""
        for i, text in enumerate(numbered(lines)):
            n = self.doc.InsertNote(text)
            if n is None:
                raise SwError(f"note {i + 1} not made")
            get(n, "GetAnnotation").SetPosition2(at[0] * MM, (at[1] - i * pitch) * MM, 0)
        self.doc.ForceRebuild3(False)

    def export(self, stem, exts=(".pdf", ".dxf")):
        """Copies at `stem` + each extension, before any native save."""
        return [export_copy(self.doc, stem + ext) for ext in exts]

    def save(self, path):
        save_as(self.doc, path)

    def close(self, part=None):
        """Close the drawing, and the part it loaded if given."""
        self.app.CloseDoc(self.doc.GetTitle)
        if part:
            want = os.path.normcase(os.path.abspath(part))
            for d in list(self.app.GetDocuments or []):
                if os.path.normcase(d.GetPathName or "") == want:
                    self.app.CloseDoc(d.GetTitle)


def draw_part(app, part, stem, template=None, show=("*Top", "*Right"), main=None, dims=(), notes=(),
              rooms=None, exports=(".pdf", ".dxf"), native=True):
    """A part's drawing end to end: views fitted, `dims` annotated, `notes` placed, exported to
    `stem` + each of `exports`, and saved as `stem`.SLDDRW when `native`. Returns
    (paths written, the scale)."""
    d = Drawing(app, template)
    try:
        box = part_box(app, part)
        d.standard_views(part, show=show, main=main)
        rooms = rooms or Rooms.for_sheet(*d.size, dims=bool(dims))
        scale = d.fit(box, rooms, show)
        if dims:
            annotate(app, d.doc, d.views, dims)
        if notes:
            d.notes(notes, rooms.notes[:2], rooms.notes[2])
        out = d.export(stem, exports)
        if native:
            d.save(stem + ".SLDDRW")
            out.append(stem + ".SLDDRW")
        return out, scale
    finally:
        d.close(part)
