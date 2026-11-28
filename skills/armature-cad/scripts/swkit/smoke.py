"""
The kit's live check against a running SOLIDWORKS holding no document. From the folder
holding swkit/:

    uv run --no-project --with pywin32 python -m swkit.smoke [--fea] [--import] [--keep]

It works in a fresh temporary folder from the seat's default templates and checks each
result against a number worked out by hand here:
- a part: a rounded plate with a bore, a boss, a pattern of bolt holes round the boss's
  axis, an L-section rib as a second body and a flanged bushing revolved as a third, and its
  mirrored hand as a configuration: no rebuild error, no faceless boss, each body's volume,
  the plate's exact extents, the rib's COM and inertia tensor against two boxes summed by the
  parallel-axis rule (the products' sign), and the mirror's bore on the other side;
- the rebuild test at the plate's width +-10 %, its volume moving by the width's strip;
- `python -m swkit audit` on the part;
- a STEP AP214 copy, its schema read back, and with `--import` read back in as a solid;
- a drawing: views fitted to the sheet, a fit, a +- distance, a radius, a 4X callout, a datum
  and two frames, notes, PDF/DXF/SLDDRW, reopened to count its annotations;
- a section through the bushing, a 2:1 detail of its flange on a 1:2 sheet, a flag, and two
  distances on cut edges (picked by their sheet point, and by placed points) read back at
  their model value;
- an assembly of the part twice, mated plane to plane with computed alignments, and in its
  mirrored configuration;
- with `--fea`, Simulation's bar against beam theory.
"""
from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile
import traceback

from . import annotate as A
from . import com
from .assembly import Asm, mated, to_assembly
from .com import C, MM, get
from .drawing import Drawing, draw_part
from .exchange import export_step, import_solid
from .expr import ZERO
from .inertia import box, combine
from .measure import faceless_bosses, find_face, mass_props, reach, rebuild_test, solid_bodies, volume
from .part import Part
from .section import detail_view, flags, section_view

G = dict(w=60.0, h=40.0, t=8.0, r=4.0, bore=10.0, boss_d=12.0, b=6.0, pcd=20.0, bolt=3.0)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'} {name}{': ' + detail if detail else ''}", flush=True)


def close_to(a, b, tol):
    return abs(a - b) <= tol


def plate_volume(g):
    w, h, t, r = g["w"], g["h"], g["t"], g["r"]
    area = w * h - (4 - math.pi) * r * r
    return (area * t - math.pi * (g["bore"] / 2) ** 2 * t - 4 * math.pi * (g["bolt"] / 2) ** 2 * t
            + math.pi * (g["boss_d"] / 2) ** 2 * g["b"])


BUSH = dict(z0=5.0, z1=17.0, r_in=4.0, r_out=6.0, r_fl=9.0, t_fl=2.0, axis=-60.0)
BUSH_V = math.pi * ((BUSH["r_fl"] ** 2 - BUSH["r_in"] ** 2) * BUSH["t_fl"]
                    + (BUSH["r_out"] ** 2 - BUSH["r_in"] ** 2) * (BUSH["z1"] - BUSH["z0"] - BUSH["t_fl"]))
RIB = [(40, 0), (60, 0), (60, 10), (50, 10), (50, 30), (40, 30)]


