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

from build123d import CenterOf, ExportSVG, LineType, Compound, Unit

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
    and `about` naming which point the tensor is taken about.
    """
    volume_m3 = part.volume * 1e-9
    mass = volume_m3 * density

    com_mm = part.center(CenterOf.MASS)
    com = (com_mm.X * 1e-3, com_mm.Y * 1e-3, com_mm.Z * 1e-3)

    # matrix_of_inertia is volumetric (density=1) and about the COM.
    scale = density * 1e-15
    inertia = [[v * scale for v in row] for row in part.matrix_of_inertia]

    if about is None:
        about_label = "com"
    else:
        d = [about[i] * 1e-3 - com[i] for i in range(3)]
        inertia = _parallel_axis(inertia, mass, d)
        about_label = f"point {tuple(about)} mm"

    return {"mass": mass, "com": com, "inertia": inertia, "about": about_label}


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
    """
    fails = []

    if "mass" in target:
        got, want = props["mass"], target["mass"]
        if _off_by(got, want, tol):
            fails.append(
                f"mass {got * 1000:.1f} g vs target {want * 1000:.1f} g "
                f"({_pct(got, want)}, tol {tol:.0%})"
            )

    if "com" in target:
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
        for i in range(3):
            for j in range(3):
                want = target["inertia"][i][j]
                got = props["inertia"][i][j]
                # Products of inertia are routinely ~0; a fractional
                # tolerance on them is meaningless, so gate them against
                # the trace scale instead.
                scale = max(abs(target["inertia"][k][k]) for k in range(3))
                if abs(want) < 0.01 * scale:
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
        if props["about"] != target.get("about", props["about"]):
            fails.append(
                f"inertia taken about {props['about']} but target is about "
                f"{target['about']} - these are not comparable"
            )

    return fails


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

    Call it in the recipe on the feature's footprint BEFORE cutting, so
    the violation raises where the dimension is (see part.py).
    """
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


def sweep_clearance(pose, qs, ignore=(), min_volume=1e-6) -> list[tuple]:
    """Check every pair of bodies for interference across a motion range.

    Args:
        pose: callable q -> {name: shape}, positioning the bodies at
            posture q. Envelope primitives are fine and preferred here —
            this runs len(qs) * n_pairs booleans.
        qs: the postures to check. Sample the workspace, and include the
            joint limits: interference lives at the extremes.
        ignore: pairs of names that are allowed to touch, as
            {("upper_arm", "forearm"), ...} — parts sharing a joint
            overlap by design and would otherwise flood the output.
        min_volume: mm^3 below which an overlap is treated as tangency
            noise rather than a collision.

    Returns [(q, name_a, name_b, overlap_mm3), ...], worst first.
    """
    ignore = {frozenset(pair) for pair in ignore}
    hits = []
    for q in qs:
        bodies = pose(q)
        names = sorted(bodies)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if frozenset((a, b)) in ignore:
                    continue
                v = interference(bodies[a], bodies[b])
                if v > min_volume:
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

    Returns the paths written.
    """
    written = []
    bbox = part.bounding_box()
    reach = max(bbox.size.X, bbox.size.Y, bbox.size.Z) * 10 + 100

    for name in views:
        direction, up = VIEWS[name]
        origin = tuple(c * reach for c in direction)
        visible, hidden = part.project_to_viewport(origin, up)

        extent = max(Compound(children=list(visible) + list(hidden)).bounding_box().size)
        exporter = ExportSVG(unit=Unit.MM, scale=100 / extent)
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
    print(f"    inertia about {props['about']} [kg m^2]:")
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
    """Self-check: the unit conversions against a closed-form box."""
    from build123d import Box, Location

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

    # contained(): the check rebuild_sweep can't make.
    plate = Box(80, 50, 6)
    assert contained(Box(4, 4, 6).locate(Location((20, 0, 0))), plate)
    assert not contained(Box(4, 4, 6).locate(Location((20, 27, 0))), plate)
    # A feature that escapes still builds one valid solid — which is the
    # whole reason this function has to exist.
    escaped = plate.cut(Box(4, 4, 6).locate(Location((20, 27, 0))))
    assert len(escaped.solids()) == 1 and escaped.volume > 0

    # compare_to_target catches what it should and passes what it should.
    assert compare_to_target(props, {"mass": m}) == []
    assert compare_to_target(props, {"mass": m * 1.5}) != []
    assert rebuild_sweep(lambda w: Box(w, 10, 10), {"w": [5, 10, 20]}) == []
    assert rebuild_sweep(lambda w: Box(w, 10, 10), {"w": [5, -1]}) != []

    print("check.py self-tests passed (units, parallel axis, interference, targets)")


if __name__ == "__main__":
    demo()
