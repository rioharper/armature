"""The plugin hook's decision (ADR 0011, #158): what Claude Code's
PreToolUse hook answers for one tool call, as a pure function of the tool's
name, its input and the repo it acts on.

    decide("Bash", {"command": "git merge armature/spec-arm"}, cwd)
    -> Decision("deny", "<the gate's lines>"), or None

`None` leaves the call to Claude Code's own permissions; the hook never
allows. In a project, a git repo whose root holds `ledger.toml`:
- **`Bash` or `PowerShell`** (`commands`): a `git merge` with `main`
  checked out, `gh pr merge` into `main`, or a `git push` to a `main`
  refspec is denied with the gate's output unless `merge` (`buy` for an
  order branch) passes, verifying: reading the stamps, running nothing. A
  `git commit` on `main` is denied when it touches gated paths outside the
  rendered ledger sections, or does more to the ledger than add or edit
  `candidate` entries.
- **`Edit`, `Write`, `MultiEdit` or `NotebookEdit`**: a path under
  `.armature/`, where the stamps live, is denied. An edit that introduces
  `status = "accepted"` in `docs/reviews/`, confirms an entry of
  `ledger.toml` (its effective status, written or by a `chosen` or
  `standard` source kind), or adds or confirms a `[[waiver]]` in
  `waivers.toml` is asked about (`ask`), naming what it confirms.

Outside a project nothing is decided. `python -m armature.gate.hook` reads
the hook's JSON event on stdin and prints the decision's JSON, or nothing;
`scripts/armature.sh hook` runs it on the plugin's own engine.
"""

import json
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ..ledger.entries import FILENAME, status_of
from . import commands, reviews, waivers
from .commands import HookError
from .repo import OWN, GateError, Repo

SHELLS = {"Bash": "bash", "PowerShell": "powershell"}
EDITS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
PREFIX = "Armature (ADR 0011): "
CONFIRMED = re.compile(r"""status\s*=\s*["']confirmed["']""")
ACCEPTED = re.compile(r"""status\s*=\s*["']accepted["']""")
WAIVER = re.compile(r"^\s*\[\[\s*waiver\s*\]\]", re.M)


@dataclass(frozen=True)
class Decision:
    """A PreToolUse decision: `deny` or `ask`, and the reason Claude (for a
    denial) or the user (for a question) reads."""
    permission: str
    reason: str

    def as_hook(self):
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": self.permission,
            "permissionDecisionReason": self.reason}}


def decide(tool_name, tool_input, cwd, *, gate=None, pr=None):
    """The decision for the tool call `tool_name(tool_input)` made from the
    folder `cwd`, or None. `gate(root, branch)` is the verdict a branch
    must pass (default: `buy` for an order branch, else `merge`, verifying);
    `pr(root, ref)` is what `gh pr merge <ref>` merges, a dict of `head`,
    `base` and `oid` (default: asked of `gh`). Where git itself fails on
    a project's repo, the call is denied with git's error."""
    try:
        if tool_name in SHELLS:
            refused = commands.shell(tool_input.get("command") or "", cwd,
                                     SHELLS[tool_name], gate or verdict,
                                     pr or pull_request)
            if refused:
                return Decision("deny", PREFIX + "\n\n".join(refused))
            return None
        if tool_name in EDITS:
            return _edit(tool_name, tool_input, cwd)
    except GateError as e:
        return Decision("deny", PREFIX + (
            f"the hook cannot read this project's repo, so it cannot tell "
            f"whether the call is gated: {e}. Repair the repo, then "
            f"retry."))
    return None


# --- edits -------------------------------------------------------------------
def _edit(tool, args, cwd):
    path = args.get("file_path") or args.get("notebook_path")
    if not path:
        return None
    file = Path(cwd, path)
    root = _project(file)
    if root is None:
        return None
    rel = os.path.relpath(file, root).replace(os.sep, "/")
    if rel.startswith("../"):
        return None
    if rel.startswith(OWN) or rel == OWN.rstrip("/"):
        return Decision("deny", PREFIX + (
            f"{OWN} holds the gate's run_all stamps, which only the gate "
            f"writes, after a green run on a clean tree. Run the gate "
            f"(merge) to stamp a run; never edit {rel}."))
    if tool == "NotebookEdit":
        return None
    before = _read(file)
    after = _after(tool, args, before)
    if after is None or after == before:
        return None
    if rel == FILENAME:
        names = _confirmed(before, after)
        if names:
            return Decision("ask", PREFIX + (
                f"this edit confirms {names} in {FILENAME}, by status = "
                f"\"confirmed\" or by a chosen or standard source kind. "
                f"Only the user confirms an entry: approve only if you "
                f"have checked it yourself."))
    elif rel == waivers.FILENAME:
        added = _waived(before, after)
        if added:
            return Decision("ask", PREFIX + (
                f"this edit adds or confirms a waiver in {waivers.FILENAME}"
                f" ({added}), exempting a gate's item. Only the user "
                f"confirms a waiver: approve only if you agree to waive "
                f"it."))
    elif rel.startswith(reviews.REVIEWS + "/"):
        ids = _accepted(before, after, rel)
        if ids:
            return Decision("ask", PREFIX + (
                f"this edit accepts {ids} in {rel}, closing it without a "
                f"fix. Only the user accepts a finding: approve only if "
                f"you accept it, with the reason written."))
    return None


