"""`check`: the ledger's findings, each coded: an entry's, then a budget's
and the project markdown's.

pint is used here and nowhere a value is read: `load` hands out floats,
and this is the one place a unit is converted, so it is the one place a
conversion can be wrong and be caught.
"""

import datetime
import json
import re
from dataclasses import asdict, dataclass

import numpy as np

from .budgets import BudgetUnitError, budgets, reqs, tally
from .entries import CONFIRMED_BY_KIND, ESTIMATE, OfError, load
from .units import CURRENCY, parse_unit, registry as _registry
from .views import number, stale

AS_WRITTEN = 1e-9      # |as_written − value| allowed, relative to the larger
SI_FACTOR = 1e-12      # |a unit's factor to SI − 1| that still counts as SI
PRICE_AGE = 90         # days before a datasheet price is old
NEEDS_AS_WRITTEN = ("datasheet", "standard", "measured")
TRACE = "docs/01-spec/traceability.md"
REQ_ROW = re.compile(r"REQ-\d+")

# A quantity as written: a number, or a JSON list of them, then its unit.
QUANTITY = re.compile(r"\s*(\[.*\]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)"
                      r"\s*(.*?)\s*$", re.DOTALL)


@dataclass(frozen=True)
class Finding:
    """One finding: its `code` (such as `unit.as-written`), its `level`,
    `error` or `warning`, the `entry` it is about, and a `message`."""
    code: str
    level: str
    entry: str
    message: str

    def __str__(self):
        return f"{self.level} {self.code} {self.entry}: {self.message}"

    def as_dict(self):
        return asdict(self)


def check(path=None, *, today=None):
    """The findings on the ledger nearest `path`, in file order. `today`
    (default: the date now) is what a price's age is counted from. A
    malformed entry raises, as `load` does."""
    ledger = load(path=path)
    today = datetime.date.today() if today is None else today
    findings = []
    for e in ledger:
        found = (_of(ledger, e) if e.of is not None
                 else [*_citation(e), *_band(e), *_unit(e), *_price(e, today)])
        findings += [Finding(code, level, e.name, message)
                     for code, level, message in found]
    return findings + [Finding(code, "error", entry, message)
                       for code, entry, message in _project(ledger)]


def _project(ledger):
    """The findings on the budgets as a whole and on the project's
    markdown: a breach, a breached REQ whose traceability row is not
    failed (when that file exists), a line in another unit from its
    budget's, which leaves the budget unsummed, and a stale view."""
    breached = []
    for budget in budgets(ledger):
        try:
            t = tally(ledger, budget)
        except BudgetUnitError as e:
            yield "budget.unit", e.entry, e.reason
            continue
        except OfError:   # the line's own of finding reports it
            continue
        if t.breached:
            breached.append(t)
            failing = reqs(ledger, budget)
            yield ("budget.breach", budget,
                   f"its lines sum to {number(t.total)} {t.unit}, past its "
                   f"allocation of {number(t.allowed)} {t.unit} by "
                   f"{number(-t.margin)} {t.unit}"
                   + (f"; it fails {', '.join(failing)}" if failing else ""))
    trace = ledger.path.parent / TRACE
    if breached and trace.is_file():
        rows = trace_statuses(trace.read_text(encoding="utf-8"))
        for t in breached:
            for req in reqs(ledger, t.name):
                status = rows.get(req)
                if status is None or _word(status) != "failed":
                    yield ("trace.unfailed", req,
                           f"{t.name} is breached, and its row in {TRACE} "
                           + ("is missing" if status is None
                              else f"reads {status!r}, not failed"))
    for view, message in stale(ledger):
        yield "view.stale", view, message


