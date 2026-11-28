"""
A part built by script with its design intent, so the model a person opens
afterwards is one they would have built by hand: few planes, each named for
what it is; one sketch per feature, fully defined by relations where the
intent is a relation (a centre on the origin, a rectangle symmetric about
its centreline, equal fillets) and by a dimension only where a number is a
design input; every such dimension an equation of the part's globals.

    from swkit.com import attach
    from swkit.expr import ZERO
    from swkit.part import Part

    app = attach()
    p = Part(app, r"C:\\work\\bracket.SLDPRT", props={"PartNo": "BRK-001"},
             globals_=[("w", 40, "mm", "width"), ("t", 6, "mm", "plate"), ("d", 8, "mm", "bore")])
    s = p.sketch("Front Plane", "plate_sk")
    s.rect(-p["w"] / 2, p["w"] / 2, p["w"] / 4, ZERO, rounded=3)
    s.close()
    p.extrude("plate_sk", "plate", p["t"], toward=+1)
    ...
    p.finish()
    p.close()

The part's frame is its own origin planes: Front is XY (normal +Z), Top
is XZ (+Y), Right is YZ (+X). Every length a caller passes is an `X` or a
number in mm; every angle degrees. The part is MMGS whatever its template.

Two traps the builder guards, each of which once shipped a wrong part:
- **A feature's side.** SOLIDWORKS's sense of "direction 1" and of a start
  offset depends on the plane and the feature kind, so `extrude` tries
  each sense and keeps the one whose faces lie on the side asked for.
- **A boss with no faces.** A boss that went the wrong way wholly into
  material already there merges and owns no faces, so its side can't be
  read; it is taken only if every sense merges so, and said so. Audit any
  part afterwards with `measure.faceless_bosses`.
"""
from __future__ import annotations

import math

from .com import (C, MM, NOTHING, SwError, default_template, new_doc, no_value_prompt,
                  objects, save, save_as, set_equation, equation_index, set_props)
from .expr import X

# the standard planes' names, as an English-language seat writes them, and each normal's axis
STANDARD = {"Front Plane": 2, "Top Plane": 1, "Right Plane": 0}
FULLY_DEFINED = 3   # swConstrainedStatus_FullyConstrained


