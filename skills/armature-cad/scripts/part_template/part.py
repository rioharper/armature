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
# Only what traces to the parameter table or an interface contract. At
# sketch grade params.py may not exist yet; fall back and say so, rather
# than blocking a definition on a derivation that hasn't run.

# Geometry is driven by INTERFACES — the datasheet numbers this part has to
# mate to. params.py drives the mass/inertia TARGET below, not the shape:
# a link length in the dynamics does not set a bracket's plate size, and
# pretending it does means inventing a conversion factor, which is exactly
# the kind of unsourced number this whole skill exists to prevent.

BOLT_CIRCLE = 45.0  # driven: actuator flange BCD, datasheet <P/N>
BORE = 22.0  # driven: bearing OD, datasheet <P/N>
EDGE_DIST = 2.0 * 4.0  # 2x bolt dia to a free edge, standard practice

# --- typed / derived dimensions ----------------------------------------
# Plain numbers, or arithmetic on a driven one. Not everything deserves to
# be a parameter — a fully parametrized one-off is fragility dressed as rigor.

PLATE_L = 80.0
PLATE_W = 75.0  # set by the bolt circle + edge distance, not by taste
PLATE_T = 6.0
BOSS_OD = BORE + 2 * 6.0  # 6 mm wall around the bearing seat
BOSS_H = 10.0
BOLT_CLEARANCE = 4.5  # M4 close clearance
CORNER_R = 6.0

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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "analysis" / "model"))
PARAM_KEY = "m1"  # the params.py entry this part's mass realizes
try:
    import params  # analysis/model/params.py — SI: metres, kilograms

    TARGET = {"mass": params.PARAMS[PARAM_KEY]}
    PROVENANCE = f"target driven from analysis/model/params.py[{PARAM_KEY}]"
except (ImportError, KeyError):
    TARGET = {"mass": 0.105}  # kg — budget row, docs/01-spec/budgets.md
    PROVENANCE = "target from budgets.md; no analysis/model/params.py yet"

# Add these once the dynamics assumes per-body values, not just a mass:
#   TARGET["com"] = (0.0, 0.0, 0.004)          # m, in the part's own frame
#   TARGET["inertia"] = [[...], [...], [...]]  # kg m^2
#   TARGET["about"] = "com"                    # or "point (0, 0, 0) mm"
TOL = 0.10


def build(
    plate_l: float = PLATE_L,
    plate_w: float = PLATE_W,
    plate_t: float = PLATE_T,
    bolt_circle: float = BOLT_CIRCLE,
    bore: float = BORE,
):
    """The build recipe, one comment per numbered step in the .md.

    Every driven dimension is a keyword argument so rebuild_sweep() can
    prove the recipe survives changing it. That IS the "model rebuilds
    cleanly after changing each driven parameter" line in Done when.
    """
    with BuildPart() as bp:
        # 1. Sketch on the mounting face plane: plate_l x plate_w centered on origin.
        with BuildSketch(Plane.XY):
            Rectangle(plate_l, plate_w)
        # 2. Extrude plate_t.
        extrude(amount=plate_t)

        # 3. Break the plate corners (before the holes, so the fillet only
        #    sees the four vertical corner edges).
        fillet(bp.edges().filter_by(Axis.Z), CORNER_R)

        # 4. Boss on the plate's top face, concentric with the bore.
        with BuildSketch(Plane.XY.offset(plate_t)):
            Circle(BOSS_OD / 2)
        extrude(amount=BOSS_H)

        # 5. 4x M4 clearance on the bolt circle (driven: flange BCD).
        #    Check the pattern lands on metal FIRST. A hole hanging off the
        #    plate edge still builds a valid solid — it just quietly removes
        #    less material — so nothing downstream would catch it.
        _assert_pattern_fits(bp.part, bolt_circle)
        with PolarLocations(bolt_circle / 2, 4):
            Hole(BOLT_CLEARANCE / 2)

        # 6. Bore through plate and boss for the bearing seat.
        Hole(bore / 2)

    if bore >= BOSS_OD:
        raise ValueError(f"bore {bore} leaves no boss wall (OD {BOSS_OD})")

    return bp.part


def _assert_pattern_fits(blank, bolt_circle: float):
    """Every bolt in the pattern must sit on metal, with its edge distance.

    The probe is exactly plate-thick and sits on the plate (Align.MIN in Z):
    a probe taller than the plate pokes out the top and bottom faces and
    reports a violation for every bolt circle, including good ones.
    """
    with BuildPart() as probe:
        with PolarLocations(bolt_circle / 2, 4):
            Cylinder(
                BOLT_CLEARANCE / 2 + EDGE_DIST,
                PLATE_T,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
    if not contained(probe.part, blank):
        raise ValueError(
            f"bolt circle {bolt_circle} mm: pattern (+{EDGE_DIST} mm edge "
            f"distance) runs off the {PLATE_L}x{PLATE_W} plate"
        )


def main() -> int:
    part = build()

    props = mass_properties(part, DENSITY, about=None)
    fails = compare_to_target(props, TARGET, tol=TOL)

    # Done when: the recipe rebuilds after changing each driven parameter.
    fails += rebuild_sweep(
        build,
        # Sweep the DRIVEN dimensions only. plate_l/plate_w are typed
        # numbers, so a sweep of them tests nothing the design promises —
        # and a plate arbitrarily shrunk 20% correctly fails the bolt
        # pattern's edge-distance check, which is a finding about the
        # sweep, not about the part.
        {
            "bolt_circle": [BOLT_CIRCLE * 0.9, BOLT_CIRCLE, BOLT_CIRCLE * 1.1],
            "bore": [BORE * 0.7, BORE, BORE * 1.3],
        },
    )

    print(f"{PART_ID} (grade: {GRADE}, {PROVENANCE})")
    ok = report(PART_ID, props, fails)

    written = write_views(part, str(Path(__file__).with_suffix("")))
    print(f"    views: {', '.join(Path(p).name for p in written)}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
