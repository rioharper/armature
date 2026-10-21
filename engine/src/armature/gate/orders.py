"""Order records (ADR 0011): `docs/orders/<date>-<name>.toml`, the file an
order branch adds, and the one input `buy` reads that `merge` does not.

A purchase buys parts the ledger holds:

    kind = "purchase"
    vendor = "RobStride"
    [[line]]
    part = "part.rs02"      # a part section of the ledger
    qty = 1

A release sends out a drawing, a DXF, a quote request or a fit print:

    kind = "release"
    vendor = "SendCutSend"
    [[line]]
    definition = "cad/parts/HIP-PLT-001"
    exports = ["cad/parts/export/HIP-PLT-001.dxf"]

A release line's `definition` names a part by its path without a suffix.
In the template's layout every part lives in one folder, `cad/parts/`, as
`<PART-ID>.md` with its build recipe `<PART-ID>.py` beside it, so
`cad/parts/HIP-PLT-001` is the part whose definition is
`cad/parts/HIP-PLT-001.md`. A part with a folder of its own,
`cad/parts/HIP-PLT-001/HIP-PLT-001.md`, is read the same way. Either way
the part's folder is the one holding its `.md`, and its `run_all.py` is
that folder's.
"""

import datetime
import re
import tomllib
from dataclasses import dataclass
from pathlib import PurePosixPath

FOLDER = "docs/orders"
KINDS = ("purchase", "release")
NAME = re.compile(r"(\d{4}-\d{2}-\d{2})-.+\.toml")
FIELDS = ("kind", "vendor", "line")
LINE_FIELDS = {"purchase": ("part", "qty"),
               "release": ("definition", "exports")}
PART = "part."


class OrderError(ValueError):
    """An order record that is not the contract's shape."""


@dataclass(frozen=True)
class Line:
    """One `[[line]]`: a part section and a quantity, for a purchase; a
    part definition and the exports sent, for a release."""
    part: str = None
    qty: int = None
    definition: str = None
    exports: tuple = ()


@dataclass(frozen=True)
class Order:
    path: str
    kind: str
    vendor: str
    lines: tuple


def paths(files):
    """The order records among `files`: each `.toml` directly in
    `docs/orders/`."""
    return [p for p in files if str(PurePosixPath(p).parent) == FOLDER
            and p.lower().endswith(".toml")]


def added(ctx):
    """The order records the branch adds: at its tip, not at its branch
    point."""
    before = set(ctx.repo.files(ctx.base)) if ctx.base else set()
    return [p for p in paths(ctx.changed)
            if p in ctx.files and p not in before]


def order(ctx):
    """The order record the branch adds, by path, or None where it adds
    none; the first of several where it adds more, so a branch adding two
    is still gated by `buy`, which fails it."""
    found = sorted(added(ctx))
    return found[0] if found else None


def record(ctx):
    """The order the branch adds, parsed, and why there is none: (order,
    None) or (None, problem). Read once per context."""
    if "_order" not in ctx.__dict__:
        found = sorted(added(ctx))
        if not found:
            got = (None, f"the branch adds no order record under {FOLDER}/")
        elif len(found) > 1:
            got = (None, f"the branch adds {len(found)} order records, "
                         f"{', '.join(found)}; an order branch adds one")
        else:
            try:
                got = (parse(ctx.repo.text(ctx.tip, found[0]), found[0]),
                       None)
            except (OrderError, UnicodeDecodeError) as e:
                got = (None, str(e))
        ctx.__dict__["_order"] = got
    return ctx.__dict__["_order"]


def of_kind(ctx, kind, otherwise):
    """(order, None) where the branch's order is a `kind`; else (None, an
    item's result): failed where there is no order, passed with `a <kind>
    <otherwise>` where it is of the other kind."""
    found, problem = record(ctx)
    if found is None:
        return None, (False, f"no order to check: {problem}")
    if found.kind != kind:
        return None, (True, f"a {found.kind} {otherwise}")
    return found, None


def parse(text, path):
    """The order `text` holds, read from `path`; raises `OrderError`."""
    match = NAME.fullmatch(PurePosixPath(path).name)
    try:
        datetime.date.fromisoformat(match[1] if match else "")
    except ValueError:
        raise OrderError(f"{path}: an order record is named "
                         f"{FOLDER}/<date>-<name>.toml, its date as "
                         f"2026-10-21") from None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise OrderError(f"{path} is not TOML: {e}") from None
    for key in data:
        if key not in FIELDS:
            raise OrderError(f"{path}: {key} is not a field of an order; "
                             f"they are {', '.join(FIELDS)}")
    kind = data.get("kind")
    if kind not in KINDS:
        raise OrderError(f"{path}: kind is one of {', '.join(KINDS)}; got "
                         f"{kind!r}")
    vendor = data.get("vendor")
    if not (isinstance(vendor, str) and vendor.strip()):
        raise OrderError(f"{path}: vendor names who the order goes to")
    lines = data.get("line")
    if not (isinstance(lines, list) and lines
            and all(isinstance(t, dict) for t in lines)):
        raise OrderError(f"{path}: an order has at least one [[line]]")
    return Order(path, kind, vendor,
                 tuple(_line(path, kind, n, t)
                       for n, t in enumerate(lines, 1)))


def _line(path, kind, n, t):
    where = f"{path}: line {n}"
    fields = LINE_FIELDS[kind]
    for key in t:
        if key not in fields:
            raise OrderError(f"{where}: {key} is not a field of a {kind}'s "
                             f"line; they are {', '.join(fields)}")
    if kind == "purchase":
        part, qty = t.get("part"), t.get("qty")
        if not (isinstance(part, str) and part.startswith(PART)
                and len(part) > len(PART)):
            raise OrderError(f"{where}: part names a ledger part section, "
                             f"such as part.rs02; got {part!r}")
        if not (isinstance(qty, int) and not isinstance(qty, bool)
                and qty > 0):
            raise OrderError(f"{where}: qty is a whole number above 0; got "
                             f"{qty!r}")
        return Line(part=part, qty=qty)
    definition, exports = t.get("definition"), t.get("exports")
    if not (isinstance(definition, str) and definition.strip()):
        raise OrderError(f"{where}: definition names a part, such as "
                         f"cad/parts/HIP-PLT-001")
    if not (isinstance(exports, list) and exports
            and all(isinstance(e, str) for e in exports)):
        raise OrderError(f"{where}: exports lists the files sent out")
    return Line(definition=definition.rstrip("/"), exports=tuple(exports))


@dataclass(frozen=True)
class Part:
    """A release line's part: its definition, its build recipe (None where
    it has none) and its folder."""
    definition: str
    recipe: str
    folder: str


def part(files, definition):
    """The part `definition` names among `files`, or None."""
    name = PurePosixPath(definition).name
    for md in (f"{definition}.md", f"{definition}/{name}.md"):
        if md in files:
            folder = str(PurePosixPath(md).parent)
            recipe = md[:-3] + ".py"
            return Part(md, recipe if recipe in files else None, folder)
    return None


def cleared(path):
    """What `buy` prints when it passes."""
    return (f"cleared {path}: the order may be placed, and nobody can see "
            f"whether it was; the gate checks the record, never the "
            f"purchase")