def trace_statuses(text):
    """Each REQ's Status cell in a traceability table, by REQ id."""
    rows, status = {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            status = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        names = [c.strip("*` ").lower() for c in cells]
        if status is None:
            status = names.index("status") if "status" in names else None
            continue
        req = cells[0].strip("*` ")
        if len(cells) > status and REQ_ROW.fullmatch(req):
            rows[req] = cells[status].strip("*` ")
    return rows


def _word(status):
    """A status cell's first word, lowercased: `failed` in "failed: the
    reserve is spent", `open` in "open (budget row failed)"."""
    words = re.findall(r"[a-z]+", status.lower())
    return words[0] if words else ""


def _citation(e):
    kind, source = e.kind, e.source
    yield from _ref(e)
    if kind == "datasheet" and "retrieved" not in source:
        yield ("source.citation", "error",
               "a datasheet entry gives the date it was retrieved, "
               "source.retrieved")
    if kind in NEEDS_AS_WRITTEN and e.as_written is None:
        yield ("source.citation", "error",
               f"a {kind} entry keeps the quantity as its source printed "
               f"it, as_written")
    if e.status is None and kind not in CONFIRMED_BY_KIND:
        yield ("source.citation", "error",
               f"a {kind} entry states its status, candidate or confirmed")


def _ref(e):
    if "ref" not in e.source:
        yield ("source.citation", "error",
               f"a {e.kind} entry cites its source in source.ref")


def _band(e):
    if e.band is None:
        if e.kind == ESTIMATE:
            yield ("band.missing", "error",
                   "an estimate carries a band, [lo, hi]")
        return
    lo, hi = e.band
    if np.any(e.value < lo) or np.any(e.value > hi):
        yield ("band.nominal-outside", "error",
               f"value {number(e.value)} is outside its band "
               f"[{number(lo)}, {number(hi)}]")


def _unit(e):
    ureg = _registry()
    unit = parse_unit(e.unit)
    if unit is None:
        yield ("unit.unparsed", "error",
               f"pint cannot parse the unit {e.unit!r}")
        return
    if unit != ureg.degC:   # the engine's temperatures are in °C
        si = ureg.Quantity(1.0, unit).to_base_units()
        if abs(si.magnitude - 1) > SI_FACTOR:
            yield ("unit.not-si", "error",
                   f"1 {e.unit} is {si:~g}; the value is written in "
                   f"{si.units:~}")
    if e.as_written is not None:
        yield from _as_written(e, ureg, unit)


def _as_written(e, ureg, unit):
    match = QUANTITY.fullmatch(e.as_written)
    units = None if match is None else parse_unit(match[2] or "1")
    written = None
    if units is not None:
        try:
            parsed = (json.loads(match[1]) if match[1].startswith("[")
                      else float(match[1]))
            written = ureg.Quantity(np.array(parsed, dtype=float), units)
        except ValueError:   # json's error is a ValueError too
            pass
    if written is None:
        yield ("unit.unparsed", "error",
               f"pint cannot parse as_written {e.as_written!r}; it is a "
               f"number, or a list of them, then a unit")
        return
    try:
        converted = written.to(unit).magnitude
    except TypeError:        # pint's DimensionalityError is a TypeError
        yield ("unit.as-written", "error",
               f"{e.as_written!r} is not a quantity in {e.unit}")
        return
    if np.shape(converted) != np.shape(e.value):
        yield ("unit.as-written", "error",
               f"{e.as_written!r} has a different shape from value")
        return
    scale = max(np.abs(converted).max(), np.abs(e.value).max())
    if np.abs(converted - e.value).max() > AS_WRITTEN * scale:
        yield ("unit.as-written", "error",
               f"{e.as_written!r} is {number(converted, 17)} {e.unit}, not "
               f"the value")


def _price(e, today):
    retrieved = e.source.get("retrieved")
    if e.kind != "datasheet" or retrieved is None:
        return
    unit = parse_unit(e.unit)
    if unit is None:
        return
    age = (today - retrieved).days
    if CURRENCY in unit.dimensionality and age > PRICE_AGE:
        yield ("price.old", "warning",
               f"retrieved {retrieved}, {age} days ago; a price is "
               f"re-checked after {PRICE_AGE}")


def _of(ledger, e):
    try:
        chain = ledger.chain(e.name)
    except OfError as error:
        yield error.code, "error", str(error)
        return
    if e.source is not None:
        yield from _ref(e)
    if e.effective_status != "confirmed":
        return
    for cited in chain[1:]:
        if cited.effective_status == "candidate":
            yield ("status.candidate-cited", "error",
                   f"confirmed, but it reads {cited.name}, a candidate")
            return
