"""`render`: the ledger's views, each a whole markdown table that `render`
writes between `<!-- ledger:<view> -->` and `<!-- /ledger -->` in the
project's markdown, so a number shown there is read, never copied.

    <!-- ledger:budget.mass -->     the budget's lines, total, allocation
    <!-- /ledger -->                and margin; any budget.<kind>

The views are `budget.<kind>`, `bom` (every `part.*` entry), `req` (the
spec's requirements, `req.*`) and `symbols` (`CONTEXT.md`'s symbol table,
the `mechanism` and `drive` entries). A row's prose is its entry's `note`;
the prose around a table is the author's, and `render` leaves it alone.
The project's markdown is every `.md` file below the ledger's folder,
except in a folder whose name starts with a dot or that holds a ledger of
its own. A marker inside a fenced code block is text, not a marker.
"""

import os
import re
from pathlib import Path

import numpy as np

from . import newlines
from .budgets import budgets, reqs, tally
from .entries import FILENAME, LedgerError, load

START = re.compile(r"<!--\s*ledger:(\S*?)\s*-->")
END = re.compile(r"<!--\s*/ledger\s*-->")
MARKER = re.compile(rb"<!--\s*/?ledger")   # a file worth reading
FENCE = re.compile(r"(`{3,}|~{3,})")
BUDGET_VIEW = re.compile(r"budget\.[^.\s]+")
VIEWS = "budget.<kind>, bom, req and symbols"
SYMBOL_SECTIONS = ("mechanism", "drive")
SKIPPED = {"node_modules", "__pycache__"}


def render(path=None):
    """Rewrite every marked section in the markdown of the project whose
    ledger is nearest `path` (default: the working directory). Returns the
    files it changed, so a second run returns none."""
    ledger = load(path=path)
    changed = []
    for file, text, newline in _documents(ledger):
        new = _rewrite(ledger, file, text)
        if new != text:
            newlines.write(file, new, newline)
            changed.append(file)
    return changed


def stale(ledger):
    """Each marked section whose text is not what `render` writes, as
    (view, message); a file whose markers cannot be read, or a view the
    ledger cannot render, is one too."""
    root = ledger.path.parent
    for file, text, _ in _documents(ledger):
        rel = file.relative_to(root).as_posix()
        lines = text.split("\n")
        try:
            marked = list(_marked(rel, lines))
        except LedgerError as e:
            yield rel, str(e)
            continue
        for view, start, end in marked:
            where = f"{rel}:{start + 1}"
            try:
                table = view_table(ledger, view)
            except LedgerError as e:
                yield view, f"{where}: {e}"
                continue
            if lines[start + 1:end] != table:
                yield view, (f"{where}: the section is not what render "
                             f"writes; run py -m armature.ledger render")


def view_table(ledger, view):
    """The lines of `view`'s table, from `ledger`."""
    if view == "bom":
        return _bom(ledger)
    if view == "req":
        return _req(ledger)
    if view == "symbols":
        return _symbols(ledger)
    if BUDGET_VIEW.fullmatch(view):
        return _budget(ledger, view)
    raise LedgerError(f"ledger:{view} is not a view; the views are {VIEWS}")


def _documents(ledger):
    """Each markdown file of the project, with its text (newlines as \\n)
    and the newline it was written with, in a stable order."""
    root = ledger.path.parent
    for folder, subs, files in os.walk(root):
        subs[:] = sorted(
            d for d in subs if not d.startswith(".") and d not in SKIPPED
            and not (Path(folder) / d / FILENAME).is_file())
        for name in sorted(files):
            if not name.lower().endswith(".md"):
                continue
            file = Path(folder) / name
            raw = file.read_bytes()
            if not MARKER.search(raw):
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                raise LedgerError(f"{file}: holds ledger markers and is "
                                  f"not UTF-8") from None
            yield file, *newlines.split(text)


def _marked(file, lines):
    """Each marked section in `lines` as (view, start line, end line),
    0-based, the markers' own lines. A fenced code block is skipped."""
    fence, open_ = None, None
    for i, line in enumerate(lines):
        text = line.strip()
        if fence is not None:
            fence = None if text.startswith(fence) else fence
            continue
        opened = FENCE.match(text)
        if opened and open_ is None:
            fence = opened[1]
            continue
        start, end = START.fullmatch(text), END.fullmatch(text)
        where = f"{file}:{i + 1}"
        if start and open_ is not None:
            raise LedgerError(f"{where}: ledger:{start[1]} opens inside "
                              f"ledger:{open_[0]}, which line "
                              f"{open_[1] + 1} opened and nothing closed")
        if start:
            if not start[1]:
                raise LedgerError(f"{where}: the marker names no view; the "
                                  f"views are {VIEWS}")
            open_ = (start[1], i)
        elif end and open_ is None:
            raise LedgerError(f"{where}: <!-- /ledger --> closes nothing")
        elif end:
            yield open_[0], open_[1], i
            open_ = None
    if open_ is not None:
        raise LedgerError(f"{file}:{open_[1] + 1}: ledger:{open_[0]} is "
                          f"never closed with <!-- /ledger -->")


def unrendered(file, text):
    """`text`'s lines with each marked section's table cut out, its markers
    kept: what an author wrote, which `render` never rewrites. Raises
    `LedgerError` on markers that cannot be read."""
    lines = text.splitlines()
    out, last = [], 0
    for _view, start, end in _marked(file, lines):
        out += lines[last:start + 1]
        last = end
    return out + lines[last:]


