"""
Reading a model back: exact extents, faces found by their geometry, each
body's mass properties at a density, the faceless-boss audit, and the
rebuild test a part definition's *Done when* asks for.

Never claim a number in a part definition without reading it off the model
this way: a build that looks right in the viewport can lack a feature.
Lengths are mm; mass properties are SI (kg, m, kg m^2), ready for a ledger.
"""
from __future__ import annotations

from .com import (C, MM, SwError, close, equation_index, errors, features, get, open_doc, scale_global,
                  set_equation)
from .inertia import from_solidworks

AXES = {"x": 0, "y": 1, "z": 2}
DIRS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def solid_bodies(doc, visible=True):
    return list(doc.GetBodies2(C["swSolidBody"], visible) or [])


def volume(body):
    """A body's volume, mm^3."""
    return body.GetMassProperties(1.0)[3] / MM ** 3


def extreme(body, d):
    """How far a body reaches along unit direction d (mm), exactly. `GetBodyBox` and a face's
    `GetBox` are loose boxes, good to about a millimetre; this is the modeller's own point."""
    out = body.GetExtremePoint(d[0], d[1], d[2], 0.0, 0.0, 0.0)
    if not (isinstance(out, tuple) and len(out) == 4 and out[0]):
        raise SwError(f"no extreme point of {body.Name} along {d}: {out!r}")
    return sum(v * c for v, c in zip(out[1:], d)) / MM


def reach(bodies):
    """The exact box the bodies reach: (xmin, ymin, zmin, xmax, ymax, zmax), mm."""
    r = [max(extreme(b, d) for b in bodies) for d in DIRS]
    return (-r[1], -r[3], -r[5], r[0], r[2], r[4])


def mass_props(body, density):
    """A body's (m, com, I about com) at `density` (kg/m^3), SI, in the part's axes."""
    return from_solidworks(body.GetMassProperties(float(density)))


def faces(doc, box=None):
    """Every face of every solid body, or only of the body whose loose box is `box` (mm)."""
    for body in solid_bodies(doc, False):
        if box is not None:
            b = [v / MM for v in body.GetBodyBox()]
            if any(abs(x - y) > 1.0 for x, y in zip(b, box)):
                continue
        for f in (get(body, "GetFaces") or []):
            yield f


def faces_where(body, pred):
    """A body's faces whose loose box (mm: x0, y0, z0, x1, y1, z1) passes `pred`."""
    return [f for f in (get(body, "GetFaces") or []) if pred([v / MM for v in get(f, "GetBox")])]


def find_face(doc, kind, spec, box=None):
    """The face a reference or a load sits on, by its geometry, the one of most area:
    - kind "cyl": a cylinder of radius `spec` (mm);
    - kind "plane": `spec` = (axis "x"/"y"/"z", position mm, outward normal's sign +1/-1)."""
    best, area = None, -1.0
    for f in faces(doc, box):
        s = get(f, "GetSurface")
        if kind == "cyl" and get(s, "IsCylinder"):
            p = get(s, "CylinderParams")      # origin xyz, axis xyz, radius
            if abs(p[6] / MM - spec) < 1e-3 and get(f, "GetArea") > area:
                best, area = f, get(f, "GetArea")
        elif kind == "plane" and get(s, "IsPlane"):
            ax, pos, sign = spec
            i = AXES[ax.lower()]
            n = get(f, "Normal")              # the face's outward normal
            if abs(n[i] - sign) < 1e-6:
                q = get(s, "PlaneParams")     # the plane's normal xyz, then a point on it
                if abs(q[3 + i] / MM - pos) < 1e-3 and get(f, "GetArea") > area:
                    best, area = f, get(f, "GetArea")
    if best is None:
        boxes = [[round(v / MM, 2) for v in b.GetBodyBox()] for b in solid_bodies(doc, False)][:5]
        raise SwError(f"no face {kind} {spec}; the first bodies' boxes: {boxes}")
    return best


# the feature type names a boss reads as (GetTypeName2)
BOSSES = ("Extrusion", "ICE", "Revolution")


def faceless_bosses(doc):
    """Boss features in the active configuration that own no faces and are not suppressed:
    each merged wholly into material already there, so it added nothing. A boss upstream of
    an active Delete Body feature owns no faces by design (a mirrored hand's originals,
    `part.mirror_config`), so only the bosses after the last active one are read."""
    out = []
    for f in features(doc):
        kind = get(f, "GetTypeName2")
        if get(f, "IsSuppressed"):
            continue
        if kind == "DeleteBody":
            out = []
            continue
        if kind in BOSSES and not list(get(f, "GetFaces") or []):
            out.append(f.Name)
    return out


def rebuild_test(app, path, names, factors=(0.9, 1.1)):
    """The part at `path` rebuilt with its globals `names` scaled together by each factor, in
    every configuration, and closed unsaved: a definition's "rebuilds at <global> +-10 %".
    Returns rows (factor, configuration, bodies, volume mm^3, errors, warnings); a row with an
    error fails. The part must not be open already."""
    doc = open_doc(app, path)
    rows = []
    try:
        em = doc.GetEquationMgr
        configs = list(doc.GetConfigurationNames or [])
        first = configs[0]
        doc.ShowConfiguration2(first)
        originals = {n: em.Equation(equation_index(em, n)) for n in names}
        try:
            for factor in (1.0,) + tuple(factors):
                doc.ShowConfiguration2(first)
                for n, text in originals.items():
                    set_equation(em, equation_index(em, n), text)
                    if factor != 1.0:
                        scale_global(em, n, factor)
                em.EvaluateAll
                for cfg in configs:
                    doc.ShowConfiguration2(cfg)
                    doc.ForceRebuild3(False)
                    errs = errors(doc)
                    bodies = solid_bodies(doc)
                    rows.append((factor, cfg, len(bodies), sum(volume(b) for b in bodies),
                                 [e for e in errs if e[2] == "error"], [e for e in errs if e[2] == "warning"]))
        finally:
            doc.ShowConfiguration2(first)
            for n, text in originals.items():
                set_equation(em, equation_index(em, n), text)
    finally:
        close(app, doc)
    return rows
