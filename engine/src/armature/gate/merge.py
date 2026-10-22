"""`merge`'s evidence, item by item (ADR 0011). Each item is a function of
the gate's `Context` returning (passed, detail), named by its id in `ITEMS`
so a waiver can name it and `buy` can extend the list. Items 3 and 4 live
in `stamps` and `engine`."""

import ast
import tempfile
from pathlib import Path, PurePosixPath

from ..ledger import LedgerError, check
from ..ledger.entries import FILENAME
from . import engine, reviews, stamps
from .changes import gated, numbers
from .repo import MAIN

ERRORS_SHOWN = 3


def fast_forward(ctx):
    """1. `main` is an ancestor of the tip, so the merge is a fast-forward
    and the tree checked is the tree `main` becomes."""
    if ctx.main is None:
        return False, f"there is no branch {MAIN}"
    if ctx.repo.is_ancestor(ctx.main, ctx.tip):
        return True, f"{MAIN} is an ancestor of {ctx.tip[:7]}"
    return False, (f"{MAIN} ({ctx.main[:7]}) is not an ancestor of "
                   f"{ctx.tip[:7]}; merge {MAIN} into {ctx.branch} first")


def ledger(ctx):
    """2. `ledger check` reports no error on the ledger at the tip, read
    with the project's markdown its views are checked against."""
    if FILENAME not in ctx.files:
        return False, f"no {FILENAME} at the project root"
    with tempfile.TemporaryDirectory() as tmp:
        ctx.repo.export(ctx.tip, [FILENAME, *(
            p for p in ctx.files if p.lower().endswith(".md"))], tmp)
        try:
            findings = check(Path(tmp) / FILENAME, today=ctx.today)
        except LedgerError as e:
            return False, str(e).replace(tmp, "").lstrip("\\/")
    errors = [f for f in findings if f.level == "error"]
    if errors:
        shown = "; ".join(str(f) for f in errors[:ERRORS_SHOWN])
        more = len(errors) - ERRORS_SHOWN
        return False, (f"{len(errors)} error(s): {shown}"
                       + (f"; and {more} more" if more > 0 else ""))
    return True, f"no error, {len(findings)} warning(s)"


def review(ctx):
    """5. A review, where the branch changes a ledger number, model code, a
    part definition, or spec or plan text outside the rendered sections;
    it counts when its `reviewed` SHA is on the branch, at or after the
    branch point. A review whose block cannot be read fails here."""
    broken = [f"cannot read {path}: {error}"
              for path, error in ctx.blocks.unreadable if path in ctx.changed]
    if broken:
        return False, "; ".join(broken)
    reasons = gated(ctx)
    counted = [r.path for r, _ in ctx.counted]
    if not reasons:
        return True, ("no review needed: the branch changes no ledger "
                      "number, model code, part definition, or spec or "
                      "plan text" + (f"; counted {', '.join(counted)}"
                                     if counted else ""))
    if counted:
        return True, f"counted {', '.join(counted)}"
    shown = ", ".join(reasons[:ERRORS_SHOWN]) + (
        f" and {len(reasons) - ERRORS_SHOWN} more"
        if len(reasons) > ERRORS_SHOWN else "")
    missed = [f"{r.path} is pinned to {r.reviewed[:7]}, {_where(ctx, r)}"
              for r in ctx.blocks.read if isinstance(r, reviews.Review)
              and r.path in ctx.changed]
    return False, (f"the branch changes {shown}, and no review is pinned to "
                   f"a commit on it" + "".join(f"; {m}" for m in missed))


def _where(ctx, r):
    """Why review `r` does not count."""
    commit = ctx.repo.commit(r.reviewed)
    if commit is None:
        return "which is no commit"
    if ctx.base is not None and ctx.repo.is_ancestor(commit, ctx.base):
        return f"before the branch point {ctx.base[:7]}"
    return f"which is not on {ctx.branch}"


