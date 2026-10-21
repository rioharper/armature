"""
check/mass.py — realized mass properties, and the comparison against what
the dynamics assumed. SI out; see the unit contract in check/__init__.py.
Self-tests in mass_checks.py.
"""

from __future__ import annotations

from build123d import CenterOf


def mass_properties(part, density: float, about=None) -> dict:
    """Realized mass properties of `part`, in SI, for comparison against
    the values the dynamics assumed.

    Args:
        part: any build123d shape with volume.
        density: kg/m^3 of the chosen stock (Al 6061 = 2700, PLA = 1240,
            steel = 7850). From the ledger, not from memory.
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


def about_label(about) -> str:
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
    is a gate that reports green forever, and `{"masss": 0.0001}` is a
    gate that never fires. Also raises on:

      * a modifier stranded without the key it modifies (`com_tol` without
        `com`), and on `inertia` without `about`, which would compare a
        tensor against whatever point `mass_properties` happened to use;
      * a `target["com"]` that doesn't carry all three axes — `zip()`
        truncates, so a 1-tuple checks x and silently skips y and z;
      * a `target["inertia"]` that isn't 3x3.

    In every case the check the author was reaching for is not the check
    they would have gotten.
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
        rows = target["inertia"]
        if len(rows) != 3 or any(not hasattr(r, "__len__") or len(r) != 3 for r in rows):
            raise ValueError(
                f"compare_to_target: target['inertia'] must be a 3x3 tensor in "
                f"kg m^2, got {rows!r}"
            )
        scale = max(abs(rows[k][k]) for k in range(3))
        for i in range(3):
            for j in range(3):
                want = rows[i][j]
                got = props["inertia"][i][j]
                # OFF-DIAGONAL products of inertia are routinely ~0; a
                # fractional tolerance on them is meaningless, so gate those
                # against the trace scale instead.
                #
                # The DIAGONAL never gets that treatment, at any magnitude.
                # A slender body — every robot link — has an axial moment
                # legitimately below 1% of its transverse ones, and an
                # absolute tolerance of tol*scale there exceeds the term
                # itself by orders of magnitude. Nor does a diagonal target
                # of EXACTLY zero earn that floor: no solid body has one, so
                # a zero on the diagonal is a dropped term or a typo, never
                # a tolerance question. `_off_by` then reduces to
                # `abs(got) > 0` and says so loudly.
                if i != j and abs(want) < 0.01 * scale:
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
        if _about_key(props["about"]) != _about_key(target["about"]):
            fails.append(
                f"inertia taken about {about_label(props['about'])} but target is "
                f"about {about_label(_about_key(target['about']))} - not comparable"
            )

    return fails


_TARGET_KEYS = ("mass", "com", "com_tol", "inertia", "about")
# Keys that only mean something alongside another key; alone they are read
# by nothing, which is the same silent pass as a typo. `inertia` needs
# `about` in the other direction too: a tensor with no stated point is
# compared against whatever point the props were taken about, with nothing
# asserting the two agree.
_TARGET_NEEDS = (("com_tol", "com"), ("about", "inertia"), ("inertia", "about"))


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