def build(app, path):
    p = Part(app, path, props={"PartNo": "SWKIT-SMOKE", "Revision": "A", "Description": "swkit smoke part"},
             globals_=[(n, v, "mm", "swkit smoke") for n, v in G.items()])
    try:
        g = p.g
        s = p.sketch("Front Plane", "plate_sk")
        s.rect(-g["w"] / 2, g["w"] / 2, g["h"] / 2, ZERO, rounded=g["r"])
        s.close()
        p.extrude("plate_sk", "plate_ext", g["t"], toward=1)
        top = p.plane("top_face", "Front Plane", g["t"])
        s = p.sketch(top, "bore_sk")
        s.circle((g["w"] / 4, ZERO, g["t"]), g["bore"])
        s.close()
        p.extrude("bore_sk", "bore", g["t"], toward=-1, cut=True, through=True)
        s = p.sketch(top, "boss_sk")
        s.circle((-g["w"] / 4, ZERO, g["t"]), g["boss_d"])
        s.close()
        p.extrude("boss_sk", "boss", g["b"], toward=1)
        p.plane("boss_x", "Right Plane", -g["w"] / 4)
        p.axis("boss_axis", "boss_x", "Top Plane")
        s = p.sketch(top, "bolt_sk")
        s.circle((-g["w"] / 4 + g["pcd"] / 2, ZERO, g["t"]), g["bolt"])
        s.close()
        p.extrude("bolt_sk", "bolt", g["t"], toward=-1, cut=True, through=True)
        p.pattern(["bolt"], "boss_axis", 4, "bolts")
        p.name_body("plate")
        rib = p.plane("rib_plane", "Front Plane", -5.0)
        s = p.sketch(rib, "rib_sk")
        s.poly([(x, y, -5.0) for x, y in RIB])
        s.close()
        p.extrude("rib_sk", "rib_ext", 5.0, toward=-1, merge=False)
        p.name_body("rib")
        s = p.sketch("Front Plane", "bush_sk")
        s.stepped_ring(BUSH["z0"], BUSH["z1"], BUSH["r_in"], BUSH["r_out"], BUSH["r_fl"], BUSH["t_fl"], True,
                       BUSH["axis"])
        s.close()
        p.revolve("bush_sk", "bushing_rev", merge=False)
        p.name_body("bushing")
        p.finish()
        default = p.mirror("R", plane="Right Plane")
        doc = p.doc
        for cfg in (default, "R"):
            doc.ShowConfiguration2(cfg)
            doc.ForceRebuild3(False)
            check(f"part {cfg}: rebuilds clean", not com.errors(doc), str(com.errors(doc)))
        doc.ShowConfiguration2("R")
        bodies = {b.Name: b for b in solid_bodies(doc)}
        check("mirror: its bodies named", set(bodies) == {"plate (mirror)", "rib (mirror)", "bushing (mirror)"},
              str(sorted(bodies)))
        bore = find_face(doc, "cyl", G["bore"] / 2)
        x = list(get(get(bore, "GetSurface"), "CylinderParams"))[0] / MM
        check("mirror: the bore on the other side", close_to(x, -G["w"] / 4, 1e-6), f"x {x:.6f}")
        doc.ShowConfiguration2(default)
        doc.ForceRebuild3(False)
        check("no faceless boss", not faceless_bosses(doc), str(faceless_bosses(doc)))
        bodies = {b.Name: b for b in solid_bodies(doc)}
        check("bodies named", set(bodies) == {"plate", "rib", "bushing"}, str(sorted(bodies)))
        v = volume(bodies["plate"])
        check("plate volume", close_to(v, plate_volume(G), 1e-4), f"{v:.4f} against {plate_volume(G):.4f} mm^3")
        r = reach([bodies["plate"]])
        want = (-30.0, -20.0, 0.0, 30.0, 20.0, 14.0)
        check("plate's exact extents", max(abs(a - b) for a, b in zip(r, want)) < 1e-6, str(tuple(round(c, 6) for c in r)))
        v = volume(bodies["bushing"])
        check("bushing volume (revolve)", close_to(v, BUSH_V, 1e-4), f"{v:.4f} against {BUSH_V:.4f} mm^3")
        m, c, i = mass_props(bodies["rib"], 1000.0)
        half = m / 2
        mm = 1e-3
        ref = combine([box(half, (20 * mm, 10 * mm, 5 * mm), (50 * mm, 5 * mm, -7.5 * mm)),
                       box(half, (10 * mm, 20 * mm, 5 * mm), (45 * mm, 20 * mm, -7.5 * mm))])
        check("rib mass (poly, extruded apart)", close_to(m, 2000e-9 * 1000, 1e-12), f"{m * 1e3:.6f} g")
        check("rib COM", max(abs(a - b) for a, b in zip(c, ref[1])) < 1e-9, str([round(v / mm, 6) for v in c]))
        err = max(abs(i[a][b] - ref[2][a][b]) for a in range(3) for b in range(3))
        check("rib inertia tensor, the products' sign", err < 1e-12,
              f"Ixy {i[0][1]:.4e} against {ref[2][0][1]:.4e} kg m^2 (max error {err:.1e})")
    finally:
        p.close()
    return default


def rebuild(app, path):
    rows = rebuild_test(app, path, ["w"], (0.9, 1.1))
    bad = [r for r in rows if r[4]]
    check("rebuild at w +-10 %: no errors", not bad and len(rows) == 6, f"{len(rows)} rows; {bad}")
    vol = {(f, cfg): v for f, cfg, n, v, e, w in rows}
    base = vol[(1.0, "Default")] if (1.0, "Default") in vol else next(v for (f, _), v in vol.items() if f == 1.0)
    strip = 0.1 * G["w"] * G["h"] * G["t"]
    ok = all(close_to(v - base, (f - 1.0) / 0.1 * strip, 1e-3) for (f, _), v in vol.items())
    check("rebuild at w +-10 %: volume moves by the strip", ok,
          ", ".join(f"x{f:.1f} {cfg} {v - base:+.3f}" for (f, cfg), v in sorted(vol.items())))


