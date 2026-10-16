"""The golden projects and their answers (ADR 0008).

Each golden project is a project-form directory: copied beside the model
template's `run_all.py`, it compiles, as `test_spec_stage.py` does for the
template's `coarse_2r/`. Its answers sit beside it in `answers.py`, never
inside it, so a copy cannot leak them; and each answer's bait, the value the
bait gives, lies outside the answer's window.
"""

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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
        if path.suffix != ".py":
            continue
        assert "answer" not in path.stem, path
        text = path.read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported |= {node.module or ""}
                imported |= {alias.name for alias in node.names}
        assert not {n.split(".")[0] for n in imported} & {"answers", "golden"}, \
            path
        for key, answer in ANSWERS.items():
            assert f"{abs(answer.value):.4g}" not in text, (path, key)


@pytest.mark.parametrize("name", golden.NAMES)
def test_a_copied_golden_project_compiles_under_run_all(name, tmp_path):
    shutil.copy(TEMPLATE / "run_all.py", tmp_path / "run_all.py")
    for path in (golden.HERE / name).glob("*.py"):
        shutil.copy(path, tmp_path / path.name)
    run = subprocess.run([sys.executable, "run_all.py"], cwd=tmp_path,
                         capture_output=True, text=True, encoding="utf-8",
                         env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                         timeout=300)
    assert run.returncode == 0, f"{run.stdout[-4000:]}\n{run.stderr[-4000:]}"
    assert "[PASS] the description compiles exactly" in run.stdout
    assert "All self-tests passed across all milestones." in run.stdout


def test_each_project_loads_with_its_own_params():
    assert golden.arm_2r.PARAMS is golden.arm_2r.params.PARAMS
    assert golden.wheel_leg.PARAMS is not golden.parallelogram.PARAMS
