"""
check/views.py — the picture: true-scale orthographic SVG views for the
part definition's "At a glance" section. Self-tests in views_checks.py.
"""

from __future__ import annotations

from build123d import ExportSVG, LineType, Unit

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
    shares that one scale. Do not normalize each view to a fixed size —
    the obvious thing — because that rescales each view independently by
    its own extent, which draws the same 6 mm plate at 7.50 mm in the
    front view and 8.00 mm in the right one while still declaring Unit.MM.

    MEASURE OFF front/top/right ONLY. Those three are true 1:1 against the
    PART, because each looks down a principal axis, so a feature measured
    off the page is the part's real millimetres (views_checks.py checks
    exactly that, on a shared dimension across two views). The 'iso' view
    is 1:1 only in its own projection plane: an isometric projection
    foreshortens every 3D length, so a number scaled off it is wrong even
    though the SVG says mm just as confidently. The iso is for orientation.

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
        exporter.add_layer("Hidden", line_color=(0.39, 0.39, 0.39),  # 0-1: 0.13 deprecates 0-255
                           line_type=LineType.ISO_DOT)
        exporter.add_shape(visible, layer="Visible")
        exporter.add_shape(hidden, layer="Hidden")

        out = f"{path_stem}-{name}.svg"
        exporter.write(out)
        written.append(out)
    return written
