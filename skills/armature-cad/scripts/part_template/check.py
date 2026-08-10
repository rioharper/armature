"""
check.py — the checks a part definition's "Done when" section asks for,
run against build123d geometry instead of against a human's patience.

Pure library. Import it from a part file (see part.py) or from a
planning-stage scratch script; it has no CLI of its own.

    from check import mass_properties, compare_to_target, interference

THE UNIT CONTRACT — read this before touching anything below.

build123d is millimetre-native: every length you hand it and every number
it hands back is mm. `analysis/model/params.py` is SI: metres, kilograms.
Mixing them silently gives a 1000x length error and a 1e15x inertia error,
both of which look like plausible numbers. So:

  * geometry is built in mm            -> convert params at the boundary
                                          with mm(), never anywhere else
  * everything this module RETURNS is SI (m, kg, kg m^2), because that is
    what params.py and the derivation are in, and the comparison has to
    happen in the derivation's units.

The conversions, derived once so nobody has to re-derive them at 3am:

  volume   mm^3 -> m^3           x 1e-9,  then x rho [kg/m^3] -> kg
  centre   mm   -> m             x 1e-3
  inertia  build123d reports the VOLUMETRIC second moment (density = 1),
           so its units are mm^5. mm^5 -> m^5 is 1e-15, and
           [kg/m^3] * [m^5] = [kg m^2]:      x rho x 1e-15 -> kg m^2

  sanity:  10x20x30 mm aluminium (2700 kg/m^3) -> m = 0.0162 kg,
           Ixx = m/12*(0.02^2+0.03^2) = 1.755e-6 kg m^2, and
           650000 mm^5 * 2700 * 1e-15 = 1.755e-6. Checked in demo().
"""

from __future__ import annotations

import math

from build123d import CenterOf, ExportSVG, LineType, Unit

MM_PER_M = 1000.0


def mm(metres: float) -> float:
    """SI length from params.py -> mm for build123d. The only place a
    factor of 1000 is allowed to appear."""
    return metres * MM_PER_M


# --- mass properties ---------------------------------------------------


def mass_properties(part, density: float, about=None) -> dict:
    """Realized mass properties of `part`, in SI, for comparison against
    the values the dynamics assumed.

    Args:
        part: any build123d shape with volume.
        density: kg/m^3 of the chosen stock (Al 6061 = 2700, PLA = 1240,
            steel = 7850). From the BOM, not from memory.
        about: optional (x, y, z) point IN MM to report inertia about.
            Default None = about the part's own centre of mass.
            The dynamics may have used a joint origin instead — if so,
            pass it, because comparing a COM tensor against a
            joint-origin tensor is a comparison of two unrelated numbers.

    Returns dict with mass [kg], com [m, 3-tuple], inertia [kg m^2, 3x3],
    and `about` naming which point the tensor is taken about: None for the
    part's own COM, else the (x, y, z) tuple in mm. It is stored as a TUPLE,
    not as a formatted label, so `compare_to_target` compares it
    structurally — as a string, a target written (50, 0, 0) reads
    'point (50, 0, 0) mm' against this module's 'point (50.0, 0, 0) mm' and
    false-fails on the rendering of a number rather than on the number.
    `report()` renders the label at print time instead.
    """
    volume_m3 = part.volume * 1e-9
    mass = volume_m3 * density

    com_mm = part.center(CenterOf.MASS)
    com = (com_mm.X * 1e-3, com_mm.Y * 1e-3, com_mm.Z * 1e-3)

    # matrix_of_inertia is volumetric (density=1) and about the COM.
    scale = density * 1e-15
    inertia = [[v * scale for v in row] for row in part.matrix_of_inertia]

    if about is not None:
        d = [about[i] * 1e-3 - com[i] for i in range(3)]
        inertia = _parallel_axis(inertia, mass, d)

    return {"mass": mass, "com": com, "inertia": inertia, "about": _about_key(about)}


def _about_key(about):
    """Normalize an `about` point so (50, 0, 0), [50.0, 0, 0] and the tuple
    a props dict carries all compare equal. None means the COM."""
    if about is None:
        return None
    try:
        x, y, z = about
        return (float(x), float(y), float(z))
    except (TypeError, ValueError) as exc:
        # Catches the old formatted-string form ("com", "point (0, 0, 0) mm")
        # loudly instead of comparing it as an opaque blob.
        raise ValueError(
            f"`about` must be None (the part's COM) or an (x, y, z) point in mm, "
            f"got {about!r}"
        ) from exc


