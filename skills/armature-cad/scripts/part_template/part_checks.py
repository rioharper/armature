"""
part_checks.py — the recipe's self-tests: an assertion behind every guard
in part.py, each written to FAIL if the guard it covers is removed.

Copy beside the part as `cad/parts/<PART-ID>_checks.py`. The line below
loads the part by this file's own name, because a part ID like ARM-BRK-001
is a file name `import` cannot spell.

The geometry assertions are about the WORKED EXAMPLE. When you replace the
recipe, replace them with the same question asked about your part — they are
the only thing standing between a silently wrong dimension and a green run.
"""

import ast
import importlib
import inspect
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from build123d import Axis

from check import compare_to_target, contained, ledger, mass_properties

part = importlib.import_module(Path(__file__).stem.removesuffix("_checks"))
HERE = Path(__file__).resolve().parent

# The body a re-derivation describes: its mass through a budget line, `of`
# a part's entry twice over, so the target reads 2 x 0.052 kg; its COM; and
# its tensor, about its COM in the part's axes. SI throughout.
BODY = {"mass": "mechanism.m2", "com": "mechanism.c2", "inertia": "mechanism.I2"}
LEDGER = """\
[mechanism.m2]
of = "budget.mass.forearm"

[mechanism.c2]
value = [0.0, 0.0, 0.004]
unit = "m"

[mechanism.I2]
value = [[5e-5, 0.0, 0.0], [0.0, 4e-5, 0.0], [0.0, 0.0, 9e-5]]
unit = "kg*m^2"
point = "the forearm's COM"
axes = "the part's"

[budget.mass.forearm]
of = "part.half.mass"
qty = 2

[budget.mass.ARM-BRK-001]
value = 0.105
unit = "kg"

[part.half.mass]
value = 0.052
unit = "kg"
"""


def _raised(exc_type, fn, *args, **kwargs):
    """The exception `fn` raised, or None. A check that cannot fail is
    not a check, so every use of this is asserted truthy."""
    try:
        fn(*args, **kwargs)
    except exc_type as exc:
        return exc
    return None


