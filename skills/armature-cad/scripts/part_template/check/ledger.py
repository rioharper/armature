"""
check/ledger.py — the ledger's numbers a part file reads, and the export it
writes them back with. Standard library only, so a part file needs build123d
and nothing else: the engine's `armature.ledger` owns checking the ledger
and writing it, and this only reads it.

The ledger is the project's `ledger.toml` (ADR 0010), the nearest one at or
above a folder, found the way the engine's `load` finds it. An entry is
named as the engine names it: `part.<pn>.<key>`, `budget.<kind>.<key>`, and
`mechanism.<key>`, `drive.<key>` or `req.<key>`. Values are SI, the unit
contract's side of check/__init__.py. Read one with `value`, which follows
an `of` line to the entry it reads, `qty` times.

`export` is what `python <part>.py --mass-properties` prints, and what
`py -m armature.ledger set part.<pn> --from-part <part>.py` writes back:
the measured mass, COM and inertia, with the frame they are in.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

FILENAME = "ledger.toml"
EXPORT = "--mass-properties"  # the flag `set --from-part` runs a part file with
# How many keys below its section an entry sits, as the engine reads it:
# `[part."moteus-r4.11".mass]` is two below `part`, `[mechanism.m2]` one.
SECTIONS = {"mechanism": 1, "drive": 1, "req": 1, "budget": 2, "part": 2}


class NoLedger(FileNotFoundError):
    """No ledger.toml at or above the folder a part file is in."""


def find(start) -> Path:
    """The nearest `ledger.toml` in `start` or a folder above it."""
    start = Path(start).resolve()
    for folder in [start, *start.parents]:
        if (folder / FILENAME).is_file():
            return folder / FILENAME
    raise NoLedger(f"no {FILENAME} in {start} or any folder above it")


def entries(path) -> dict:
    """Every entry's table in the ledger at `path`, by its full name."""
    with Path(path).open("rb") as f:
        data = tomllib.load(f)
    found = {}
    for top, body in data.items():
        if top not in SECTIONS:
            raise ValueError(f"{path}: {top} is not a ledger section; they "
                             f"are {', '.join(SECTIONS)}")
        for keys, table in _tables(body, SECTIONS[top]):
            found[".".join((top, *keys))] = table
    return found


def _tables(body, depth, keys=()):
    if not isinstance(body, dict):
        raise ValueError(f"{'.'.join(keys)}: an entry is a table, "
                         f"{depth - len(keys)} key(s) further down")
    if len(keys) == depth:
        yield keys, body
        return
    for key, sub in body.items():
        yield from _tables(sub, depth, (*keys, key))


def value(found: dict, name: str):
    """(value, the entry it was read from) for the entry `name`: its own
    value, or `qty` times the value its `of` chain ends at. A name that
    resolves to nothing raises KeyError, and a chain that loops ValueError:
    either is a broken link, never a reason to read a different number."""
    seen, qty = [name], 1.0
    entry = found[name]
    while "of" in entry:
        qty *= entry.get("qty", 1.0)
        if entry["of"] in seen:
            raise ValueError(f"{name}: of loops, {' -> '.join(seen)} -> "
                             f"{entry['of']}")
        seen.append(entry["of"])
        entry = found[entry["of"]]
    return scaled(entry["value"], qty), entry


def scaled(x, k: float):
    """`x` times `k`: a number, a vector or a tensor, as nested lists."""
    return [scaled(v, k) for v in x] if isinstance(x, list) else x * k


def export(props: dict, part_id: str, origin: str, axes: str) -> dict:
    """The measurement `set --from-part` writes back: `props` from
    `mass_properties`, SI, with the frame it is in. The COM is measured from
    `origin`, the tensor is about `props["about"]` (None: the COM), and
    both are in `axes`, each named in words for the ledger's reader."""
    about = props["about"]
    point = (f"{part_id}'s COM" if about is None
             else f"{tuple(about)} mm from {origin}")
    return {"mass": props["mass"], "com": list(props["com"]),
            "inertia": [list(row) for row in props["inertia"]],
            "point": point, "axes": axes, "origin": origin}
