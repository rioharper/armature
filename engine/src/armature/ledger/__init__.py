"""The ledger (ADR 0010): every input number a project's decisions rest on,
written once in `ledger.toml` at its root, with its unit, band, status and
provenance.

    p = load("mechanism")          # {"l1": 0.3, ...}, SI, `of` resolved
    ledger = load()                # the whole ledger, parsed and validated
    ledger.bands("mechanism")      # {"m2": (0.72, 0.88)}
    check()                        # [Finding(code, level, entry, message)]
    print(show("budget.mass"))     # its lines, total, allocation and margin
    render()                       # rewrite the markdown's marked sections

From a shell, `py -m armature.ledger check [--json]`,
`py -m armature.ledger show <prefix>` and `py -m armature.ledger render`;
`check` exits 1 on any error.

An entry is the table `[<section>.<name>]`, in a section `mechanism`
(exactly what `mechanism(p)` reads), `drive`, `req` (keyed by REQ id),
`budget.<kind>` or `part.<pn>`:

    [drive.ke1]
    value = 0.8441578181594128      # SI: V·s/rad
    unit = "V*s/rad"
    basis = { per = "V_rms", between = "line" }
    as_written = "88.4 V/krpm"
    band = [0.80, 0.88]
    status = "confirmed"
    source = { kind = "datasheet", ref = "RobStride-02", retrieved = 2026-10-18 }
    note = "shoulder winding"

- `value` is a float, a 3-list or a symmetric 3×3 nested list, in SI with
  temperatures in °C; a tensor also names the `point` and `axes` it is
  about. `value`, `unit` and `source` are required.
- `source` is `{ kind, ref, retrieved? }`, `kind` one of chosen, standard,
  estimate, datasheet, cad or measured. Every kind cites a `ref`; a
  datasheet also its `retrieved` date; a datasheet, standard or measured
  entry its `as_written`, the quantity as the source printed it, which
  `check` converts with pint and holds to `value` within 1e-9.
- `status` is candidate or confirmed. It defaults to confirmed for chosen
  and standard entries and is stated for every other kind.
- `band` is `[lo, hi]` around the nominal, each end the value's shape, so a
  vector's or a tensor's band holds element by element; an estimate has one.
- An entry with `of = "<section.name>"` and an optional `qty` (default 1)
  has no value of its own: it reads `qty` times the entry it names, through
  any chain of `of`s. A budget line is one. Its status defaults to
  confirmed, so a line citing a candidate says `status = "candidate"`.
- A budget `budget.<kind>` holds its lines and one `allocation` entry, the
  most its lines may sum to. Lines past it are a breach, which fails each
  REQ the budget answers to: a `req.*` entry one of its entries' `of`
  chains reaches, or a REQ id one of its entries' `source.ref` names.
  Every line is in the allocation's unit; `check` fails one that is not,
  `budget.unit`, and sums nothing for that budget. A
  reserve is a line holding the headroom its REQ demands.
- A view is a whole markdown table `render` writes between
  `<!-- ledger:<view> -->` and `<!-- /ledger -->`: `budget.<kind>`, `bom`,
  `req` or `symbols` (see `views`). `check` fails a section that is not
  what `render` writes, a breach, and a breached REQ whose row in
  `docs/01-spec/traceability.md` is not `failed`.
"""

from .check import Finding, check
from .entries import (ALLOCATION, KINDS, SECTIONS, STATUSES, Entry, Ledger,
                      LedgerError, OfError, find, load, parse)
from .show import show
from .views import render

__all__ = ["ALLOCATION", "Entry", "Finding", "KINDS", "Ledger",
           "LedgerError", "OfError", "SECTIONS", "STATUSES", "check", "find",
           "load", "parse", "render", "show"]

# CAD's write-back: `set_from_part("part.<pn>", <file>)`, or from a shell
# `py -m armature.ledger set part.<pn> --from-part <file>`, writes the part
# file's measured mass, COM and inertia as cad candidates (`write.py`).
from .write import set_from_part  # noqa: E402

__all__ += ["set_from_part"]