class Part:
    """A new part from `template` (the seat's default if None), saved at `path` at once: its
    custom properties, its typed globals (name, value, unit, comment), unlinked, and the
    features built on it."""

    def __init__(self, app, path, template=None, props=None, globals_=()):
        self.app = app
        self._prompt = no_value_prompt(app)
        self._prompt.__enter__()
        try:
            self.doc = new_doc(app, template or default_template(app, "part"))
            self.ext, self.sm, self.fm = self.doc.Extension, self.doc.SketchManager, self.doc.FeatureManager
            self.em = self.doc.GetEquationMgr
            self.ext.SetUserPreferenceInteger(C["swUnitSystem"], 0, C["swUnitSystem_MMGS"])
            if self.ext.GetUserPreferenceInteger(C["swUnitSystem"], 0) != C["swUnitSystem_MMGS"]:
                raise SwError("the part would not take MMGS units")
            save_as(self.doc, path)
            if props:
                set_props(self.doc, props)
            self.em.AngularEquationUnits = C["swAngularEquationUnitsDegrees"]
            self.g = {}
            for name, value, unit, comment in globals_:
                self.add_equation(f'"{name}" = {value:.9g}{unit}' + (f" '{comment}" if comment else ""))
                self.g[name] = X(value, f'"{name}"')
            self.planes = {p: (axis, 0.0) for p, axis in STANDARD.items()}
            self._on = {}            # sketch name -> (its plane's normal axis, its offset, mm)
            self._named = set()      # bodies named so far
            save(self.doc)
        except BaseException:
            self._prompt.__exit__(None, None, None)
            raise

    def __getitem__(self, name):
        return self.g[name]

    # --- selection
    def clear(self):
        self.doc.ClearSelection2(True)

    def select(self, name, kind, append=False, mark=0):
        if not self.ext.SelectByID2(name, kind, 0, 0, 0, append, mark, NOTHING, 0):
            raise SwError(f"could not select {kind} {name!r}")

    def pick(self, entity, append=True, mark=0):
        data = self.doc.SelectionManager.CreateSelectData
        data.Mark = mark
        if not entity.Select4(append, data):
            raise SwError(f"could not select {entity!r}")

    def origin(self, append=True):
        self.select("Point1@Origin", "EXTSKETCHPOINT", append)

    # --- equations
    def add_equation(self, text):
        n0 = self.em.GetCount
        idx = self.em.Add2(-1, text, True)
        if self.em.GetCount != n0 + 1:
            raise SwError(f"equation not added ({idx}, status {self.em.Status}): {text}")
        return idx

    def equate(self, full, x):
        """Dimension `full` ("D1@boss") driven by expression `x`."""
        self.add_equation(f'"{full}" = {X.of(x).text}')

    # --- reference geometry
    def plane(self, name, ref, at):
        """Plane `name`, parallel to `ref` (a standard plane or one made here) at signed offset
        `at` (mm, along ref's normal), made once and checked where it landed."""
        at = X.of(at)
        axis, base = self.planes[ref]
        want = base + at.value
        if name in self.planes:
            if abs(self.planes[name][1] - want) > 1e-9:
                raise SwError(f"plane {name} exists at {self.planes[name][1]}, not {want}")
            return name
        self.clear()
        self.select(ref, "PLANE")
        flip = C["swRefPlaneReferenceConstraint_OptionFlip"] if at.value < 0 else 0
        f = self.fm.InsertRefPlane(C["swRefPlaneReferenceConstraint_Distance"] | flip,
                                   abs(at.value) * MM, 0, 0, 0, 0)
        if f is None:
            raise SwError(f"plane {name} not made")
        f.Name = name
        self.equate(f"D1@{name}", abs(at))
        self.clear()
        got = list(f.GetSpecificFeature2.Transform.ArrayData)[9 + axis] / MM
        if abs(got - want) > 1e-6:
            raise SwError(f"plane {name} landed at {got:.6f} along axis {axis}, not {want:.6f}")
        self.planes[name] = (axis, want)
        return name

    def axis(self, name, plane_a, plane_b):
        """A reference axis where two planes meet, named for what it is."""
        self.clear()
        self.select(plane_a, "PLANE")
        self.select(plane_b, "PLANE", append=True)
        if not self.doc.InsertAxis2(True):
            raise SwError(f"axis {name} not made")
        self.doc.FeatureByPositionReverse(0).Name = name
        self.clear()
        return name

    # --- sketches
    def open_sketch(self, plane, name):
        """A new sketch on `plane`, renamed `name` at once so its dimensions' equations can
        cite it while it is drawn."""
        self.clear()
        self.select(plane, "PLANE")
        self.sm.InsertSketch(True)
        f = self.doc.FeatureByPositionReverse(0)
        if f.GetTypeName2 != "ProfileFeature":
            raise SwError(f"the newest feature is a {f.GetTypeName2}, not the new sketch")
        f.Name = name
        if f.Name != name:
            raise SwError(f"sketch not renamed to {name}: {f.Name}")
        return self.doc.GetActiveSketch2

    def close_sketch(self):
        self.sm.InsertSketch(True)       # toggles the sketch shut
        self.clear()

    def sketch(self, plane, name):
        """A Sketch on a standard or named plane, its plane remembered for `extrude`."""
        if plane not in self.planes:
            raise SwError(f"no plane {plane!r}: make it with Part.plane first")
        self._on[name] = self.planes[plane]
        return Sketch(self, plane, name)

    # --- features
    def extrude(self, sketch, name, depth, toward=1, depth2=None, offset=None,
                cut=False, merge=True, through=False, axis=None):
        """Extrude `sketch` blind by `depth` along its plane's normal toward `toward` (+1, -1);
        a second direction `depth2`; a start `offset` off the sketch's plane, the way it goes;
        a cut through all with `through`; `merge=False` starts a new body."""
        ax, at = self._on[sketch]
        axis = ax if axis is None else axis
        depth = X.of(depth)
        two = depth2 is not None
        t1 = C["swEndCondThroughAll"] if through else C["swEndCondBlind"]
        t2 = C["swEndCondBlind"] if two else 0
        d2 = X.of(depth2).value * MM if two else 0
        t0 = C["swStartOffset"] if offset is not None else C["swStartSketchPlane"]
        off = X.of(offset).value * MM if offset is not None else 0

        def make(flip, flip_off):
            self.clear()
            self.select(sketch, "SKETCH")
            if cut:
                return self.fm.FeatureCut4(not two, False, flip, t1, t2, depth.value * MM, d2, False, False,
                                           False, False, 0, 0, False, False, False, False, False, True, True,
                                           False, False, False, t0, off, flip_off, False)
            return self.fm.FeatureExtrusion3(not two, False, flip, t1, t2, depth.value * MM, d2, False, False,
                                             False, False, 0, 0, False, False, False, False, merge, False, True,
                                             t0, off, flip_off)

        lead = X.of(offset).value if offset is not None else 0.0
        if two and cut and abs(depth.value - X.of(depth2).value) > 1e-9:
            # a cut's faces lie only where it met material, so its sense can't be read back
            raise ValueError(f"{name}: a two-way cut must be symmetric; cut one way from a plane")
        tries, f, unread = [], None, None
        senses = ((False, False), (True, False)) if two else ((False, False), (True, True), (True, False), (False, True))
        for flips in senses:
            f = make(*flips)
            if f is None:
                tries.append((flips, "nothing"))
                continue
            # a merged feature's faces may span its whole body, so only a new body is read
            if two and (cut or merge or self._spans(f, axis, toward, at, depth.value, X.of(depth2).value)):
                break
            if not two and not cut and not list(f.GetFaces or []):
                tries.append((flips, "merged, no faces"))
                unread = unread or flips
            elif not two and (self._goes(f, axis, toward, at, lead)
                              or (offset is None and not through and self._reaches(f, axis, toward, at, depth.value))):
                break
            else:
                tries.append((flips, self._span(f, axis)))
            self.clear()
            self.doc.EditUndo2(1)            # the sketch stays, as a deletion's wouldn't
            f = None
        if f is None and unread is not None:
            print(f"    {name}: merged with no faces every way, taken as {unread}: {tries}", flush=True)
            f = make(*unread)                # inside material whichever way it goes
        if f is None:
            raise SwError(f"{name} won't go {toward:+d} along axis {axis} from its plane at {at}: {tries}")
        f.Name = name
        # each of the feature's own dimensions takes its equation by its value: SOLIDWORKS
        # names a start offset's dimension by its own count, not D3
        wanted = [x for x in ((None if through else depth), (X.of(depth2) if two else None),
                              (X.of(offset) if offset is not None else None)) if x is not None]
        self._equate_by_value(f, name, wanted)
        self.clear()
        return f

    def _equate_by_value(self, f, name, wanted):
        dims = []
        disp = f.GetFirstDisplayDimension
        while disp is not None:
            dm = disp.GetDimension2(0)
            dims.append((dm.Name, dm.GetSystemValue3(1, None)[0] / MM))
            disp = f.GetNextDisplayDimension(disp)
        for x in wanted:
            hit = min(dims, key=lambda nd: abs(nd[1] - x.value), default=None)
            if hit is None or abs(hit[1] - x.value) > 1e-6:
                raise SwError(f"{name}: no dimension of {x.value} among {dims}")
            dims.remove(hit)
            self.equate(f"{hit[0]}@{name}", x)

    @staticmethod
    def _span(f, axis):
        """The extent of feature f's faces along `axis` (mm)."""
        boxes = [fc.GetBox for fc in (f.GetFaces or [])]
        return (min(b[axis] for b in boxes) / MM, max(b[axis + 3] for b in boxes) / MM)

    def _spans(self, f, axis, toward, at, d1, d2):
        """Does two-way feature f run d1 on the `toward` side of its plane and d2 on the other?"""
        lo, hi = self._span(f, axis)
        want = (at - d2, at + d1) if toward > 0 else (at - d1, at + d2)
        return abs(lo - want[0]) < 0.01 and abs(hi - want[1]) < 0.01

    def _reaches(self, f, axis, toward, at, depth):
        """Does f end exactly `depth` off its plane on the `toward` side? A cut opening into a
        cavity, or a boss whose face runs on into a coaxial face, spans past its plane."""
        lo, hi = self._span(f, axis)
        far = hi if toward > 0 else lo
        return abs(far - (at + toward * depth)) < 0.01

    def _goes(self, f, axis, toward, at, lead=0.0):
        """Does f lie on the `toward` side of its plane, its near end `lead` or more off it?"""
        lo, hi = self._span(f, axis)
        near = lo - at if toward > 0 else at - hi
        return near >= lead - 0.01

    def revolve(self, sketch, name, cut=False, merge=False):
        """`sketch` revolved whole about its one centreline."""
        self.clear()
        self.select(sketch, "SKETCH")
        f = self.fm.FeatureRevolve2(True, True, False, cut, False, False, C["swEndCondBlind"], 0,
                                    2 * math.pi, 0, False, False, 0, 0, 0, 0, 0, merge, False, True)
        if f is None:
            raise SwError(f"revolve {name} from {sketch} not made")
        f.Name = name
        self.clear()
        return f

    def pattern(self, features, axis, count, name):
        """`features` repeated `count` times, equally round reference axis `axis`."""
        self.clear()
        self.select(axis, "AXIS", append=False, mark=1)
        for feat in features:
            self.select(feat, "BODYFEATURE", append=True, mark=4)
        f = self.fm.FeatureCircularPattern5(count, 2 * math.pi, False, "NULL", False, True, False, False,
                                            False, False, 1, 0.0, "NULL", False)
        if f is None:
            raise SwError(f"pattern {name} of {features} not made")
        f.Name = name
        self.clear()
        return f

    def fillet(self, edges, radius, name, propagate=False):
        """A constant-radius feature fillet on `edges` (mm). Tangent propagation is off by
        default: on, a corner's fillet creeps down every concave edge tangent to it. Edges go
        stale after any feature, so find them afresh before each fillet; a group that fails
        can take its edges one at a time. Returns the feature, or None if it would not take."""
        self.clear()
        data = self.fm.CreateDefinition(C["swFmFillet"])
        data.Initialize(C["swConstRadiusFillet"])
        data.DefaultRadius = X.of(radius).value * MM
        data.PropagateToTangentFaces = propagate
        data.Edges = objects(edges)
        f = self.fm.CreateFeature(data)
        if f is not None:
            f.Name = name
        self.clear()
        return f

    # --- bodies
    def bodies(self):
        return {b.Name: b for b in (self.doc.GetBodies2(C["swSolidBody"], True) or [])}

    def name_body(self, name):
        """Name the one solid body not named yet: build each body whole, name it, then begin
        the next. SOLIDWORKS refuses a body a feature's own name."""
        fresh = [b for b in (self.doc.GetBodies2(C["swSolidBody"], True) or []) if b.Name not in self._named]
        if len(fresh) != 1:
            raise SwError(f"naming {name}: {len(fresh)} unnamed bodies, {[b.Name for b in fresh]}")
        fresh[0].Name = name
        if fresh[0].Name != name:
            raise SwError(f"naming {name}: the body kept {fresh[0].Name}")
        self._named.add(name)
        return fresh[0]

    def mirror(self, config, plane="Right Plane", suffix=" (mirror)"):
        """The part's other hand as configuration `config` (see mirror_config)."""
        return mirror_config(self, config, plane, suffix)

    # --- finishing
    def finish(self):
        """Rebuild, show it isometric and zoomed, save."""
        self.doc.ForceRebuild3(False)
        self.doc.ShowNamedView2("*Isometric", -1)
        self.doc.ViewZoomtofit2()
        save(self.doc)

    def close(self):
        """Close the part and put the seat's value-prompt preference back."""
        try:
            self.app.CloseDoc(self.doc.GetTitle)
        finally:
            self._prompt.__exit__(None, None, None)


