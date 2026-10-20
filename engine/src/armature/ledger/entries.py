"""The ledger's entries: parsed from `ledger.toml`, validated, and resolved.

Standard library and numpy only, so a reader of values never imports pint:
units are checked by `check`, never converted here.
"""

import datetime
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

FILENAME = "ledger.toml"

# Each section and how many keys deep its entries sit: `[mechanism.l1]` is
# one key below `mechanism`, `[part."moteus-r4.11".mass]` two below `part`.
SECTIONS = {"mechanism": 1, "drive": 1, "req": 1, "budget": 2, "part": 2}
KINDS = ("chosen", "standard", "estimate", "datasheet", "cad", "measured")
STATUSES = ("candidate", "confirmed")
CONFIRMED_BY_KIND = ("chosen", "standard")  # status defaults to confirmed
ALLOCATION = "allocation"   # the budget entry its lines are summed against
SYMMETRIC = 1e-9            # |I − Iᵀ| allowed in a tensor, relative to |I|

VALUE_FIELDS = {"value", "unit", "basis", "as_written", "band", "status",
                "source", "note", "point", "axes"}
OF_FIELDS = {"of", "qty", "status", "source", "note"}
SOURCE_FIELDS = {"kind", "ref", "retrieved"}


class LedgerError(ValueError):
    """A ledger that cannot be read: no file, a malformed entry (named, with
    its field), or an `of` that names nothing or loops."""


class OfError(LedgerError):
    """An `of` chain that cannot be followed; `code` is `of.dangling` or
    `of.cycle`, the finding `check` reports it as."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Entry:
    """One entry, `[<section>.<key>]`. `value` is a float, a (3,) array or
    a symmetric (3, 3) array, or None for an `of` entry, which reads
    `qty` times the entry it names. `source` is a dict with `kind`, and
    `ref` and `retrieved` where given. `status` is as written, or None."""
    name: str
    section: str
    key: str
    value: object = None
    unit: str = None
    basis: dict = None
    as_written: str = None
    band: tuple = None
    status: str = None
    source: dict = None
    note: str = None
    point: str = None
    axes: str = None
    of: str = None
    qty: float = 1.0

    @property
    def kind(self):
        return None if self.source is None else self.source["kind"]

    @property
    def effective_status(self):
        """The status as written, else `confirmed` for an `of` entry, which
        cites a candidate only by saying so, or for a chosen or standard
        entry, else None."""
        if self.status is None and (self.of is not None
                                    or self.kind in CONFIRMED_BY_KIND):
            return "confirmed"
        return self.status


class Ledger:
    """A parsed ledger: its entries by full name, in file order."""

    def __init__(self, entries, path):
        self.entries = entries
        self.path = path

    def __getitem__(self, name):
        try:
            return self.entries[name]
        except KeyError:
            raise LedgerError(f"no entry named {name!r}") from None

    def __contains__(self, name):
        return name in self.entries

    def __iter__(self):
        return iter(self.entries.values())

    @property
    def sections(self):
        return list(dict.fromkeys(e.section for e in self))

    def _in(self, section):
        found = [e for e in self if e.section == section]
        if not found:
            raise LedgerError(f"no section {section!r}; the ledger has "
                              f"{', '.join(self.sections) or 'none'}")
        return found

    def section(self, section):
        """The section's values by key, in SI, with each `of` resolved."""
        return {e.key: self.resolve(e.name) for e in self._in(section)}

    def bands(self, section):
        """The section's bands by key, as (lo, hi), for the entries that
        carry one: floats, or arrays of the value's shape."""
        return {e.key: e.band for e in self._in(section)
                if e.band is not None}

    def chain(self, name):
        """The entries an `of` chain passes through from `name`, `name`'s
        own entry first. Raises on an `of` that names nothing or loops."""
        seen = [self[name]]
        while seen[-1].of is not None:
            target = seen[-1].of
            if target not in self.entries:
                raise OfError("of.dangling", f"{seen[-1].name}: of = "
                              f"{target!r} names no entry")
            if any(e.name == target for e in seen):
                loop = " → ".join([e.name for e in seen] + [target])
                raise OfError("of.cycle", f"{name}: of loops, {loop}")
            seen.append(self.entries[target])
        return seen

    def resolve(self, name):
        """`name`'s value in SI: its own, or the product of every `qty` on
        its `of` chain times the value the chain ends at."""
        chain = self.chain(name)
        return math.prod(e.qty for e in chain[:-1]) * chain[-1].value

    def unit(self, name):
        """The unit `name`'s value is in, read through its `of` chain."""
        return self.chain(name)[-1].unit