def audit(path):
    from .__main__ import main
    check("python -m swkit audit", main(["audit", path]) == 0)


def step(app, path, tmp, do_import):
    out = os.path.join(tmp, "smoke.step")
    size, schema = export_step(app, path, out, 214)
    check("STEP AP214, schema read back", "AUTOMOTIVE_DESIGN" in schema.upper(), f"{size} bytes, {schema}")
    if do_import:
        v = import_solid(app, out, os.path.join(tmp, "imported.SLDPRT"), bodies=3)
        want = plate_volume(G) + 2000.0 + BUSH_V
        check("STEP read back in as a solid", close_to(v, want, 1e-2), f"{v:.3f} against {want:.3f} mm^3")


def drawing(app, path, tmp):
    dims = [
        A.dia("*Front", A.circle(G["bore"] / 2, x=G["w"] / 4, y=0.0), ("right", 0.75, None), A.fit("H7")),
        A.dist("*Front", A.line("y", x=-30.0), A.line("y", x=30.0), ("top", 0.5, None), A.pm(0.1)),
        A.rad("*Front", A.circle(G["r"], x=26.0, y=16.0), ("right", 0.95, None)),
        A.dia("*Front", A.circle(G["bolt"] / 2, x=-5.0, y=0.0), ("bottom", 0.3, None), pre="4X ", post=" THRU",
              prec=1),
        A.datum("*Top", A.line("x", z=0.0), "A", ("bottom", 0.3, None)),
        A.frame("pos", "0.1", ["A"], ("right", 0.55, None), on=0, dia=True),
        A.frame("flat", "0.05", [], ("top", 0.8, None), on=("*Top", A.line("x", z=8.0))),
    ]
    notes = ["MATERIAL: AL 6061-T6.", "DIMENSIONS NOT SHOWN PER SWKIT-SMOKE_A.STEP; ISO 2768-m.",
             "BREAK SHARP EDGES 0.2 MAX."]
    stem = os.path.join(tmp, "SWKIT-SMOKE_A")
    out, scale = draw_part(app, path, stem, dims=dims, notes=notes)
    sizes = {os.path.splitext(f)[1]: os.path.getsize(f) for f in out}
    check("drawing: PDF, DXF and SLDDRW written", set(sizes) == {".pdf", ".dxf", ".SLDDRW"} and min(sizes.values()) > 0,
          f"{sizes}, scale {scale[0]}:{scale[1]}")
    check("drawing: the PDF is one", open(stem + ".pdf", "rb").read(5) == b"%PDF-")
    with com.opened(app, stem + ".SLDDRW") as drw:
        kinds, texts = {}, []
        fit = False
        v = get(drw, "GetFirstView")
        while v is not None:
            for ann in (get(v, "GetAnnotations") or []):
                k = get(ann, "GetType")
                kinds[k] = kinds.get(k, 0) + 1
                if k == C["swDisplayDimension"]:
                    dim = get(ann, "GetSpecificAnnotation").GetDimension2(0)
                    fit = fit or dim.Tolerance.Type == C["swTolFIT"]
                elif k == C["swNote"]:
                    texts.append(get(get(ann, "GetSpecificAnnotation"), "GetText"))
            v = get(v, "GetNextView")
        n = {name: kinds.get(C[name], 0) for name in ("swDisplayDimension", "swGTol", "swDatumTag")}
        check("drawing reopened: 4 dimensions, 2 frames, 1 datum",
              n == {"swDisplayDimension": 4, "swGTol": 2, "swDatumTag": 1}, str(n))
        mine = [f"{i + 1}. {t}" for i, t in enumerate(notes)]
        check("drawing reopened: its 3 numbered notes, once each", all(texts.count(t) == 1 for t in mine),
              str([t for t in texts if t[:2] in ("1.", "2.", "3.")]))
        check("drawing reopened: the bore's fit is a fit", fit)


def _value(ann):
    return get(ann, "GetSpecificAnnotation").GetDimension2(0).SystemValue / MM


