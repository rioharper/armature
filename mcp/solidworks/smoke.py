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
        check("open test part", lambda: sw.open_doc(app, TEST_PART))
        # later tasks append their sections here, guarded by the same if

    failed = [n for n, e in RESULTS if e]
    print(f"\n{len(RESULTS) - len(failed)} passed, {len(failed)} failed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
