"""Stamps: each a record that a `run_all.py` passed on one content, a
cache keyed by that content.

A stamp is `.armature/runs/<key>.json`, written when a `run_all.py` passes
on a clean tree. Its key hashes the folder's git tree, the `ledger.toml`
blob and the `uv.lock` of the environment the folder runs in, so any change
to what the run read misses it. It is a cache, not authority: nothing is
stored that a content change would not invalidate.

A folder runs in its own environment where it has a `pyproject.toml` or a
`uv.lock`; otherwise in the model's, `analysis/model/`, as a CAD part
folder does, with build123d added (`part_template/run_all.py`).
"""

import datetime
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath

from ..ledger.entries import FILENAME
from .repo import OWN

RUN_ALL = "run_all.py"
LOCK = "uv.lock"
PYPROJECT = "pyproject.toml"
MODEL = "analysis/model"
BUILD123D = "build123d~=0.11"
RUNS = OWN + "runs"     # the hook denies an edit under OWN
TAIL = 3                # lines of a failing run's output shown
# Set by the plugin's launcher for its own engine; a project's run_all
# runs in the project's environment, never the plugin's.
FOREIGN_ENV = ("UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV")


def within(folder, name=""):
    """`name` in `folder`, both posix paths from the repo root, where the
    root is `.`: the one place a folder and a name are joined, so the root's
    `run_all.py` is `run_all.py`, never `./run_all.py`. With no `name`, the
    folder itself (`""` for the root, as git names the root tree)."""
    if folder == ".":
        return name
    return f"{folder}/{name}" if name else folder


def folders(files):
    """Each folder holding a `run_all.py`, as a posix path from the repo
    root (`.` for the root), skipping dot-folders."""
    found = []
    for path in files:
        p = PurePosixPath(path)
        if p.name == RUN_ALL and not any(part.startswith(".")
                                         for part in p.parts[:-1]):
            found.append(str(p.parent))
    return sorted(found)


def environment(files, folder):
    """The folder whose environment `folder`'s `run_all.py` runs in."""
    own = {within(folder, LOCK), within(folder, PYPROJECT)}
    return folder if own & set(files) or folder == MODEL else MODEL


def key(repo, tip, files, folder):
    """The stamp key of `folder` at commit `tip`: its tree, the ledger's
    blob and its environment's lock blob, hashed."""
    lock = within(environment(files, folder), LOCK)
    parts = [folder,
             repo.object(tip, within(folder)),
             repo.object(tip, FILENAME) or "-",
             repo.object(tip, lock) if lock in files else "-"]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def stamped(root, k):
    """Whether a green stamp is cached under key `k`."""
    try:
        data = json.loads((Path(root) / RUNS / f"{k}.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("passed") is True


def write(root, k, folder, tip):
    path = Path(root) / RUNS / f"{k}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "folder": folder, "commit": tip, "passed": True,
        "at": datetime.datetime.now(datetime.UTC).isoformat(
            timespec="seconds")}, indent=2) + "\n", encoding="utf-8")


def run_all(folder, project, *command):
    """Run `folder`'s `run_all.py` with uv in `project`'s environment, or
    `python <command>` where one is given; (passed, output)."""
    uv = shutil.which("uv")
    if uv is None:
        return False, "uv is not on PATH; install uv"
    args = [uv, "run"]
    if Path(project) != Path(folder):
        args += ["--project", str(project), "--with", BUILD123D]
    env = {k: v for k, v in os.environ.items() if k not in FOREIGN_ENV}
    env["PYTHONUTF8"] = "1"
    run = subprocess.run([*args, "python", *(command or (RUN_ALL,))],
                         cwd=folder, env=env,
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace")
    return run.returncode == 0, run.stdout + run.stderr


def tail(output):
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return " | ".join(lines[-TAIL:]) or "no output"


def stamp_or_run(ctx, k, folder, attempt, missing, gate):
    """Whether a check of `folder`'s content at the tip holds, by its stamp
    under key `k`, or else by running `attempt()`, which returns why the
    check fails or None, and stamping it. It runs only unless verifying,
    with the branch checked out on a clean tree, and a run that changes
    the tree is no pass. `missing` names what has no stamp, `gate` the
    verb that runs it. (None, "stamped" | "ran") where it holds, else (why,
    None)."""
    if stamped(ctx.repo.root, k) and not (ctx.fresh and not ctx.verify):
        return None, "stamped"
    if ctx.verify:
        return (f"{missing} for its content; run py -m armature.gate "
                f"{gate}"), None
    if not (ctx.repo.head == ctx.tip and ctx.repo.head_branch == ctx.branch):
        return (f"{missing}, and {ctx.branch} is not checked out to run "
                f"it"), None
    dirty = ctx.repo.dirty()
    if dirty:
        return (f"{missing}, and the tree has uncommitted changes "
                f"({', '.join(dirty[:3])}); commit them, then run the "
                f"gate"), None
    why = attempt()
    if why:
        return why, None
    changed = ctx.repo.dirty()
    if changed:
        return (f"it passed and changed {', '.join(changed[:3])}; commit "
                f"that, then run the gate"), None
    write(ctx.repo.root, k, folder, ctx.tip)
    return None, "ran"


def check(ctx):
    """3. Every `run_all.py` has a green stamp for its content at the tip,
    or runs green and is stamped (`stamp_or_run`)."""
    found = folders(ctx.files)
    if not found:
        return True, f"no {RUN_ALL} in the project"
    root, failed, notes = ctx.repo.root, [], []
    runner = ctx.runner or run_all
    for folder in found:
        def attempt(folder=folder):
            passed, output = runner(root / folder,
                                    root / environment(ctx.files, folder))
            return None if passed else f"{RUN_ALL} fails: {tail(output)}"
        why, how = stamp_or_run(ctx, key(ctx.repo, ctx.tip, ctx.files,
                                         folder), folder, attempt,
                                "no green stamp", "merge")
        if why:
            failed.append(f"{folder}: {why}")
        else:
            notes.append(f"{folder} ran green, stamped" if how == "ran"
                         else f"{folder} stamped")
    if failed:
        return False, "; ".join(failed)
    return True, "; ".join(notes)
