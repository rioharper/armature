"""The catch rate of each eval case, from `claude plugin eval --json`.

    uv run --project engine python evals/score.py <out>.json

A run is caught only when every `catch-*` grader passed and no `peeked-*`
grader did: the built-in score averages graders, so it credits half a catch,
and a run that read the answers is a copy. A red-team run whose
`false-alarm` grader failed raised a BLOCKER or MAJOR the golden derivation
shows wrong: it is counted beside the catch, and never gates. Every other
grader is a diagnostic, counted and never part of the catch. Exits 1 unless
the result is whole and every case but the hold-out is caught in at least
2/3 of its runs (evals/README.md).

A hold-out case, one under evals/holdout/, is reported in a section of its
own beside the gate, with its baseline and Δ, and never moves the exit code
either way (#132).
"""

import json
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

GATE = Fraction(2, 3)
ALARM = "false-alarm"
# The hold-out cases, each named for its directory under evals/holdout/.
HOLDOUT = {p.parent.name for p in
           (Path(__file__).resolve().parent / "holdout").glob("*/case.yaml")}


@dataclass
class Row:
    """One case: its with-arm runs, caught and peeked, its baseline's, how
    many with-arm runs passed each diagnostic, and how many raised a false
    alarm, None for a case with no `false-alarm` grader."""
    case: str
    runs: int
    caught: int
    peeked: int
    base_runs: int
    base_caught: int
    diagnostics: dict = field(default_factory=dict)
    false_alarms: int | None = None

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
            if not name.startswith(("catch-", "peeked-", ALARM)):
                counts[name] = counts.get(name, 0) + ok
    return counts


def _false_alarms(runs):
    """How many of `runs` failed their `false-alarm` grader, or None where
    none carries one."""
    alarms = [ok for run in runs for name, ok in _graders(run).items()
              if name == ALARM]
    return sum(not ok for ok in alarms) if alarms else None


def score(doc):
    """A `Row` per case in `doc`, a `--json` result."""
    rows = []
    for case in doc["cases"]:
        runs, caught, peeked = _arm(case, "with")
        base_runs, base_caught, _ = _arm(case, "without")
        with_runs = case["arms"].get("with") or []
        rows.append(Row(case["name"], runs, caught, peeked, base_runs,
                        base_caught, _diagnostics(with_runs),
                        _false_alarms(with_runs)))
    return rows


def _print(r, verdict):
    base = (f"baseline {r.base_caught}/{r.base_runs}  Δ {r.delta:+.2f}"
            if r.delta is not None else "no baseline")
    alarms = ("" if r.false_alarms is None
              else f"  false alarms {r.false_alarms}/{r.runs}")
    print(f"{verdict}  {r.case}: caught "
          f"{r.caught}/{r.runs}  {base}  peeked {r.peeked}{alarms}")
    print("      " + ", ".join(f"{n} {k}/{r.runs}"
                               for n, k in r.diagnostics.items()))


def main(argv):
    doc = json.loads(open(argv[0], encoding="utf-8").read())
    rows, held = [], []
    for r in score(doc):
        (held if r.case in HOLDOUT else rows).append(r)
    for r in rows:
        _print(r, "PASS" if r.passes else "FAIL")
    if held:
        print("hold-out, reported beside the gate and never part of it:")
    for r in held:
        _print(r, "no verdict")  # a hold-out never passes or fails
    whole = not doc.get("partial")
    if not whole:
        print(f"partial result ({doc.get('partialReason')}): not a gate run")
    ok = whole and bool(rows) and all(r.passes for r in rows)
    print(f"suite {'passes' if ok else 'fails'}: every case but the hold-out "
          f"at {GATE.numerator}/{GATE.denominator} or above, the result "
          f"whole")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
