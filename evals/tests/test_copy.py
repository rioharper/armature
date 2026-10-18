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
import subprocess

import pytest

import generate
from test_planted import _bash, _run

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
def copy(tmp_path_factory):
    bash = _bash()
    if bash is None:
        pytest.skip("no bash to run copy.sh with")
    tmp = tmp_path_factory.mktemp("copy")
    dest = tmp / "armature-eval"
    made = _run([bash, (generate.EVALS / "copy.sh").as_posix(),
                 dest.as_posix(), _tree(tmp / "index")], ROOT)
    assert made.returncode == 0, made.stdout + made.stderr
    return dest


def test_the_copy_holds_no_engine_tests(copy):
    assert (copy / "engine" / "src" / "armature" / "__init__.py").is_file()
    assert (copy / "engine" / "pyproject.toml").is_file()
    assert not (copy / "engine" / "tests").exists()
    assert not list(copy.rglob("test_fixture_*"))
    assert not list(copy.rglob("answers.py"))


def test_the_copy_holds_every_golden_project_under_evals(copy):
    assert MECHANISMS
    for name in MECHANISMS:
        for source in (GOLDEN / name).glob("*.py"):
            copied = copy / "evals" / "golden" / name / source.name
            assert copied.read_bytes() == source.read_bytes(), copied


@pytest.mark.slow
def test_a_scaffold_in_the_copy_lays_down_the_golden_project(copy, tmp_path):
    """The scaffold reads the golden project from the copy, and points the
    project's engine at the copy's engine, which holds no tests."""
    cache = _run(["uv", "cache", "dir"], tmp_path).stdout.strip()
    scaffold = (copy / "evals" / "wheel-leg-derive" / "scaffold.sh").as_posix()
    laid = _run([_bash(), scaffold], tmp_path, ARMATURE_EVAL_UV_CACHE=cache)
    assert laid.returncode == 0, laid.stdout + laid.stderr
    model = tmp_path / "analysis" / "model"
    for source in (GOLDEN / "wheel_leg").glob("*.py"):
        assert (model / source.name).read_bytes() == source.read_bytes()
    engine = (copy / "engine").resolve().as_posix()
    pyproject = (model / "pyproject.toml").read_text(encoding="utf-8")
    assert f'path = "{engine}"' in pyproject.replace("\\", "/")