def _about_label(about) -> str:
    """Human-readable name for the point a tensor is taken about, for print."""
    return "com" if about is None else f"point {tuple(about)} mm"


def _parallel_axis(i_com, mass, d):
    """Shift an inertia tensor from the COM to a point offset by d [m].

    I_P = I_com + m * ((d.d) * identity - outer(d, d))
    """
    dd = sum(x * x for x in d)
    return [
        [i_com[r][c] + mass * ((dd if r == c else 0.0) - d[r] * d[c]) for c in range(3)]
        for r in range(3)
    ]


def compare_to_target(props: dict, target: dict, tol: float = 0.10) -> list[str]:
    """Compare realized mass properties against the dynamics' assumption.

    `target` uses the same keys and units as `mass_properties` returns, and
    only needs the keys you actually want checked — a part the dynamics
    lumped into a larger body has a mass budget and no inertia tensor, so
    give it {"mass": ...} alone rather than inventing a tensor for it.

    tol is fractional (0.10 = 10%). Returns a list of human-readable
    failures; empty list means the loop closes.

    Raises on a target that cannot check anything — empty, or all typos.
    Every branch below is `if "<key>" in target`, so an unvalidated target
    is a gate that reports green forever: `{"masss": 0.0001}` used to pass.
    Also raises on a modifier left stranded without the key it modifies
    (`com_tol` without `com`, `about` without `inertia`): the check the
    author was reaching for is not the check they would have gotten.
    """
    _validate_target(target)
    fails = []

    if "mass" in target:
        got, want = props["mass"], target["mass"]
        if _off_by(got, want, tol):
            fails.append(
                f"mass {got * 1000:.1f} g vs target {want * 1000:.1f} g "
                f"({_pct(got, want)}, tol {tol:.0%})"
            )

    if "com" in target:
        # zip() truncates: a 1-tuple used to check x and silently skip y, z.
        if len(target["com"]) != 3:
            raise ValueError(
                f"compare_to_target: target['com'] needs all 3 axes in m, "
                f"got {len(target['com'])}: {target['com']!r}"
            )
        for axis, got, want in zip("xyz", props["com"], target["com"]):
            # COM is compared on an absolute scale, not fractional: a
            # target of 0.0 on an axis has no percentage to be off by.
            if abs(got - want) > target.get("com_tol", 0.002):
                fails.append(
                    f"com {axis} {got * 1000:.1f} mm vs target "
                    f"{want * 1000:.1f} mm (tol "
                    f"{target.get('com_tol', 0.002) * 1000:.1f} mm)"
                )

    if "inertia" in target:
        scale = max(abs(target["inertia"][k][k]) for k in range(3))
        for i in range(3):
            for j in range(3):
                want = target["inertia"][i][j]
                got = props["inertia"][i][j]
                # OFF-DIAGONAL products of inertia are routinely ~0; a
                # fractional tolerance on them is meaningless, so gate those
                # against the trace scale instead.
                #
                # The DIAGONAL never gets that treatment (`i != j`), even
                # when it is small. A slender body — every robot link — has
                # an axial moment legitimately below 1% of its transverse
                # ones, and an absolute tolerance of tol*scale there exceeds
                # the term itself by orders of magnitude. A 400x8x8 bar
                # target vs a realized 30 mm OD tube is 20x wrong on Ixx and
                # used to report a clean pass. A diagonal that is EXACTLY
                # zero has no fraction to take (and no solid body has one),
                # so it gets the absolute floor and nothing else does.
                if (i != j and abs(want) < 0.01 * scale) or (i == j and want == 0.0):
                    if abs(got - want) > tol * scale:
                        fails.append(
                            f"inertia[{i}][{j}] {got:.3e} vs target ~0 "
                            f"(> {tol:.0%} of {scale:.3e})"
                        )
                elif _off_by(got, want, tol):
                    fails.append(
                        f"inertia[{i}][{j}] {got:.3e} vs target {want:.3e} "
                        f"({_pct(got, want)}, tol {tol:.0%})"
                    )
        if _about_key(props["about"]) != _about_key(target.get("about", props["about"])):
            fails.append(
                f"inertia taken about {_about_label(props['about'])} but target is "
                f"about {_about_label(_about_key(target['about']))} - not comparable"
            )

    return fails


_TARGET_KEYS = ("mass", "com", "com_tol", "inertia", "about")
# Keys that only mean something alongside another key; alone they are read
# by nothing, which is the same silent pass as a typo.
_TARGET_NEEDS = (("com_tol", "com"), ("about", "inertia"))


