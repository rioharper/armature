"""`buy`'s evidence beyond `merge`'s (ADR 0011), item by item, on a branch
adding one order record (`orders`). Each item is a function of the gate's
`Context` returning (passed, detail), as `merge`'s are, and `ITEMS` names
them so a `buy` waiver can.

A purchase's items: the record itself, every entry of each ordered part
confirmed and none an estimate, each line's price tier fresh, and a review
naming the record. A release's: each part's stubs gone, and each part's
and the model's `run_all.py` stamped green (`release`).
"""

import datetime
import re

from ..ledger import LedgerError
from ..ledger.check import PRICE_AGE    # its price.old, an error here
from ..ledger.entries import ESTIMATE
from . import orders, release

TIER = re.compile(r"price_at_(\d+)")


def order(ctx):
    """The branch adds exactly one order record, of the contract's shape;
    a release's exports are committed."""
    found, problem = orders.record(ctx)
    if found is None:
        return False, problem
    missing = [e for line in found.lines for e in line.exports
               if e not in ctx.files]
    if missing:
        return False, (f"{found.path}: the exports {', '.join(missing)} are "
                       f"not at the tip; commit what is sent out")
    return True, (f"{found.path}: a {found.kind} from {found.vendor}, "
                  f"{len(found.lines)} line(s)")


def _purchase(ctx):
    """(order, ledger, None) for a purchase, the ledger at the tip read;
    else (None, None, the item's result)."""
    found, result = orders.of_kind(ctx, "purchase", "buys no part")
    if found is None:
        return None, None, result
    try:
        ledger = ctx.ledger(ctx.tip)
    except LedgerError as e:
        return None, None, (False, f"cannot read the ledger: {e}")
    if ledger is None:
        return None, None, (False, "no ledger.toml at the project root")
    return found, ledger, None


def confirmed(ctx):
    """Every entry under each part the order's lines name is confirmed,
    and none rests on an estimate, through its `of` chain."""
    found, ledger, result = _purchase(ctx)
    if found is None:
        return result
    failed, count = [], 0
    for line in found.lines:
        entries = [e for e in ledger if e.section == line.part]
        if not entries:
            failed.append(f"{line.part} has no entry in the ledger")
        for e in entries:
            count += 1
            try:
                chain = ledger.chain(e.name)
            except LedgerError as error:
                failed.append(f"{e.name}: {error}")
                continue
            if e.effective_status != "confirmed":
                failed.append(f"{e.name} is {e.effective_status or 'of no '
                                              'status'}, not confirmed")
            rests = [c.name for c in chain if c.kind == ESTIMATE]
            if rests:
                failed.append(f"{e.name} rests on an estimate, "
                              f"{', '.join(rests)}")
    if failed:
        return False, "; ".join(failed)
    named = dict.fromkeys(line.part for line in found.lines)
    return True, (f"{count} entr{'y' if count == 1 else 'ies'} of "
                  f"{', '.join(named)} confirmed, none an estimate")


def tier(ledger, line):
    """The entry a line's price is: the largest `price_at_<n>` of its part
    at or below its qty, or None."""
    tiers = {int(m[1]): e for e in ledger if e.section == line.part
             and (m := TIER.fullmatch(e.key))}
    at = [n for n in tiers if n <= line.qty]
    return tiers[max(at)] if at else None


def price(ctx):
    """Each line's price, its tier (`tier`), was retrieved no more than 90
    days ago: `price.old`, a warning to `ledger check`, is an error here."""
    found, ledger, result = _purchase(ctx)
    if found is None:
        return result
    failed, notes = [], []
    for line in found.lines:
        e = tier(ledger, line)
        if e is None:
            failed.append(f"{line.part} x {line.qty}: no price_at_<n> tier "
                          f"at or below {line.qty}")
            continue
        retrieved = (e.source or {}).get("retrieved")
        if not isinstance(retrieved, datetime.date):
            failed.append(f"{e.name} has no retrieved date")
            continue
        age = (ctx.today - retrieved).days
        if age > PRICE_AGE:
            failed.append(f"price.old {e.name}: retrieved {retrieved}, "
                          f"{age} days ago, past {PRICE_AGE}; re-check it")
        else:
            notes.append(f"{line.part} x {line.qty} at {e.name}, "
                         f"{age} days old")
    if failed:
        return False, "; ".join(failed)
    return True, "; ".join(notes)


def review(ctx):
    """A review counted on the branch lists the order record in its
    `artifacts`, pinned at a commit holding it. An order is never
    review-free."""
    found, problem = orders.record(ctx)
    path = found.path if found else orders.order(ctx)
    if path is None:
        return False, f"no order to review: {problem}"
    listing = [(r, sha) for r, sha in ctx.counted if path in r.artifacts]
    holding = [r.path for r, sha in listing
               if ctx.repo.object(sha, path) is not None]
    if holding:
        return True, f"{path} reviewed in {', '.join(holding)}"
    if listing:
        return False, (f"{', '.join(r.path for r, _ in listing)} list(s) "
                       f"{path}, which is not at the commit reviewed")
    return False, (f"no review on the branch lists {path} in its "
                   f"artifacts; an order is never review-free")


# Each item's id, in the order the gate prints them after merge's.
ITEMS = [("order", order), ("confirmed", confirmed), ("price", price),
         ("order-review", review),
         ("placeholders", release.placeholders),
         ("release-stamps", release.stamped)]
