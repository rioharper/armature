"""
part.py — template for an executable build recipe.

Copy to `cad/parts/<PART-ID>.py` beside the part's `<PART-ID>.md` and edit,
and copy `part_checks.py` beside it as `<PART-ID>_checks.py` — its self-tests.
Copy `check/`, `run_all.py`, and `layout.py` into `cad/parts/` too — this file
imports `check` from its own directory — and `stubs.py` with `stubs_checks.py`
if you need COTS placeholders. Leave the template's `ledger.toml` behind: it
is the worked example's, and beside the part it would shadow the project's.
The .md is still the part definition — the contract, the loads, the
rationale, the thing a human reads. This file is only its Build recipe
section, written so a machine can run it and answer three questions the
markdown can't:

  * does the recipe actually close?  (a bolt circle that doesn't fit,
    a boss that misses, a wall that goes negative under a fillet)
  * does the part hit the mass and inertia the dynamics assumed?
  * what does it look like?  (SVG views for the "At a glance" section)

Run it:  uv run --with 'build123d~=0.11' python cad/parts/<PART-ID>.py
Exits nonzero when the part misses its target, so it works in a pre-commit
hook or CI; `python cad/parts/run_all.py` runs its self-tests with every
other module's. (The version bound is deliberate — see the template README.
The ledger is read with the standard library's tomllib, by check/ledger.py,
so a part file needs build123d and nothing else: not the engine.)

Write the measurement back, once it is worth the dynamics' re-run:

    uv run --project analysis/model --with 'build123d~=0.11' \
        python -m armature.ledger set part.<PART-ID> --from-part cad/parts/<PART-ID>.py

runs `<PART-ID>.py --mass-properties` and writes its mass, COM and inertia
into the ledger as `cad` candidates, with ORIGIN and AXES below as their
frame. A body in the description then reads them with `of`.

THE ONE RULE: this file must never restate a number that already lives in
the project's `ledger.toml` or in an interface table. It reads those.
A number typed in two places is a number that will disagree with itself,
and the .md and .py disagreeing is worse than not having the .py.

Worked example below: ARM-BRK-001, the plate-with-a-boss from the SKILL.md
recipe — 80x75x6 plate, 4x M4 clearance on a 45 mm bolt circle, central
boss bored 22 H7. Replace it with your part; keep the shape of the file.
"""

from __future__ import annotations

import json
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
    ledger,
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
# below is a dimension with two values.

# Geometry is driven by INTERFACES — the datasheet numbers this part has to
# mate to. The ledger drives the mass/inertia TARGET below, not the shape:
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

# --- the ledger ----------------------------------------------------------
# Every number below the geometry is a ledger entry's (ADR 0010): the
# project's `ledger.toml`, the nearest one at or above this file's folder.
# None of them is typed here. No ledger at all raises: without one there is
# no density to weigh the part with, and no number to put in its place.
LEDGER = ledger.find(Path(__file__).resolve().parent)

# The stock this part is cut from, by its BOM entry: kg/m^3.
DENSITY_ENTRY = "part.al-6061-t6.density"
DENSITY = ledger.value(ledger.entries(LEDGER), DENSITY_ENTRY)[0]

# The frame build() models the part in, in words, which `set --from-part`
# writes beside the measurement: the COM is measured from ORIGIN, and the
# COM and the tensor are both in AXES.
ORIGIN = "the mounting face's centre"
AXES = "X along the plate's length, Y across it, Z up the boss's axis"

# --- the target the loop closes against --------------------------------
# What the dynamics ASSUMED for this body, in SI, about the stated point:
# its mass, COM and inertia entries. If the dynamics lumped this part into a
# larger body there is no per-part tensor to invent: name the mass alone,
# set "com" and "inertia" to None, and check the lump at batch end.
#
# Point BODY at the entries of the body this part realizes and the target
# follows the derivation automatically; when the derivation is re-run the
# target moves with it, which is the entire reason not to type the number
# here. The angle brackets mean "not pointed at anything yet", which is NOT
# the same as an entry that has gone missing: an unset placeholder falls
# back and says so, while a name that was set and no longer resolves
# raises. A renamed entry is the most likely thing a re-derivation does,
# and it is exactly the event that means the loop is broken — swallowing it
# substitutes another number for a derived one and prints a line claiming
# the derivation drove it.
BODY = {
    "mass": "<ledger entry: this body's mass, such as mechanism.m2>",
    "com": "<ledger entry: its COM, a 3-vector in AXES from ORIGIN>",
    "inertia": "<ledger entry: its inertia tensor, about ABOUT in AXES>",
}
# The point the target tensor is about, in MM in this part's frame (a
# build123d-side point, as check/__init__.py's unit contract says), or None
# for the part's own COM. The entry names its point in words; PROVENANCE
# prints them, because nothing can check that the two say the same thing.
ABOUT = None
# The mass budget's line for this part, the fallback target.
BUDGET_LINE = f"budget.mass.{PART_ID}"

# The budget fallback is allowed at SKETCH grade only, where the derivation
# may genuinely not have run yet. A release-grade part whose target cannot
# be traced to the derivation must fail rather than quietly check itself
# against a budget line.
ALLOW_BUDGET_FALLBACK = GRADE == "sketch"