def find(path=None):
    """The ledger file: `path` itself if it is a file, else the nearest
    `ledger.toml` in `path` (default: the working directory) or above."""
    start = Path.cwd() if path is None else Path(path)
    if start.is_file():
        return start
    for folder in [start.resolve(), *start.resolve().parents]:
        if (folder / FILENAME).is_file():
            return folder / FILENAME
    raise LedgerError(f"no {FILENAME} in {start} or any folder above it")


def load(section=None, *, path=None):
    """The ledger nearest `path` (default: the working directory), parsed
    and validated, or one `section` of it as plain SI values, `of`
    resolved: `load("mechanism")` is what `armature.compile` takes. A
    malformed entry raises `LedgerError` naming the entry and the field."""
    ledger = parse(find(path))
    return ledger if section is None else ledger.section(section)


def parse(path):
    """Parse and validate the ledger file at `path`."""
    path = Path(path)
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise LedgerError(f"{path}: not TOML: {e}") from None
    entries = {}
    for top, body in data.items():
        if top not in SECTIONS:
            raise LedgerError(f"{top}: not a ledger section; the sections "
                              f"are {', '.join(SECTIONS)}")
        for keys, table in _tables(top, body, SECTIONS[top]):
            entry = _entry(top, keys, table)
            if entry.name in entries:
                raise LedgerError(f"{entry.name}: written twice")
            entries[entry.name] = entry
    return Ledger(entries, path)


def _tables(top, body, depth, keys=()):
    """Each entry's keys below `top` and its table, `depth` keys down."""
    where = ".".join((top, *keys))
    if not isinstance(body, dict):
        raise LedgerError(f"{where}: an entry is a table "
                          f"[{top}{'.<name>' * (depth - len(keys))}]")
    if len(keys) == depth:
        yield keys, body
        return
    for key, sub in body.items():
        yield from _tables(top, sub, depth, (*keys, key))


def _entry(top, keys, t):
    section = ".".join((top, *keys[:-1]))
    name = f"{section}.{keys[-1]}"
    if ("value" in t) == ("of" in t):
        raise LedgerError(f"{name}: an entry has a value or an of, not "
                          f"{'both' if 'value' in t else 'neither'}")
    allowed = OF_FIELDS if "of" in t else VALUE_FIELDS
    for field in t:
        if field not in allowed:
            raise LedgerError(f"{name}: {field} is not a field of "
                              f"{'an of' if 'of' in t else 'a value'} "
                              f"entry; its fields are "
                              f"{', '.join(sorted(allowed))}")
    if "of" in t:
        return Entry(name, section, keys[-1], of=_text(name, "of", t["of"]),
                     qty=_number(name, "qty", t.get("qty", 1.0)),
                     status=_status(name, t.get("status")),
                     source=_source(name, t["source"]) if "source" in t
                     else None,
                     note=_text(name, "note", t.get("note"), optional=True))
    for field in ("unit", "source"):
        if field not in t:
            raise LedgerError(f"{name}: {field} is required")
    value = _value(name, t["value"])
    point = _text(name, "point", t.get("point"), optional=True)
    axes = _text(name, "axes", t.get("axes"), optional=True)
    if np.ndim(value) == 2 and (point is None or axes is None):
        raise LedgerError(f"{name}: a tensor states the point and axes it "
                          f"is about; {'point' if point is None else 'axes'}"
                          f" is missing")
    basis = t.get("basis")
    if basis is not None and not (isinstance(basis, dict) and all(
            isinstance(v, str) for v in basis.values())):
        raise LedgerError(f"{name}: basis is a table of words, such as "
                          f"{{ per = \"V_rms\", between = \"line\" }}")
    return Entry(name, section, keys[-1], value=value,
                 unit=_text(name, "unit", t["unit"]), basis=basis,
                 as_written=_text(name, "as_written", t.get("as_written"),
                                  optional=True),
                 band=_band(name, t.get("band"), value),
                 status=_status(name, t.get("status")),
                 source=_source(name, t["source"]),
                 note=_text(name, "note", t.get("note"), optional=True),
                 point=point, axes=axes)


