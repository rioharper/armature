"""Waivers: an exemption from an item of a gate's evidence, argued in the
project's root `waivers.toml` and confirmed by the user (ADR 0011).

    [[waiver]]
    gate = "merge"                 # merge | buy
    item = "review"                # an item's id, as the gate prints it
    scope = "armature/m0-setup"    # a branch, or "standing"
    reason = "the template copy makes no claim to review"
    confirmed = 2026-10-21         # the date the user confirmed it

A waiver applies to a failing item of its gate on its branch, or on every
branch when it is `standing`. One with no `confirmed` date, or one that
cannot be read, is ignored with a warning.
"""

import datetime
import tomllib
from dataclasses import dataclass

FILENAME = "waivers.toml"
GATES = ("merge", "buy")
STANDING = "standing"


@dataclass(frozen=True)
class Waiver:
    gate: str
    item: str
    scope: str
    reason: str
    confirmed: datetime.date

    def applies(self, gate, branch, item):
        return (self.gate == gate and self.item == item
                and self.scope in (branch, STANDING))


def parse(text):
    """The confirmed waivers in `text`, and a warning for each one
    ignored."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        return [], [f"{FILENAME} is not TOML, so no waiver applies: {e}"]
    tables = data.get("waiver", [])
    if not isinstance(tables, list):
        return [], [f"{FILENAME}: waiver is an array of tables, [[waiver]]"]
    found, warnings = [], []
    for n, w in enumerate(tables, 1):
        where = (f"{FILENAME}: waiver {n} ({w.get('gate')} {w.get('item')}, "
                 f"{w.get('scope')})" if isinstance(w, dict)
                 else f"{FILENAME}: waiver {n}")
        problem = _problem(w)
        if problem:
            warnings.append(f"{where} {problem}, so it is ignored")
            continue
        found.append(Waiver(w["gate"], w["item"], w["scope"], w["reason"],
                            w["confirmed"]))
    return found, warnings


def _problem(w):
    if not isinstance(w, dict):
        return "is not a table"
    if w.get("gate") not in GATES:
        return f"names no gate; gate is one of {', '.join(GATES)}"
    for field in ("item", "scope", "reason"):
        if not (isinstance(w.get(field), str) and w[field].strip()):
            return f"has no {field}"
    confirmed = w.get("confirmed")
    if confirmed is None:
        return "has no confirmed date"
    if not isinstance(confirmed, datetime.date) or isinstance(
            confirmed, datetime.datetime):
        return "has a confirmed that is not a TOML date, such as 2026-10-21"
    return None
