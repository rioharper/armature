"""`py -m armature.check [folder ...]`: the project's whole check, run when
asked (ADR 0013). It runs `ledger check`, then every `run_all.py` in the
project, or only those in the folders named, each in its own environment
with its output streamed as it comes. It prints one `pass` or `fail` line
per item at the end and exits 1 on any failure. Nothing is cached or
recorded, and git is never read.

A folder runs in its own environment where it has a `pyproject.toml` or a
`uv.lock`; otherwise in the model's, `analysis/model/`, as a CAD part
folder does, with build123d added (`part_template/run_all.py`).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .ledger import LedgerError, check as ledger_check
from .ledger.entries import find

RUN_ALL = "run_all.py"
MODEL = "analysis/model"
BUILD123D = "build123d~=0.11"
SKIPPED = ("node_modules", "__pycache__")
# Set by the plugin's launcher for its own engine; a project's run_all
# runs in the project's environment, never the plugin's.
FOREIGN_ENV = ("UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV")


def folders(root):
    """Each folder under `root` holding a `run_all.py`, as a posix path
    from it (`.` for the root), skipping dot-folders."""
    found = []
    for at, names, files in os.walk(root):
        names[:] = [n for n in names
                    if not n.startswith(".") and n not in SKIPPED]
        if RUN_ALL in files:
            found.append(Path(at).relative_to(root).as_posix())
    return sorted(found)


def environment(root, folder):
    """The folder whose environment `folder`'s `run_all.py` runs in."""
    own = any((Path(root) / folder / name).is_file()
              for name in ("pyproject.toml", "uv.lock"))
    return folder if own or folder == MODEL else MODEL


def run_all(root, folder):
    """Run `folder`'s `run_all.py` with uv, streaming its output; whether
    it passed."""
    uv = shutil.which("uv")
    if uv is None:
        print("uv is not on PATH; install uv", file=sys.stderr)
        return False
    args = [uv, "run"]
    project = environment(root, folder)
    if project != folder:
        args += ["--project", str(Path(root) / project), "--with", BUILD123D]
    env = {k: v for k, v in os.environ.items() if k not in FOREIGN_ENV}
    env["PYTHONUTF8"] = env["PYTHONUNBUFFERED"] = "1"
    sys.stdout.flush()
    return subprocess.run([*args, "python", RUN_ALL],
                          cwd=Path(root) / folder, env=env).returncode == 0


def main(argv=None, runner=run_all):
    argv = sys.argv[1:] if argv is None else argv
    for stream in (sys.stdout, sys.stderr):   # a Windows pipe is cp1252
        stream.reconfigure(encoding="utf-8")
    try:
        root = find(None).parent
        findings = ledger_check(root)
    except LedgerError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    found = folders(root)
    wanted = [Path(a).as_posix().rstrip("/") or "." for a in argv] or found
    missing = [w for w in wanted if w not in found]
    if missing:
        print(f"error: no {RUN_ALL} in {', '.join(missing)}; the project "
              f"has {', '.join(found) or 'none'}", file=sys.stderr)
        return 1
    print(*findings, sep="\n")
    results = [("ledger", not any(f.level == "error" for f in findings))]
    for folder in wanted:
        print(f"== {folder}/{RUN_ALL}", flush=True)
        results.append((folder, runner(root, folder)))
    print()
    for item, passed in results:
        print(f"{'pass' if passed else 'fail'} {item}")
    return 0 if all(passed for _, passed in results) else 1


if __name__ == "__main__":
    sys.exit(main())
