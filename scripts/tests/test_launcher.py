"""The launcher (#158, ADR 0011): `scripts/armature.sh`, and
`scripts/armature.ps1` for the PowerShell fallback, run the plugin's own
engine through uv with its venv under `CLAUDE_PLUGIN_DATA`; as the hook,
they start Python only for a call that may be gated, and with no uv deny
only what looks gated.

A fake `uv` first on PATH records its arguments, the venv it was given and
the event it read, so the tests see what the launcher hands the engine
without building one. `hooks/hooks.json`'s command is run as Claude Code
runs it: by Git Bash, and by PowerShell where there is no Git Bash. Run
from the plugin root:

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

FAKE_UV = """#!/usr/bin/env bash
{ printf 'uv %s\\n' "$*"; printf 'venv %s\\n' "$UV_PROJECT_ENVIRONMENT"
  printf 'event %s\\n' "$(cat)"; } >> "$FAKE_LOG"
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
    """A plugin copy holding the launchers, a project with a root
    `ledger.toml`, a plain repo, and a PATH with git and maybe a fake
    uv."""

    def __init__(self, tmp_path):
        self.plugin = tmp_path / "plugin"
        (self.plugin / "scripts").mkdir(parents=True)
        (self.plugin / "hooks").mkdir()
        for name in ("armature.sh", "armature.ps1"):
            shutil.copy(SCRIPTS / name, self.plugin / "scripts")
        shutil.copy(ROOT / "hooks" / "hooks.json", self.plugin / "hooks")
        self.project = tmp_path / "arm"
        self.plain = tmp_path / "plain"
        for repo in (self.project, self.plain):
            repo.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)],
                           check=True)
        (self.project / "ledger.toml").write_text("# entries\n")
        self.data = tmp_path / "data"
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.fakes = tmp_path / "fakes"
        self.fakes.mkdir()
        self.log = tmp_path / "uv.log"
        git = Path(shutil.which("git")).resolve()
        tools = [str(git.parent)]
        if sys.platform == "win32":     # Git's coreutils, and powershell
            tools += [str(p / "usr" / "bin") for p in git.parents
                      if (p / "usr" / "bin").is_dir()][:1]
            tools += [os.path.expandvars(r"%SystemRoot%\System32"),
                      os.path.expandvars(
                          r"%SystemRoot%\System32\WindowsPowerShell\v1.0")]
        else:
            tools += ["/usr/bin", "/bin"]
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

    def event(self, tool, cwd=None, **tool_input):
        return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool,
                           "cwd": str(cwd or self.project),
                           "tool_input": tool_input})

    def bash(self, *args, stdin=""):
        bash = find_bash()
        if bash is None:
            pytest.skip("no bash to run the launcher with")
        return subprocess.run(
            [bash, (self.plugin / "scripts" / "armature.sh").as_posix(),
             *args], input=stdin.encode("utf-8"), capture_output=True,
            env=self.env, cwd=self.project)

    def hook_command(self):
        command = json.loads((self.plugin / "hooks" / "hooks.json")
                             .read_text())["hooks"]["PreToolUse"][0]["hooks"][0]
        return command["command"].replace("${CLAUDE_PLUGIN_ROOT}",
                                          self.plugin.as_posix())


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def decision(run):
    assert run.returncode == 0, run.stderr.decode(errors="replace")
    out = run.stdout.decode().strip()
    return json.loads(out)["hookSpecificOutput"] if out else None


# --- with no uv: deny only what is gated, asking for uv ----------------------
def test_with_no_uv_a_gated_merge_is_denied_asking_for_uv(setup):
    out = decision(setup.bash("hook", stdin=setup.event(
        "Bash", command="git checkout main && git merge armature/spec-arm")))
    assert out["permissionDecision"] == "deny"
    assert "install uv" in out["permissionDecisionReason"].lower()


