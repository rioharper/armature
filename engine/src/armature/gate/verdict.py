"""A gate's verdict: one result per item of evidence, each `pass`, `fail`
or `waived`, and the warnings met computing them."""

from dataclasses import dataclass, field

STATES = ("pass", "fail", "waived")


@dataclass(frozen=True)
class Result:
    """One item of evidence: its id, its state and what it found."""
    item: str
    state: str
    detail: str

    def __str__(self):
        return f"{self.state} {self.item} {self.detail}"

    def as_dict(self):
        return {"item": self.item, "state": self.state,
                "detail": self.detail}


@dataclass
class Verdict:
    """A gate computed for a branch at its tip commit."""
    gate: str
    branch: str
    tip: str
    results: list
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)   # printed after the items

    @property
    def passed(self):
        return all(r.state != "fail" for r in self.results)

    def __getitem__(self, item):
        for r in self.results:
            if r.item == item:
                return r
        raise KeyError(f"{self.gate} has no item {item!r}; its items are "
                       f"{', '.join(r.item for r in self.results)}")

    def lines(self):
        """The printed verdict: a line per item, then `warning` lines, then
        its notes."""
        return ([str(r) for r in self.results]
                + [f"warning {w}" for w in self.warnings] + self.notes)

    def as_dict(self):
        return {"gate": self.gate, "branch": self.branch, "tip": self.tip,
                "passed": self.passed,
                "items": [r.as_dict() for r in self.results],
                "warnings": list(self.warnings), "notes": list(self.notes)}
