"""The eval harness's own tests, kept apart from `engine/tests/` so the engine
suite stays fast. Run from the plugin root:

    uv run --project engine pytest evals/tests

They import the harness (`evals/generate.py`, `evals/score.py`) and the golden
answers (`engine/tests/golden/`) by path.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

EVALS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(EVALS), str(EVALS.parent / "engine" / "tests")]


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: assembles a case's project and runs its model")


def find_bash():
    """Git's bash on Windows, where `bash` on PATH may be WSL's; else
    `bash`."""
    if sys.platform == "win32":
        git = shutil.which("git")
        if git:
            for up in Path(git).resolve().parents:
                if (up / "bin" / "bash.exe").is_file():
                    return str(up / "bin" / "bash.exe")
        return None
    return shutil.which("bash")


def run(args, cwd, **env):
    """`args` in `cwd`, outside this suite's venv, its output as UTF-8."""
    outside = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env={**outside, "PYTHONIOENCODING": "utf-8", **env})
