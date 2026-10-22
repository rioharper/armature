"""What one gate computation reads: the repo, the branch and its tip, the
branch point, and the files, ledgers and reviews at the commits that
matter, each read once."""

import datetime
from dataclasses import dataclass, field
from functools import cached_property

from ..ledger import LedgerError
from ..ledger.entries import FILENAME, loads
from . import reviews
from .repo import MAIN, GateError, Repo


@dataclass
class Context:
    """A gate computed for `branch` at its tip. `verify` reads the stamps
    and never runs a `run_all.py`; `fresh` runs every one, ignoring the
    stamps; `runner(folder, project)` runs one, returning (passed, output),
    where `project` is the folder whose environment it runs in, and
    `runner(folder, project, *command)` runs `python <command>` there, as
    a release's stub check does."""
    repo: Repo
    branch: str
    verify: bool = False
    fresh: bool = False
    today: datetime.date = None
    runner: object = None
    warnings: list = field(default_factory=list)

    @classmethod
    def at(cls, path=None, branch=None, **kw):
        repo = Repo(path)
        branch = branch or repo.head_branch
        if branch is None:
            raise GateError("HEAD is detached; name the branch with "
                            "--branch")
        if repo.commit(f"refs/heads/{branch}") is None:
            raise GateError(f"no branch named {branch!r}")
        return cls(repo, branch, **kw)

    @cached_property
    def tip(self):
        return self.repo.commit(f"refs/heads/{self.branch}")

    @cached_property
    def main(self):
        """`main`'s commit, or None where there is no `main`."""
        return self.repo.commit(f"refs/heads/{MAIN}")

    @cached_property
    def base(self):
        """The branch point: where the branch left `main`, or None."""
        return None if self.main is None \
            else self.repo.merge_base(self.main, self.tip)

    @cached_property
    def files(self):
        return self.repo.files(self.tip)

    @cached_property
    def changed(self):
        """The paths the branch changes, from its branch point to its
        tip."""
        return self.repo.changed(self.base, self.tip)

    @cached_property
    def blocks(self):
        """Every review and recheck at the tip, parsed, and each file whose
        block cannot be read, as (path, error)."""
        found, broken = [], []
        for path, raw in self.repo.read(self.tip,
                                        reviews.paths(self.files)).items():
            try:
                parsed = reviews.parse(raw.decode("utf-8"), path)
            except (reviews.ReviewError, UnicodeDecodeError) as e:
                broken.append((path, str(e)))
                continue
            if parsed is not None:
                found.append(parsed)
        return found, broken

    def on_branch(self, sha):
        """`sha`'s full commit SHA where it is on the branch, at or after
        its branch point; else None."""
        commit = self.repo.commit(sha)
        if commit is None or not self.repo.is_ancestor(commit, self.tip):
            return None
        if self.base is not None and not self.repo.is_ancestor(self.base,
                                                               commit):
            return None
        return commit

    @cached_property
    def counted(self):
        """The reviews that count: each pinned to a commit on the branch,
        at or after its branch point, with that commit's full SHA."""
        return [(r, sha) for r in self.blocks[0]
                if isinstance(r, reviews.Review)
                and (sha := self.on_branch(r.reviewed)) is not None]

    @cached_property
    def rechecks(self):
        """Every recheck pinned on the branch, oldest first, as (recheck,
        full SHA): ordered by its commit's depth, then by path."""
        found = [(r, sha) for r in self.blocks[0]
                 if isinstance(r, reviews.Recheck)
                 and (sha := self.on_branch(r.reviewed)) is not None]
        depth = {sha: int(self.repo.git("rev-list", "--count", sha))
                 for _, sha in found}
        return sorted(found, key=lambda rs: (depth[rs[1]], rs[0].path))

    def ledger(self, rev):
        """The ledger at `rev`, parsed; None where there is none. A ledger
        that will not parse raises `LedgerError`."""
        cache = self.__dict__.setdefault("_ledgers", {})
        if rev not in cache:
            text = self.repo.text(rev, FILENAME)
            try:
                cache[rev] = None if text is None else loads(text, FILENAME)
            except LedgerError as e:
                cache[rev] = e
        if isinstance(cache[rev], LedgerError):
            raise cache[rev]
        return cache[rev]
