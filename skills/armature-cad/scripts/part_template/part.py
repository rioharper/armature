"""
part.py — template for an executable build recipe.

Copy to `cad/parts/<PART-ID>.py` beside the part's `<PART-ID>.md` and edit.
Copy `check.py` into `cad/parts/` too — this file imports it from its own
directory — and `stubs.py` as well if you need COTS placeholders.
The .md is still the part definition — the contract, the loads, the
rationale, the thing a human reads. This file is only its Build recipe
section, written so a machine can run it and answer three questions the
markdown can't:

  * does the recipe actually close?  (a bolt circle that doesn't fit,
    a boss that misses, a wall that goes negative under a fillet)
  * does the part hit the mass and inertia the dynamics assumed?
  * what does it look like?  (SVG views for the "At a glance" section)

Run it:  uv run --with build123d python cad/parts/<PART-ID>.py
Exits nonzero when a check fails, so it works in a pre-commit hook or CI.

THE ONE RULE: this file must never restate a dimension that already lives
in `analysis/model/params.py` or in an interface table. It imports those.
A number typed in two places is a number that will disagree with itself,
and the .md and .py disagreeing is worse than not having the .py.

Worked example below: ARM-BRK-001, the plate-with-a-boss from the SKILL.md
recipe — 80x75x6 plate, 4x M4 clearance on a 45 mm bolt circle, central
boss bored 22 H7. Replace it with your part; keep the shape of the file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from build123d import (
    Align,
    Axis,
    BuildPart,
    BuildSketch,
    Circle,
    Cylinder,
    Hole,
    Mode,
    Plane,
    PolarLocations,
    Rectangle,
    extrude,
    fillet,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import (  # noqa: E402
    compare_to_target,
    contained,
    mass_properties,
    rebuild_sweep,
    report,
    write_views,
)

PART_ID = "ARM-BRK-001"
GRADE = "sketch"  # sketch | release — mirror the .md header

# --- driven dimensions -------------------------------------------------
# Only what traces to the parameter table or an interface contract, and
# nothing else: a dimension that is both an argument here and a constant
# below is a dimension with two values. At sketch grade params.py may not
# exist yet, so the mass target may fall back — loudly, and only at sketch
# grade — rather than blocking a definition on a derivation that hasn't run.

# Geometry is driven by INTERFACES — the datasheet numbers this part has to
# mate to. params.py drives the mass/inertia TARGET below, not the shape:
# a link length in the dynamics does not set a bracket's plate size, and
# pretending it does means inventing a conversion factor, which is exactly
# the kind of unsourced number this whole skill exists to prevent.

BOLT_CIRCLE = 45.0  # driven: actuator flange BCD, datasheet <P/N>
BORE = 22.0  # driven: bearing OD, datasheet <P/N>
BOLT_DIA = 4.0  # driven: M4, the flange's fastener size, datasheet <P/N>

# --- typed / derived dimensions ----------------------------------------
# Plain numbers, or arithmetic on a driven one. Not everything deserves to
# be a parameter — a fully parametrized one-off is fragility dressed as rigor.

PLATE_L = 80.0
PLATE_W = 75.0  # set by the bolt circle + edge distance, not by taste
PLATE_T = 6.0
BOSS_WALL = 6.0  # metal around the bearing seat — hoop stress on the press fit
BOSS_H = 10.0
CORNER_R = 6.0

# ISO 273 clearance holes, MEDIUM (normal) series. The row is picked by
# BOLT_DIA so the fastener size is stated once: for M4 the standard's three
# series are close 4.3 / medium 4.5 / free 4.8, and medium is the default
# for a flange that has to align to a bolt circle. A size not in the table
# raises here rather than being guessed.
ISO_273_MEDIUM = {3.0: 3.4, 4.0: 4.5, 5.0: 5.5, 6.0: 6.6}
BOLT_CLEARANCE = ISO_273_MEDIUM[BOLT_DIA]

# EDGE_DIST is metal from the hole WALL to any free edge — the plate outline
# or the bore — because that is what the probe below measures: it demands
# solid metal out to EDGE_REACH from the bolt CENTRE, which is the hole
# radius plus EDGE_DIST.
#
# Basis: the "2D edge distance" rule of general fastener practice — edge
# distance two hole diameters, measured from the hole CENTRE, so 2*4.5 =
# 9.0 mm here. This file applies 2x nominal bolt dia beyond the hole WALL
# instead, 10.25 mm from the centre, which is deliberately conservative
# against that rule and far above any code minimum.
#
# For the code minimum, read the structural code FOR YOUR MATERIAL: this
# part is 6061-T6, so that is Eurocode 9 (EN 1999-1-1), not the steel one.
# For order of magnitude only, steel's Eurocode 3 (EN 1993-1-8 Table 3.3)
# puts its minimum end/edge distance at 1.2*d0 from the hole centre — 5.4 mm
# here. Neither of those is a design basis for an aluminium bracket: replace
# EDGE_DIST with what your own structural basis gives, and cite it, the way
# every driven number above is cited.
EDGE_DIST = 2.0 * BOLT_DIA
EDGE_REACH = BOLT_CLEARANCE / 2 + EDGE_DIST

DENSITY = 2700.0  # Al 6061-T6 [kg/m^3] — from docs/01-spec/bom.md

# --- the target the loop closes against --------------------------------
# What the dynamics ASSUMED for this body, in SI, about the stated point.
# If the dynamics lumped this part into a larger body there is no per-part
# tensor to invent: give {"mass": ...} alone and check the lump at batch end.
#
# THIS is what params.py drives. Point PARAM_KEY at the body this part
# realizes and the target follows the derivation automatically; when the
# derivation is re-run the target moves with it, which is the entire reason
# not to type the number here.

PARAMS_DIR = Path(__file__).resolve().parents[2] / "analysis" / "model"
sys.path.insert(0, str(PARAMS_DIR))

# Point this at the body this part realizes. The angle brackets mean "not
# pointed at anything yet", which is NOT the same as a key that has gone
# missing: an unset placeholder falls back and says so, while a key that
# was set and no longer resolves raises. A renamed key is the most likely
# thing a re-derivation does, and it is exactly the event that means the
# loop is broken — swallowing it substitutes a hand-typed number for a
# derived one and prints a line claiming the derivation drove it.
PARAM_KEY = "<params key for this body>"
BUDGET_MASS = 0.105  # kg — budget row, docs/01-spec/budgets.md

# The budget fallback is allowed at SKETCH grade only, where the derivation
# may genuinely not have run yet. A release-grade part whose target cannot
# be traced to params.py must fail rather than quietly check itself against
# a number somebody typed.
ALLOW_BUDGET_FALLBACK = GRADE == "sketch"


def _resolve_target(param_key: str, allow_fallback: bool = ALLOW_BUDGET_FALLBACK):
    """(TARGET, PROVENANCE) for `param_key`, or raise saying why not.

    Only a missing `params` MODULE is a fallback. A KeyError (the key was
    renamed), an AttributeError (no PARAMS table), and a ModuleNotFoundError
    raised from inside params.py itself (a dependency of the derivation is
    missing) all propagate: each of those means the derivation is there and
    the link to it is broken, and a broken link is not a reason to check the
    part against a different number.

    PROVENANCE says what actually happened, and is printed. It must never
    claim params.py is absent while params.py is sitting right there — nor
    name a file it did not read.
    """
    try:
        import params  # analysis/model/params.py — SI: metres, kilograms
    except ModuleNotFoundError as exc:
        if exc.name != "params":
            raise  # params.py imports something that isn't installed
        params = None

    if params is not None and not param_key.startswith("<"):
        # KeyError / AttributeError deliberately propagate.
        #
        # The path comes from params.__file__, not from PARAMS_DIR. `import
        # params` searches ALL of sys.path — which includes this file's own
        # directory, where you were told to put check.py and stubs.py — so a
        # params.py dropped beside the part file resolves fine and naming
        # PARAMS_DIR would credit a file that was never read.
        return (
            {"mass": params.PARAMS[param_key]},
            f"target driven from {params.__file__}[{param_key}]",
        )

    why = (
        f"no params.py on sys.path ({PARAMS_DIR})"
        if params is None
        else f"PARAM_KEY is still the placeholder {param_key!r}"
    )
    if not allow_fallback:
        raise RuntimeError(
            f"{PART_ID}: no target to check against - {why}. At grade "
            f"'{GRADE}' the budget fallback is off; point PARAM_KEY at the "
            f"body this part realizes, or drop the grade back to sketch."
        )
    return {"mass": BUDGET_MASS}, f"target from budgets.md - FALLBACK, {why}"


TARGET, PROVENANCE = _resolve_target(PARAM_KEY)

# Add these once the dynamics assumes per-body values, not just a mass:
#   TARGET["com"] = (0.0, 0.0, 0.004)          # m, in the part's own frame
#   TARGET["inertia"] = [[...], [...], [...]]  # kg m^2
#   TARGET["about"] = None                     # the COM, or (0.0, 0.0, 0.0) mm
#     — a point, not a label: it is compared structurally, so "point
#       (0, 0, 0) mm" is rejected rather than false-failing on formatting.
TOL = 0.10


def build(bolt_circle: float = BOLT_CIRCLE, bore: float = BORE):
    """The build recipe, one comment per numbered step in the .md.

    Every DRIVEN dimension is a keyword argument so rebuild_sweep() can
    prove the recipe survives changing it. That IS the "model rebuilds
    cleanly after changing each driven parameter" line in Done when.

    The typed numbers — plate size, boss height, corner radius — are read
    from module scope and are deliberately NOT arguments. A number that is
    both a parameter and a constant is a number with two values: the probe
    below used to read module PLATE_T while build() took a plate_t, so
    build(plate_t=3.0) blamed the BOLT CIRCLE for a plate-thickness problem
    and build(plate_t=12.0) passed on a probe that tested the bottom half.
    """
    # The seat sizes the boss, so the boss follows the `bore` ARGUMENT.
    # Frozen at module scope it followed the module BORE instead, and a
    # swept bore ate the wall down to 2.70 mm while the sweep reported PASS.
    boss_od = bore + 2 * BOSS_WALL

    with BuildPart() as bp:
        # 1. Sketch on the mounting face plane: PLATE_L x PLATE_W centered on origin.
        with BuildSketch(Plane.XY):
            Rectangle(PLATE_L, PLATE_W)
        # 2. Extrude PLATE_T.
        extrude(amount=PLATE_T)

        # 3. Break the plate corners (before the holes, so the fillet only
        #    sees the four vertical corner edges).
        fillet(bp.edges().filter_by(Axis.Z), CORNER_R)

        # 4. Boss on the plate's top face, concentric with the bore.
        with BuildSketch(Plane.XY.offset(PLATE_T)):
            Circle(boss_od / 2)
        extrude(amount=BOSS_H)

        # 5. 4x M4 clearance on the bolt circle (driven: flange BCD).
        with PolarLocations(bolt_circle / 2, 4):
            Hole(BOLT_CLEARANCE / 2)

        # 6. Bore through plate and boss for the bearing seat.
        Hole(bore / 2)

    # 7. Every bolt must have landed on metal. A hole hanging off the plate
    #    edge — or sitting inside the bore — still builds a valid solid, it
    #    just quietly removes less material, so nothing else would catch it.
    _assert_pattern_fits(bp.part, bolt_circle, bore)

    return bp.part


def _pattern_probe(bolt_circle: float):
    """The metal each bolt needs: a plate-thick RING around every hole,
    inner radius the hole itself, outer radius EDGE_REACH.

    A ring, not a disc, because the bolt hole is not metal — that is what
    lets this be measured against the FINISHED part. A disc probe leaks its
    own four holes (381.7 mm^3 on the worked example), so it only worked
    against the blank, which made the check silently depend on running
    before the holes and the bore were cut.

    Exactly plate-thick and sitting on the plate (Align.MIN in Z): a probe
    taller than the plate pokes out the top and bottom faces and reports a
    violation for every bolt circle, including good ones.
    """
    with BuildPart() as probe:
        with PolarLocations(bolt_circle / 2, 4):
            Cylinder(EDGE_REACH, PLATE_T, align=(Align.CENTER, Align.CENTER, Align.MIN))
            Cylinder(
                BOLT_CLEARANCE / 2,
                PLATE_T,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT,
            )
    return probe.part


def _assert_pattern_fits(part, bolt_circle: float, bore: float):
    """Every bolt in the pattern must sit on metal, with its edge distance,
    on the FINISHED part — after the bore and the bolt holes are cut.

    Probing the blank tested clearance to the plate edge and nothing else:
    a 26 mm bolt circle broke into the 22 mm bore, and a 22 mm one put the
    bolt holes ENTIRELY INSIDE it, and both built without complaint.
    """
    if contained(_pattern_probe(bolt_circle), part):
        return
    # Name the cause. The bore and the plate outline are both free edges to
    # this rule, and reporting the wrong one sends the reader to the wrong
    # dimension — which is how a plate-thickness bug got blamed on the bolt
    # circle for a whole review cycle.
    culprit = (
        f"into the {bore} mm bore"
        if bolt_circle / 2 - EDGE_REACH < bore / 2
        else f"off the {PLATE_L}x{PLATE_W} plate"
    )
    raise ValueError(
        f"bolt circle {bolt_circle} mm: the pattern needs {EDGE_DIST} mm of "
        f"metal beyond each hole wall ({EDGE_REACH} mm from its centre) and "
        f"runs {culprit}"
    )


def main() -> int:
    part = build()

    props = mass_properties(part, DENSITY, about=None)
    fails = compare_to_target(props, TARGET, tol=TOL)

    # Done when: the recipe rebuilds after changing each driven parameter.
    # The band is what the recipe's own edge-distance rule allows, derived
    # here so it tracks the constants instead of being a decorative +-10%:
    # below bc_min the pattern runs into the bore, above bc_max it runs off
    # the plate, and bore_max is the same rule read from the bore's side.
    # A blind +-10% on the bolt circle reaches 40.5, which leaves 7.0 mm of
    # metal to the bore against the 8.0 mm this part demands — a real
    # finding, and one about the sweep's range rather than about the part.
    bc_min = BORE + 2 * EDGE_REACH  # 42.5 mm
    bc_max = PLATE_W - 2 * EDGE_REACH  # 54.5 mm
    bore_max = BOLT_CIRCLE - 2 * EDGE_REACH  # 24.5 mm
    fails += rebuild_sweep(
        build,
        # Sweep the DRIVEN dimensions only, 1 mm inside each limit so the
        # sweep tests the recipe rather than the boolean tolerance at exact
        # tangency. The typed numbers aren't parameters at all any more.
        {
            "bolt_circle": [bc_min + 1.0, BOLT_CIRCLE, bc_max - 1.0],
            "bore": [BORE * 0.7, BORE, bore_max - 1.0],
        },
    )

    print(f"{PART_ID} (grade: {GRADE}, {PROVENANCE})")
    ok = report(PART_ID, props, fails)

    written = write_views(part, str(Path(__file__).with_suffix("")))
    print(f"    views: {', '.join(Path(p).name for p in written)}")

    return 0 if ok else 1


def demo():
    """Self-check: one assertion per red-team finding this file was fixed
    for, each written to FAIL if its fix is reverted.

    The geometry assertions are about the WORKED EXAMPLE. When you replace
    the recipe, replace them with the same question asked about your part —
    they are the only thing standing between a silently wrong dimension and
    a green run.
    """
    import importlib
    import inspect
    import math
    import tempfile

    def raised(exc_type, fn, *args, **kwargs):
        """The exception `fn` raised, or None. A check that cannot fail is
        not a check, so every use of this is asserted truthy."""
        try:
            fn(*args, **kwargs)
        except exc_type as exc:
            return exc
        return None

    # --- F1/F13: the target's provenance is the truth, or there is no run.
    def resolve_with(params_src, key, allow=True):
        """Resolve a target against a params.py written to a temp dir, and
        return (target, provenance, that temp params.py).

        EVERY directory on sys.path that holds a params.py is dropped for
        the duration, not just PARAMS_DIR: `import params` searches the
        whole path, including this file's own directory, so a project that
        keeps params.py beside the part file would otherwise have its real
        one answer the case that is meant to test having none.
        """
        saved = sys.path[:]
        with tempfile.TemporaryDirectory() as tmp:
            if params_src is not None:
                Path(tmp, "params.py").write_text(params_src)
            sys.path[:] = [tmp] + [p for p in saved if not Path(p or ".", "params.py").exists()]
            sys.modules.pop("params", None)
            importlib.invalidate_caches()
            try:
                return _resolve_target(key, allow_fallback=allow) + (Path(tmp, "params.py"),)
            finally:
                sys.path[:] = saved
                sys.modules.pop("params", None)

    renamed = "PARAMS = {'m_link1': 1.20}\n"  # what a re-derivation does
    # THE finding: params.py present, key gone. This used to substitute a
    # hand-typed 0.105 kg, print "no analysis/model/params.py yet" with
    # params.py sitting right there, and exit 0.
    assert raised(KeyError, resolve_with, renamed, "m1")
    # A missing PARAMS table and a params.py whose own imports fail are the
    # same class of event, and used to fail three different ways.
    assert raised(AttributeError, resolve_with, "MASSES = {}\n", "m1")
    assert raised(ModuleNotFoundError, resolve_with, "import no_such_module_xyz\n", "m1")

    target, prov, real = resolve_with("PARAMS = {'m1': 0.104}\n", "m1")
    assert target == {"mass": 0.104}
    # The line must name the file that was actually imported. `import
    # params` searches all of sys.path, so a params.py anywhere on it
    # resolves — and printing the directory this template HOPED to read
    # credits a file that was never opened. That is the same falsehood F1
    # exists to remove, and this assertion used to pass on it: the module
    # here is loaded from a temp dir and the line said analysis/model.
    assert prov == f"target driven from {real}[m1]", prov

    # The fallback: opt-in, and honest about which of the two reasons it is.
    target, prov, _ = resolve_with(None, "m1")
    assert target == {"mass": BUDGET_MASS} and "FALLBACK" in prov, prov
    assert raised(RuntimeError, resolve_with, None, "m1", False)
    # F13: an unset PARAM_KEY falls back even though params.py is RIGHT
    # THERE, so the line must not claim the file is missing. Spelled out
    # rather than read from PARAM_KEY, which you are expected to set.
    target, prov, _ = resolve_with(renamed, "<params key for this body>")
    assert "FALLBACK" in prov and "placeholder" in prov, prov
    assert "no params.py" not in prov, prov
    # Whatever the fallback produces still has to be a target check.py will
    # accept — it raises on an empty one, and an empty one is a green gate.
    assert isinstance(compare_to_target(mass_properties(build(), DENSITY), target), list)

    # --- F5a: the boss follows the bore, and is measured off the solid.
    def boss_wall(part, bore):
        """Wall read off the finished part: its top face is the boss
        annulus, area pi/4 * (od^2 - bore^2)."""
        area = part.faces().sort_by(Axis.Z)[-1].area
        return (math.sqrt(4 * area / math.pi + bore**2) - bore) / 2

    for bore in (BORE, 24.0):
        # Frozen at module scope this was 5.00 mm at a 24 mm bore, and the
        # only guard fired at wall <= 0, i.e. never in the swept range.
        assert math.isclose(boss_wall(build(bore=bore), bore), BOSS_WALL, abs_tol=1e-9)

    # --- F5b: the probe sees the bore, because it runs on the finished part.
    for bc in (22.0, 26.0):  # holes inside the bore / breaking into it
        assert "bore" in str(raised(ValueError, build, bolt_circle=bc))
    # The measured case from the finding: a 28.6 mm bore used to build
    # clean, on a 2.70 mm boss wall, with the bolt holes 1.05 mm into it.
    assert "bore" in str(raised(ValueError, build, bore=28.6))
    # Ordering can no longer change the answer: the ring probe is contained
    # in the FINISHED part, where the old disc probe leaked its own holes.
    assert contained(_pattern_probe(BOLT_CIRCLE), build())

    # --- F6: no dimension is both a parameter and a typed constant.
    assert set(inspect.signature(build).parameters) == {"bolt_circle", "bore"}
    assert raised(TypeError, build, plate_t=3.0)  # used to blame the bolt circle

    # --- F12: the code applies the rule its comment states — EDGE_DIST of
    # metal beyond the hole WALL, not from its centre. Both bounds are
    # spelled out from the rule rather than from EDGE_REACH, so a probe
    # that reverted to measuring from the centre (which would put the limit
    # at 59.0 mm, not 54.5) fails the second one instead of moving with it.
    # 1 mm inside the limit, for the same reason main()'s sweep is: at
    # exactly 54.5 the probe's outer face is exactly on the plate edge, and
    # asking every copied project to bet its self-check on an OCCT boolean
    # returning 0.0 rather than 1e-9 is not a test, it is a coin toss. The
    # 58.0 raise below is what discriminates anyway.
    build(bolt_circle=PLATE_W - BOLT_CLEARANCE - 2 * EDGE_DIST - 1.0)  # 53.5
    assert "plate" in str(raised(ValueError, build, bolt_circle=PLATE_W - 2 * EDGE_DIST - 1))

    print("part.py self-tests passed (provenance, boss wall, bolt pattern vs bore/edge)")


if __name__ == "__main__":
    demo()
    sys.exit(main())
