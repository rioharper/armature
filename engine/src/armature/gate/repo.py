"""The project's git repo, read at a commit: what the gate's evidence is
computed from. Every read is of a committed object, never the working tree,
so the gate judges the tree `main` becomes, whichever branch is checked
out."""

import subprocess
from functools import cached_property
from pathlib import Path, PurePosixPath

MAIN = "main"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
# What the gate writes into the project, never part of its evidence.
OWN = ".armature/"


class GateError(RuntimeError):
    """A gate that cannot be computed: no git repo, no such branch, or a
    detached HEAD with no branch named."""


class Repo:
    """The git repo at or above `path`."""

    def __init__(self, path=None):
        start = Path.cwd() if path is None else Path(path)
        try:
            top = self._git(start, "rev-parse", "--show-toplevel")
        except GateError:
            raise GateError(f"{start} is not in a git repo") from None
        self.root = Path(top)

    @staticmethod
    def _git(cwd, *args, input=None, check=True):
        run = subprocess.run(["git", "-C", str(cwd), *args], input=input,
                             capture_output=True)
        if check and run.returncode:
            raise GateError(f"git {' '.join(args)}: "
                            f"{run.stderr.decode('utf-8', 'replace').strip()}")
        return run.stdout.decode("utf-8", "replace").strip()

    def git(self, *args, input=None):
        """`git <args>` in the repo, its stdout stripped; raises on a
        nonzero exit."""
        return self._git(self.root, *args, input=input)

    def ok(self, *args):
        """Whether `git <args>` exits 0."""
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True).returncode == 0

    def commit(self, rev):
        """`rev`'s full commit SHA, or None if it names no commit."""
        if not self.ok("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"):
            return None
        return self.git("rev-parse", "--verify", f"{rev}^{{commit}}")

    @cached_property
    def head_branch(self):
        """The branch checked out, or None on a detached HEAD."""
        if not self.ok("symbolic-ref", "-q", "HEAD"):
            return None
        return self.git("symbolic-ref", "--short", "HEAD")

    @cached_property
    def head(self):
        return self.commit("HEAD")

    def is_ancestor(self, a, b):
        """Whether commit `a` is `b` or one of its ancestors."""
        return self.ok("merge-base", "--is-ancestor", a, b)

    def merge_base(self, a, b):
        return self.git("merge-base", a, b) if self.ok("merge-base", a, b) \
            else None

    def changed(self, a, b):
        """The paths that differ between commits `a` (None: the empty tree)
        and `b`."""
        out = self.git("diff", "--name-only", "--no-renames", "-z",
                       a or EMPTY_TREE, b)
        return [p for p in out.split("\0") if p]

    def files(self, rev):
        """Every file path in `rev`'s tree."""
        out = self.git("ls-tree", "-r", "-z", "--name-only", rev)
        return [p for p in out.split("\0") if p]

    def object(self, rev, path=""):
        """The SHA of `rev`'s blob or tree at `path` (the root tree for
        ""), or None where there is none."""
        spec = f"{rev}^{{tree}}" if not path else f"{rev}:{path}"
        if not self.ok("rev-parse", "--verify", "--quiet", spec):
            return None
        return self.git("rev-parse", "--verify", spec)

    def read(self, rev, paths):
        """Each of `paths` at `rev`, as bytes, or None where it is not a
        file there, in one `git cat-file --batch`."""
        if not paths:
            return {}
        query = "".join(f"{rev}:{p}\n" for p in paths).encode("utf-8")
        run = subprocess.run(["git", "-C", str(self.root), "cat-file",
                              "--batch"], input=query, capture_output=True,
                             check=True)
        out, at, found = run.stdout, 0, {}
        for path in paths:
            end = out.index(b"\n", at)
            header = out[at:end].split()
            at = end + 1
            if len(header) != 3 or header[1] != b"blob":
                found[path] = None
                if len(header) == 3:      # a tree: skip its listing
                    at += int(header[2]) + 1
                continue
            size = int(header[2])
            found[path] = out[at:at + size]
            at += size + 1
        return found

    def text(self, rev, path):
        """The file `path` at `rev` as text, or None."""
        raw = self.read(rev, [path])[path]
        return None if raw is None else raw.decode("utf-8")

    def export(self, rev, paths, dest):
        """Write each of `paths` at `rev` below the folder `dest`."""
        for path, raw in self.read(rev, paths).items():
            if raw is None:
                continue
            file = Path(dest, *PurePosixPath(path).parts)
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)

    def dirty(self):
        """The paths with uncommitted changes, untracked files included,
        leaving out the gate's own `.armature/`."""
        run = subprocess.run(["git", "-C", str(self.root), "status",
                              "--porcelain", "-z", "--untracked-files=all"],
                             capture_output=True, check=True)
        entries = iter(run.stdout.decode("utf-8", "replace").split("\0"))
        paths = []
        for entry in entries:
            if len(entry) > 3:
                paths.append(entry[3:])
                if "R" in entry[:2] or "C" in entry[:2]:
                    next(entries, None)     # a rename's source path
        return [p for p in paths if not p.startswith(OWN)]
