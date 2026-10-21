"""What a diff changes that a review gates: a ledger number, model code, a
part definition, or spec or plan text outside the rendered sections."""

from pathlib import PurePosixPath

import numpy as np

from ..ledger import LedgerError
from ..ledger.entries import FILENAME
from ..ledger.views import unrendered

MODEL = "analysis/model/"
CAD = "cad/"
OTS = "cad/ots-parts/"          # vendor models the librarian caches
PART_SUFFIXES = (".md", ".py")
TEXT = ("docs/01-spec/", "docs/02-plan/")


def numbers(old, new):
    """The entries whose numbers differ between ledgers `old` and `new`
    (either None for no ledger): an entry added or removed, or its
    `value`, `band`, `status`, `of` or `qty` changed."""
    a = {} if old is None else old.entries
    b = {} if new is None else new.entries
    return sorted(n for n in {*a, *b}
                  if n not in a or n not in b or not _same(a[n], b[n]))


def _same(e, f):
    return (_equal(e.value, f.value) and e.status == f.status
            and e.of == f.of and e.qty == f.qty
            and (e.band is None) == (f.band is None)
            and (e.band is None or all(_equal(x, y)
                                       for x, y in zip(e.band, f.band))))


def _equal(x, y):
    if x is None or y is None:
        return x is y
    return np.shape(x) == np.shape(y) and bool(np.all(np.equal(x, y)))


def text_outside(repo, old_rev, new_rev, path):
    """Whether `path`'s text differs between the two commits outside its
    rendered ledger sections. A file added, removed or not markdown, or
    one whose markers cannot be read, differs."""
    if not path.lower().endswith(".md"):
        return True
    old = repo.text(old_rev, path) if old_rev else None
    new = repo.text(new_rev, path)
    if old is None or new is None:
        return True
    try:
        return unrendered(path, old) != unrendered(path, new)
    except LedgerError:
        return True


def gated(ctx):
    """Why the branch needs a review: one reason per thing it changes that
    a review gates, from its branch point to its tip. A ledger that will
    not parse at either end counts as every number changed."""
    reasons = []
    if FILENAME in ctx.changed:
        try:
            moved = numbers(ctx.ledger(ctx.base) if ctx.base else None,
                            ctx.ledger(ctx.tip))
        except LedgerError:
            moved = [FILENAME]
        reasons += [f"ledger number {n}" for n in moved]
    for path in ctx.changed:
        what = kind(path)
        if what is not None and (what != "text" or text_outside(
                ctx.repo, ctx.base, ctx.tip, path)):
            reasons.append(f"{what} {path}")
    return reasons


def kind(path):
    """What a review gates that `path` is: `model code`, a `part
    definition`, or spec or plan `text` (gated outside its rendered
    sections alone); None for anything else. The ledger is gated by its
    numbers (`numbers`), never by its path."""
    if path.startswith(MODEL):
        return "model code"
    if (path.startswith(CAD) and not path.startswith(OTS)
            and PurePosixPath(path).suffix in PART_SUFFIXES):
        return "part definition"
    if path.startswith(TEXT):
        return "text"
    return None