def _resolve_with(text, body=BODY, allow=True):
    """Resolve a target against a ledger written to a temp dir, and return
    (target, provenance, that ledger's path). The budget line is read from
    the same ledger, by the name part.py gives it."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, ledger.FILENAME)
        path.write_text(text.replace("budget.mass.ARM-BRK-001", part.BUDGET_LINE), encoding="utf-8")
        return part._resolve_target(body, allow_fallback=allow, ledger_path=path) + (path,)


def test_target_provenance_is_the_truth():
    target, prov, real = _resolve_with(LEDGER)
    # All three, not the mass alone, and the mass through both hops.
    assert target == {
        "mass": 2 * 0.052, "com": (0.0, 0.0, 0.004),
        "inertia": [[5e-5, 0.0, 0.0], [0.0, 4e-5, 0.0], [0.0, 0.0, 9e-5]],
        "about": part.ABOUT,
    }, target
    # The line names the file actually read, each entry it read, and the
    # frame the tensor is about, so a point that isn't ABOUT shows.
    assert prov.startswith(f"target driven from {real}: mass mechanism.m2"), prov
    assert "the forearm's COM" in prov and "the part's" in prov, prov

    # Entry gone (what a re-derivation's rename does): swallowing that
    # substitutes the budget line and prints a line claiming the
    # derivation drove it.
    renamed = LEDGER.replace("[mechanism.m2]", "[mechanism.m_forearm]")
    assert _raised(KeyError, _resolve_with, renamed)
    # A tensor with no stated point is compared against whatever point the
    # props were taken about: refused, as `set` refuses writing one.
    frameless = LEDGER.replace('point = "the forearm\'s COM"\n', "")
    assert "point" in str(_raised(ValueError, _resolve_with, frameless))
    # Half-pointed is neither a target nor a placeholder.
    half = dict(BODY, com="<ledger entry: the body's COM>")
    assert _raised(ValueError, _resolve_with, LEDGER, half)
    # A lumped body names its mass alone, and is checked on its mass alone.
    target, _, _ = _resolve_with(LEDGER, {"mass": "mechanism.m2", "com": None, "inertia": None})
    assert target == {"mass": 2 * 0.052}, target

    # The fallback: opt-in, honest about why, and still read from the ledger.
    target, prov, real = _resolve_with(LEDGER, part.BODY)
    assert target == {"mass": 0.105}, target
    assert "FALLBACK" in prov and "placeholder" in prov and str(real) in prov, prov
    assert _raised(RuntimeError, _resolve_with, LEDGER, part.BODY, False)
    # A budget line that has gone is a broken link too, not a fallback.
    assert _raised(KeyError, _resolve_with, LEDGER.replace("budget.mass.ARM", "budget.mass.X"), part.BODY)
    # Whatever the fallback produces still has to be a target check/ will
    # accept — it raises on an empty one, and an empty one is a green gate.
    assert isinstance(compare_to_target(mass_properties(part.build(), part.DENSITY), target), list)
    print("  [PASS] target provenance: all three from the ledger, fallback opt-in, broken links raise")


def test_the_part_file_imports_the_standard_library_and_build123d_alone():
    # A part file runs where the engine doesn't: it reads the ledger with
    # tomllib (through check/ledger.py, itself standard library only) and
    # imports neither the engine, nor tomlkit, nor the model's params.py.
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    imported = {alias.name.split(".")[0] for node in ast.walk(tree)
                if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                 if isinstance(node, ast.ImportFrom) and node.level == 0}
    outside = imported - sys.stdlib_module_names
    assert outside == {"build123d", "check"}, outside
    assert part.DENSITY == ledger.value(ledger.entries(part.LEDGER), part.DENSITY_ENTRY)[0]
    print("  [PASS] the part file imports the standard library, build123d and check/ alone")


def test_set_from_part_writes_the_measurement_back():
    try:
        from armature.ledger import check, load
    except ModuleNotFoundError as exc:
        if exc.name != "armature":
            raise
        print("  [SKIP] no engine here; the full run, in the model's environment, runs this")
        return
    name = f"part.{part.PART_ID}"
    with tempfile.TemporaryDirectory() as tmp:
        # The part file, check/ and its ledger, copied where set may write.
        shutil.copy(part.LEDGER, Path(tmp, ledger.FILENAME))
        shutil.copytree(HERE / "check", Path(tmp, "check"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(part.__file__, tmp)
        argv = [sys.executable, "-m", "armature.ledger", "set", name,
                "--from-part", Path(part.__file__).name]

        def run():
            done = subprocess.run(argv, cwd=tmp, capture_output=True,
                                  text=True, encoding="utf-8")
            assert done.returncode == 0, done.stderr
            return done.stdout.splitlines(), Path(tmp, ledger.FILENAME).read_bytes()

        said, first = run()
        assert said == [f"set {name}.{k}" for k in ("mass", "com", "inertia")], said
        errors = [f for f in check(tmp) if f.level == "error"]
        assert errors == [], errors
        props = mass_properties(part.build(), part.DENSITY, about=part.ABOUT)
        written = load(path=tmp)
        assert written[f"{name}.mass"].value == props["mass"]
        assert list(written[f"{name}.com"].value) == list(props["com"])
        assert written[f"{name}.inertia"].point == ledger.export(
            props, part.PART_ID, part.ORIGIN, part.AXES)["point"]
        assert written[f"{name}.mass"].source["kind"] == "cad"
        # A second run of the same part changes nothing.
        assert run() == ([f"{name}: unchanged"], first)
    print("  [PASS] set --from-part writes three cad entries check passes, and a re-run changes nothing")


def test_the_export_is_one_json_line():
    done = subprocess.run([sys.executable, part.__file__, ledger.EXPORT],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    assert len(lines) == 1 and set(json.loads(lines[0])) == {
        "mass", "com", "inertia", "point", "axes", "origin"}, lines
    print("  [PASS] the export prints one JSON line and nothing else")


def test_boss_follows_the_bore():
    def boss_wall(solid, bore):
        """Wall read off the finished part: its top face is the boss
        annulus, area pi/4 * (od^2 - bore^2)."""
        area = solid.faces().sort_by(Axis.Z)[-1].area
        return (math.sqrt(4 * area / math.pi + bore**2) - bore) / 2

    for bore in (part.BORE, 24.0):
        # Frozen at module scope this reads 5.00 mm at a 24 mm bore, and a
        # wall <= 0 guard fires nowhere in the swept range.
        assert math.isclose(boss_wall(part.build(bore=bore), bore), part.BOSS_WALL, abs_tol=1e-9)
    print("  [PASS] boss wall measured off the solid, at two bores")


def test_bolt_pattern_probe_sees_bore_and_edge():
    for bc in (22.0, 26.0):  # holes inside the bore / breaking into it
        assert "bore" in str(_raised(ValueError, part.build, bolt_circle=bc))
    # Measured: a 28.6 mm bore builds clean on a 2.70 mm boss wall, with
    # the bolt holes 1.05 mm into it.
    assert "bore" in str(_raised(ValueError, part.build, bore=28.6))
    # Ordering cannot change the answer: the ring probe is contained in the
    # FINISHED part, where a disc probe leaks its own holes.
    assert contained(part._pattern_probe(part.BOLT_CIRCLE), part.build())

    # The code applies the rule its comment states: EDGE_DIST of metal
    # beyond the hole WALL, not from its centre. Both bounds are spelled out
    # from the rule rather than from EDGE_REACH, so a probe measuring from
    # the centre instead (limit 59.0 mm, not 54.5) fails the second one
    # rather than moving with it. 1 mm inside the limit, as main()'s sweep
    # is: at exactly 54.5 the probe's outer face lands on the plate edge,
    # and betting a self-check on an OCCT boolean returning 0.0 rather than
    # 1e-9 is a coin toss.
    part.build(bolt_circle=part.PLATE_W - part.BOLT_CLEARANCE - 2 * part.EDGE_DIST - 1.0)  # 53.5
    assert "plate" in str(_raised(ValueError, part.build, bolt_circle=part.PLATE_W - 2 * part.EDGE_DIST - 1))
    print("  [PASS] bolt pattern probe sees the bore and the plate edge")


def test_no_dimension_is_both_parameter_and_constant():
    assert set(inspect.signature(part.build).parameters) == {"bolt_circle", "bore"}
    assert _raised(TypeError, part.build, plate_t=3.0)  # not a parameter at all
    print("  [PASS] only driven dimensions are parameters")