def _validate_target(target: dict) -> None:
    unknown = sorted(set(target) - set(_TARGET_KEYS))
    if unknown:
        raise ValueError(
            f"compare_to_target: unknown target key(s) {unknown}; "
            f"recognized keys are {list(_TARGET_KEYS)}"
        )
    if not {"mass", "com", "inertia"} & set(target):
        raise ValueError(
            f"compare_to_target: target {dict(target)} checks nothing. Give it at "
            f"least one of mass, com, inertia - an empty target is a green gate."
        )
    for key, needs in _TARGET_NEEDS:
        if key in target and needs not in target:
            raise ValueError(
                f"compare_to_target: target['{key}'] does nothing without "
                f"target['{needs}']"
            )


def _off_by(got, want, tol):
    return abs(got - want) > tol * abs(want)


def _pct(got, want):
    return f"{(got - want) / want:+.1%}" if want else "n/a"


# --- the recipe actually builds ----------------------------------------


def contained(inner, outer, tol: float = 1e-6) -> bool:
    """True if `inner` lies entirely inside `outer`.

    This is the check `rebuild_sweep` alone cannot make. A feature that
    escapes its parent — a bolt hole hanging off a plate edge, a boss
    overhanging its flange — still produces one valid solid with the same
    bounding box, and a hole that's half outside removes LESS material, so
    volume goes up rather than down. Nothing about the build fails. The
    part is simply wrong.

    Call it in the recipe on a SOLID probe of the feature: the shape that
    has to BE metal, extruded. Prefer a probe that stays valid against the
    FINISHED part — part.py's `_assert_pattern_fits` probes the RING of
    metal around each bolt hole rather than a disc over it, and so runs
    after every cut. A probe only valid against the blank has to run before
    the cut, and nothing in the code can say so: that unstated ordering is
    what let a bolt circle whose holes sat inside the bore pass.

    `inner` must be a solid. This measures the leaked VOLUME, and a sketch,
    face or wire has none, so a flat probe would read as contained from
    500 mm away. That is why it raises rather than returning True.

    tol is the leak volume in mm^3 tolerated as boolean noise. Measured on
    build123d 0.11.1 / OCCT: a probe whose face is coincident with an R6
    fillet — plus both flat faces — leaks EXACTLY 0.0 mm^3. The noise floor
    at a filleted corner is zero, not merely small, so the 1e-6 default is
    absorbing nothing and nothing measured here argues for a larger one.
    Keep it small for that reason: every mm^3 of tol is a real escape this
    would not report (see demo(), which measures both).
    """
    if inner.volume <= 0:
        raise ValueError(
            "contained(): `inner` has no volume, so there is nothing to test - "
            "pass a solid probe of the feature, not a sketch, face or wire."
        )
    leak = inner.cut(outer)
    if leak is None:
        return True
    return sum(s.volume for s in leak.solids()) <= tol


def rebuild_sweep(build, cases: dict[str, list]) -> list[str]:
    """"The model rebuilds cleanly after changing each driven parameter."

    `build` is a callable taking keyword overrides and returning the part.
    `cases` maps a driven parameter name to the values to try. Each value
    is built on its own; a build that raises, returns None, or produces
    zero volume is a recipe that only works at its nominal numbers.

    Returns a list of failures; empty means every driven parameter rebuilds.
    """
    fails = []
    for name, values in cases.items():
        for value in values:
            try:
                part = build(**{name: value})
            except Exception as exc:  # noqa: BLE001 - any failure is the finding
                fails.append(f"{name}={value}: rebuild raised {type(exc).__name__}: {exc}")
                continue
            if part is None or part.volume <= 0:
                fails.append(f"{name}={value}: rebuilt to empty geometry")
    return fails


# --- interference ------------------------------------------------------


def interference(a, b) -> float:
    """Overlap volume of two shapes in mm^3. 0.0 means they clear.

    Cheap enough to run over a whole motion sweep, which is the point:
    at the kinematics or planning stage the parts are still crude
    envelopes and this is the only clearance check available.
    """
    common = a.intersect(b)
    if common is None:
        return 0.0
    return sum(s.volume for s in common.solids())


