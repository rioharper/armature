"""Manual smoke test. Prereq: SolidWorks 2026 running.
From mcp/solidworks/: uv run --with pywin32 smoke.py
Tasks 2+ additionally require test-part.SLDPRT (same folder) to exist."""
import math
import os
import sys
import sw

RESULTS = []

def check(name, fn):
    try:
        fn()
        RESULTS.append((name, None))
        print(f"PASS {name}")
    except Exception as e:
        RESULTS.append((name, e))
        print(f"FAIL {name}: {e}")

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_PART = os.path.join(HERE, "test-part.SLDPRT")

# Known answers for test-part.SLDPRT: 40x20x10 mm block, 1060 Alloy (2700 kg/m3),
# minus a 10 mm through-hole (10 mm deep): 8000 - pi*25*10 = 7214.6 mm^3 -> 19.48 g.
BLOCK_MASS_KG = (40 * 20 * 10 - math.pi * 5**2 * 10) * 1e-9 * 2700  # ≈ 0.01948

def main():
    app = sw.attach()

    def t_status():
        s = sw.status(app)
        assert s["solidworks_version"], "no version string"
        assert isinstance(s["open_documents"], list)
    check("status", t_status)

    def t_bad_doc():
        try:
            sw.resolve_doc(app, "no-such-doc-xyz")
        except sw.DocNotFound as e:
            assert "Open documents" in str(e)
            return
        raise AssertionError("DocNotFound not raised")
    check("doc-not-found lists open docs", t_bad_doc)

    if os.path.isfile(TEST_PART):
        def t_open():
            r = sw.open_doc(app, TEST_PART)
            assert r["linear_units"] == "mm", r  # MMGS fixture; guards the LengthUnit lookup
        check("open test part", t_open)
        doc = sw.resolve_doc(app, "test-part")
        # later tasks append their sections here, guarded by the same if

        def t_params_roundtrip():
            p = sw.get_params(doc)["params"]
            assert "block_len" in p, f"block_len missing; got {list(p)}"
            assert abs(p["block_len"]["value"] - 40) < 1e-6
            sw.set_params(doc, {"block_len": 50})
            assert abs(sw.get_params(doc)["params"]["block_len"]["value"] - 50) < 1e-6
            sw.set_params(doc, {"block_len": 40})  # restore
        check("params round-trip", t_params_roundtrip)

        def t_params_no_create():
            try:
                sw.set_params(doc, {"not_a_var": 1})
            except sw.NameNotFound as e:
                assert "block_len" in str(e)
                return
            raise AssertionError("NameNotFound not raised")
        check("set_params refuses unknown names", t_params_no_create)

        def t_params_global_only():
            all_params = sw.get_params(doc)["params"]
            non_global = [n for n, v in all_params.items() if not v["global"]]
            if non_global:
                target = non_global[0]
                try:
                    sw.set_params(doc, {target: 1})
                except sw.NameNotFound as e:
                    available = str(e).split("Available:", 1)[1]
                    assert f"'{target}'" not in available, f"non-global name leaked into Available: {e}"
                    return
                raise AssertionError("NameNotFound not raised for non-global name")
            else:
                # part has no feature-driven equations to test against directly;
                # pin the same contract via get_params' global flag on whatever IS listed
                try:
                    sw.set_params(doc, {"__does_not_exist__": 1})
                except sw.NameNotFound as e:
                    available = str(e).split("Available:", 1)[1]
                    for n, v in all_params.items():
                        if f"'{n}'" in available:
                            assert v["global"], f"non-global {n} listed as available: {e}"
                    return
                raise AssertionError("NameNotFound not raised")
        check("set_params rejects non-global names", t_params_global_only)

        def t_rebuild_perturb():
            sw.set_params(doc, {"block_len": 60})
            r = sw.rebuild(doc)
            assert r["problems"] == [], f"unexpected problems: {r['problems']}"
            sw.set_params(doc, {"block_len": 40})
            assert sw.rebuild(doc)["problems"] == []
        check("perturb+rebuild clean", t_rebuild_perturb)

        def t_rebuild_reports_problems():
            try:
                sw.set_params(doc, {"block_len": 0})  # degenerate extrude -> real feature fault
                problems = sw.rebuild(doc)["problems"]
                assert problems, "expected non-empty problems for block_len=0"
                for p in problems:
                    assert p["feature"], f"empty feature name: {p}"
                    assert p["kind"] in ("error", "warning"), f"bad kind: {p}"
            finally:
                sw.set_params(doc, {"block_len": 40})  # must run even if asserts fail
            assert sw.rebuild(doc)["problems"] == []
        check("rebuild reports problems", t_rebuild_reports_problems)

        def t_mass_props():
            m = sw.mass_properties(doc, None)
            assert abs(m["mass"] - BLOCK_MASS_KG) / BLOCK_MASS_KG < 0.01, m["mass"]
            t = m["inertia_tensor"]
            for i in range(3):
                for j in range(3):
                    assert abs(t[i][j] - t[j][i]) < 1e-12, "tensor not symmetric"
            mc = sw.mass_properties(doc, "CS_corner")
            assert mc["about"] == "CS_corner"
            # parallel axis: every diagonal moment about the corner CS must be >= about COM
            for i in range(3):
                assert mc["inertia_tensor"][i][i] > t[i][i], (
                    "corner moments not larger than COM moments — moment-type enum is wrong")
        check("mass properties + parallel-axis", t_mass_props)

        def t_mass_bad_cs():
            try:
                sw.mass_properties(doc, "CS_nope")
            except sw.NameNotFound as e:
                assert "CS_corner" in str(e)
                return
            raise AssertionError("NameNotFound not raised")
        check("mass props lists coordinate systems on bad name", t_mass_bad_cs)

        def t_dimensions():
            d = sw.get_dimensions(doc, ["bore@Sketch2"])["dimensions"]["bore@Sketch2"]
            assert abs(d["value"] - 0.010) < 1e-9, d  # SystemValue is meters
        check("read named dimension in SI", t_dimensions)

        def t_tolerance_roundtrip():
            try:
                sw.set_tolerance(doc, "bore@Sketch2", "fit", {"hole": "H7", "shaft": ""})
                d = sw.get_dimensions(doc, ["bore@Sketch2"])["dimensions"]["bore@Sketch2"]
                assert d["tolerance"] and d["tolerance"]["type"] == "fit", d
                # ISO 286 H7 deviations for a 10 mm bore: upper +15 um, lower 0 —
                # observed live via SolidWorks' own fit resolution, not computed here.
                assert abs(d["tolerance"]["max"] - 1.5e-05) < 1e-9, d
                assert d["tolerance"]["min"] == 0.0, d
                sw.set_tolerance(doc, "bore@Sketch2", "bilateral",
                                 {"max": 0.0001, "min": -0.0001})
                d = sw.get_dimensions(doc, ["bore@Sketch2"])["dimensions"]["bore@Sketch2"]
                assert d["tolerance"]["type"] == "bilateral"
                assert abs(d["tolerance"]["max"] - 0.0001) < 1e-9
                assert abs(d["tolerance"]["min"] - (-0.0001)) < 1e-9
            finally:
                # restore tolerance state so repeated smoke runs stay idempotent
                sw.set_tolerance(doc, "bore@Sketch2", "none", {})
        check("tolerance set/read round-trip", t_tolerance_roundtrip)

        def t_dimension_not_found():
            try:
                sw.get_dimensions(doc, ["no_such_dim@Sketch2"])
            except sw.NameNotFound as e:
                assert "no_such_dim@Sketch2" in str(e)
                return
            raise AssertionError("NameNotFound not raised")
        check("get_dimensions raises NameNotFound for bad name", t_dimension_not_found)

        def t_custom_props():
            sw.custom_props_set(doc, {"PartNo": "ARM-TST-001", "Material": "1060 Alloy"})
            got = sw.custom_props_get(doc)
            assert got.get("PartNo") == "ARM-TST-001", got
        check("custom props set/get", t_custom_props)

    failed = [n for n, e in RESULTS if e]
    print(f"\n{len(RESULTS) - len(failed)} passed, {len(failed)} failed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