def test_with_no_uv_an_ungated_command_or_another_repo_is_left_alone(setup):
    assert decision(setup.bash("hook", stdin=setup.event(
        "Bash", command="git status && git log -1"))) is None
    assert decision(setup.bash("hook", stdin=setup.event(
        "Bash", cwd=setup.plain, command="git merge feature"))) is None
    assert decision(setup.bash("hook", stdin=setup.event(
        "Edit", file_path=str(setup.project / "ledger.toml"),
        old_string="0.3", new_string="0.31"))) is None
    out = decision(setup.bash("hook", stdin=setup.event(
        "Edit", file_path=str(setup.project / "ledger.toml"),
        old_string='"candidate"', new_string='"confirmed"')))
    assert out["permissionDecision"] == "deny"


LAUNCHERS = ["bash", "powershell"]


def launch(setup, which, event):
    """The hook's decision from `which` launcher, run directly."""
    if which == "bash":
        return decision(setup.bash("hook", stdin=event))
    if powershell() is None:
        pytest.skip("no PowerShell")
    return decision(subprocess.run(
        [powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(setup.plugin / "scripts" / "armature.ps1"),
         "hook"], input=event.encode("utf-8"), capture_output=True,
        env=setup.env, cwd=setup.project))


@pytest.mark.parametrize("which", LAUNCHERS)
def test_with_no_uv_nothing_outside_a_project_is_denied(setup, which):
    """The hook is a no-op where no root ledger.toml is reachable: an edit
    accepting a finding in a plain repo, and a commit behind a `cd` into a
    folder of it."""
    (setup.plain / "sub").mkdir()
    for event in (
            setup.event("Edit", cwd=setup.plain,
                        file_path=str(setup.plain / "docs/reviews/a.md"),
                        old_string="open", new_string='status = "accepted"'),
            setup.event("Write", cwd=setup.plain,
                        file_path="reviews/a.md",
                        content='status = "accepted"\n'),
            setup.event("Bash", cwd=setup.plain,
                        command="cd sub && git commit -m x"),
            setup.event("Bash", cwd=setup.plain,
                        command="git -C sub merge feature")):
        assert launch(setup, which, event) is None, event


@pytest.mark.parametrize("which", LAUNCHERS)
def test_with_no_uv_a_project_reached_by_cd_or_dash_c_is_gated(setup, which):
    project = setup.project.as_posix()
    for command in (f"cd {project} && git merge feature",
                    f'cd "{project}"; git push',
                    f"git -C {project} commit -m x"):
        out = launch(setup, which, setup.event("Bash", cwd=setup.plain,
                                               command=command))
        assert out and out["permissionDecision"] == "deny", command


@pytest.mark.parametrize("which", LAUNCHERS)
def test_with_no_uv_only_what_the_edit_writes_is_read(setup, which):
    """Inside a project an edit is denied for what it writes, never for a
    word elsewhere in the event: `confirmed` in a review, or in the text an
    edit replaces, confirms nothing."""
    reviews = str(setup.project / "docs/reviews/a.md")
    ledger = str(setup.project / "ledger.toml")
    for event in (
            setup.event("Edit", file_path=reviews, old_string="a",
                        new_string="the confirmed torque is 2 N m"),
            setup.event("Edit", file_path=ledger,
                        old_string='status = "confirmed"',
                        new_string='status = "candidate"')):
        assert launch(setup, which, event) is None, event
    for event in (
            setup.event("Edit", file_path=reviews, old_string="open",
                        new_string='status = "accepted"'),
            setup.event("Edit", file_path=ledger, old_string="# entries",
                        new_string='[mechanism.l1]\nvalue = 0.3\nunit = "m"\n'
                                   'source = { kind = "chosen", ref = "x" }'),
            setup.event("Write", file_path=str(setup.project / "waivers.toml"),
                        content='[[waiver]]\ngate = "merge"\n'),
            setup.event("Write", file_path=str(
                setup.project / ".armature/runs/k.json"), content="{}")):
        out = launch(setup, which, event)
        assert out and out["permissionDecision"] == "deny", event


