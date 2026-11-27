"""`engine-source.sh` (#134, ADR 0009): `pin` writes a model directory's
engine source as the git tag of the plugin it runs from, whatever it held.

Each test copies the script and a `plugin.json` at a chosen version into a
temporary plugin root, so the plugin's version is a test input. A fake `uv`
goes first on PATH and records that it ran. Run from the plugin root:

    uv run --project engine pytest scripts/tests
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
TEMPLATE = ROOT / "skills" / "armature-derive" / "scripts" / "model_template"
REPO = "https://github.com/rioharper/armature"
SHA = "0123456789abcdef0123456789abcdef01234567"

FAKE_UV = """#!/usr/bin/env bash
printf 'uv %s in %s\\n' "$*" "$(pwd)" >> "$FAKE_LOG"
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


def run(args, cwd, env):
    """`args` in `cwd` under exactly `env`, its output as UTF-8."""
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)


def git_source(tag=None, rev=None):
    """The `{ … }` of a git source at `tag` or `rev`."""
    pin = f'tag = "{tag}"' if tag else f'rev = "{rev}"'
    return f'{{ git = "{REPO}", {pin}, subdirectory = "engine" }}'


PATH_SOURCE = '{ path = "../../../../engine", editable = true }'


class Plugin:
    """A plugin root holding the script at `version`, and a model directory
    copied from the template."""

    def __init__(self, tmp_path, version):
        self.root = tmp_path / "plugin"
        (self.root / "scripts").mkdir(parents=True)
        (self.root / ".claude-plugin").mkdir()
        shutil.copy(SCRIPTS / "engine-source.sh", self.root / "scripts")
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json")
                              .read_text(encoding="utf-8"))
        manifest["version"] = version
        (self.root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.model = tmp_path / "project" / "analysis" / "model"
        self.model.mkdir(parents=True)
        shutil.copy(TEMPLATE / "pyproject.toml", self.model)
        fakes = tmp_path / "fakes"
        fakes.mkdir()
        (fakes / "uv").write_bytes(FAKE_UV.encode())
        (fakes / "uv").chmod(0o755)
        self.log = tmp_path / "fakes.log"
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PLUGIN_ROOT", "VIRTUAL_ENV")}
        self.env.update(PATH=str(fakes) + os.pathsep + os.environ["PATH"],
                        FAKE_LOG=self.log.as_posix())

    @property
    def pyproject(self):
        return self.model / "pyproject.toml"

    def source(self, source):
        """The model with its engine source set to `source`, a `{ … }`
        table."""
        text = self.pyproject.read_bytes().decode()
        old = f"armature-engine = {PATH_SOURCE}"
        assert old in text
        self.pyproject.write_bytes(
            text.replace(old, f"armature-engine = {source}").encode())

    def engine_lines(self):
        return [line for line in self.pyproject.read_text(
            encoding="utf-8").splitlines() if "armature-engine =" in line]

    def calls(self):
        return (self.log.read_text(encoding="utf-8").splitlines()
                if self.log.exists() else [])

    def __call__(self, *args, cwd=None, script=None):
        """The script run with `args`, by default by its absolute path
        from the model directory."""
        bash = find_bash()
        if bash is None:
            pytest.skip("no bash to run engine-source.sh with")
        script = script or (self.root / "scripts" / "engine-source.sh")
        return run([bash, Path(script).as_posix(), *args], cwd or self.model,
                   self.env)


@pytest.fixture
def plugin(tmp_path):
    return lambda version: Plugin(tmp_path, version)


def test_pin_writes_the_git_source_at_the_plugins_tag(plugin):
    p = plugin("2.4.1")
    done = p("pin", "--no-lock", p.model.as_posix())
    assert done.returncode == 0, done.stdout + done.stderr
    assert p.engine_lines() == [
        'armature-engine = { git = "https://github.com/rioharper/armature", '
        'tag = "v2.4.1", subdirectory = "engine" }']


def test_pin_locks_the_upgraded_engine_in_the_model_directory(plugin):
    p = plugin("2.4.1")
    done = p("pin", p.model.as_posix(), cwd=p.root)
    assert done.returncode == 0, done.stdout + done.stderr
    [call] = p.calls()
    assert call.startswith("uv lock --upgrade-package armature-engine in ")
    assert call.endswith("/project/analysis/model"), call


def test_pin_with_no_lock_runs_no_uv(plugin):
    p = plugin("2.4.1")
    done = p("pin", "--no-lock", p.model.as_posix())
    assert done.returncode == 0, done.stdout + done.stderr
    assert p.calls() == []


def test_pin_prints_the_old_source_and_the_new(plugin):
    p = plugin("2.4.1")
    done = p("pin", "--no-lock", p.model.as_posix())
    assert done.stdout.splitlines() == [
        f"old: {PATH_SOURCE}", f"new: {git_source(tag='v2.4.1')}"]


@pytest.mark.parametrize("source", [
    git_source(tag="v2.4.1"), git_source(tag="v2.0.0"),
    git_source(tag="v1.9.9"), git_source(tag="v3.0.0"), git_source(rev=SHA)])
def test_pin_moves_any_tag_or_rev_to_the_plugins_tag(plugin, source):
    p = plugin("2.4.1")
    p.source(source)
    done = p("pin", "--no-lock", p.model.as_posix())
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.splitlines() == [
        f"old: {source}", f"new: {git_source(tag='v2.4.1')}"]
    assert p.engine_lines() == [f"armature-engine = {git_source(tag='v2.4.1')}"]


def test_a_pyproject_with_no_engine_line_fails_loudly(plugin):
    command = ["pin", "--no-lock"]
    p = plugin("2.4.1")
    text = p.pyproject.read_text(encoding="utf-8")
    p.pyproject.write_text(text.replace(f"armature-engine = {PATH_SOURCE}",
                                        ""), encoding="utf-8")
    before = p.pyproject.read_bytes()
    done = p(*command, p.model.as_posix())
    assert done.returncode == 2
    assert "no armature-engine = { … } line" in done.stderr
    assert p.pyproject.read_bytes() == before


def test_the_script_finds_its_plugin_json_with_no_plugin_root_set(plugin):
    """Called by a relative path from the plugin root, the way nothing
    in the Bash tool can rely on `CLAUDE_PLUGIN_ROOT`."""
    p = plugin("7.0.3")
    assert "CLAUDE_PLUGIN_ROOT" not in p.env
    done = p("pin", "--no-lock", p.model.as_posix(), cwd=p.root,
             script="scripts/engine-source.sh")
    assert done.stdout.splitlines()[-1] == \
        f"new: {git_source(tag='v7.0.3')}", done.stderr


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_pin_changes_nothing_but_the_engine_line(plugin, newline):
    """Byte for byte, so a Windows checkout's CRLF line endings survive."""
    p = plugin("2.4.1")
    lf = p.pyproject.read_bytes().replace(b"\r\n", b"\n")
    p.pyproject.write_bytes(lf.replace(b"\n", newline))
    before = p.pyproject.read_bytes()
    done = p("pin", "--no-lock", p.model.as_posix())
    assert done.returncode == 0, done.stdout + done.stderr
    assert p.pyproject.read_bytes() == before.replace(
        f"armature-engine = {PATH_SOURCE}".encode(),
        f"armature-engine = {git_source(tag='v2.4.1')}".encode())


@pytest.mark.parametrize("args", [
    ["pin", "{model}", "--no-lock"], ["pin", "--no-lock", "{model}"]])
def test_no_lock_is_taken_before_or_after_the_model_directory(plugin, args):
    p = plugin("2.4.1")
    done = p(*(a.format(model=p.model.as_posix()) for a in args))
    assert done.returncode == 0, done.stdout + done.stderr
    assert p.calls() == []


@pytest.mark.parametrize("args", [
    [], ["pin"], ["check", "{model}"],
    ["pin", "{model}", "{model}"]])
def test_a_wrong_call_is_refused_with_its_usage(plugin, args):
    p = plugin("2.4.1")
    done = p(*(a.format(model=p.model.as_posix()) for a in args))
    assert done.returncode == 2
    assert "usage: engine-source.sh pin [--no-lock] <model-dir>" in done.stderr
