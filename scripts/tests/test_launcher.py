"""The launcher: `scripts/armature.sh`, and `scripts/armature.ps1` for
PowerShell, run the plugin's own engine through uv with its venv under
`CLAUDE_PLUGIN_DATA`.

A fake `uv` first on PATH records its arguments and the venv it was given,
so the tests see what the launcher hands the engine without building one.
Run from the plugin root:

    uv run --project engine pytest scripts/tests
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]

FAKE_UV = """#!/usr/bin/env bash
{ printf 'uv %s\\n' "$*"; printf 'venv %s\\n' "$UV_PROJECT_ENVIRONMENT"; } \\
    >> "$FAKE_LOG"
"""
FAKE_UV_CMD = """@echo off
echo uv %* >> "%FAKE_LOG%"
echo venv %UV_PROJECT_ENVIRONMENT% >> "%FAKE_LOG%"
"""


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


def powershell():
    return shutil.which("powershell") or shutil.which("pwsh")


class Setup:
    """A plugin copy holding the launchers, a project folder, and a PATH
    with maybe a fake uv."""

    def __init__(self, tmp_path):
        self.plugin = tmp_path / "plugin"
        (self.plugin / "scripts").mkdir(parents=True)
        for name in ("armature.sh", "armature.ps1"):
            shutil.copy(SCRIPTS / name, self.plugin / "scripts")
        self.project = tmp_path / "arm"
        self.project.mkdir()
        self.data = tmp_path / "data"
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.fakes = tmp_path / "fakes"
        self.fakes.mkdir()
        self.log = tmp_path / "uv.log"
        tools = ["/usr/bin", "/bin"]
        if sys.platform == "win32":     # Git's coreutils, and powershell
            git = Path(shutil.which("git")).resolve()
            tools = [str(p / "usr" / "bin") for p in git.parents
                     if (p / "usr" / "bin").is_dir()][:1]
            tools += [os.path.expandvars(r"%SystemRoot%\System32"),
                      os.path.expandvars(
                          r"%SystemRoot%\System32\WindowsPowerShell\v1.0")]
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("CLAUDE_", "UV_", "VIRTUAL_ENV"))}
        self.env.update(PATH=os.pathsep.join([str(self.fakes), *tools]),
                        HOME=str(self.home), USERPROFILE=str(self.home),
                        CLAUDE_PLUGIN_DATA=str(self.data),
                        FAKE_LOG=str(self.log))

    def with_uv(self):
        (self.fakes / "uv").write_text(FAKE_UV, newline="\n")
        (self.fakes / "uv").chmod(0o755)
        (self.fakes / "uv.cmd").write_text(FAKE_UV_CMD)
        return self

    def calls(self):
        return (self.log.read_text(encoding="utf-8", errors="replace")
                .splitlines() if self.log.exists() else [])

    def bash(self, *args):
        bash = find_bash()
        if bash is None:
            pytest.skip("no bash to run the launcher with")
        return subprocess.run(
            [bash, (self.plugin / "scripts" / "armature.sh").as_posix(),
             *args], capture_output=True, env=self.env, cwd=self.project)


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def test_a_verb_runs_the_plugins_engine_through_uv(setup):
    setup.with_uv()
    assert setup.bash("check", "analysis/model").returncode == 0
    uv, venv = setup.calls()
    assert uv.split()[1:6] == ["run", "--quiet", "--frozen", "--no-dev",
                               "--project"]
    assert Path(uv.split()[6]) == setup.plugin / "engine"
    assert uv.endswith("python -m armature.check analysis/model")
    assert Path(venv.split(" ", 1)[1]) == setup.data / "venv"


def test_with_no_uv_it_says_to_install_uv(setup):
    run = setup.bash("ledger", "check")
    assert run.returncode == 2
    assert "install uv" in run.stderr.decode()


def test_help_prints_the_header_comment_and_nothing_else(setup):
    run = setup.bash("--help")
    assert run.returncode == 2
    lines = run.stdout.decode().splitlines()
    assert lines[0].startswith("The plugin's own engine, run through uv")
    assert lines[-1].endswith("the same launcher for PowerShell.")
    assert not any(line.startswith(("set ", "#")) for line in lines)


@pytest.mark.skipif(powershell() is None, reason="no PowerShell")
def test_powershell_runs_the_same_engine(setup):
    setup.with_uv()
    run = subprocess.run(
        [powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(setup.plugin / "scripts" / "armature.ps1"),
         "ledger", "check"],
        capture_output=True, env=setup.env, cwd=setup.project)
    assert run.returncode == 0, run.stderr
    uv, venv = setup.calls()[:2]
    assert "python -m armature.ledger check" in uv
    assert Path(venv.split(" ", 1)[1].strip()) == setup.data / "venv"
