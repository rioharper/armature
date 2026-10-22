"""An eval case's project under the gates (#160, ADR 0011).

`claude plugin eval` loads the plugin's hook, so a case's project is gated
as a user's is: its root `ledger.toml` puts it in the hook's scope. The
scaffold must therefore leave what `init` leaves, a clean tree on `main`
that ignores `.armature/`, so that a derive case's merge finds a committed
state the gate can read, and a stamp never dirties it. The plugin's launcher
runs the gate from `copy.sh`'s copy, as a run does, and must leave that copy
with no venv and no hard link, which `claude plugin eval` refuses.

Slow: the scaffold syncs a venv, and `gate merge` runs the model.
"""

import json
import os
import subprocess

import pytest

import generate
from conftest import find_bash, run

ROOT = generate.EVALS.parent
# What `claude plugin eval`'s sandbox lays over a run's workspace, as the
# agent's `git status` listed it untracked in #160's on-demand run (Claude
# Code 2.1.301): shell and editor configuration masked from the agent, and
# the harness's own artifacts. Directories end in `/`.
MASKED = [".bash_profile", ".bashrc", ".claude/", ".eval-artifacts",
          ".gitconfig", ".gitmodules", ".idea", ".mcp.json", ".profile",
          ".ripgreprc", ".vscode", ".zprofile", ".zshrc"]


