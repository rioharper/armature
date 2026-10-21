"""
sweep/report.py — prints the sweep's summary. A renderer: it checks nothing;
what a reader sees is asserted through main() in summary_checks.py.
"""

from __future__ import annotations

import math

from sweep.grid import grid_steps


def fmt_q(q, free=None):
    """A posture in degrees. An axis flagged in `free` - one the pair
    interferes at EVERY sampled value of - prints as `any` instead of one
    arbitrary sample, because that axis is not part of the finding. The
    worst-overlap row passes no flags: it is one real measured posture,
    labelled as such, not a claim about a boundary."""
    free = (False,) * len(q) if free is None else free
    return "(" + ", ".join(
        "    any" if f else f"{math.degrees(v):7.1f}" for v, f in zip(q, free)
    ) + ") deg"


def print_summary(hits, summary, qs):
    """The rows a joint limit is read off: labelled as samples, with the
    grid step and what it means for the boundary beside them."""
    steps = grid_steps(qs)
    print(f"swept {len(qs)} postures, {len(hits)} interfering ({len(summary)} distinct pair(s))")
    print(
        "  grid step: "
        + ", ".join("n/a" if s is None else f"{s:.1f}" for s in steps)
        + " deg. The rows below are SAMPLES, not boundaries: the true"
    )
    print("  onset lies up to one step before the first interfering sample, so set a")
    print("  joint limit at least one step inside it, or re-run a fine scan around it.")
    for a, b, count, first_q, first_vol, worst_q, worst_vol, free in summary:
        print(f"  {a} <-> {b}: {count} of {len(qs)} postures interfere")
        print(
            f"    first interfering sample  q = {fmt_q(first_q, free)}"
            f"  overlap {first_vol / 1000:8.1f} cm^3"
        )
        print(
            f"    worst                     q = {fmt_q(worst_q)}"
            f"  overlap {worst_vol / 1000:8.1f} cm^3"
        )
    if hits:
        print(
            "\nThis is an armature-derive finding, not a CAD one: narrow a joint's\n"
            "range in mechanism.py or change a link length in the ledger,\n"
            "re-derive, re-run."
        )