def closed(ctx):
    """6. Every BLOCKER and MAJOR of every counted review is closed: fixed
    with a check in the review's checks file or a recheck that holds, or
    accepted with a reason. A later recheck that reopens it opens it."""
    still, count = [], 0
    for r, sha in ctx.counted:
        for f in r.findings:
            if f.blocking:
                count += 1
                why = _open(ctx, r, sha, f)
                if why:
                    still.append(f"{r.path} {f.id} ({f.severity}) {why}")
    if still:
        return False, "; ".join(still)
    return True, (f"{count} BLOCKER or MAJOR finding(s) closed in "
                  f"{len(ctx.counted)} review(s)")


def _open(ctx, r, sha, f):
    """Why finding `f` of review `r` is open, or None where it is
    closed."""
    last = None
    for recheck, _ in ctx.rechecks:
        if recheck.rechecks == r.path and f.id in recheck.findings:
            last = recheck
    if last is not None and last.findings[f.id] == "reopened":
        return f"is reopened by {last.path}"
    if f.status == "open":
        return "is open"
    c = f.closure
    if f.status == "accepted":
        return None if c.get("reason") else "is accepted with no reason"
    if ("check" in c) == ("recheck" in c):
        return "is fixed, and its closure names no check or recheck, or both"
    return (_check(ctx, r, c["check"]) if "check" in c
            else _recheck(ctx, r, sha, f, c["recheck"]))


def _check(ctx, r, check):
    """Why `check`, `<file>::<test>`, does not back a fix of review `r`, or
    None: the test is in the review's checks file, beside a `run_all.py`
    that collects it, whose stamp is item 3's."""
    file, _, test = check.partition("::")
    where = PurePosixPath(file)
    if where.name != r.checks_name:
        return f"is fixed by {file}, which is not the review's checks file, " \
               f"{r.checks_name}"
    if file not in ctx.files:
        return f"is fixed by {file}, which is not at the tip"
    if str(where.parent / stamps.RUN_ALL) not in ctx.files:
        return (f"is fixed by {file}, and no {stamps.RUN_ALL} beside it "
                f"collects it")
    try:
        tree = ast.parse(ctx.repo.text(ctx.tip, file))
    except SyntaxError as e:
        return f"is fixed by {file}, which does not parse: {e}"
    defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    if not test.startswith("test_") or test not in defined:
        return f"is fixed by {check}, and {file} defines no {test or 'test'}"
    return None


def _recheck(ctx, r, sha, f, path):
    """Why the recheck at `path` does not close finding `f`, or None."""
    for recheck, rsha in ctx.rechecks:
        if recheck.path == path and recheck.rechecks == r.path \
                and ctx.repo.is_ancestor(sha, rsha):
            status = recheck.findings.get(f.id)
            return None if status == "holds" else \
                f"is not marked holds by {path}"
    return f"is fixed by {path}, which is no recheck of {r.path} pinned " \
           f"after it on the branch"


def moves(ctx):
    """7. Every ledger number changed after a counted review's SHA is named
    in some closure's `moves`."""
    if not ctx.counted:
        return True, "no counted review"
    named = {m for r, _ in ctx.counted for f in r.findings for m in f.moves}
    unnamed = {}
    for r, sha in ctx.counted:
        try:
            moved = numbers(ctx.ledger(sha), ctx.ledger(ctx.tip))
        except LedgerError as e:
            return False, f"cannot compare the ledger since {r.path}: {e}"
        for name in moved:
            if name not in named:
                unnamed.setdefault(name, r.path)
    if unnamed:
        return False, "; ".join(f"{name} changed after {path} and no "
                                f"closure's moves names it"
                                for name, path in unnamed.items())
    return True, (f"{len(named)} number(s) named in moves; none changed "
                  f"unnamed")


# Each item's id, in the order the gate prints them.
ITEMS = [("fast-forward", fast_forward), ("ledger", ledger),
         ("stamps", stamps.check), ("engine", engine.check),
         ("review", review), ("closed", closed), ("moves", moves)]
