"""
Where a drawing's views go on the sheet: the scale from a standard series
that fits the part's box in the views' room, and each view's centre from
the outlines SOLIDWORKS reports. Pure Python, mm on the sheet throughout.

The default rooms are fractions of the sheet, read off an A3 landscape
sheet with an ISO title block bottom right: the orthographic views in the
upper left, the isometric in the upper right, the notes below the views.
Pass your own `Rooms` for another sheet format.
"""
from __future__ import annotations

from dataclasses import dataclass

# ISO 5455's preferred scales, largest first
SERIES = ((5, 1), (2, 1), (1, 1), (1, 2), (1, 5), (1, 10), (1, 20))


@dataclass(frozen=True)
class Rooms:
    views: tuple      # x0, x1, y0, y1: the orthographic views' room (mm on the sheet)
    iso: tuple        # cx, cy, size: the isometric's centre and the square it fits in
    notes: tuple      # x, y of the notes' first line, and the pitch between lines
    gap: float = 4.0  # between view outlines, which carry a few mm of margin of their own

    @staticmethod
    def for_sheet(width, height, dims=False):
        """The default rooms for a sheet `width` x `height` mm. A sheet with dimensions on its
        views leaves them more room: a wider gap and an inset room."""
        w, h = width, height
        views = (0.038 * w, 0.714 * w, 0.458 * h, 0.963 * h)
        if dims:
            views = (0.081 * w, 0.714 * w, 0.485 * h, 0.949 * h)
        return Rooms(views=views, iso=(0.869 * w, 0.690 * h, 0.238 * w),
                     notes=(0.038 * w, 0.438 * h, 4.2), gap=18.0 if dims else 4.0)


def first_scale(box, room, gap, show=("*Top", "*Right")):
    """The index in SERIES of the largest scale at which the front view (X by Y) and those of
    the top (X by Z) and right (Z by Y) in `show` fit `room` side by side, by the part's box
    (x, y, z spans, mm). Outlines carry margins of their own, so this is a first guess that
    the real outlines then confirm."""
    x, y, z = box
    x0, x1, y0, y1 = room
    top, right = "*Top" in show, "*Right" in show
    for i, (num, den) in enumerate(SERIES):
        k = num / den
        if (k * (x + z * right) + gap * right <= x1 - x0
                and k * (y + z * top) + gap * top <= y1 - y0):
            return i
    return len(SERIES) - 1


def iso_scale(box, size):
    """The largest series scale at which the isometric of the box fits a square of `size` mm."""
    x, y, z = box
    fits = [n / d for n, d in SERIES if n / d * (x + y + z) * 0.75 <= size]
    return max(fits) if fits else SERIES[-1][0] / SERIES[-1][1]


def arrangement(outlines, room, gap, first_angle=False):
    """Each orthographic view's centre (mm), from their outlines {name: (x0, y0, x1, y1)} at
    the sheet's scale, packed into the room's lower left with the front's projections where
    the angle puts them: third angle the top above the front and the right to its right,
    first angle the top below and the right to its left. Returns ({name: (cx, cy)}, fits)."""
    x0, x1, y0, y1 = room
    f = outlines["*Front"]
    wf, hf = f[2] - f[0], f[3] - f[1]
    t, r = outlines.get("*Top"), outlines.get("*Right")
    ht = (t[3] - t[1]) if t else 0.0
    wr = (r[2] - r[0]) if r else 0.0
    gt, gr = (gap if t else 0.0), (gap if r else 0.0)
    out = {}
    if not first_angle:
        out["*Front"] = (x0 + wf / 2, y0 + hf / 2)
        if t:
            out["*Top"] = (x0 + wf / 2, y0 + hf + gt + ht / 2)
        if r:
            out["*Right"] = (x0 + wf + gr + wr / 2, y0 + hf / 2)
    else:
        fx, fy = x0 + wr + gr + wf / 2, y0 + ht + gt + hf / 2
        out["*Front"] = (fx, fy)
        if t:
            out["*Top"] = (fx, y0 + ht / 2)
        if r:
            out["*Right"] = (x0 + wr / 2, fy)
    fits = x0 + wf + gr + wr <= x1 and y0 + hf + gt + ht <= y1
    return out, fits


def numbered(lines):
    """Notes numbered 1., 2., ...; a line opening with a space continues the one above."""
    out, n = [], 0
    for t in lines:
        if not t.startswith(" "):
            n += 1
            t = f"{n}. {t}"
        out.append(t)
    return out
