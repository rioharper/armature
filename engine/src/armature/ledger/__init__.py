"""The ledger (ADR 0010): every input number a project's decisions rest on,
written once in `ledger.toml` at its root, with its unit, band, status and
provenance.

    p = load("mechanism")          # {"l1": 0.3, ...}, SI, `of` resolved
    ledger = load()                # the whole ledger, parsed and validated
    ledger.bands("mechanism")      # {"m2": (0.72, 0.88)}
    check()                        # [Finding(code, level, entry, message)]
    print(show("budget.mass"))     # its lines, total, allocation and margin

From a shell, `py -m armature.ledger check [--json]` and
`py -m armature.ledger show <prefix>`; `check` exits 1 on any error.

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
  most its lines may sum to.
"""

from .check import Finding, check
from .entries import (ALLOCATION, KINDS, SECTIONS, STATUSES, Entry, Ledger,
                      LedgerError, OfError, find, load, parse)
from .show import show

__all__ = ["ALLOCATION", "Entry", "Finding", "KINDS", "Ledger",
           "LedgerError", "OfError", "SECTIONS", "STATUSES", "check", "find",
           "load", "parse", "show"]

# CAD's write-back: `set_from_part("part.<pn>", <file>)`, or from a shell
# `py -m armature.ledger set part.<pn> --from-part <file>`, writes the part
# file's measured mass, COM and inertia as cad candidates (`write.py`).
from .write import set_from_part  # noqa: E402

__all__ += ["set_from_part"]