class Sketch:
    """A sketch open on `plane`, its entities placed at their nominal values and held by
    relations and by equations of the part's globals. Its own axes are the plane's: a plane
    parallel to Front sketches in (X, Y), one parallel to Right in (-Z, Y) or as
    ModelToSketchTransform says; `at` maps a model point to them."""

    def __init__(self, part, plane, name):
        self.p, self.name = part, name
        part.open_sketch(plane, name)
        self.sm = part.sm
        self.sm.AddToDB = True              # no snapping onto what is already there
        arr = list(self.sm.ActiveSketch.ModelToSketchTransform.ArrayData)
        self.rows, self.t = [arr[0:3], arr[3:6], arr[6:9]], arr[9:12]
        self.k = 0
        self._fillets = []

    def at(self, p):
        """Model point (X, Y, Z), each an X or mm, to the sketch's (sx, sy) X's."""
        p = [X.of(c) for c in p]
        out = []
        for j in range(2):
            col = [self.rows[i][j] for i in range(3)]
            k = max(range(3), key=lambda i: abs(col[i]))
            x = p[k] if col[k] > 0 else -p[k]
            out.append(x + self.t[j] / MM if abs(self.t[j]) > 1e-12 else x)
        return out

    # --- dimensions and relations
    def _pick(self, ents):
        self.p.clear()
        for e in ents:
            if isinstance(e, str) and e == "origin":
                self.p.origin(append=True)
            else:
                self.p.pick(e, append=True)

    def dim(self, ents, x, kind="d", where=(0.0, 0.0)):
        """A dimension between `ents` ("origin" for the origin), driven by X `x`'s absolute
        value: kind "d" (aligned or angle), "h", "v", "dia" or "r"; its text near `where`."""
        self._pick(ents)
        doc = self.p.doc
        f = {"d": doc.AddDimension2, "h": doc.AddHorizontalDimension2, "v": doc.AddVerticalDimension2,
             "dia": doc.AddDiameterDimension2, "r": doc.AddRadialDimension2}[kind]
        dd = f(where[0] * MM, where[1] * MM, 0)
        if dd is None:
            raise SwError(f"{self.name}: a dimension not made")
        self.k += 1
        dm = dd.GetDimension2(0)
        dm.Name = f"dm{self.k}"
        self.p.equate(f"dm{self.k}@{self.name}", abs(X.of(x)))
        self.p.clear()
        return dm

    def dim_any(self, ents, choices, where=(0.0, 0.0)):
        """A dimension between `ents` (an angle, say) driven by whichever of the X `choices`
        matches what SOLIDWORKS measured as it placed it (deg for an angle, mm for a length)."""
        self._pick(ents)
        dd = self.p.doc.AddDimension2(where[0] * MM, where[1] * MM, 0)
        if dd is None:
            raise SwError(f"{self.name}: a dimension not made")
        self.k += 1
        dm = dd.GetDimension2(0)
        dm.Name = f"dm{self.k}"
        raw = dm.GetSystemValue3(1, None)[0]
        got = min((math.degrees(raw), raw / MM), key=lambda g: min(abs(c.value - g) for c in choices))
        x = min(choices, key=lambda c: abs(c.value - got))
        if abs(x.value - got) > 0.05:
            raise SwError(f"{self.name}: measured {got:.3f}, none of {[c.value for c in choices]}")
        self.p.equate(f"dm{self.k}@{self.name}", x)
        self.p.clear()
        return dm

    def rel(self, ents, relation):
        """A sketch relation by its name: "sgCOINCIDENT", "sgHORIZONTAL2D", "sgSYMMETRIC", ..."""
        self._pick(ents)
        self.p.doc.SketchAddConstraints(relation)
        self.p.clear()

    def place(self, pt, p):
        """Hold point `pt` at sketch (sx, sy) X's: on the origin or an axis by relation,
        else by a dimension from the origin along each."""
        sx, sy = (X.of(c) for c in p)
        if sx.zero() and sy.zero():
            return self.rel([pt, "origin"], "sgCOINCIDENT")
        for x, kind, rel in ((sx, "h", "sgVERTICALPOINTS2D"), (sy, "v", "sgHORIZONTALPOINTS2D")):
            if x.zero():
                self.rel([pt, "origin"], rel)
            else:
                self.dim(["origin", pt], x, kind, (sx.value + 3, sy.value + 3))

    # --- entities, at model points unless said
    def circle(self, c, dia, centre_held=True):
        """A circle at model point c, its diameter driven by `dia`."""
        sx, sy = self.at(c)
        dia = X.of(dia)
        ci = self.sm.CreateCircleByRadius(sx.value * MM, sy.value * MM, 0, dia.value / 2 * MM)
        if ci is None:
            raise SwError(f"{self.name}: a circle not made")
        if centre_held:
            self.place(ci.GetCenterPoint2, (sx, sy))
        self.dim([ci], dia, "dia", (sx.value + dia.value / 2, sy.value))
        return ci

    def ring(self, c, outer, inner):
        """Two circles about one held centre."""
        a = self.circle(c, outer)
        b = self.circle(c, inner, centre_held=False)
        self.rel([b.GetCenterPoint2, a.GetCenterPoint2], "sgCOINCIDENT")
        return a, b

    def rect(self, u0, u1, half, axis_at, rounded=None):
        """A rectangle in the sketch's own (u, w): from u0 to u1 along u, `half` either side
        of the line w = axis_at, held symmetric about a centreline there; its corners
        filleted to `rounded` (one radius, SOLIDWORKS's equal relations) where given. Each
        argument an X or mm in sketch coordinates. Returns its sides by name."""
        u0, u1, half, axis_at = map(X.of, (u0, u1, half, axis_at))
        lo, hi = axis_at - half, axis_at + half
        segs = self.sm.CreateCornerRectangle(u0.value * MM, lo.value * MM, 0, u1.value * MM, hi.value * MM, 0)
        if not segs or len(segs) != 4:
            raise SwError(f"{self.name}: a rectangle not made")
        side = {}
        for s in segs:
            a, z = s.GetStartPoint2, s.GetEndPoint2
            if abs(a.Y - z.Y) < 1e-9:
                side["top" if a.Y > axis_at.value * MM else "bottom"] = s
            else:
                side["right" if a.X > (u0.value + u1.value) / 2 * MM else "left"] = s
        cl = self.sm.CreateCenterLine(u0.value * MM, axis_at.value * MM, 0, u1.value * MM, axis_at.value * MM, 0)
        self.rel([cl], "sgHORIZONTAL2D")
        self.rel([cl.GetStartPoint2, side["left"]], "sgCOINCIDENT")
        self.rel([cl.GetEndPoint2, side["right"]], "sgCOINCIDENT")
        self.rel([side["top"], side["bottom"], cl], "sgSYMMETRIC")
        if axis_at.zero():
            self.rel([cl.GetStartPoint2, "origin"], "sgHORIZONTALPOINTS2D")
        else:
            self.dim(["origin", cl], axis_at, "v", (u0.value - 4, axis_at.value / 2))
        self.dim([side["top"], side["bottom"]], 2 * half, "v", (u1.value + 4, axis_at.value))
        for key, u in (("left", u0), ("right", u1)):
            if u.zero():
                self.rel([side[key], "origin"], "sgCOINCIDENT")
            else:
                self.dim(["origin", side[key]], u, "h", (u.value / 2, hi.value + 3))
        if rounded is not None:
            corners = []
            for s in segs:
                for q in (s.GetStartPoint2, s.GetEndPoint2):
                    if all(abs(q.X - c.X) + abs(q.Y - c.Y) > 1e-9 for c in corners):
                        corners.append(q)
            self._pick(corners)
            self.sm.CreateFillet(X.of(rounded).value * MM, 1)
            self.p.clear()
            self.k += 1          # the fillet's own radius dimension, equated in close()
            self._fillets.append((self.k, X.of(rounded)))
        return side

    def poly(self, points):
        """A closed polygon through model points, each vertex held by `place`: for an outline
        no relation states, where every vertex is a design input. Returns its lines."""
        pts = [self.at(p) for p in points]
        lines = []
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            ln = self.sm.CreateLine(a[0].value * MM, a[1].value * MM, 0, b[0].value * MM, b[1].value * MM, 0)
            if ln is None:
                raise SwError(f"{self.name}: a line not made")
            lines.append(ln)
        for i, ln in enumerate(lines):
            self.rel([ln.GetEndPoint2, lines[(i + 1) % len(lines)].GetStartPoint2], "sgCOINCIDENT")
        for ln, p in zip(lines, pts):
            self.place(ln.GetStartPoint2, p)
        return lines

    def line(self, a, b, construction=False):
        """A line between model points a and b."""
        (ax, ay), (bx, by) = self.at(a), self.at(b)
        ln = self.sm.CreateLine(ax.value * MM, ay.value * MM, 0, bx.value * MM, by.value * MM, 0)
        if ln is None:
            raise SwError(f"{self.name}: a line not made")
        ln.ConstructionGeometry = construction
        return ln

    def arc(self, a, b, direction=1, centre=(0, 0, 0)):
        """An arc about model point `centre` (the origin by default, held by relation) from
        model point a to b; direction +1 counter-clockwise in the sketch."""
        (ax, ay), (bx, by) = self.at(a), self.at(b)
        cx, cy = self.at(centre)
        arc = self.sm.CreateArc(cx.value * MM, cy.value * MM, 0, ax.value * MM, ay.value * MM, 0,
                                bx.value * MM, by.value * MM, 0, direction)
        if arc is None:
            raise SwError(f"{self.name}: an arc not made")
        self.place(arc.GetCenterPoint2, (cx, cy))
        return arc

    def horizontal(self, arc, at):
        """A horizontal centreline from the origin to `arc`'s circle at model point `at`: a
        reference to dimension angles from, held with no dimension of its own."""
        x, _ = self.at(at)
        h = self.sm.CreateCenterLine(0, 0, 0, x.value * MM, 0, 0)
        self.rel([h], "sgHORIZONTAL2D")
        self.rel([h.GetStartPoint2, "origin"], "sgCOINCIDENT")
        self.rel([h.GetEndPoint2, arc], "sgCOINCIDENT")
        return h

    def angle(self, ln, ref, x, where):
        """An angle dimension between line `ln` and line `ref`, driven by X `x` (deg)."""
        return self.dim([ln, ref], x, "d", where)

    def stepped_ring(self, z0, z1, r_in, r_out, r_fl, t_fl, flange_first, axis_u):
        """A flanged bushing's half-section for `Part.revolve`, in the sketch's own (radius
        along u, along the axis w): from w = z0 to z1, bored r_in, its barrel r_out, its
        flange r_fl over t_fl at z0's end (`flange_first`) or z1's; the axis a centreline at
        u = axis_u. Each an X or mm in sketch coordinates."""
        z0, z1, r_in, r_out, r_fl, t_fl, axis_u = map(X.of, (z0, z1, r_in, r_out, r_fl, t_fl, axis_u))
        zf = z0 + t_fl if flange_first else z1 - t_fl
        if flange_first:
            pts = [(r_in, z0), (r_fl, z0), (r_fl, zf), (r_out, zf), (r_out, z1), (r_in, z1)]
        else:
            pts = [(r_in, z0), (r_out, z0), (r_out, zf), (r_fl, zf), (r_fl, z1), (r_in, z1)]
        pts = [(axis_u + u, w) for u, w in pts]
        lines = []
        for i, (u, w) in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            lines.append(self.sm.CreateLine(u.value * MM, w.value * MM, 0, q[0].value * MM, q[1].value * MM, 0))
        for i, ln in enumerate(lines):
            self.rel([ln.GetEndPoint2, lines[(i + 1) % len(lines)].GetStartPoint2], "sgCOINCIDENT")
            self.rel([ln], "sgHORIZONTAL2D" if i % 2 == 0 else "sgVERTICAL2D")
        cl = self.sm.CreateCenterLine(axis_u.value * MM, z0.value * MM, 0, axis_u.value * MM, z1.value * MM, 0)
        self.rel([cl], "sgVERTICAL2D")
        if axis_u.zero():
            self.rel([cl.GetStartPoint2, "origin"], "sgVERTICALPOINTS2D")
        else:
            self.dim(["origin", cl], axis_u, "h", (axis_u.value / 2, z0.value - 3))
        for ln, r in ((lines[5], r_in), (lines[1], r_fl if flange_first else r_out),
                      (lines[3], r_out if flange_first else r_fl)):
            self.dim([cl, ln], r, "d", (axis_u.value + r.value / 2, zf.value))
        self.dim(["origin", lines[0]], z0, "v", (axis_u.value - 3, z0.value / 2))
        self.dim([lines[0], lines[2]], t_fl if flange_first else z1 - t_fl - z0, "v",
                 (axis_u.value + 1, z0.value + 1))
        self.dim([lines[0], lines[4]], z1 - z0, "v", (axis_u.value + 2, (z0.value + z1.value) / 2))
        return cl

    def close(self):
        """Close the sketch, equate each sketch fillet's own radius dimension, and require the
        sketch fully defined."""
        self.sm.AddToDB = False
        status = self.sm.ActiveSketch.GetConstrainedStatus
        self.p.close_sketch()
        feat = self.p.doc.FeatureByName(self.name)
        # a sketch fillet's radius dimension is SOLIDWORKS-named (D<n>, which a name of ours
        # mustn't echo: its names ignore case); found by its value
        auto = []
        disp = feat.GetFirstDisplayDimension
        while disp is not None:
            dm = disp.GetDimension2(0)
            if not dm.Name.startswith("dm"):
                auto.append(dm)
            disp = feat.GetNextDisplayDimension(disp)
        left = []
        for k, r in self._fillets:
            hit = min(auto, key=lambda dm: abs(dm.GetSystemValue3(1, None)[0] / MM - r.value), default=None)
            if hit is None or abs(hit.GetSystemValue3(1, None)[0] / MM - r.value) > 1e-6:
                left.append((k, r))
                continue
            auto.remove(hit)
            hit.Name = f"rf{k}"
            self.p.equate(f"rf{k}@{self.name}", r)
        if left:
            raise SwError(f"{self.name}: {len(left)} sketch fillet radius dimension(s) not found")
        if status != FULLY_DEFINED:
            raise SwError(f"sketch {self.name} is not fully defined (status {status})")
        return self.name


