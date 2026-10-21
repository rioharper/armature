"""A budget's arithmetic: its lines resolved, their total against its
allocation, and the requirements its breach fails. Nothing here is stored;
`show`, `render` and `check` each work it out on read."""

import re
from dataclasses import dataclass

from .entries import ALLOCATION, LedgerError
from .units import parse_unit

BREACH = 1e-12   # a total past its allocation by less, relative, is level
REQ_ID = re.compile(r"\bREQ-\d+\b")


class BudgetUnitError(LedgerError):
    """A budget line in another unit from its budget's: `entry` is the
    line, the finding `check` reports it as `budget.unit`."""

    def __init__(self, entry, message):
        super().__init__(f"{entry}: {message}")
        self.entry = entry
        self.reason = message


@dataclass(frozen=True)
class Tally:
    """A budget `budget.<kind>`: each line's entry and resolved value, its
    allocation entry (or None), the unit they are all in, and `allowed`,
    the allocation's resolved value (or None)."""
    name: str
    lines: list
    allocation: object
    unit: str
    allowed: float = None

    @property
    def total(self):
        return sum(value for _, value in self.lines)

    @property
    def margin(self):
        """The allocation less the total, or None with no allocation."""
        if self.allowed is None:
            return None
        return self.allowed - self.total

    @property
    def breached(self):
        return self.margin is not None and -self.margin > BREACH * max(
            abs(self.allowed), abs(self.total))


def budgets(ledger):
    """The ledger's budget names, `budget.<kind>`, in file order."""
    return [s for s in ledger.sections if s.startswith("budget.")]


def tally(ledger, budget):
    """`budget`'s lines resolved, in the allocation's unit or its first
    line's. Raises on a line in another unit or an `of` it cannot follow."""
    entries = [e for e in ledger if e.section == budget]
    allocation = next((e for e in entries if e.key == ALLOCATION), None)
    lines = [e for e in entries if e.key != ALLOCATION]
    units = {e.name: ledger.unit(e.name) for e in entries}
    unit = (units[allocation.name] if allocation is not None
            else units[lines[0].name] if lines else "1")
    for name, other in units.items():
        if parse_unit(other) != parse_unit(unit):
            raise BudgetUnitError(name, f"a {budget} line is in {other}, "
                                  f"and the budget in {unit}")
    return Tally(budget, [(e, ledger.resolve(e.name)) for e in lines],
                 allocation, unit,
                 None if allocation is None
                 else ledger.resolve(allocation.name))


def reqs(ledger, budget):
    """The REQ ids `budget` answers to: each `req.*` entry one of its
    entries' `of` chains reaches, and each REQ id its entries' own
    `source.ref` names. A breach of the budget fails each."""
    found = []
    for e in ledger:
        if e.section != budget:
            continue
        if e.source is not None:
            found += REQ_ID.findall(e.source.get("ref", ""))
        try:
            found += [c.key for c in ledger.chain(e.name)[1:]
                      if c.section == "req"]
        except LedgerError:   # check reports the of itself
            pass
    return list(dict.fromkeys(found))