def _project(file):
    """The root of the project `file` is in: its git repo's top, holding
    `ledger.toml`; else None."""
    folder = file.parent
    while not folder.is_dir():
        if folder.parent == folder:
            return None
        folder = folder.parent
    try:
        root = Repo(folder).root
    except GateError:
        return None
    return root if (root / FILENAME).is_file() else None


def _read(file):
    try:
        return file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _after(tool, args, before):
    """The file's text once the edit is made; None where it cannot be."""
    if tool == "Write":
        return args.get("content")
    edits = args.get("edits") if tool == "MultiEdit" else [args]
    text = before
    for e in edits or []:
        old, new = e.get("old_string"), e.get("new_string")
        if old is None or new is None:
            return None
        text = text.replace(old, new, -1 if e.get("replace_all") else 1) \
            if old else new + text
    return text


def _confirmed(before, after):
    """The entries the edit leaves `confirmed` that were not, named."""
    try:
        a = commands.entries(tomllib.loads(before))
        b = commands.entries(tomllib.loads(after))
    except tomllib.TOMLDecodeError:
        return _more(CONFIRMED, before, after, "an entry")
    names = [n for n, e in b.items()
             if _confirmed_by(e) and not _confirmed_by(a.get(n))]
    return ", ".join(names)


def _waived(before, after):
    """The waivers the edit adds or confirms, named."""
    try:
        a = _waivers(before)
        b = _waivers(after)
    except tomllib.TOMLDecodeError:
        return _more(WAIVER, before, after, "a waiver")
    added = [w for w in b if w not in a]
    return "; ".join(f"{w[0]} {w[1]}, {w[2]}" for w in added)


def _waivers(text):
    tables = tomllib.loads(text).get("waiver", [])
    return [(w.get("gate"), w.get("item"), w.get("scope"),
             w.get("confirmed")) for w in tables if isinstance(w, dict)] \
        if isinstance(tables, list) else []


def _accepted(before, after, rel):
    """The findings the edit leaves `accepted` that were not, named."""
    try:
        a, b = (reviews.parse(t, rel) for t in (before, after))
    except reviews.ReviewError:
        return _more(ACCEPTED, before, after, "a finding")

    def accepted(r):
        return {f.id for f in r.findings if f.status == "accepted"} \
            if isinstance(r, reviews.Review) else set()
    if b is None:
        return _more(ACCEPTED, before, after, "a finding")
    return ", ".join(sorted(accepted(b) - accepted(a)))


def _more(pattern, before, after, what):
    """`what`, where `pattern` occurs more often after the edit."""
    return what if len(pattern.findall(after)) > len(
        pattern.findall(before)) else ""


def _confirmed_by(entry):
    """Whether the raw TOML `entry` is confirmed by what it says itself:
    the ledger's effective status (`status_of`), written or by its source
    kind. An `of` entry's default is left out: it is confirmed only as far
    as the entry it cites, so it confirms no number of its own."""
    if not isinstance(entry, dict):
        return False
    source = entry.get("source")
    kind = source.get("kind") if isinstance(source, dict) else None
    return status_of(entry.get("status"), kind) == "confirmed"


# --- the defaults: the gate, and what a pull request merges ------------------
def verdict(root, branch):
    """The gate `branch` must pass, verifying (`required`): `buy` where the
    branch adds an order record, else `merge`."""
    from . import required     # the package imports this module
    return required(root, branch, verify=True)


def pull_request(root, ref):
    """What `gh pr merge <ref>` merges (the branch checked out's pull
    request, for no `ref`): its head branch, base branch and head SHA."""
    run = subprocess.run(
        ["gh", "pr", "view", *([ref] if ref else []), "--json",
         "headRefName,baseRefName,headRefOid"], cwd=root,
        capture_output=True)
    if run.returncode:
        raise HookError(run.stderr.decode("utf-8", "replace").strip()
                        or "gh pr view failed")
    data = json.loads(run.stdout)
    return {"head": data["headRefName"], "base": data["baseRefName"],
            "oid": data["headRefOid"]}


def main(stdin=None, stdout=None):
    """Read one PreToolUse event as JSON, print the decision's JSON."""
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout
    event = json.loads(stdin.read().decode("utf-8") or "{}")
    decision = decide(event.get("tool_name", ""),
                      event.get("tool_input") or {},
                      event.get("cwd") or os.getcwd())
    if decision is not None:
        stdout.write(json.dumps(decision.as_hook()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