def sweep_clearance(pose, qs, ignore=None, min_volume=1e-6) -> list[tuple]:
    """Check every pair of bodies for interference across a motion range.

    Args:
        pose: callable q -> {name: shape}, positioning the bodies at
            posture q. Envelope primitives are fine and preferred here —
            this runs len(qs) * n_pairs booleans.
        qs: the postures to check. Sample the workspace, and include the
            joint limits: interference lives at the extremes.
        ignore: {frozenset({"upper_arm", "forearm"}): threshold_mm3, ...}
            — a pair sharing a joint can overlap there even when nothing
            is wrong (e.g. a base post's radius reaching past the joint
            into the next link, by construction). Give the OVERLAP
            MEASURED AT THE PAIR'S OWN DESIGN/NEUTRAL POSTURE as the
            threshold, not a guessed margin — sweep.py derives it by
            calling `pose()` once at the home posture and taking
            `interference()` for the ONE pair that fits this mechanism
            (see below — most pairs don't), so the excuse is sized to
            what the envelope actually does at rest, not picked by feel.
            Overlap ABOVE the threshold is reported like any other pair,
            at whatever posture it happens.

            This replaces a plain set of always-ignored pairs, which hid
            the dominant self-collision class on a worked 2R arm (F7): a
            pair sharing a joint also has the widest range of legitimate
            relative motion, so a blanket "never report this pair"
            suppressed the elbow's actual fold-in collision at every
            posture, not only the one where the design excuses it — a
            link1<->link2 overlap that grew to 18689 mm^3 partway through
            the swept range went unreported while a smaller, unrelated
            5321.8 mm^3 base<->link2 fold WAS reported, because only the
            latter pair happened not to be on the blanket list. (Fix round
            4: this read "300000 mm^3 base<->link2" and was wrong twice
            over. 300000 was link1<->link2's OWN fully-folded overlap, not
            base<->link2's — misattributed, and large enough to make the
            sentence call it "smaller" than the 18689 it was contrasted
            with. base<->link2's fold measures 5321.8 mm^3, unchanged by
            JOINT_TRIM, which trims the elbow end of link2 rather than the
            far end that reaches the post. link1<->link2's 300000 is now
            276000 for the same reason; see sweep.py's JOINT_TRIM.)

            A THRESHOLD MEASURED AT ONE POSTURE ONLY FITS A PAIR WHOSE
            OVERLAP DOES NOT CHANGE WITH POSTURE. sweep.py's own worked
            example is the cautionary tale: link1<->link2's overlap is
            0.0 mm^3 at the neutral posture and GROWS with the elbow's
            bend, so a threshold measured at neutral excuses effectively
            nothing (round 1 of this fix used exactly that measurement and
            flagged 98.2% of the swept grid — the flood the blanket
            `ignore` existed to avoid, back under a different name). A
            pair like that needs its excuse built into the GEOMETRY
            instead — sweep.py's `JOINT_TRIM` sets link2's box back from
            the elbow so it has a real gap to bend through before it
            overlaps at all, which is what a threshold, measured at any
            single posture, cannot give it. Use `ignore` only for a pair
            you have checked behaves like base<->link1 here: the SAME
            overlap at every posture the pair reaches, not merely the
            smallest one.

            RESIDUAL BLIND SPOT, for a pair that DOES fit `ignore`: it is
            excused up to its threshold volume at EVERY posture in the
            sweep, not only near the joint. A genuine collision whose
            volume is smaller than that pair's own design overlap is
            invisible wherever it occurs. This is harmless for a pair
            whose design overlap is the SAME at every posture that reaches
            it (e.g. one fixed by a rotationally-symmetric envelope, as
            base<->link1 is in sweep.py's worked example) — there, the
            threshold can never be smaller than what is already there
            while something else is wrong. It is a real gap for any other
            pair, which is exactly why a growing-overlap pair belongs in
            geometry, not in this dict.

            A GEOMETRIC excuse (a trim, a rounded corner) has a DIFFERENT
            residual blind spot than a threshold, and it is not this one
            (Important C, fix round 3): it removes material from the
            model, so a collision between that missing material and ANY
            body — not only the pair it was trimmed for — is invisible,
            because there is nothing there to test. sweep.py's `JOINT_TRIM`
            documents this explicitly next to where it's applied; a `.py`
            that adds a geometric excuse of its own needs the same
            disclosure, in that file, not just here.
        min_volume: mm^3 below which an overlap is discarded as a boolean
            sliver — the floor every pair gets, including one named in
            `ignore` with a smaller threshold. NOT a tangency floor — OCC
            reports exact tangency as exactly 0.0 (measured on 0.11.1:
            coincident faces, a touched edge, and a cylinder tangent to a
            plane all return 0.0), so tangency never reaches this test.
            Nor is the default a meaningful envelope filter: 0.0001 mm of
            interpenetration between two 10 mm cubes measures 0.01 mm^3,
            ten thousand times this default, so every real contact is
            reported. It exists only to drop slivers, and it is
            deliberately left where it swallows nothing physical. Raise it
            if you want shallow grazes ignored, and pick the number from
            the graze depth you'll accept. This is the ONLY floor a pair
            with no `ignore` entry gets (a bare `v > min_volume`, exactly
            as documented above) — it is not doubled for those pairs; see
            below for the one that does get more.

            A pair NAMED in `ignore` gets `min_volume` a second time, as a
            floating-point slop guard on its threshold (Critical 1, fix
            round 2 — Minor, fix round 3: this note used to read as
            applying to every pair, doubling the floor for ordinary ones
            without saying so): a threshold IS the OCC volume measured at
            one posture, and recomputing "the same" boolean at a different
            posture can differ in the last bits (measured on sweep.py's
            base<->link1: +2.18e-11 / -1.46e-11 mm^3 across 37 samples of
            the SAME nominal overlap). A bare `v > threshold` reports that
            noise as a collision — 444 of round 1's 1924 hits were exactly
            this. `min_volume`'s default (1e-6) is ~1e5x that measured
            noise and still ~1e4x below the shallowest real contact this
            module measures (0.01 mm^3, see demo()'s F15 case), so it
            swallows the float noise and nothing physical either way.

    Returns [(q, name_a, name_b, overlap_mm3), ...], worst first.
    """
    ignore = {} if ignore is None else {frozenset(pair): float(v) for pair, v in ignore.items()}
    hits = []
    for q in qs:
        bodies = pose(q)
        names = sorted(bodies)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                v = interference(bodies[a], bodies[b])
                key = frozenset((a, b))
                if key in ignore:
                    # Critical 1: `ignore[key]` IS a measured OCC volume,
                    # not an exact mathematical constant - compare with
                    # min_volume's slop, not bit-exact, or a recomputation
                    # of "the same" overlap a few ULPs off false-reports.
                    threshold = ignore[key] + min_volume
                else:
                    # Minor (fix round 3): an ordinary pair keeps exactly
                    # min_volume, not min_volume*2 - there is no separate
                    # measurement here for float noise to creep in between.
                    threshold = min_volume
                if v > threshold:
                    hits.append((q, a, b, v))
    return sorted(hits, key=lambda h: -h[3])