def sections(app, path, tmp):
    d = Drawing(app)
    try:
        w, h = d.size
        front = d.model_view(path, "*Front", (0.22 * w, 0.55 * h))
        d.scale(1, 2)
        front.UseSheetScale = True
        d.doc.ForceRebuild3(False)
        x = BUSH["axis"]
        sec = section_view(d.doc, front, (x, 30.0, 0.0), (x, -5.0, 0.0), (0.5 * w, 0.55 * h), "C")
        det = detail_view(d.doc, sec, (x, 3.0, 2.0), (x, 10.0, 11.0), (0.78 * w, 0.55 * h), (2, 1), "D")
        flags(d.doc, det, [(1, (x, BUSH["z0"], 6.5), (-12.0, 4.0))])
        made = A.annotate(app, d.doc, {"C": sec, "D": det}, [
            A.dist("C", A.spot((x, BUSH["z0"], 6.5)), A.spot((x, BUSH["z0"] + BUSH["t_fl"], 7.5)), ("left", 0.5, None)),
            A.dist("D", A.sharp((x, BUSH["z0"], BUSH["r_in"])), A.sharp((x, BUSH["z0"] + BUSH["t_fl"], BUSH["r_in"])),
                   ("right", 0.5, None), orient="v"),
        ])
        a, b = _value(made[0]), _value(made[1])
        check("section: a distance between cut edges picked through model points", close_to(a, BUSH["t_fl"], 1e-6), f"{a:.6f} mm")
        check("detail 2:1 on a 1:2 sheet: placed points measured at the view's scale",
              close_to(b, BUSH["t_fl"], 1e-6), f"{b:.6f} mm")
        pdf = d.export(os.path.join(tmp, "SWKIT-SMOKE_sections"), (".pdf",))[0]
        check("section drawing exported", os.path.getsize(pdf) > 0)
    finally:
        d.close(path)


def assembly(app, path, tmp):
    asm = Asm(app, com.default_template(app, "assembly"), os.path.join(tmp, "smoke.SLDASM"))
    try:
        a = asm.insert(path)
        b = asm.insert(path, at=(150, 80, 40))
        planes = [("swMateCOINCIDENT", n, "PLANE", n, "PLANE") for n in ("Front Plane", "Top Plane", "Right Plane")]
        identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        mated(asm, b, a, identity, planes)
        asm.doc.ForceRebuild3(False)
        pa, pb = to_assembly(a, (10, 20, 30)), to_assembly(b, (10, 20, 30))
        check("assembly: mated plane to plane, alignments computed",
              max(abs(u - v) for u, v in zip(pa, pb)) < 1e-6 and not com.errors(asm.doc), f"{pa} / {pb}")
        c = asm.insert(path, at=(-150, 0, 0), config="R")
        check("assembly: a component in its mirrored configuration", get(c, "ReferencedConfiguration") == "R")
        asm.finish()
    finally:
        app.CloseDoc(asm.doc.GetTitle)


def fea(app, tmp):
    from .simulation import validate_bar
    got, want = validate_bar(app, tmp)
    check("Simulation: the bar's tip against beam theory", abs(got / want - 1) < 0.03,
          f"{got:.5f} against {want:.5f} mm ({got / want - 1:+.2%})")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    app = com.attach()
    com.require_empty(app)
    tmp = tempfile.mkdtemp(prefix="swkit_smoke_")
    path = os.path.join(tmp, "SWKIT-SMOKE.SLDPRT")
    print(f"SOLIDWORKS {app.RevisionNumber}; working in {tmp}", flush=True)
    steps = [("part", lambda: build(app, path)), ("rebuild", lambda: rebuild(app, path)),
             ("audit", lambda: audit(path)), ("step", lambda: step(app, path, tmp, "--import" in argv)),
             ("drawing", lambda: drawing(app, path, tmp)), ("sections", lambda: sections(app, path, tmp)),
             ("assembly", lambda: assembly(app, path, tmp))]
    if "--fea" in argv:
        steps.append(("fea", lambda: fea(app, tmp)))
    try:
        for name, fn in steps:
            try:
                fn()
            except Exception as e:
                check(f"{name} ran", False, f"{type(e).__name__}: {e}")
                traceback.print_exc()
                if name == "part":
                    break
    finally:
        for d in list(app.GetDocuments or []):
            if os.path.normcase(d.GetPathName or "").startswith(os.path.normcase(tmp)):
                app.CloseDoc(d.GetTitle)
        if "--keep" not in argv:
            shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} passed, {len(failed)} failed" + (f"; kept {tmp}" if "--keep" in argv else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
