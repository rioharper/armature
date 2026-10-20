"""`engine-source.sh` (#134, ADR 0009): `pin` writes a model directory's
engine source as the git tag of the plugin it runs from, and `check` reports
how far the project's source is from that tag.

Each test copies the script and a `plugin.json` at a chosen version into a
temporary plugin root, so the plugin's version is a test input. Fake `gh` and
`uv` go first on PATH: `gh` answers the `rev` containment query with a status
the test chooses, and `uv` records that it ran. Run from the plugin root:

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

FAKE_GH = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FAKE_LOG"
[ "${FAKE_GH_EXIT:-0}" = 0 ] || { echo "HTTP 404: Not Found" >&2; exit 1; }
printf '%s\\n' "$FAKE_GH_STATUS"
"""
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
        for name, body in (("gh", FAKE_GH), ("uv", FAKE_UV)):
            (fakes / name).write_bytes(body.encode())
            (fakes / name).chmod(0o755)
        self.log = tmp_path / "fakes.log"
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PLUGIN_ROOT", "VIRTUAL_ENV")}
        self.env.update(PATH=str(fakes) + os.pathsep + os.environ["PATH"],
                        FAKE_LOG=self.log.as_posix(), FAKE_GH_STATUS="")

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

    def __call__(self, *args, gh_status="", gh_exit=0, cwd=None,
                 script=None):
        """The script run with `args`, by default by its absolute path
        from the model directory."""
        bash = find_bash()
        if bash is None:
            pytest.skip("no bash to run engine-source.sh with")
        env = {**self.env, "FAKE_GH_STATUS": gh_status,
               "FAKE_GH_EXIT": str(gh_exit)}
        script = script or (self.root / "scripts" / "engine-source.sh")
        return run([bash, Path(script).as_posix(), *args], cwd or self.model,
                   env)


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


@pytest.mark.parametrize("source, line", [
    (git_source(tag="v2.4.1"), "in-step v2.4.1"),
    (git_source(tag="v2.3.9"), "behind v2.3.9 -> v2.4.1 (minor)"),
    (git_source(tag="v2.4.0"), "behind v2.4.0 -> v2.4.1 (minor)"),
    (git_source(tag="v1.9.9"), "behind v1.9.9 -> v2.4.1 (major)"),
    (git_source(tag="v2.4.2"), "ahead v2.4.2 > v2.4.1"),
    (git_source(tag="v2.10.0"), "ahead v2.10.0 > v2.4.1"),
    (git_source(tag="v3.0.0"), "ahead v3.0.0 > v2.4.1"),
    (PATH_SOURCE, "path ../../../../engine"),
])
def test_check_reports_the_projects_state(plugin, source, line):
    p = plugin("2.4.1")
    p.source(source)
    before = p.pyproject.read_bytes()
    done = p("check", p.model.as_posix())
    assert done.stdout.splitlines() == [line], done.stderr
    assert done.returncode == (0 if line.startswith("in-step") else 1)
    assert p.pyproject.read_bytes() == before
    assert p.calls() == []


@pytest.mark.parametrize("status, state", [
    ("behind", "in v2.4.1"),
    ("identical", "in v2.4.1"),
    ("ahead", "unreleased"),
    ("diverged", "unreleased"),
])
def test_check_reports_whether_the_tag_contains_a_rev_pin(
        plugin, status, state):
    p = plugin("2.4.1")
    p.source(git_source(rev=SHA))
    done = p("check", p.model.as_posix(), gh_status=status)
    assert done.stdout.splitlines() == [f"rev {SHA} ({state})"], done.stderr
    assert done.returncode == 1
    assert p.calls() == [
        f"api repos/rioharper/armature/compare/v2.4.1...{SHA} --jq .status"]


def test_check_reports_a_rev_pin_unknown_when_gh_fails(plugin):
    p = plugin("2.4.1")
    p.source(git_source(rev=SHA))
    done = p("check", p.model.as_posix(), gh_exit=1)
    assert done.stdout.splitlines() == [f"rev {SHA} (unknown)"]
    assert done.returncode == 1


@pytest.mark.parametrize("command", [["check"], ["pin", "--no-lock"]])
def test_a_tag_that_is_not_vX_Y_Z_is_refused(plugin, command):
    p = plugin("2.4.1")
    p.source(git_source(tag="v2.4"))
    done = p(*command, p.model.as_posix())
    assert done.returncode == 2
    assert "'v2.4' is not a vX.Y.Z tag" in done.stderr
    assert done.stdout == ""


@pytest.mark.parametrize("source, gh_status", [
    (git_source(tag="v2.4.1"), ""),
    (git_source(tag="v2.0.0"), ""),
    (git_source(tag="v2.3.7"), ""),
    (git_source(rev=SHA), "behind"),
    (git_source(rev=SHA), "identical"),
])
def test_pin_upgrades_a_tag_or_contained_rev_on_the_plugins_major(
        plugin, source, gh_status):
    p = plugin("2.4.1")
    p.source(source)
    done = p("pin", "--no-lock", p.model.as_posix(), gh_status=gh_status)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.splitlines() == [
        f"old: {source}", f"new: {git_source(tag='v2.4.1')}"]
    assert p.engine_lines() == [f"armature-engine = {git_source(tag='v2.4.1')}"]


@pytest.mark.parametrize("source, gh_status, gh_exit, says", [
    (git_source(tag="v1.9.9"), "", 0, "CHANGELOG.md"),
    (git_source(tag="v2.4.2"), "", 0, "plugin is out of date"),
    (git_source(tag="v3.0.0"), "", 0, "plugin is out of date"),
    (git_source(rev=SHA), "ahead", 0, "does not contain"),
    (git_source(rev=SHA), "diverged", 0, "does not contain"),
    (git_source(rev=SHA), "", 1, "could not tell"),
])
def test_pin_refuses_a_migration_a_newer_tag_and_an_uncontained_rev(
        plugin, source, gh_status, gh_exit, says):
    p = plugin("2.4.1")
    p.source(source)
    before = p.pyproject.read_bytes()
    done = p("pin", p.model.as_posix(), gh_status=gh_status, gh_exit=gh_exit)
    assert done.returncode == 2, done.stdout + done.stderr
    assert says in done.stderr
    assert p.pyproject.read_bytes() == before
    assert not any(c.startswith("uv ") for c in p.calls())


@pytest.mark.parametrize("command", [["check"], ["pin", "--no-lock"]])
def test_a_pyproject_with_no_engine_line_fails_loudly(plugin, command):
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
    p.source(git_source(tag="v7.0.3"))
    done = p("check", p.model.as_posix(), cwd=p.root,
             script="scripts/engine-source.sh")
    assert done.stdout.splitlines() == ["in-step v7.0.3"], done.stderr


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
    [], ["pin"], ["check", "--no-lock", "{model}"],
    ["pin", "{model}", "{model}"]])
def test_a_wrong_call_is_refused_with_its_usage(plugin, args):
    p = plugin("2.4.1")
    done = p(*(a.format(model=p.model.as_posix()) for a in args))
    assert done.returncode == 2
    assert "usage: engine-source.sh pin [--no-lock] <model-dir>" in done.stderr
