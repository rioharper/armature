# ADR 0010 — Every input number lives once, in the project's ledger

2026-10-20 — Status: accepted

A project keeps every input number a decision rests on in one file,
`ledger.toml` at its root, beside `CONTEXT.md`. That covers the mechanism's and
the drive's parameters, their tolerance bands, the requirements' thresholds,
the budgets' allocations and line items, and the facts a decision reads off a
part's datasheet. A number is written there once. Every other place that shows
it either reads it or is a view `render` generates from it. Derived numbers
are never stored; the model or the view computes them. Those are a budget's
total and margin, a realized sum, and a margin's slack.

An entry is a TOML table named `<section>.<name>`. Its sections are
`mechanism` (exactly what `mechanism(p)` reads), `drive`, `req` (keyed by REQ
id), `budget.<kind>` and `part.<pn>`:

```toml
[drive.ke1]
value = 0.8442            # SI
unit = "V*s/rad"
basis = { per = "V_rms", between = "line" }
as_written = "88.4 V/krpm"
band = [0.80, 0.88]
status = "confirmed"
source = { kind = "datasheet", ref = "RobStride-02", retrieved = 2026-10-18 }
note = "shoulder winding"
```

- **Units.** A value is stored in SI, with temperatures in °C, which is the
  engine's own convention (`armature/drive/electrical.py`). A datasheet basis
  (rms or peak, line or phase) is its own field, never part of the unit. The
  quantity as the source printed it is kept in `as_written`, and `check`
  converts it with pint and fails if the conversion disagrees with `value`.
  Readers get plain floats, and the one place a conversion happens is checked.
  That covers the common-mode slip, a wrong unit in the shared parameter file
  that the truth model and the derivation both read and agree on.
- **Values** are scalars, 3-vectors or symmetric 3×3 tensors. A tensor states
  its point and axes, so a CAD inertia goes back in whole.
- **Provenance** is one of six kinds, each with the citation it requires:

  | Kind | Means | Cites |
  |---|---|---|
  | `chosen` | a design decision or a requirement's threshold, exact by definition | the spec section or REQ id |
  | `standard` | a book or standards value | the reference |
  | `estimate` | a guess with a basis | the basis, and a band |
  | `datasheet` | a published figure, list prices included | the index row's P/N, `retrieved` |
  | `cad` | measured off a model | the part file and its rev |
  | `measured` | measured on the bench | the test report |

  Trust rises estimate → datasheet → cad → measured. `chosen` and `standard`
  are off that ladder. These six replace the budgets' guess / datasheet /
  model / measured, the BOM's Confirmed / TBD / Assumed, and derive's
  `standard` tag.
- **Status** is `candidate` or `confirmed`, separate from provenance. A part's
  numbers the librarian found from a description arrive as `candidate`, and
  only the user makes them `confirmed`.
- **A band** is `[lo, hi]` on any entry, and an `estimate` must carry one. The
  ledger's bands replace `params.BANDS`, and the engine's `Band` axes are built
  from them unchanged.
- **References, not copies.** A budget line is `of = "<entry>"` and `qty`,
  with no value of its own.

The machinery is `armature.ledger` in the engine (ADR 0004), with five verbs:
`load`, `check`, `show`, `render` and `set`. They are called as
`py -m armature.ledger <verb>` until Overhaul 05's verb CLI exists. pint and
tomlkit become engine dependencies; the model itself never imports pint.
A reader that must stay standard-library-only, such as a CAD part file,
reads the TOML with `tomllib`. `check` emits coded findings and exits nonzero
on an error. Which actions those findings block is Overhaul 07's to decide;
this ADR installs no hook. The views are marked sections of the budgets, the
BOM, the spec's requirements table and `CONTEXT.md`'s symbol table, each a
whole table that `render` rewrites. Prose a row needs lives in its entry's
`note`, and `check` fails a hand edit inside a marked section.

The template's `params.py` keeps only structure, the load-case table and the
workspace keyed to joint names. It carries no numeric literal, and its
self-tests fail on one. A check's expected value is computed from ledger
inputs by an independent route, never pinned from a model's output.

Why. On 2026-10-11, 4 of the 36 Blocker and Major findings in Plumb and Ibex
were stale or unpropagated numbers. Ibex spec F8 cited CANDIDATE rows as if
they were confirmed. One geometry change re-pinned 8 checks files in Plumb
(`822226f`) and 7 in Ibex (`f2fe7fc`). Plumb writes the moteus r4.11's 14.2 g
in its datasheet index, its BOM and its budgets. No number carried a unit, a
band or a provenance: units lived in comments, there were four provenance
vocabularies, CANDIDATE had no column, traceability had no failed state, and a
link's inertia was two scalars on a diagonal that no CAD tensor could replace.

Rejected:
- **The model's inputs only** (PARAMS, DRIVE, BANDS). Half the drift is
  between the spec's tables, the BOM and the datasheet index.
- **A checker over today's markdown first.** Only Plumb has today's markdown,
  and Plumb is deferred. Ibex's restarted spec is about to write the tables,
  so they are written to the ledger from the start.
- **YAML,** which needs a dependency even to read. **A Python ledger,** which no
  tool can rewrite safely and which a render step would have to execute.
- **pint quantities through the model.** pint doesn't pass through SymPy
  (pint#606), and the engine's parameters are plain floats.
- **Whole generated files for the views.** The budgets' reserve rules and the
  BOM's design notes are prose around the tables.

The cost accepted:
- An entry is several lines where a `params.py` line was one.
- Agents edit TOML, then run `render`. A forgotten `render` is a `check` error,
  not a silent drift.
- `as_written` must parse in pint, so `mohm` is written rather than `mOhm`.
- Plumb and CineWave V2 keep their markdown until they are moved, which is
  later.

Revisit when an input number a decision needs has no section to live in, or
when Overhaul 07's gate needs a finding `check` cannot produce.

**Amended 2026-10-21 (ADR 0011):** a hook now consumes `check`. ADR 0011 gates
two actions, `merge` and `buy`, on `check` reporting no error, among other
evidence. At `buy`, `price.old` counts as an error, and an ordered part's
entries must be `confirmed` with no `estimate` source. The plugin's hook asks
the user before an edit sets `status = "confirmed"`.
