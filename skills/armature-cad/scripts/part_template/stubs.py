"""
stubs.py — envelope-correct placeholders for COTS parts, for when the
armature-librarian agent can't find a vendor STEP model.

The geometry here is trivial: a bearing is two cylinders, a motor flange is
a disc with a bolt circle. If that were all this module did it would be
five lines inline in the part file and not worth importing.

What it actually enforces is the thing that goes wrong with placeholders:
a stub that outlives its excuse. A rough bearing modeled to "about 22 mm"
gets used for a clearance check, then a stack-up, then a drawing, and by
then nobody remembers it was a guess. So every builder here REQUIRES a
`source` — the datasheet P/N and the row it came from — labels the shape
`PLACEHOLDER <p/n>` so it announces itself in any assembly or export, and
can emit its own `cad/ots-parts/index.md` row.

Placeholders are good for: envelope and clearance checks, motion sweeps,
mass estimates, deciding whether a part fits before you buy it.
They are NOT good for: mating geometry in a released assembly, tolerance
stack-ups on a fit, or anything that leaves CAD. Before release grade,
every stub is replaced by vendor geometry or by a drawing dimensioned
from the datasheet — that is what `still_placeholder()` is for.
"""

from __future__ import annotations

from build123d import BuildPart, Cylinder, Hole, Mode, PolarLocations

PLACEHOLDER_COLOR = (1.0, 0.4, 0.0, 0.6)  # orange, translucent: "not real yet"

_REGISTRY: list[tuple[str, str]] = []


def _stamp(shape, part_number: str, source: str):
    if not source:
        raise ValueError(
            f"{part_number}: a placeholder without a datasheet source is a "
            "guess with a part number on it. Pass source='<datasheet row / "
            "docs/datasheets/index.md entry>', or fetch the real model with "
            "the armature-librarian agent."
        )
    shape.label = f"PLACEHOLDER {part_number}"
    shape.color = PLACEHOLDER_COLOR
    _REGISTRY.append((part_number, source))
    return shape


def bearing(bore: float, od: float, width: float, *, part_number: str, source: str):
    """Deep-groove ball bearing envelope, mm. Origin at the bore centre,
    axis along Z. Races and shields are not modeled — this is an envelope.
    """
    with BuildPart() as bp:
        Cylinder(od / 2, width)
        Cylinder(bore / 2, width, mode=Mode.SUBTRACT)
    return _stamp(bp.part, part_number, source)


def flange(
    od: float,
    thickness: float,
    bolt_circle: float,
    bolt_count: int,
    bolt_dia: float,
    pilot_dia: float = 0.0,
    *,
    part_number: str,
    source: str,
):
    """Actuator/gearbox output flange envelope, mm. Origin at the flange
    face centre, axis along Z, body extending in -Z.

    bolt_circle is the BCD (diameter, not radius) — the single most
    commonly transposed number in a mating interface, which is why it is
    named for the datasheet's own term.
    """
    with BuildPart() as bp:
        Cylinder(od / 2, thickness)
        with PolarLocations(bolt_circle / 2, bolt_count):
            Hole(bolt_dia / 2)
        if pilot_dia:
            Hole(pilot_dia / 2)
    return _stamp(bp.part, part_number, source)


def index_rows() -> str:
    """Emit the `cad/ots-parts/index.md` rows for every stub built so far,
    so the index can't silently fall behind the geometry."""
    if not _REGISTRY:
        return ""
    lines = ["| model | P/N | source | status |", "|---|---|---|---|"]
    lines += [
        # ASCII only: this string gets printed, and a Windows cp1252
        # console garbles an em dash into a replacement character.
        f"| (build123d stub) | {pn} | {src} | PLACEHOLDER - replace before release |"
        for pn, src in _REGISTRY
    ]
    return "\n".join(lines)


def still_placeholder() -> list[str]:
    """Every stub built in this process. Call from a release-grade check:
    a non-empty list is a release gate failure, because a placeholder has
    reached a point where money is about to move."""
    return [pn for pn, _ in _REGISTRY]


def demo():
    b = bearing(22, 44, 12, part_number="6004-2RS", source="docs/datasheets/index.md#6004")
    assert abs(b.volume - (3.14159 * (22**2 - 11**2) * 12)) / b.volume < 1e-3
    assert b.label.startswith("PLACEHOLDER")

    f = flange(
        60, 6, 45, 4, 4.5, pilot_dia=22,
        part_number="AK80-9", source="docs/datasheets/index.md#ak80-9",
    )
    # Four bolt holes and one pilot bore removed from the disc.
    solid = 3.14159 * 30**2 * 6
    assert f.volume < solid, "holes were not cut"
    assert f.volume > solid * 0.7

    try:
        bearing(10, 20, 5, part_number="X", source="")
    except ValueError:
        pass
    else:
        raise AssertionError("empty source must be rejected")

    assert still_placeholder() == ["6004-2RS", "AK80-9"]
    assert "PLACEHOLDER" in index_rows()
    print("stubs.py self-tests passed (envelopes, provenance stamp, release gate)")


if __name__ == "__main__":
    demo()
