"""The golden projects and their answers (ADR 0008).

Each golden project is a project-form directory: copied beside the model
template's `run_all.py`, it compiles, as `test_spec_stage.py` does for the
template's `coarse_2r/`. Its numbers are its own `ledger.toml`'s (ADR 0010),
which `ledger check` passes clean, and its `params.py` writes none, by the
template's own rule. Its answers sit beside it in `answers.py`, never inside
it, so a copy cannot leak them; and each answer's bait, the value the bait
gives, lies outside the answer's window.
"""

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from armature.ledger import check

import golden
from golden.answers import ANSWERS

TEMPLATE = (Path(__file__).resolve().parents[2] / "skills" / "armature-derive"
            / "scripts" / "model_template")


@pytest.mark.parametrize("name", ANSWERS)
def test_every_bait_lies_outside_its_window(name):
    answer = ANSWERS[name]
    assert answer.inside(answer.value)
    assert not answer.inside(answer.bait), (
        f"{name}: the bait's {answer.bait} {answer.unit} lies inside "
        f"{answer.bounds}")


def test_every_answer_says_how_and_in_what():
    assert ANSWERS
    assert all(a.how and a.unit and 0 < a.window < 1 for a in ANSWERS.values())


@pytest.mark.parametrize("name", golden.NAMES)
def test_no_golden_project_contains_or_imports_an_answer(name):
    for path in (golden.HERE / name).glob("*"):
        if path.suffix not in (".py", ".toml"):
            continue
        assert "answer" not in path.stem, path
        text = path.read_text(encoding="utf-8")
        for key, answer in ANSWERS.items():
            assert f"{abs(answer.value):.4g}" not in text, (path, key)
        if path.suffix != ".py":
            continue
        imported = set()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported |= {node.module or ""}
                imported |= {alias.name for alias in node.names}
        assert not {n.split(".")[0] for n in imported} & {"answers", "golden"}, \
            path


@pytest.mark.parametrize("name", golden.NAMES)
def test_a_copied_golden_project_compiles_under_run_all(name, tmp_path):
    shutil.copy(TEMPLATE / "run_all.py", tmp_path / "run_all.py")
    for path in [*(golden.HERE / name).glob("*.py"),
                 golden.HERE / name / "ledger.toml"]:
        shutil.copy(path, tmp_path / path.name)
    run = subprocess.run([sys.executable, "run_all.py"], cwd=tmp_path,
                         capture_output=True, text=True, encoding="utf-8",
                         env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                         timeout=300)
    assert run.returncode == 0, f"{run.stdout[-4000:]}\n{run.stderr[-4000:]}"
    assert "[PASS] ledger check on ledger.toml: no error" in run.stdout
    assert "[PASS] the description compiles exactly" in run.stdout
    assert "All self-tests passed across all milestones." in run.stdout


def test_each_project_loads_with_its_own_params():
    assert golden.arm_2r.PARAMS is golden.arm_2r.params.PARAMS
    assert golden.wheel_leg.PARAMS is not golden.parallelogram.PARAMS


@pytest.mark.parametrize("name", golden.NAMES)
def test_each_golden_ledger_checks_clean(name):
    """Every number a golden project reads is its ledger's, and `ledger
    check` finds nothing in it: no error, and no warning either."""
    path = golden.HERE / name / "ledger.toml"
    assert path.is_file(), f"{name} has no ledger.toml"
    assert [str(f) for f in check(path)] == []


def _template_rule():
    """`numeric_literals` from the template's `params_checks.py`, compiled
    from its source alone, so a golden `params.py` is held by the rule the
    template's is and not by a copy of it. Importing the module would import
    the template's `params`."""
    path = TEMPLATE / "params_checks.py"
    found = [node for node in ast.parse(path.read_text(encoding="utf-8")).body
             if isinstance(node, ast.FunctionDef)
             and node.name == "numeric_literals"]
    assert found, f"{path} has no numeric_literals"
    namespace = {"ast": ast}
    exec(compile(ast.Module(body=found, type_ignores=[]), str(path), "exec"),
         namespace)
    return namespace["numeric_literals"]


@pytest.mark.parametrize("name", golden.NAMES)
def test_each_golden_params_writes_no_number(name):
    """A golden `params.py` holds structure only, as the template's does:
    no number but 0 and +-1, each of the rest a ledger entry's."""
    numeric_literals = _template_rule()
    assert numeric_literals("x = (0, 1.0, -1)\ny = 0.5\n") == [(2, 0.5)]
    path = golden.HERE / name / "params.py"
    found = numeric_literals(path.read_text(encoding="utf-8"))
    assert not found, (f"{name}/params.py writes numbers {found} (line, "
                       f"value); each belongs in its ledger.toml")