def _select_body(part, body, append, mark):
    data = part.doc.SelectionManager.CreateSelectData
    data.Mark = mark
    if not body.Select2(append, data):
        raise SwError(f"could not select body {body.Name}")


def mirror_config(part, config, plane="Right Plane", suffix=" (mirror)"):
    """The part's other hand as configuration `config`: every solid body mirrored across
    `plane`, each mirror named its original's name and `suffix` (matched by volume), and the
    originals deleted; both features suppressed in the default configuration, which keeps the
    hand as built. Returns the default configuration's name. A configuration's suppression
    takes only from that configuration active (a list of names passed silently does nothing),
    and the document's AddConfiguration3 hung the seat: the manager's AddConfiguration2 is used."""
    doc = part.doc
    originals = list(doc.GetBodies2(C["swSolidBody"], True) or [])
    volumes = {b.Name: b.GetMassProperties(1.0)[3] for b in originals}
    part.clear()
    part.select(plane, "PLANE", append=False, mark=2)
    for b in originals:
        _select_body(part, b, True, 256)
    f = part.fm.InsertMirrorFeature2(True, False, False, False, 0)
    if f is None:
        raise SwError(f"the mirror for {config} not made")
    f.Name = f"mirror {config}"
    names = {b.Name for b in originals}
    for b in doc.GetBodies2(C["swSolidBody"], True) or []:
        if b.Name in names:
            continue
        v = b.GetMassProperties(1.0)[3]
        match = min(volumes, key=lambda n: abs(volumes[n] - v))
        if abs(volumes[match] - v) > 1e-6 * max(v, 1e-12) + 1e-12:
            raise SwError(f"mirrored body {b.Name}: no original of its volume")
        b.Name = match + suffix
    part.clear()
    for b in originals:
        _select_body(part, b, True, 0)
    g = part.fm.InsertDeleteBody2(False)
    if g is None:
        raise SwError(f"the originals' deletion for {config} not made")
    g.Name = f"delete originals {config}"
    part.clear()
    default = doc.ConfigurationManager.ActiveConfiguration.Name
    if doc.ConfigurationManager.AddConfiguration2(config, f"the other hand, mirrored across {plane}",
                                                  "", 0, "", "", True) is None:
        raise SwError(f"configuration {config} not made")
    doc.ShowConfiguration2(default)
    for feat in (f, g):
        feat.SetSuppression2(C["swSuppressFeature"], C["swThisConfiguration"], NOTHING)
    doc.ForceRebuild3(False)
    save(doc)
    return default


def set_globals(doc, values):
    """An existing part's globals set from `values`, {name: (number, unit)}, each equation's
    comment kept, then every configuration rebuilt: how a moved ledger number reaches a model
    built with unlinked globals. Show the configuration the globals were written in first.
    Returns {name: (old text, new text)}; the caller saves."""
    import re
    em = doc.GetEquationMgr
    out = {}
    for name, (number, unit) in values.items():
        i = equation_index(em, name)
        old = em.Equation(i)
        m = re.match(r'^(\s*"[^"]+"\s*=\s*)[^\']*?(\s*\'.*)?$', old)
        new = f"{m.group(1)}{number:.9g}{unit}{m.group(2) or ''}" if m else f'"{name}" = {number:.9g}{unit}'
        set_equation(em, i, new)
        out[name] = (old, new)
    em.EvaluateAll
    doc.ForceRebuild3(False)
    return out
