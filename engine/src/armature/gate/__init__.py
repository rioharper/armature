"""The gates (ADR 0011): `merge`, a work branch into `main`, computed from
the repo every time it is asked. Nothing stores a pass; the stored inputs
are the reviews, `waivers.toml` and the stamp cache.

    verdict = merge()                    # HEAD's branch, at its tip
    verdict.passed                       # no item failed
    verdict["review"]                    # Result(item, state, detail)
    print("\\n".join(verdict.lines()))   # pass|fail|waived <item> <detail>
    merge(verify=True)                   # read the stamps, run nothing
    status()                             # [merge's verdict], verifying

From a shell, `py -m armature.gate <merge|status> [--branch <b>] [--json]
[--fresh]`; it exits 1 on any failed item.

`merge`'s items, by id, each read at the branch tip:
1. `fast-forward`: `main` is an ancestor of the tip.
2. `ledger`: `ledger check` reports no error.
3. `stamps`: every `run_all.py` has a green stamp for its content
   (`stamps`); `merge` runs one without, unless verifying.
4. `engine`: each model directory's `engine-source.sh check` is in-step, or
   a path pin (`engine`).
5. `review`: a review pinned on the branch, at or after its branch point,
   where the branch changes a ledger number, model code, a part
   definition, or spec or plan text outside the rendered sections
   (`changes`, `reviews`).
6. `closed`: every BLOCKER and MAJOR of every counted review is closed.
7. `moves`: every ledger number changed after a counted review is named in
   some closure's `moves`.

An item is a function of the `Context` returning (passed, detail); a gate
is a list of (id, function) pairs, `MERGE`, and `evaluate` computes one and
applies the waivers (`waivers`). `verify` is the mode the hook calls.
"""

import datetime

from .context import Context
from .merge import ITEMS as MERGE
from .repo import GateError
from .reviews import Recheck, Review, ReviewError
from .verdict import Result, Verdict
from .waivers import FILENAME as WAIVERS, parse as parse_waivers

__all__ = ["GateError", "MERGE", "Recheck", "Result", "Review",
           "ReviewError", "Verdict", "evaluate", "merge", "status"]


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
    ctx = Context.at(path, branch, verify=verify, fresh=fresh,
                     today=today or datetime.date.today(), runner=runner)
    return evaluate("merge", MERGE, ctx)


def status(path=None, branch=None, *, today=None):
    """Every gate that applies to `branch` (default: HEAD's), verifying:
    `merge`'s verdict."""
    return [merge(path, branch, verify=True, today=today)]
