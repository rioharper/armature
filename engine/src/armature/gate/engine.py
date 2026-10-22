"""Item 4: each model directory's engine source is in step with the plugin
(ADR 0009), as `scripts/engine-source.sh check` reports it.

A model directory is a folder holding a `run_all.py` and its own
`pyproject.toml`. Its `pyproject.toml` at the tip is checked, by the script
of the plugin this engine ships in. A path pin, as the plugin's own
templates and the evals use, passes as one; behind, ahead and a rev fail.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .stamps import PYPROJECT, folders, within

SCRIPT = Path("scripts") / "engine-source.sh"
# engine/src/armature/gate/engine.py: the plugin root is four folders up.
PLUGIN = Path(__file__).resolve().parents[4]


def script():
    """The plugin's `engine-source.sh`, or None: this engine's own plugin,
    else `$CLAUDE_PLUGIN_ROOT`'s."""
    roots = [PLUGIN, *([Path(os.environ["CLAUDE_PLUGIN_ROOT"])]
                       if os.environ.get("CLAUDE_PLUGIN_ROOT") else [])]
    return next((r / SCRIPT for r in roots if (r / SCRIPT).is_file()), None)


def bash():
    """Git's bash on Windows, where `bash` on PATH may be WSL's; else
    `bash`."""
    if sys.platform == "win32":
        git = shutil.which("git")
        for up in Path(git).resolve().parents if git else []:
            if (up / "bin" / "bash.exe").is_file():
                return str(up / "bin" / "bash.exe")
        return None
    return shutil.which("bash")


def check(ctx):
    """4. `engine-source.sh check` is in-step, or a path pin, for each
    model directory."""
    models = [f for f in folders(ctx.files)
              if within(f, PYPROJECT) in ctx.files]
    if not models:
        return True, "no model directory pins an engine"
    found, shell = script(), bash()
    if found is None or shell is None:
        return False, ("cannot run engine-source.sh check: "
                       + ("no bash" if found else "no scripts/engine-source.sh"
                          " in this engine's plugin"))
    failed, notes = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for model in models:
            ctx.repo.export(ctx.tip, [within(model, PYPROJECT)], tmp)
            run = subprocess.run(
                [shell, found.as_posix(), "check",
                 (Path(tmp) / model).as_posix()],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace")
            line = (run.stdout.strip().splitlines() or [""])[0]
            if run.returncode == 0:
                notes.append(f"{model} {line}")
            elif line.startswith("path "):
                notes.append(f"{model} path pin")
            else:
                failed.append(f"{model}: {line or run.stderr.strip()}")
    if failed:
        return False, "; ".join(failed)
    return True, "; ".join(notes)