def _tree(index):
    """The working tree as a git tree, through a throwaway index."""
    env = {**os.environ, "GIT_INDEX_FILE": str(index)}
    for args in (["read-tree", "HEAD"], ["add", "-A"]):
        subprocess.run(["git", *args], cwd=ROOT, env=env, check=True,
                       capture_output=True)
    return subprocess.run(["git", "write-tree"], cwd=ROOT, env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


def git(project, *args):
    done = run(["git", *args], project)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout.strip()


@pytest.fixture(scope="module")
def laid(tmp_path_factory):
    """`(plugin copy, project, uv cache)`: copy.sh's copy of this working
    tree, and a derive case's project laid down from it by its scaffold."""
    bash = find_bash()
    if bash is None:
        pytest.skip("no bash to run copy.sh and the scaffold with")
    tmp = tmp_path_factory.mktemp("gated")
    plugin = tmp / "armature-eval"
    made = run([bash, (generate.EVALS / "copy.sh").as_posix(),
                plugin.as_posix(), _tree(tmp / "index")], ROOT)
    assert made.returncode == 0, made.stdout + made.stderr
    project = tmp / "work"
    project.mkdir()
    cache = run(["uv", "cache", "dir"], project).stdout.strip()
    scaffold = (plugin / "evals" / "spring-cable-derive" / "scaffold.sh")
    done = run([bash, scaffold.as_posix()], project,
               ARMATURE_EVAL_UV_CACHE=cache)
    assert done.returncode == 0, done.stdout + done.stderr
    return plugin, project, cache


@pytest.mark.slow
def test_the_scaffold_leaves_a_clean_main_that_ignores_the_stamps(laid):
    """The skills merge into `main` and the hook guards `main`, so a project
    on git's default `master` would have neither; a stamp under
    `.armature/` must not dirty the tree the gate needs clean."""
    _, project, _ = laid
    assert git(project, "symbolic-ref", "--short", "HEAD") == "main"
    assert git(project, "status", "--porcelain") == ""
    ignored = run(["git", "check-ignore", "-q", ".armature/runs/key.json"],
                  project)
    assert ignored.returncode == 0, "the scaffold's .gitignore lacks .armature/"


def mask(project):
    """Lay down what the eval's sandbox lays over the workspace."""
    for name in MASKED:
        path = project / name.rstrip("/")
        if name.endswith("/"):
            path.mkdir(exist_ok=True)
            (path / "settings.json").write_text("{}\n", encoding="utf-8")
        else:
            path.write_text("", encoding="utf-8")


@pytest.mark.slow
def test_the_sandboxs_masks_leave_the_tree_clean(laid):
    """The gate stamps a model run only on a clean tree, so the files the
    sandbox lays over the workspace must not dirty it: in #160's run they
    did, no stamp was ever written, and the hook refused every merge, which
    no grader saw. They are excluded in the clone, not in a `.gitignore`
    the agent would read as the project's."""
    _, project, _ = laid
    mask(project)
    assert git(project, "status", "--porcelain", "--untracked-files=all") == ""
    assert ".bashrc" not in (project / ".gitignore").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def milestone(laid, tmp_path_factory):
    """`(plugin copy, project, plugin data, gate merge's verdict, the hook's
    output on the merge)`: derive's Milestone 0 committed on its branch,
    under the sandbox's masks, gated through the copy's launcher, as
    derive's checkpoint does before it dispatches the red team, and then
    the merge the hook sees."""
    plugin, project, cache = laid
    mask(project)
    data = tmp_path_factory.mktemp("plugin-data")
    git(project, "checkout", "-q", "-b", "armature/m0-setup")
    notes = project / "analysis" / "derivation"
    notes.mkdir(parents=True)
    (notes / "00_setup.md").write_text("# Milestone 0: setup\n",
                                       encoding="utf-8")
    with (project / "analysis" / "model" / "params.py").open(
            "a", encoding="utf-8", newline="\n") as f:
        f.write("# Milestone 0 read the structure here.\n")
    git(project, "add", "analysis")    # the run's own `add -A` failed on a mask
    git(project, "-c", "user.name=t", "-c", "user.email=t@t.invalid",
        "commit", "-qm", "m0: setup")
    launcher = (plugin / "scripts" / "armature.sh").as_posix()
    env = {"CLAUDE_PLUGIN_DATA": str(data), "UV_CACHE_DIR": cache}
    gated = run([find_bash(), launcher, "gate", "merge", "--json"], project,
                **env)
    git(project, "checkout", "-q", "main")
    event = json.dumps({
        "hook_event_name": "PreToolUse", "tool_name": "Bash",
        "cwd": str(project),
        "tool_input": {"command": "git merge --ff-only armature/m0-setup"}})
    hooked = subprocess.run(
        [find_bash(), launcher, "hook"], input=event, cwd=project,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**{k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"},
             **env})
    return plugin, project, data, gated, hooked


@pytest.mark.slow
def test_a_derive_merge_finds_a_committed_state_the_gate_reads(milestone):
    """Every item but the review is the scaffold's to satisfy: `main` is
    the branch point, the golden ledger checks, the model runs green and
    is stamped, and the engine's path pin, which a project never commits,
    is waived by the scaffold's standing waiver. Only the review, the red
    team's to supply, is missing."""
    _, project, _, gated, _ = milestone
    assert gated.returncode == 1, gated.stdout + gated.stderr
    verdict = json.loads(gated.stdout)
    states = {i["item"]: i["state"] for i in verdict["items"]}
    assert states == {"fast-forward": "pass", "ledger": "pass",
                      "stamps": "pass", "engine": "waived", "review": "fail",
                      "closed": "pass", "moves": "pass"}, verdict["items"]
    engine = next(i for i in verdict["items"] if i["item"] == "engine")
    assert "eval sandbox" in engine["detail"]
    assert verdict["warnings"] == []
    assert git(project, "status", "--porcelain") == ""
    assert list((project / ".armature" / "runs").glob("*.json"))


@pytest.mark.slow
def test_the_hooks_denial_of_that_merge_carries_the_gates_lines(milestone):
    """A run's merge with the review missing is denied, and the denial,
    which is what the agent and a trace see, names the item that failed."""
    *_, hooked = milestone
    assert hooked.returncode == 0, hooked.stderr
    decision = json.loads(hooked.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "fail review" in decision["permissionDecisionReason"]


@pytest.mark.slow
def test_the_launcher_leaves_the_plugin_copy_without_a_venv_or_hard_link(
        milestone):
    """`claude plugin eval` refuses a plugin with any file of more than one
    name, and uv hard-links a venv's files from its cache: the launcher's
    venv is under CLAUDE_PLUGIN_DATA, never in the copy."""
    plugin, _, data, *_ = milestone
    assert (data / "venv").is_dir()
    assert not list(plugin.rglob("pyvenv.cfg"))
    linked = [p for p in plugin.rglob("*")
              if p.is_file() and os.stat(p).st_nlink > 1]
    assert not linked, linked[:5]