def _rewrite(ledger, file, text):
    lines = text.split("\n")
    out, last = [], 0
    for view, start, end in _marked(file, lines):
        try:
            table = view_table(ledger, view)
        except LedgerError as e:
            raise LedgerError(f"{file}:{start + 1}: {e}") from None
        out += lines[last:start + 1] + table
        last = end
    return "\n".join(out + lines[last:])


# --- the views ------------------------------------------------------------------
def _budget(ledger, view):
    if view not in budgets(ledger):
        return _table(["Line item", "Entry", "Budget", "Current estimate",
                       "Margin", "Source", "Status"], [])
    t = tally(ledger, view)
    u = f" ({t.unit})"
    rows = [[e.note or e.key, f"`{e.name}`", "", number(v), "",
             _source(ledger, e), _status(e)] for e, v in t.lines]
    a = t.allocation
    if a is None:
        rows.append(["Total", "", "", number(t.total), "", "", ""])
    else:
        margin = number(t.margin) + (", breached" if t.breached else "")
        rows.append(["Total", f"`{a.name}`", number(t.allowed),
                     number(t.total), margin, _source(ledger, a),
                     _status(a)])
    return _table(["Line item", "Entry", f"Budget{u}",
                   f"Current estimate{u}", f"Margin{u}", "Source", "Status"],
                  rows)


def _bom(ledger):
    rows = []
    for e in ledger:
        if not e.section.startswith("part."):
            continue
        rows.append([e.note or "", e.section[len("part."):], e.key,
                     _value(ledger, e), _as_written(e), _source(ledger, e),
                     _status(e), _drives(ledger, e)])
    return _table(["Item", "Part / spec", "Parameter", "Value", "As written",
                   "Source", "Status", "Drives"], rows)


def _req(ledger):
    rows = [[e.key, e.note or "", _value(ledger, e)
             + (f" ({e.as_written})" if e.as_written else ""),
             _source(ledger, e), _status(e)]
            for e in ledger if e.section == "req"]
    return _table(["ID", "Requirement", "Value / Threshold", "Source",
                   "Status"], rows)


def _symbols(ledger):
    rows = [[f"`{e.key}`", e.note or "", _value(ledger, e, unit=False),
             ledger.unit(e.name), _band(ledger, e), _source(ledger, e),
             _status(e)]
            for e in ledger if e.section in SYMBOL_SECTIONS]
    return _table(["Symbol", "Meaning", "Value", "Unit", "Band", "Source",
                   "Status"], rows)


# --- the cells ------------------------------------------------------------------
def _table(header, rows):
    return ["| " + " | ".join(_cell(c) for c in row) + " |"
            for row in [header, ["---"] * len(header), *rows]]


def _cell(text):
    return " ".join(str(text).split()).replace("|", "\\|")


def number(v, digits=6):
    """A scalar to `digits` significant figures, or a nested list of them:
    every number `render`, `show` and `check` print."""
    if np.ndim(v) == 0:
        return f"{v:.{digits}g}"
    return "[" + ", ".join(number(x, digits) for x in v) + "]"


def _value(ledger, e, unit=True):
    end = ledger.end(e.name)
    text = number(ledger.resolve(e.name))
    if unit:
        text += f" {end.unit}"
    if end.point is not None:
        text += f", about {end.point} in {end.axes} axes"
    return text


def _band(ledger, e):
    end = ledger.end(e.name)
    if end.band is None:
        return ""
    band = end.band
    qty = ledger.resolve(e.name) / end.value if e.of is not None else 1
    return f"[{number(np.multiply(qty, band[0]))}, " \
           f"{number(np.multiply(qty, band[1]))}]"


def _as_written(e):
    if e.as_written is None:
        return ""
    basis = ", ".join(f"{k} {v}" for k, v in (e.basis or {}).items())
    return e.as_written + (f" ({basis})" if basis else "")


def _source(ledger, e):
    """Where `e`'s value comes from: its source, or for an `of` entry what
    it reads, `qty` times, and the source the chain ends at."""
    if e.of is None:
        return _cited(e.source)
    end = ledger.end(e.name)
    reads = ("" if e.qty == 1 else f"{e.qty:g} × ") + f"`{e.of}`"
    own = "" if e.source is None else f"; {_cited(e.source)}"
    return f"{reads} → {_cited(end.source)}{own}"


def _cited(source):
    text = source["kind"]
    if "ref" in source:
        text += f": {source['ref']}"
    if "retrieved" in source:
        text += f", retrieved {source['retrieved']}"
    return text


def _status(e):
    return e.effective_status or ""


def _drives(ledger, e):
    """The entries that read `e` through an `of` chain, and the REQs the
    budgets among them answer to."""
    readers = []
    for other in ledger:
        if other.of is None or other.name == e.name:
            continue
        try:
            if any(c.name == e.name for c in ledger.chain(other.name)[1:]):
                readers.append(other)
        except LedgerError:   # check reports the of itself
            pass
    ids = [r for b in dict.fromkeys(o.section for o in readers
                                    if o.section.startswith("budget."))
           for r in reqs(ledger, b)]
    names = [f"`{o.name}`" for o in readers]
    return ", ".join([*dict.fromkeys(ids), *names])
