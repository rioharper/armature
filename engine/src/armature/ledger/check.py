"""`check`: the ledger's entry-level findings, each coded.

pint is imported here and nowhere a value is read: `load` hands out floats,
and this is the one place a unit is converted, so it is the one place a
conversion can be wrong and be caught.
"""

import datetime
import functools
import json
import re
from dataclasses import asdict, dataclass

import numpy as np

from .entries import CONFIRMED_BY_KIND, OfError, load

AS_WRITTEN = 1e-9      # |as_written − value| allowed, relative to the larger
SI_FACTOR = 1e-12      # |a unit's factor to SI − 1| that still counts as SI
PRICE_AGE = 90         # days before a datasheet price is old
NEEDS_AS_WRITTEN = ("datasheet", "standard", "measured")
CURRENCY = "[currency]"

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
    return findings


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
        if e.kind == "estimate":
            yield ("band.missing", "error",
                   "an estimate carries a band, [lo, hi]")
        return
    lo, hi = e.band
    if np.any(e.value < lo) or np.any(e.value > hi):
        yield ("band.nominal-outside", "error",
               f"value {_shown(e.value)} is outside its band "
               f"[{_shown(lo)}, {_shown(hi)}]")


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
            number = (json.loads(match[1]) if match[1].startswith("[")
                      else float(match[1]))
            written = ureg.Quantity(np.array(number, dtype=float), units)
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
               f"{e.as_written!r} is {_shown(converted, 17)} {e.unit}, not "
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


def _shown(x, digits=6):
    """A scalar or an array, to `digits` significant figures."""
    if np.ndim(x) == 0:
        return f"{x:.{digits}g}"
    return np.array2string(np.asarray(x), precision=digits)


def parse_unit(text):
    """`text` as a pint unit, or None where pint cannot parse it."""
    try:
        return _registry().Unit(text)
    except Exception:   # pint's parser raises more types than it documents
        return None


@functools.cache
def _registry():
    """pint's registry, with a currency, so a price is a quantity too."""
    import pint
    ureg = pint.UnitRegistry()
    ureg.define(f"USD = {CURRENCY}")
    return ureg
