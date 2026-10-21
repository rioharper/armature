"""The eval's copy of the plugin, made by `copy.sh` (#128).

The agent reads the plugin through the engine path its project's
`pyproject.toml` names, so the copy holds no `engine/tests/`: the fixture
tests and the golden answers are not there to read. The scaffold still
lays down the golden project, from the copy's `evals/golden/`, which the
harness masks from the agent.

The copy is made from a tree of this working tree, so an uncommitted edit
is what is tested.
"""

import os
import re
import subprocess

import pytest

import generate
from conftest import find_bash, run

ROOT = generate.EVALS.parent
GOLDEN = ROOT / "engine" / "tests" / "golden"
MECHANISMS = sorted(p.parent.name for p in GOLDEN.glob("*/mechanism.py"))


def _tree(index):
    """The working tree as a git tree, through a throwaway index."""
    env = {**os.environ, "GIT_INDEX_FILE": str(index)}
    for args in (["read-tree", "HEAD"], ["add", "-A"]):
        subprocess.run(["git", *args], cwd=ROOT, env=env, check=True,
                       capture_output=True)
    return subprocess.run(["git", "write-tree"], cwd=ROOT, env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture(scope="module")
def plugin_copy(tmp_path_factory):
    bash = find_bash()
    if bash is None:
        pytest.skip("no bash to run copy.sh with")
    tmp = tmp_path_factory.mktemp("copy")
    dest = tmp / "armature-eval"
    made = run([bash, (generate.EVALS / "copy.sh").as_posix(),
                dest.as_posix(), _tree(tmp / "index")], ROOT)
    assert made.returncode == 0, made.stdout + made.stderr
    return dest


def test_the_copy_holds_no_engine_tests(plugin_copy):
    engine = plugin_copy / "engine"
    assert (engine / "src" / "armature" / "__init__.py").is_file()
    assert (engine / "pyproject.toml").is_file()
    assert not (engine / "tests").exists()
    assert not list(plugin_copy.rglob("test_fixture_*"))
    assert not list(plugin_copy.rglob("answers.py"))


def test_the_copy_holds_no_progress_log(plugin_copy):
    """PROGRESS.md is the maintainers' log, and quotes golden numbers."""
    assert (ROOT / "PROGRESS.md").is_file()
    assert (plugin_copy / "CHANGELOG.md").is_file()
    assert not (plugin_copy / "PROGRESS.md").exists()


def _project(name):
    """The golden project `name`'s files: its modules and its ledger."""
    return [*(GOLDEN / name).glob("*.py"), GOLDEN / name / "ledger.toml"]


def test_the_copy_holds_every_golden_project_under_evals(plugin_copy):
    assert MECHANISMS
    for name in MECHANISMS:
        for source in _project(name):
            copied = plugin_copy / "evals" / "golden" / name / source.name
            assert copied.read_bytes() == source.read_bytes(), copied


def test_the_copy_holds_the_hold_out(plugin_copy):
    """The hold-out's case, its scaffold and graders among it, goes with
    the rest of evals/, which the harness masks from the agent (#132)."""
    held = generate.EVALS / "holdout"
    files = [p for p in held.rglob("*") if p.is_file()]
    assert generate.HOLDOUT and files
    for source in files:
        copied = plugin_copy / "evals" / source.relative_to(generate.EVALS)
        assert copied.read_bytes() == source.read_bytes(), copied


@pytest.mark.slow
@pytest.mark.parametrize("case, mechanism", [
    ("wheel-leg-derive", "wheel_leg"),
    *((f"holdout/{name}", case.mechanism)
      for name, case in generate.HOLDOUT.items())])
def test_a_scaffold_in_the_copy_lays_down_the_golden_project(
        plugin_copy, tmp_path, case, mechanism):
    """The scaffold reads the golden project from the copy, and points the
    project's engine at the copy's engine, which holds no tests; the
    project's `run_all.py` then passes on it, its ledger check first. The
    ledger lands at the project's root, where `load` finds it walking up
    from analysis/model/, and nowhere else. The hold-out's scaffold is
    checked here too, since no tuned check reaches it."""
    cache = run(["uv", "cache", "dir"], tmp_path).stdout.strip()
    scaffold = (plugin_copy / "evals" / case / "scaffold.sh").as_posix()
    laid = run([find_bash(), scaffold], tmp_path,
               ARMATURE_EVAL_UV_CACHE=cache)
    assert laid.returncode == 0, laid.stdout + laid.stderr
    model = tmp_path / "analysis" / "model"
    for source in (GOLDEN / mechanism).glob("*.py"):
        assert (model / source.name).read_bytes() == source.read_bytes()
    ledger = GOLDEN / mechanism / "ledger.toml"
    assert (tmp_path / "ledger.toml").read_bytes() == ledger.read_bytes()
    assert not (model / "ledger.toml").exists()
    engine = (plugin_copy / "engine").resolve().as_posix()
    pyproject = (model / "pyproject.toml").read_text(encoding="utf-8")
    assert f'path = "{engine}"' in pyproject.replace("\\", "/")
    checked = run(["uv", "run", "--offline", "python", "run_all.py"], model,
                  UV_CACHE_DIR=cache)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert re.search(r"\[PASS\] ledger check on \.\.[\\/]\.\.[\\/]ledger\.toml"
                     r": no error", checked.stdout), checked.stdout[:2000]