# --- the picture -------------------------------------------------------

VIEWS = {
    # name: (camera origin direction, up) — orthographic-ish standard views.
    "front": ((0, -1, 0), (0, 0, 1)),
    "top": ((0, 0, 1), (0, 1, 0)),
    "right": ((1, 0, 0), (0, 0, 1)),
    "iso": ((1, -1, 1), (0, 0, 1)),
}


def write_views(part, path_stem: str, views=("front", "top", "right", "iso")) -> list[str]:
    """Write orthographic SVG views with hidden lines, for the part
    definition's "At a glance" section.

    A crude picture orients a modeler faster than a paragraph, and this one
    is not crude — it is the real projected geometry, so it cannot drift
    from the recipe the way a hand-drawn ASCII sketch does.

    The views are exported at scale 1: the SVG declares millimetres and
    they are the projection's own millimetres, and every view in the set
    shares that one scale. Normalizing each view to a fixed size — the
    obvious thing, and what this did — rescales each view independently by
    its own extent, which drew the same 6 mm plate at 7.50 mm in the front
    view and 8.00 mm in the right one while still declaring Unit.MM.

    MEASURE OFF front/top/right ONLY. Those three are true 1:1 against the
    PART, because each looks down a principal axis, so a feature measured
    off the page is the part's real millimetres (demo() checks exactly
    that, on a shared dimension across two views). The 'iso' view is 1:1
    only in its own projection plane: an isometric projection foreshortens
    every 3D length, so a number scaled off it is wrong even though the SVG
    says mm just as confidently. The iso is for orientation.

    The camera is aimed at the bounding-box centre, not at the origin.
    `project_to_viewport` defaults `look_at` to the shape's centre, so a
    camera parked on a bare axis direction views an off-origin part along a
    slightly TILTED axis and the projection is no longer 1:1 in either
    direction: a 16 mm-tall part measured 16.67 mm in its front view.

    Returns the paths written.
    """
    written = []
    bbox = part.bounding_box()
    centre = bbox.center()
    reach = max(bbox.size.X, bbox.size.Y, bbox.size.Z) * 10 + 100

    for name in views:
        direction, up = VIEWS[name]
        origin = tuple(c + d * reach for c, d in zip(tuple(centre), direction))
        visible, hidden = part.project_to_viewport(origin, up, look_at=centre)

        exporter = ExportSVG(unit=Unit.MM)  # scale left at 1: true 1:1
        exporter.add_layer("Visible")
        exporter.add_layer("Hidden", line_color=(99, 99, 99), line_type=LineType.ISO_DOT)
        exporter.add_shape(visible, layer="Visible")
        exporter.add_shape(hidden, layer="Hidden")

        out = f"{path_stem}-{name}.svg"
        exporter.write(out)
        written.append(out)
    return written