def _number(name, field, x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) \
            or not math.isfinite(x):
        raise LedgerError(f"{name}: {field} is a finite number; got {x!r}")
    return float(x)


def _text(name, field, x, optional=False):
    if x is None and optional:
        return None
    if not isinstance(x, str) or not x.strip():
        raise LedgerError(f"{name}: {field} is a string; got {x!r}")
    return x


def _value(name, x):
    """A float, a 3-vector or a symmetric 3×3 tensor."""
    if not isinstance(x, list):
        return _number(name, "value", x)
    if len(x) == 3 and not any(isinstance(r, list) for r in x):
        return np.array([_number(name, "value", v) for v in x])
    if len(x) == 3 and all(isinstance(r, list) and len(r) == 3 for r in x):
        a = np.array([[_number(name, "value", v) for v in r] for r in x])
        if np.abs(a - a.T).max() > SYMMETRIC * np.abs(a).max():
            raise LedgerError(f"{name}: value is a tensor and not "
                              f"symmetric")
        return a
    raise LedgerError(f"{name}: value is a number, a 3-list or a 3×3 "
                      f"nested list; got {x!r}")


def _band(name, x, value):
    if x is None:
        return None
    if not isinstance(x, list) or len(x) != 2:
        raise LedgerError(f"{name}: band is [lo, hi]; got {x!r}")
    lo, hi = (_value(name, v) for v in x)
    if np.shape(lo) != np.shape(value) or np.shape(hi) != np.shape(value):
        raise LedgerError(f"{name}: band is [lo, hi], each the value's "
                          f"shape, element by element; got {x!r}")
    if np.any(lo > hi):
        raise LedgerError(f"{name}: band is [lo, hi] with lo ≤ hi; got "
                          f"{x!r}")
    return lo, hi


def _status(name, x):
    if x is not None and x not in STATUSES:
        raise LedgerError(f"{name}: status is one of {', '.join(STATUSES)}; "
                          f"got {x!r}")
    return x


def _source(name, x):
    if not isinstance(x, dict) or "kind" not in x:
        raise LedgerError(f"{name}: source is a table "
                          f"{{ kind, ref, retrieved? }}; got {x!r}")
    for field in x:
        if field not in SOURCE_FIELDS:
            raise LedgerError(f"{name}: source.{field} is not a field; "
                              f"they are {', '.join(sorted(SOURCE_FIELDS))}")
    if x["kind"] not in KINDS:
        raise LedgerError(f"{name}: source.kind is one of {', '.join(KINDS)}"
                          f"; got {x['kind']!r}")
    if "ref" in x:
        _text(name, "source.ref", x["ref"])
    retrieved = x.get("retrieved")
    if retrieved is not None and (
            not isinstance(retrieved, datetime.date)
            or isinstance(retrieved, datetime.datetime)):
        raise LedgerError(f"{name}: source.retrieved is a TOML date, such "
                          f"as 2026-10-18; got {retrieved!r}")
    return dict(x)