# --- with uv: the engine, its venv under CLAUDE_PLUGIN_DATA ------------------
def test_a_call_that_may_be_gated_reaches_the_engine_through_uv(setup):
    setup.with_uv()
    event = setup.event("Bash", command="git merge armature/spec-arm")
    assert decision(setup.bash("hook", stdin=event)) is None
    uv, venv, seen = setup.calls()
    assert uv.split()[1:6] == ["run", "--quiet", "--frozen", "--no-dev",
                               "--project"]
    assert uv.endswith("python -m armature.gate.hook")
    assert Path(uv.split()[6]) == setup.plugin / "engine"
    assert Path(venv.split(" ", 1)[1]) == setup.data / "venv"
    assert json.loads(seen.split(" ", 1)[1])["tool_input"]["command"] == \
        "git merge armature/spec-arm"


def test_the_skills_verbs_run_the_same_engine(setup):
    setup.with_uv()
    assert setup.bash("gate", "status", "--json").returncode == 0
    uv = setup.calls()[0]
    assert uv.endswith("python -m armature.gate status --json")


def test_help_prints_the_header_comment_and_nothing_else(setup):
    run = setup.bash("--help")
    assert run.returncode == 2
    lines = run.stdout.decode().splitlines()
    assert lines[0].startswith("The plugin's own engine, run through uv")
    assert lines[-1].endswith("PowerShell, the hook's fallback where there "
                              "is no Git Bash.")
    assert not any(line.startswith(("set ", "#")) for line in lines)


def test_a_call_that_cannot_be_gated_never_starts_python(setup):
    setup.with_uv()
    for event in (
            setup.event("Bash", command="ls -la && cat ledger.toml"),
            setup.event("Bash", cwd=setup.plain, command="git commit -m x"),
            setup.event("Edit", file_path=str(setup.project / "docs/a.md"),
                        old_string="a", new_string="b"),
            setup.event("Read", file_path=str(setup.project / "ledger.toml"))):
        assert decision(setup.bash("hook", stdin=event)) is None
    assert setup.calls() == []
    setup.bash("hook", stdin=setup.event(
        "Bash", cwd=setup.plain, command=f"cd {setup.project.as_posix()} "
                                         f"&& git merge x"))
    assert len(setup.calls()) == 3


# --- the hook's command, as Claude Code runs it ------------------------------
def test_git_bash_runs_the_hook_command(setup):
    setup.with_uv()
    bash = find_bash()
    if bash is None:
        pytest.skip("no bash")
    run = subprocess.run([bash, "-c", setup.hook_command()],
                         input=setup.event("Bash", command="git push").encode(),
                         capture_output=True, env=setup.env)
    assert run.returncode == 0, run.stderr
    assert setup.calls()[0].endswith("python -m armature.gate.hook")


@pytest.mark.skipif(powershell() is None, reason="no PowerShell")
def test_powershell_runs_the_hook_command_through_its_own_launcher(setup):
    run = subprocess.run(
        [powershell(), "-NoProfile", "-NonInteractive", "-Command",
         setup.hook_command()],
        input=setup.event("PowerShell",
                          command="git merge armature/spec-arm").encode(),
        capture_output=True, env={**setup.env, "PATH": os.pathsep.join(
            p for p in setup.env["PATH"].split(os.pathsep)
            if "usr" not in p.lower())})
    out = decision(run)
    assert out["permissionDecision"] == "deny"
    assert "install uv" in out["permissionDecisionReason"].lower()
    setup.with_uv()
    run = subprocess.run(
        [powershell(), "-NoProfile", "-NonInteractive", "-Command",
         setup.hook_command()],
        input=setup.event("PowerShell", command="git push").encode(),
        capture_output=True, env=setup.env)
    assert run.returncode == 0, run.stderr
    uv, venv = setup.calls()[:2]
    assert "python -m armature.gate.hook" in uv
    assert Path(venv.split(" ", 1)[1].strip()) == setup.data / "venv"