# --- report ------------------------------------------------------------


def report(name: str, props: dict, fails: list[str]) -> bool:
    """Print one part's result. Returns True if it passed."""
    print(f"--- {name}")
    print(f"    mass      {props['mass'] * 1000:9.2f} g")
    print("    com       " + "  ".join(f"{c * 1000:8.2f}" for c in props["com"]) + "  mm")
    print(f"    inertia about {_about_label(props['about'])} [kg m^2]:")
    for row in props["inertia"]:
        print("      " + "  ".join(f"{v: .4e}" for v in row))
    if fails:
        print(f"    FAIL ({len(fails)}):")
        for f in fails:
            print(f"      - {f}")
    else:
        print("    ok")
    return not fails


def demo():
    """Self-check: the unit conversions against a closed-form box, plus one
    assertion per red-team finding this file was fixed for. Each of those is
    written to FAIL if its fix is reverted — they are the fix's only guard."""
    import re
    import tempfile
    from pathlib import Path

    from build123d import Axis, Box, Cylinder, Location, Rectangle

    def raises(fn, *args, **kwargs) -> bool:
        """A check handed nothing must say so, not report green."""
        try:
            fn(*args, **kwargs)
        except ValueError:
            return True
        return False

    rho = 2700.0  # aluminium 6061
    box = Box(10, 20, 30)
    props = mass_properties(box, rho)

    m = 10 * 20 * 30 * 1e-9 * rho
    assert math.isclose(props["mass"], m, rel_tol=1e-9), props["mass"]

    ixx = m / 12 * (0.020**2 + 0.030**2)
    assert math.isclose(props["inertia"][0][0], ixx, rel_tol=1e-9), props["inertia"][0][0]

    # Parallel axis: shifting to a point 50 mm off in x must not change
    # Ixx (the offset is along x) but must add m*d^2 to Iyy and Izz.
    off = mass_properties(box, rho, about=(50, 0, 0))
    assert math.isclose(off["inertia"][0][0], ixx, rel_tol=1e-9)
    iyy = m / 12 * (0.010**2 + 0.030**2) + m * 0.050**2
    assert math.isclose(off["inertia"][1][1], iyy, rel_tol=1e-9), off["inertia"][1][1]

    # Translating the part must not change its COM-referenced inertia.
    moved = mass_properties(Box(10, 20, 30).locate(Location((7, -3, 11))), rho)
    assert math.isclose(moved["inertia"][0][0], ixx, rel_tol=1e-9)
    assert math.isclose(moved["com"][0], 0.007, abs_tol=1e-12)

    # Interference: overlapping, disjoint, and face-touching.
    a = Box(10, 10, 10)
    assert math.isclose(interference(a, Box(10, 10, 10).locate(Location((5, 0, 0)))), 500.0)
    assert interference(a, Box(1, 1, 1).locate(Location((100, 0, 0)))) == 0.0
    assert interference(a, Box(10, 10, 10).locate(Location((10, 0, 0)))) == 0.0

    # F15: min_volume is NOT a tangency floor. These two measurements are
    # exactly what sweep_clearance's docstring now claims — tangency reads
    # as 0.0 (above), and the shallowest real interpenetration reads four
    # orders ABOVE the 1e-6 default, so the default filters nothing
    # physical. If either number moves, that docstring has gone stale.
    grazed = interference(a, Box(10, 10, 10).locate(Location((10 - 1e-4, 0, 0))))
    assert 0.009 < grazed < 0.011, grazed  # 0.0001 mm deep over 10x10 mm

    # F7: sweep_clearance's `ignore` is a per-pair THRESHOLD, not a
    # blanket "always skip". Two 10 mm boxes overlapping 200 mm^3 at their
    # design offset must clear; the SAME pair overlapping 500 mm^3 at a
    # bigger offset (further apart at the far end, closer at the near
    # end — the geometry doesn't matter, only that it exceeds the design
    # overlap) must still be reported, which the old set-based `ignore`
    # could never do once a pair was listed.
    def two_boxes(offset):
        return {
            "a": Box(10, 10, 10),
            "b": Box(10, 10, 10).locate(Location((10 - offset, 0, 0))),
        }

    design_overlap = interference(two_boxes(2.0)["a"], two_boxes(2.0)["b"])
    assert math.isclose(design_overlap, 200.0), design_overlap
    pair_ignore = {frozenset(("a", "b")): design_overlap}
    hits = sweep_clearance(two_boxes, [2.0, 5.0], ignore=pair_ignore)
    assert len(hits) == 1 and hits[0][1:3] == ("a", "b") and math.isclose(hits[0][3], 500.0), hits
    # A pair with no entry in `ignore` gets only the ordinary min_volume
    # floor, not the pair's design overlap — the same 200 mm^3 that was
    # excused above is reported here.
    hits = sweep_clearance(two_boxes, [2.0], ignore={})
    assert len(hits) == 1 and hits[0][1:3] == ("a", "b") and math.isclose(hits[0][3], 200.0), hits

    # Critical 1 (fix round 2): a threshold IS a measured OCC volume, and
    # recomputing "the same" boolean elsewhere can differ by float noise
    # (measured on sweep.py's base<->link1: ~2e-11 mm^3). A threshold that
    # is a hair BELOW what gets measured at the excused posture must not
    # cause a false report — min_volume's slop absorbs it.
    noisy_ignore = {frozenset(("a", "b")): design_overlap - 1e-10}
    assert sweep_clearance(two_boxes, [2.0], ignore=noisy_ignore) == []

    # contained(): the check rebuild_sweep can't make.
    plate = Box(80, 50, 6)
    assert contained(Box(4, 4, 6).locate(Location((20, 0, 0))), plate)
    assert not contained(Box(4, 4, 6).locate(Location((20, 27, 0))), plate)
    # A feature that escapes still builds one valid solid — which is the
    # whole reason this function has to exist.
    escaped = plate.cut(Box(4, 4, 6).locate(Location((20, 27, 0))))
    assert len(escaped.solids()) == 1 and escaped.volume > 0

    # F4: contained() summed leak.solids(), and a sketch, face or wire has
    # none — so a flat probe read as contained from 500 mm away. It must
    # raise instead, because a zero-volume probe checked nothing.
    assert raises(contained, Rectangle(4, 4).locate(Location((500, 0, 0))), plate)
    assert raises(contained, plate.faces().sort_by(Axis.Z)[-1], plate)

    # F17: is tol=1e-6 mm^3 actually above OCC's sliver noise? The worked
    # example never drives a probe at the filleted corners, which is where
    # booleans leave slivers, so measure it here. This probe's cylindrical
    # face is coincident with the R6 fillet AND its flat faces are coplanar
    # with the plate's — the worst tangency this template can produce.
    rounded = Box(80, 50, 6)
    rounded = rounded.fillet(6.0, rounded.edges().filter_by(Axis.Z))
    flush = Cylinder(6, 6).locate(Location((80 / 2 - 6, 50 / 2 - 6, 0)))
    spill = flush.cut(rounded)
    sliver = 0.0 if spill is None else sum(s.volume for s in spill.solids())
    # Measured, build123d 0.11.1 / OCCT: exactly 0.0 mm^3 — the floor is
    # zero, not merely small, so tol is doing no work here and must not be
    # raised to where it starts swallowing real escapes like the one below.
    assert sliver < 1e-9, f"OCC sliver at an R6 fillet is {sliver} mm^3, above tol"
    assert contained(flush, rounded)
    # .located(), not .locate(): the latter moves `flush` in place, which
    # would make this block depend on the order its assertions run in.
    assert not contained(flush.located(Location((80 / 2 - 5.9, 50 / 2 - 5.9, 0))), rounded)

    # compare_to_target catches what it should and passes what it should.
    assert compare_to_target(props, {"mass": m}) == []
    assert compare_to_target(props, {"mass": m * 1.5}) != []
    assert rebuild_sweep(lambda w: Box(w, 10, 10), {"w": [5, 10, 20]}) == []
    assert rebuild_sweep(lambda w: Box(w, 10, 10), {"w": [5, -1]}) != []

    # F2: a slender body — every robot link — has an axial moment
    # legitimately far below its transverse ones. Gating the DIAGONAL
    # against the trace scale, the treatment off-diagonal products need,
    # buys it an absolute tolerance bigger than the term itself. This
    # 400x8x8 bar target vs a realized 30 mm OD tube is 20x wrong on Ixx
    # (7.37e-07 against 1.49e-05) and used to return [].
    bar = mass_properties(Box(400, 8, 8), rho)
    tube = Cylinder(15, 400).cut(Cylinder(14.3, 400)).rotate(Axis.Y, 90)
    tube_props = mass_properties(tube, rho)
    assert tube_props["inertia"][0][0] / bar["inertia"][0][0] > 20
    slender = compare_to_target(tube_props, {"inertia": bar["inertia"]})
    assert any("inertia[0][0]" in f for f in slender), slender
    # ...while an off-diagonal product still gets its absolute tolerance,
    # which is the whole reason that branch exists.
    near_zero = [row[:] for row in bar["inertia"]]
    # Guard the guard: this only proves anything while the realized Ixy is
    # nonzero (OCC leaves ~1e-22). If a future OCCT returns an exact 0.0 the
    # control would pass vacuously, comparing 0.0 against 0.0.
    assert bar["inertia"][0][1] != 0.0
    near_zero[0][1] = near_zero[1][0] = 0.0
    assert compare_to_target(bar, {"inertia": near_zero}) == []

    # F3: a target that can check nothing is a permanently green gate.
    assert raises(compare_to_target, props, {})
    assert raises(compare_to_target, props, {"masss": 0.0001})
    assert raises(compare_to_target, props, {"com_tol": 0.001})
    assert raises(compare_to_target, props, {"mass": m, "com_tol": 0.001})
    assert raises(compare_to_target, props, {"mass": m, "about": None})

    # F14a: zip() truncates, so a short com used to check x and silently
    # skip y and z.
    assert raises(compare_to_target, props, {"com": (0.0,)})
    assert compare_to_target(props, {"com": props["com"]}) == []

    # F14b: `about` is a structural point, not a formatted string. A target
    # written (50, 0, 0) has to match a tensor taken about (50.0, 0, 0);
    # compared as text those render differently and false-FAIL, and the
    # commented template in part.py suggests exactly that text.
    assert off["about"] == (50.0, 0.0, 0.0)
    assert compare_to_target(off, {"inertia": off["inertia"], "about": (50, 0, 0)}) == []
    assert compare_to_target(off, {"inertia": off["inertia"], "about": [50.0, 0, 0]}) == []
    # A genuine mismatch — COM tensor vs joint-origin tensor — still fails.
    assert compare_to_target(off, {"inertia": off["inertia"], "about": None}) != []
    # The old string form is rejected loudly, not compared as an opaque blob.
    assert raises(compare_to_target, off, {"inertia": off["inertia"], "about": "com"})

    # F8: the views are 1:1, so a shared dimension measures the same in
    # every view of the set. Rescaling each view by its own extent drew this
    # part's 80 mm width as 100.09 mm, and its one 16 mm height as two
    # different numbers. Off-origin on purpose: that is what tilts a camera
    # aimed by direction alone, and a tilted view is not 1:1 either.
    tall = Box(80, 75, 16).locate(Location((0, 0, 8)))
    with tempfile.TemporaryDirectory() as tmp:
        size = {}
        for path in write_views(tall, str(Path(tmp) / "v"), views=("front", "right")):
            # The DECLARED size, not the viewBox: the viewBox stays in model
            # units whatever `scale` is, so it is exactly the number that
            # cannot catch this bug.
            wh = re.search(r'width="([\d.]+)mm"\s+height="([\d.]+)mm"', Path(path).read_text())
            size[Path(path).stem.split("-")[-1]] = tuple(float(v) for v in wh.groups())
    pad = 0.09  # ExportSVG fit_to_stroke pads the box by one line weight
    assert math.isclose(size["front"][0], 80 + pad, abs_tol=0.01), size
    assert math.isclose(size["right"][0], 75 + pad, abs_tol=0.01), size
    # The SAME 16 mm dimension, measured off two different views.
    assert math.isclose(size["front"][1], size["right"][1], abs_tol=1e-6), size
    assert math.isclose(size["front"][1], 16 + pad, abs_tol=0.01), size

    print(
        "check.py self-tests passed (units, parallel axis, interference, "
        "containment, target validation, view scale)"
    )


if __name__ == "__main__":
    demo()
