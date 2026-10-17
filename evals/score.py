"""The catch rate of each eval case, from `claude plugin eval --json`.

    uv run --project engine python evals/score.py <out>.json

A run is caught only when every `catch-*` grader passed and no `peeked-*`
grader did: the built-in score averages graders, so it credits half a catch,
and a run that read the answers is a copy. Every other grader is a
diagnostic, counted and never part of the catch. Exits 1 unless the result is
whole and every case is caught in at least 2/3 of its runs (evals/README.md).
"""

import json
import sys
from dataclasses import dataclass, field
from fractions import Fraction

GATE = Fraction(2, 3)


@dataclass
class Row:
    """One case: its with-arm runs, caught and peeked, its baseline's, and how
    many with-arm runs passed each diagnostic."""
    case: str
    runs: int
    caught: int
    peeked: int
    base_runs: int
    base_caught: int
    diagnostics: dict = field(default_factory=dict)

    @property
    def delta(self):
        """The with-arm catch rate less the baseline's; None with no
        baseline."""
        if not (self.runs and self.base_runs):
            return None
        return self.caught / self.runs - self.base_caught / self.base_runs

    @property
    def passes(self):
        return self.runs > 0 and Fraction(self.caught, self.runs) >= GATE


def _graders(run):
    return {g["name"]: g["passed"] for g in run.get("graders") or []}


def _caught(run):
    """Whether `run` caught the trap, and whether it peeked."""
    passed = _graders(run)
    catches = [ok for name, ok in passed.items() if name.startswith("catch-")]
    peeked = any(ok for name, ok in passed.items()
                 if name.startswith("peeked-"))
    return bool(catches) and all(catches) and not peeked, peeked


def _arm(case, arm):
    runs = [_caught(r) for r in case["arms"].get(arm) or []]
    return len(runs), sum(c for c, _ in runs), sum(p for _, p in runs)


def _diagnostics(runs):
    counts = {}
    for run in runs:
        for name, ok in _graders(run).items():
            if not name.startswith(("catch-", "peeked-")):
                counts[name] = counts.get(name, 0) + ok
    return counts


def score(doc):
    """A `Row` per case in `doc`, a `--json` result."""
    rows = []
    for case in doc["cases"]:
        runs, caught, peeked = _arm(case, "with")
        base_runs, base_caught, _ = _arm(case, "without")
        rows.append(Row(case["name"], runs, caught, peeked, base_runs,
                        base_caught,
                        _diagnostics(case["arms"].get("with") or [])))
    return rows


def main(argv):
    doc = json.loads(open(argv[0], encoding="utf-8").read())
    rows = score(doc)
    for r in rows:
        base = (f"baseline {r.base_caught}/{r.base_runs}  Δ {r.delta:+.2f}"
                if r.delta is not None else "no baseline")
        print(f"{'PASS' if r.passes else 'FAIL'}  {r.case}: caught "
              f"{r.caught}/{r.runs}  {base}  peeked {r.peeked}")
        print("      " + ", ".join(f"{n} {k}/{r.runs}"
                                   for n, k in r.diagnostics.items()))
    whole = not doc.get("partial")
    if not whole:
        print(f"partial result ({doc.get('partialReason')}): not a gate run")
    ok = whole and bool(rows) and all(r.passes for r in rows)
    print(f"suite {'passes' if ok else 'fails'}: every case at "
          f"{GATE.numerator}/{GATE.denominator} or above, the result whole")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
