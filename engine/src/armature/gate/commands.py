"""The gated shell commands (ADR 0011): a `git merge` with `main` checked
out, `gh pr merge` into `main`, a `git push` to a `main` refspec, and a
`git commit` on `main`. A command line is walked in order, so a `cd`, a
`git -C` or a `git checkout main` before a command is where and on what it
runs. Plumbing such as `update-ref` is not chased."""

import os
import re
import sys
import tomllib
from pathlib import Path

from ..ledger import LedgerError
from ..ledger.entries import FILENAME, SECTIONS
from ..ledger.views import unrendered
from .changes import kind
from .repo import MAIN, GateError, Repo
from .shell import UNKNOWN, commands

CD = {"cd", "pushd", "chdir", "set-location", "sl", "push-location"}
PREFIXES = {"!", "{", "if", "then", "do", "else", "elif", "while", "until",
            "time", "command", "builtin", "exec", "nohup", "sudo", "env",
            "xargs"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
SHELLS = {"bash": "bash", "sh": "bash", "zsh": "bash", "dash": "bash",
          "powershell": "powershell", "pwsh": "powershell"}
# Each option that takes the next word as its value, by subcommand.
VALUES = {
    "merge": {"-m", "-F", "-s", "-X", "--message", "--file", "--strategy",
              "--strategy-option", "--into-name", "--cleanup"},
    "commit": {"-m", "-F", "-C", "-c", "-t", "--message", "--file",
               "--reuse-message", "--reedit-message", "--fixup", "--squash",
               "--author", "--date", "--template", "--trailer", "--cleanup",
               "--pathspec-from-file"},
    "push": {"-o", "--push-option", "--repo", "--receive-pack", "--exec"},
    "checkout": {"-b", "-B", "--orphan", "--conflict"},
    "switch": {"-c", "-C", "--create", "--force-create", "--orphan",
               "--conflict"},
    "pr merge": {"-b", "-F", "-t", "-A", "-R", "--body", "--body-file",
                 "--subject", "--author-email", "--match-head-commit",
                 "--repo"},
}
# A commit on `main` may touch these only inside rendered ledger sections:
# what `merge` reviews, the derivation's notes, and the order records `buy`
# gates.
DERIVATION = "analysis/derivation/"
ORDERS = "docs/orders/"
BRANCH_RULE = ("Commit it on a branch, armature/<kind>-<name>, and merge "
               "that through the gate.")


class HookError(RuntimeError):
    """A command the hook cannot read well enough to let through."""


def shell(command, cwd, dialect, gate, pr):
    """Why `command`, run in `cwd` by `dialect` (bash or powershell), is
    refused: one reason per gated command that fails, or []."""
    walk = Walk(cwd, gate, pr)
    walk.run(command, dialect)
    return list(dict.fromkeys(walk.refused))


class Walk:
    """A command line walked in order: the directory each `cd` leaves, the
    branch each checkout leaves checked out in each repo, and the repos a
    `git add` stages into before a commit."""

    def __init__(self, cwd, gate, pr):
        self.dir = Path(cwd)
        self.gate, self.pr = gate, pr
        self.branches, self.staged, self.repos = {}, set(), {}
        self.refused = []

    def run(self, command, dialect):
        for words in commands(command, dialect):
            words = _bare(words)
            if not words:
                continue
            name = _program(words[0])
            if name in CD:
                self.cd(words[1:])
            elif name in SHELLS:
                inner = _inline(words[1:], SHELLS[name])
                if inner is not None:
                    self.run(inner, SHELLS[name])
            elif name == "git":
                self.git(words[1:])
            elif name == "gh" and words[1:3] == ["pr", "merge"]:
                self.gh_merge(words[3:])

    # --- where a command runs --------------------------------------------
    def cd(self, args):
        named = [args[at + 1] for at, a in enumerate(args[:-1])
                 if a.lower() in ("-path", "-literalpath")]
        pos = named or [a for a in args if not a.startswith("-")]
        target = pos[0] if pos else "~"
        if target != "-" and UNKNOWN not in target:
            self.dir = self.resolve(target, self.dir)

    @staticmethod
    def resolve(target, base):
        """`target`, a path as a shell reads it, from the folder `base`."""
        target = os.path.expanduser(target)
        if sys.platform == "win32":     # Git Bash's /c/... is C:/...
            target = re.sub(r"^/([a-zA-Z])(?=/|$)", r"\1:", target)
        path = Path(target)
        return path if path.is_absolute() else base / path

    def repo(self, where):
        """The project's repo at `where`: a git repo with a root
        `ledger.toml`, or None."""
        key = str(where)
        if key not in self.repos:
            try:
                repo = Repo(where)
            except GateError:
                repo = None
            if repo is not None and not (repo.root / FILENAME).is_file():
                repo = None
            self.repos[key] = repo
        return self.repos[key]

    def branch(self, repo):
        """The branch checked out in `repo` at this point of the line."""
        key = str(repo.root)
        return self.branches[key] if key in self.branches \
            else repo.head_branch

    # --- git -------------------------------------------------------------
    def git(self, args):
        dirs, at = [], 0
        while at < len(args) and args[at].startswith("-"):
            if args[at] in ("-C", "-c", "--git-dir", "--work-tree",
                            "--namespace", "--config-env"):
                if args[at] == "-C" and at + 1 < len(args):
                    dirs.append(args[at + 1])
                at += 2
            else:
                at += 1
        if at >= len(args):
            return
        sub, rest = args[at], args[at + 1:]
        where = self.dir
        for d in dirs:
            if UNKNOWN not in d:
                where = self.resolve(d, where)
        repo = self.repo(where)
        if repo is None:
            return
        if sub in ("checkout", "switch"):
            self.checkout(repo, sub, rest)
        elif sub in ("add", "rm", "mv", "stage"):
            self.staged.add(str(repo.root))
        elif sub == "merge" and self.on_main(repo):
            self.merge(repo, rest)
        elif sub == "commit" and self.on_main(repo):
            self.commit(repo, rest)
        elif sub == "push":
            self.push(repo, rest)

    def on_main(self, repo):
        return self.branch(repo) in (MAIN, UNKNOWN)

    def checkout(self, repo, sub, args):
        key = str(repo.root)
        flags, pos = _parse(args, VALUES[sub])
        for at, a in enumerate(args):
            if a in VALUES[sub] - {"--conflict"} and at + 1 < len(args):
                self.branches[key] = args[at + 1]
                return
        if "--detach" in flags:
            self.branches[key] = None
        elif "--" in args or len(pos) != 1:
            return                            # paths, not a branch
        elif UNKNOWN in pos[0]:
            self.branches[key] = UNKNOWN
        elif pos[0] == "-":
            self.branches[key] = repo.git("rev-parse", "--abbrev-ref",
                                          "@{-1}") or None
        elif (repo.commit(f"refs/heads/{pos[0]}")
              or repo.commit(f"refs/remotes/origin/{pos[0]}")):
            self.branches[key] = pos[0]
        elif sub == "checkout" and repo.commit(pos[0]):
            self.branches[key] = None         # a detached HEAD

    def merge(self, repo, args):
        flags, refs = _parse(args, VALUES["merge"])
        if {"--abort", "--quit"} & set(flags):
            return
        if "--continue" in flags:
            self.refused.append(
                f"git merge --continue concludes a merge into {MAIN} that "
                f"was no fast-forward, which the gate's first item refuses. "
                f"Abort it (git merge --abort), merge {MAIN} into the "
                f"branch, and merge again.")
            return
        for ref in refs:
            branch = self.local(repo, ref)
            if branch is None and not self.remote_main(repo, ref):
                self.refused.append(
                    f"git merge {ref.replace(UNKNOWN, '…')} into {MAIN}: "
                    f"name a local branch plainly, so the gate can compute "
                    f"it.")
            elif branch is not None:
                self.verdict(repo, branch, f"merge {branch} into {MAIN}")

    def push(self, repo, args):
        flags, pos = _parse(args, VALUES["push"])
        current = self.branch(repo)
        delete = {"-d", "--delete"} & set(flags)
        if {"--all", "--branches", "--mirror"} & set(flags):
            self.verdict(repo, MAIN, f"push {MAIN}")
        if len(pos) < 2:                      # the branch checked out
            if current == MAIN:
                self.verdict(repo, MAIN, f"push {MAIN}")
            elif current and current != UNKNOWN and repo.ok(
                    "rev-parse", "--verify", "--quiet", f"{current}@{{u}}") \
                    and repo.git("rev-parse", "--abbrev-ref",
                                 f"{current}@{{u}}").endswith(f"/{MAIN}"):
                self.verdict(repo, current, f"push {current} to {MAIN}")
            return
        for spec in pos[1:]:
            src, colon, dst = spec.lstrip("+").partition(":")
            if not colon:
                dst = src
            dst = dst.removeprefix("refs/heads/")
            if dst == "HEAD":
                dst = current
            if UNKNOWN in (dst or "") and MAIN in dst:
                dst = MAIN
            if dst != MAIN:
                continue
            if delete or (colon and not src):
                self.refused.append(f"git push {spec} deletes {MAIN} on "
                                    f"the remote.")
                continue
            src = src.removeprefix("refs/heads/")
            src = current if src == "HEAD" else src
            branch = self.local(repo, src) if src else None
            if branch is None:
                self.refused.append(
                    f"git push {spec.replace(UNKNOWN, '…')}: push a branch "
                    f"by name to {MAIN}, so the gate can compute it.")
            else:
                self.verdict(repo, branch, f"push {branch} to {MAIN}")

    def gh_merge(self, args):
        flags, pos = _parse(args, VALUES["pr merge"])
        if "--disable-auto" in flags:
            return
        repo = self.repo(self.dir)
        if repo is None:
            return
        ref = pos[0] if pos else None
        try:
            pr = self.pr(repo.root, ref)
        except HookError as e:
            self.refused.append(f"gh pr merge {ref or ''}: cannot tell what "
                                f"it merges: {e}")
            return
        if pr["base"] != MAIN:
            return
        head, oid = pr["head"], pr.get("oid")
        local = repo.commit(f"refs/heads/{head}")
        if local is None:
            self.refused.append(
                f"gh pr merge merges {head}, which is no local branch; "
                f"fetch it (git fetch origin {head}:{head}) so the gate can "
                f"compute it.")
        elif oid and local != oid:
            self.refused.append(
                f"gh pr merge merges {head} at {oid[:7]}, but the local "
                f"{head} is at {local[:7]}; push or pull until they agree, "
                f"so the gate computes what merges.")
        else:
            self.verdict(repo, head, f"merge {head} into {MAIN}")

    def local(self, repo, ref):
        """`ref`'s local branch name, or None where it names none."""
        ref = ref.removeprefix("refs/heads/")
        if UNKNOWN in ref or repo.commit(f"refs/heads/{ref}") is None:
            return None
        return ref

    def remote_main(self, repo, ref):
        """Whether `ref` is a remote's `main`: bringing it in is no
        merge of work."""
        ref = ref.removeprefix("refs/remotes/")
        return ("/" in ref and ref.split("/", 1)[1] == MAIN
                and repo.commit(f"refs/remotes/{ref}") is not None)

    def verdict(self, repo, branch, action):
        try:
            verdict = self.gate(repo.root, branch)
        except GateError as e:
            self.refused.append(f"{action}: the gate cannot be computed: "
                                f"{e}")
            return
        if not verdict.passed:
            self.refused.append(
                f"{action}: {verdict.gate} fails for {branch} at "
                f"{verdict.tip[:7]}.\n" + "\n".join(verdict.lines()))

    # --- a commit on main -------------------------------------------------
    def commit(self, repo, args):
        flags, paths = _parse(args, VALUES["commit"])
        pending = bool(paths) or str(repo.root) in self.staged or any(
            f in ("--all", "--include", "--only", "--pathspec-from-file")
            or (re.fullmatch(r"-[a-zA-Z]+", f) and set(f[1:]) & set("aio"))
            for f in flags)
        problems = main_commit(repo, pending)
        if problems:
            self.refused.append(
                f"git commit on {MAIN}: a commit on {MAIN} may touch gated "
                f"paths only inside rendered ledger sections, and change "
                f"the ledger only by adding or editing candidate entries. "
                f"This one: " + "; ".join(problems) + f". {BRANCH_RULE}")


def main_commit(repo, pending):
    """What a commit on `main` would do beyond the rendered sections and
    candidate ledger entries: the staged changes, or with `pending` (a
    `git add` before it, `-a`, or paths named) every change in the working
    tree, untracked files included."""
    head = repo.commit("HEAD")
    against = [head] if head else []
    paths = set(_lines(repo.git("diff", "--cached", "--name-only",
                                "--no-renames", "-z", *against)))
    if pending:
        paths |= set(_lines(repo.git("diff", "--name-only", "--no-renames",
                                     "-z", *against)))
        paths |= set(_lines(repo.git("ls-files", "--others",
                                     "--exclude-standard", "-z")))
    old = repo.read(head, sorted(paths)) if head else {}
    if pending:
        new = {p: _file(repo.root / p) for p in paths}
    else:
        new = repo.read("", sorted(paths))    # the index
    problems = []
    for path in sorted(paths):
        before, after = old.get(path), new.get(path)
        if path == FILENAME:
            problems += ledger_moves(before, after)
        elif not (before or b"") and not (after or b""):
            continue                          # an empty file, a .gitkeep
        else:
            what = _gated(path)
            if what == "text" and not _outside(path, before, after):
                continue
            if what is not None:
                problems.append(f"{what} {path}" + (
                    " outside its rendered sections" if what == "text"
                    else ""))
    return problems


def ledger_moves(before, after):
    """What a ledger change does beyond adding or editing `candidate`
    entries, one phrase each; [] where it does nothing more."""
    if after is None:
        return [f"it removes {FILENAME}"]
    try:
        a = tomllib.loads((before or b"").decode("utf-8"))
        b = tomllib.loads(after.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        return [f"{FILENAME} does not parse: {e}"]
    if _rest(a) != _rest(b):
        return [f"it changes {FILENAME} outside its entries"]
    ea, eb = entries(a), entries(b)
    problems = []
    for name in sorted(ea.keys() | eb.keys()):
        if ea.get(name) == eb.get(name):
            continue
        if name not in eb:
            problems.append(f"it removes the entry {name}")
        elif _status(eb[name]) != "candidate":
            problems.append(f"it {'edits' if name in ea else 'adds'} {name}"
                            f", which it leaves {_status(eb[name])}")
        elif name in ea and _status(ea[name]) != "candidate":
            problems.append(f"it edits {name}, which was "
                            f"{_status(ea[name])}")
    return problems


def entries(data):
    """A ledger's raw TOML tables, by entry name (`part.<pn>.<key>`)."""
    found = {}
    for top, depth in SECTIONS.items():
        tables = data.get(top)
        if not isinstance(tables, dict):
            if tables is not None:
                found[top] = tables
            continue
        for key, table in tables.items():
            if depth == 2 and isinstance(table, dict):
                for sub, entry in table.items():
                    found[f"{top}.{key}.{sub}"] = entry
            else:
                found[f"{top}.{key}"] = table
    return found


def _status(entry):
    status = entry.get("status") if isinstance(entry, dict) else None
    return status or "with no status"


def _rest(data):
    return {k: v for k, v in data.items() if k not in SECTIONS}


def _gated(path):
    """What `path` is that a commit on `main` may touch only inside the
    rendered sections, or None."""
    what = kind(path)
    if what is not None:
        return what
    if path.startswith(DERIVATION):
        return "text"
    if path.startswith(ORDERS):
        return "the order record"
    return None


def _outside(path, before, after):
    """Whether markdown `path` differs outside its rendered sections."""
    if not path.lower().endswith(".md") or before is None or after is None:
        return True
    try:
        return unrendered(path, before.decode("utf-8")) != unrendered(
            path, after.decode("utf-8"))
    except (LedgerError, UnicodeDecodeError):
        return True


# --- reading words ----------------------------------------------------------
def _bare(words):
    """`words` without the assignments and keywords ahead of the
    program."""
    at = 0
    while at < len(words) and (words[at] in PREFIXES
                               or ASSIGNMENT.match(words[at])
                               or (at and words[at - 1] == "env"
                                   and words[at].startswith("-"))):
        at += 1
    return words[at:]


def _program(word):
    name = re.split(r"[/\\]", word)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _inline(args, dialect):
    """The command a shell runs from `-c` (bash) or `-Command`
    (PowerShell), or None."""
    for at, a in enumerate(args[:-1]):
        if dialect == "bash" and re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", a):
            return args[at + 1]
        if dialect == "powershell" and a.lower() in ("-c", "-command"):
            return " ".join(args[at + 1:])
    return None


def _parse(args, values):
    """`args` split into options and positionals; an option in `values`
    takes the next word, and `--` ends the options."""
    flags, pos, at = [], [], 0
    while at < len(args):
        a = args[at]
        if a == "--":
            flags.append(a)
            pos += args[at + 1:]
            break
        if a.startswith("-") and len(a) > 1:
            flags.append(a)
            short = re.fullmatch(r"-[a-zA-Z]+", a) and f"-{a[-1]}" in values
            if a in values or short:
                at += 1
        else:
            pos.append(a)
        at += 1
    return flags, pos


def _lines(out):
    return [p for p in out.split("\0") if p]


def _file(path):
    try:
        return path.read_bytes()
    except OSError:
        return None
