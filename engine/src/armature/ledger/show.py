"""`show`: the entries under a prefix, one line each, so a reader loads the
part of the ledger an artifact cites rather than all of it."""

import numpy as np

from .check import parse_unit
from .entries import ALLOCATION, LedgerError, load

DASH = "-"   # a column with nothing in it


def show(prefix, *, path=None):
    """The entries under `prefix` (`part.moteus-r4.11`, `budget.mass`, or
    one entry's name), one line each: name, value, unit, band, kind and
    status. Each budget under the prefix adds its lines' resolved values,
    their total, its allocation and its margin, allocation minus total."""
    ledger = load(path=path)
    found = [e for e in ledger
             if e.name == prefix or e.name.startswith(prefix + ".")]
    if not found:
        raise LedgerError(f"no entry under {prefix!r}; the ledger has "
                          f"{', '.join(ledger.sections) or 'none'}")
    rows = [[e.name, _value(e), e.unit or DASH, _band(e.band),
             e.kind or DASH, e.effective_status or DASH] for e in found]
    out = _columns(rows)
    for budget in dict.fromkeys(e.section for e in found
                                if e.section.startswith("budget.")):
        out += [f"{budget}:", *_columns(_budget(ledger, budget), "  ")]
    return "\n".join(out)


def _budget(ledger, budget):
    """A budget's rows: each line resolved, the total, the allocation and
    the margin, all in the allocation's unit, or the first line's."""
    entries = [e for e in ledger if e.section == budget]
    lines = [e for e in entries if e.key != ALLOCATION]
    allocation = next((e for e in entries if e.key == ALLOCATION), None)
    units = {e.name: ledger.unit(e.name) for e in entries}
    unit = units[allocation.name] if allocation else units[lines[0].name]
    for name, other in units.items():
        if parse_unit(other) != parse_unit(unit):
            raise LedgerError(f"{name}: a {budget} line is in {other}, and "
                              f"the budget in {unit}")
    values = {e.key: ledger.resolve(e.name) for e in lines}
    total = sum(values.values())
    rows = [[key, _number(v), unit] for key, v in values.items()]
    rows.append(["total", _number(total), unit])
    if allocation is None:
        return rows + [["allocation", DASH, ""]]
    have = ledger.resolve(allocation.name)
    return rows + [["allocation", _number(have), unit],
                   ["margin", _number(have - total), unit]]


def _value(e):
    if e.of is None:
        return _number(e.value)
    return f"of {e.of}" + ("" if e.qty == 1 else f" x{e.qty:g}")


def _number(v):
    if np.ndim(v) == 0:
        return f"{v:.6g}"
    return "[" + ", ".join(_number(x) for x in v) + "]"


def _band(band):
    if band is None:
        return DASH
    return f"[{_number(band[0])}, {_number(band[1])}]"


def _columns(rows, indent=""):
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return [indent + "  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip()
            for r in rows]
