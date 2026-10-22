"""The gates (ADR 0011): `merge`, a work branch into `main`, and `buy`, the
merge of an order branch adding an order record, each computed from the
repo every time it is asked. Nothing stores a pass; the stored inputs are
the reviews, `waivers.toml`, the order records and the stamp cache.

    verdict = merge()                    # HEAD's branch, at its tip
    verdict.passed                       # no item failed
    verdict["review"]                    # Result(item, state, detail)
    print("\\n".join(verdict.lines()))   # pass|fail|waived <item> <detail>
    merge(verify=True)                   # read the stamps, run nothing
    buy()                                # merge's items, then buy's
    status()                             # [merge's, and buy's on an
                                         #  order branch], verifying

From a shell, `py -m armature.gate <merge|buy|status> [--branch <b>]
[--json] [--fresh]`; it exits 1 on any failed item.

`merge`'s items, by id, each read at the branch tip:
1. `fast-forward`: `main` is an ancestor of the tip.
2. `ledger`: `ledger check` reports no error.
3. `stamps`: every `run_all.py` has a green stamp for its content
   (`stamps`); `merge` runs one without, unless verifying.
4. `engine`: each model directory's `engine-source.sh check` is in-step
   (`engine`); a path pin fails.
5. `review`: a review pinned on the branch, at or after its branch point,
   where the branch changes a ledger number, model code, a part
   definition, or spec or plan text outside the rendered sections
   (`changes`, `reviews`).
6. `closed`: every BLOCKER and MAJOR of every counted review is closed.
7. `moves`: every ledger number changed after a counted review is named in
   some closure's `moves`.

`buy`'s, after merge's, on a branch adding one `docs/orders/*.toml`
(`orders`, `buy`, `release`):
- `order`: the branch adds exactly one order record, of the contract's
  shape.
- `confirmed`: every entry of each ordered part is confirmed, and none
  rests on an estimate.
- `price`: each line's price tier, the largest `price_at_<n>` at or below
  its qty, was retrieved no more than 90 days ago.
- `order-review`: a review on the branch lists the order record in its
  `artifacts`, whatever item 5 says.
- `placeholders`, for a release: each part's build leaves no stub.
- `release-stamps`, for a release: each part's and the model's
  `run_all.py` are stamped green.

An item is a function of the `Context` returning (passed, detail); a gate
is a list of (id, function) pairs, `MERGE` or `BUY`, and `evaluate`
computes one and applies the waivers of that gate alone (`waivers`).
`verify` is the mode the hook calls; `order(ctx)` tells it which gate a
branch takes.
"""

import datetime

from .buy import ITEMS as BUY_ITEMS
from .context import Context
from .merge import ITEMS as MERGE
from .orders import cleared, order
from .repo import GateError
from .reviews import Recheck, Review, ReviewError
from .verdict import Result, Verdict
from .waivers import FILENAME as WAIVERS, parse as parse_waivers

BUY = MERGE + BUY_ITEMS

__all__ = ["BUY", "Context", "GateError", "MERGE", "Recheck", "Result",
           "Review", "ReviewError", "Verdict", "buy", "evaluate", "merge",
           "order", "status"]


def evaluate(gate, items, ctx):
    """`gate`'s verdict: each of `items`, (id, function) pairs, computed on
    `ctx`, a failed one `waived` where a confirmed waiver in scope names
    it."""
    found, warnings = parse_waivers(ctx.repo.text(ctx.tip, WAIVERS) or "")
    ctx.warnings += warnings
    ids = [item for item, _ in items]
    for w in found:
        if w.gate == gate and w.item not in ids:
            ctx.warnings.append(f"{WAIVERS}: a waiver names {w.item}, no "
                                f"item of {gate}; its items are "
                                f"{', '.join(ids)}")
    results = []
    for item, fn in items:
        passed, detail = fn(ctx)
        waiver = None if passed else next(
            (w for w in found if w.applies(gate, ctx.branch, item)), None)
        if waiver is not None:
            results.append(Result(item, "waived", (
                f"{waiver.reason} (waived for {waiver.scope}, confirmed "
                f"{waiver.confirmed}; {detail})")))
        else:
            results.append(Result(item, "pass" if passed else "fail",
                                  detail))
    return Verdict(gate, ctx.branch, ctx.tip, results, ctx.warnings)


def merge(path=None, branch=None, *, verify=False, fresh=False, today=None,
          runner=None):
    """`merge`'s verdict for `branch` (default: HEAD's) of the repo at or
    above `path`. `verify` reads the stamps and runs nothing, as the hook
    does; `fresh` runs every `run_all.py`, ignoring them. `today` is the
    date the ledger's check counts a price's age from. `runner(folder,
    project)` runs one `run_all.py` (default: with uv)."""
    return evaluate("merge", MERGE,
                    _context(path, branch, verify, fresh, today, runner))


def buy(path=None, branch=None, *, verify=False, fresh=False, today=None,
        runner=None):
    """`buy`'s verdict for `branch` (default: HEAD's), computed as
    `merge`'s is: merge's items, then buy's. On a pass its notes say the
    order is cleared, and that nobody can see whether it was placed."""
    ctx = _context(path, branch, verify, fresh, today, runner)
    verdict = evaluate("buy", BUY, ctx)
    if verdict.passed:
        verdict.notes.append(cleared(order(ctx)))
    return verdict


def _context(path, branch, verify, fresh, today, runner):
    return Context.at(path, branch, verify=verify, fresh=fresh,
                      today=today or datetime.date.today(), runner=runner)


def status(path=None, branch=None, *, today=None):
    """Every gate that applies to `branch` (default: HEAD's), verifying:
    `merge`'s verdict, and `buy`'s where the branch adds an order
    record."""
    verdicts = [merge(path, branch, verify=True, today=today)]
    if order(_context(path, branch, True, False, today, None)) is not None:
        verdicts.append(buy(path, branch, verify=True, today=today))
    return verdicts
