"""The red team's findings blocks (ADR 0011, `agents/red-team.md`): the one
fenced `toml` block a review or a recheck in `docs/reviews/` ends with.

A review's block:

    reviewed = "<sha>"
    artifacts = ["docs/01-spec/spec.md", "ledger.toml"]

    [[finding]]
    id = "F3"
    severity = "MAJOR"           # BLOCKER | MAJOR | MINOR | QUESTION
    status = "fixed"             # open | fixed | accepted
    closure = { check = "analysis/model/review_2026-10-21_spec_checks.py::test_F3_spring_rate", moves = ["part.rs02.torque_peak"] }

A recheck's block names the review it rechecks, and marks each finding it
was given `holds` or `reopened`:

    reviewed = "<sha>"
    rechecks = "docs/reviews/2026-10-21-spec-review.md"

    [[finding]]
    id = "F3"
    status = "holds"

A split review's staging files, under `docs/reviews/staging/`, carry no
block and are never read.
"""

import re
import tomllib
from dataclasses import dataclass
from pathlib import PurePosixPath

REVIEWS = "docs/reviews"
SEVERITIES = ("BLOCKER", "MAJOR", "MINOR", "QUESTION")
BLOCKING = ("BLOCKER", "MAJOR")
STATUSES = ("open", "fixed", "accepted")
RECHECKED = ("holds", "reopened")
CLOSURE_FIELDS = ("check", "recheck", "reason", "moves")

OPEN_FENCE = re.compile(r"(`{3,}|~{3,})\s*toml\s*")
NAME = re.compile(r"(\d{4}-\d{2}-\d{2})-(.+)-review\.md")


class ReviewError(ValueError):
    """A block that cannot be read: not TOML, or not the contract's shape."""


@dataclass(frozen=True)
class Finding:
    """One finding of a review. `closure` is its table, {} if it has
    none."""
    id: str
    severity: str
    status: str
    closure: dict

    @property
    def blocking(self):
        return self.severity in BLOCKING

    @property
    def moves(self):
        return tuple(self.closure.get("moves", ()))


@dataclass(frozen=True)
class Review:
    """A review: the commit it is pinned to, what it read, its findings."""
    path: str
    reviewed: str
    artifacts: tuple
    findings: tuple

    @property
    def checks_name(self):
        """The file name its checks land in,
        `review_<date>_<artifact>_checks.py`."""
        name = PurePosixPath(self.path).name
        match = NAME.fullmatch(name)
        stem = (f"{match[1]}_{match[2]}" if match
                else PurePosixPath(name).stem)
        return f"review_{stem}_checks.py"


@dataclass(frozen=True)
class Recheck:
    """A recheck of the review at `rechecks`: each finding id it was given,
    `holds` or `reopened`."""
    path: str
    reviewed: str
    rechecks: str
    findings: dict


def paths(files):
    """The review and recheck files among `files`: each `.md` directly in
    `docs/reviews/`, never in `staging/` below it."""
    return [p for p in files
            if str(PurePosixPath(p).parent) == REVIEWS
            and p.lower().endswith(".md")]


def block(text, path):
    """The last fenced `toml` block in `text`, parsed; None where there is
    none."""
    lines, found, at = text.splitlines(), None, 0
    while at < len(lines):
        opened = OPEN_FENCE.fullmatch(lines[at].strip())
        at += 1
        if not opened:
            continue
        fence, body = opened[1], []
        while at < len(lines) and not (
                lines[at].strip().startswith(fence[0] * len(fence))
                and not lines[at].strip().strip(fence[0])):
            body.append(lines[at])
            at += 1
        at += 1
        found = "\n".join(body)
    if found is None:
        return None
    try:
        return tomllib.loads(found)
    except tomllib.TOMLDecodeError as e:
        raise ReviewError(f"{path}: its block is not TOML: {e}") from None


def parse(text, path):
    """The review or recheck `text` holds, read from `path`; None where it
    ends in no block."""
    data = block(text, path)
    if data is None:
        return None
    fields = {"reviewed", "finding",
              "rechecks" if "rechecks" in data else "artifacts"}
    for key in data:
        if key not in fields:
            raise ReviewError(f"{path}: {key} is not a field of its block; "
                              f"they are {', '.join(sorted(fields))}")
    reviewed = _text(path, "reviewed", data.get("reviewed"))
    findings = data.get("finding", [])
    if not isinstance(findings, list):
        raise ReviewError(f"{path}: finding is an array of tables, "
                          f"[[finding]]")
    ids = [_text(path, "finding.id", f.get("id")) if isinstance(f, dict)
           else _text(path, "finding", None) for f in findings]
    if len(ids) != len(set(ids)):
        raise ReviewError(f"{path}: a finding id is written twice")
    if "rechecks" in data:
        return Recheck(path, reviewed,
                       _text(path, "rechecks", data["rechecks"]),
                       {i: _recheck(path, f) for i, f in zip(ids, findings)})
    artifacts = data.get("artifacts", [])
    if not (isinstance(artifacts, list)
            and all(isinstance(a, str) for a in artifacts)):
        raise ReviewError(f"{path}: artifacts is a list of paths")
    return Review(path, reviewed, tuple(artifacts),
                  tuple(_finding(path, i, f) for i, f in zip(ids, findings)))


def _text(path, field, x):
    if not isinstance(x, str) or not x.strip():
        raise ReviewError(f"{path}: {field} is a string; got {x!r}")
    return x


def _choice(path, field, x, choices):
    if x not in choices:
        raise ReviewError(f"{path}: {field} is one of {', '.join(choices)}; "
                          f"got {x!r}")
    return x


def _recheck(path, f):
    where = f"{path}: {f['id']}"
    for key in f:
        if key not in ("id", "status"):
            raise ReviewError(f"{where}: {key} is not a field of a "
                              f"recheck's finding")
    return _choice(where, "status", f.get("status"), RECHECKED)


def _finding(path, id, f):
    where = f"{path}: {id}"
    for key in f:
        if key not in ("id", "severity", "status", "closure"):
            raise ReviewError(f"{where}: {key} is not a field of a finding")
    closure = f.get("closure", {})
    if not isinstance(closure, dict):
        raise ReviewError(f"{where}: closure is a table")
    for key, value in closure.items():
        if key not in CLOSURE_FIELDS:
            raise ReviewError(f"{where}: closure.{key} is not a field; they "
                              f"are {', '.join(CLOSURE_FIELDS)}")
        if key == "moves":
            if not (isinstance(value, list)
                    and all(isinstance(m, str) for m in value)):
                raise ReviewError(f"{where}: closure.moves is a list of "
                                  f"ledger entry names")
        else:
            _text(where, f"closure.{key}", value)
    return Finding(id, _choice(where, "severity", f.get("severity"),
                               SEVERITIES),
                   _choice(where, "status", f.get("status"), STATUSES),
                   dict(closure))