def _resolve_target(body: dict = BODY, allow_fallback: bool = ALLOW_BUDGET_FALLBACK,
                    ledger_path: Path = LEDGER):
    """(TARGET, PROVENANCE) for the entries `body` names, or raise saying
    why not.

    Only a BODY still all placeholders is a fallback. A KeyError (an entry
    renamed, or the budget line gone) and a ValueError (an `of` that loops,
    a tensor with no point or axes, a BODY half pointed) propagate: each
    means the ledger is there and the link to it is broken, and a broken
    link is not a reason to check the part against a different number.

    PROVENANCE says what actually happened, and is printed: the ledger file
    it read, each entry and that entry's kind, and the frame the tensor is
    stated in.
    """
    found = ledger.entries(ledger_path)
    named = {key: name for key, name in body.items() if name is not None}
    unset = [key for key, name in named.items() if name.startswith("<")]
    if unset and len(unset) < len(named):
        raise ValueError(
            f"{PART_ID}: BODY still has placeholders for {unset}; point "
            f"every target at its entry, or set it to None for a lumped body"
        )
    if named and not unset:
        target, read = {}, []
        for key, name in named.items():
            value, entry = ledger.value(found, name)  # KeyError propagates
            target[key] = tuple(value) if key == "com" else value
            read.append(f"{key} {name} ({entry.get('source', {}).get('kind', '?')})")
            if key == "inertia":
                missing = [f for f in ("point", "axes") if f not in entry]
                if missing:
                    raise ValueError(
                        f"{name}: a tensor states the point and axes it is "
                        f"about, and {missing} is missing"
                    )
                target["about"] = ABOUT
                read[-1] += f" about {entry['point']}, axes {entry['axes']}"
        return target, f"target driven from {ledger_path}: {', '.join(read)}"

    why = (f"BODY is still the placeholder for {', '.join(unset)}" if unset
           else "BODY names no entry")
    if not allow_fallback:
        raise RuntimeError(
            f"{PART_ID}: no target to check against - {why}. At grade "
            f"'{GRADE}' the budget fallback is off; point BODY at the "
            f"body this part realizes, or drop the grade back to sketch."
        )
    mass = ledger.value(found, BUDGET_LINE)[0]  # KeyError propagates
    return {"mass": mass}, f"target from {ledger_path}[{BUDGET_LINE}] - FALLBACK, {why}"


TARGET, PROVENANCE = _resolve_target()
TOL = 0.10


def build(bolt_circle: float = BOLT_CIRCLE, bore: float = BORE):
    """The build recipe, one comment per numbered step in the .md.

    Every DRIVEN dimension is a keyword argument so rebuild_sweep() can
    prove the recipe survives changing it. That IS the "model rebuilds
    cleanly after changing each driven parameter" line in Done when.

    The typed numbers — plate size, boss height, corner radius — are read
    from module scope and are deliberately NOT arguments. A number that is
    both a parameter and a constant is a number with two values: a probe
    reading module PLATE_T while build() takes a plate_t makes
    build(plate_t=3.0) blame the BOLT CIRCLE for a plate-thickness problem,
    and build(plate_t=12.0) pass on a probe that tested the bottom half.
    """
    # The seat sizes the boss, so the boss follows the `bore` ARGUMENT.
    # Frozen at module scope it follows the module BORE instead, and a
    # swept bore eats the wall down to 2.70 mm while the sweep reports PASS.
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
    own four holes (381.7 mm^3 on the worked example), so it only works
    against the blank, which makes the check silently depend on running
    before the holes and the bore are cut.

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

    Probing the blank tests clearance to the plate edge and nothing else:
    a 26 mm bolt circle breaks into the 22 mm bore, a 22 mm one puts the
    bolt holes ENTIRELY INSIDE it, and both build without complaint.
    """
    if contained(_pattern_probe(bolt_circle), part):
        return
    # Name the cause. The bore and the plate outline are both free edges to
    # this rule, and reporting the wrong one sends the reader to the wrong
    # dimension.
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


def main(argv: list[str]) -> int:
    part = build()
    props = mass_properties(part, DENSITY, about=ABOUT)

    # The export `set --from-part` runs: the measurement and its frame, one
    # JSON line and nothing else, whatever the target says of it. One
    # DENSITY: a multi-material part takes mass_properties per solid and
    # combines them (masses summed, the COM mass-weighted, each tensor
    # shifted to one point and summed), since build123d's Compound weights
    # mass() by density but neither its COM nor its tensor.
    if argv == [ledger.EXPORT]:
        print(json.dumps(ledger.export(props, PART_ID, ORIGIN, AXES)))
        return 0

    fails = compare_to_target(props, TARGET, tol=TOL)

    # Done when: the recipe rebuilds after changing each driven parameter.
    # The band is what the recipe's own edge-distance rule allows, derived
    # here rather than a decorative +-10%: below bc_min the pattern runs
    # into the bore, above bc_max off the plate, and bore_max is the same
    # rule from the bore's side. A blind +-10% reaches bc=40.5, which leaves
    # 7.0 mm of metal to the bore against the 8.0 mm this part demands — a
    # finding about the sweep's range, not about the part.
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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
