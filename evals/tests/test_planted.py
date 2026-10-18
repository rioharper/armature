"""The guard on each red-team case's planted derivation (ADR 0008).

Each case is assembled by its own `scaffold.sh`, as `claude plugin eval`
runs it: the model template's runner and gates, the golden project, then
the case's `planted/`. The guard holds the trap where the case needs it:
1. `run_all.py` passes, so the trap gets past derive's own gates;
2. the planted report's number lies outside the case's window, and the
   golden value inside it;
3. no number inside the window appears anywhere in the planted derivation
   or in what its run prints, so a review cannot copy the answer from it.

Slow: each assembly syncs a venv and runs the model. On Windows the
scaffold runs under Git's bash, never WSL's, and its uv cache is uv's own.
"""

import math
import re

import pytest

import generate
from conftest import find_bash, run
from golden.answers import ANSWERS

# The stated cases only: an unstated variant lays down its case's own
# planted/, so assembling it again would check the same derivation.
REVIEWS = [name for name, case in generate.CASES.items()
           if isinstance(case, generate.Review) and case.stated]


@pytest.fixture(scope="module", params=REVIEWS)
def assembled(request, tmp_path_factory):
    """`(name, workspace, run_all's output)`: the case's project, laid down
    by its scaffold in an empty directory and run."""
    name, bash = request.param, find_bash()
    if bash is None:
        pytest.skip("no bash to run the scaffold with")
    work = tmp_path_factory.mktemp(name)
    cache = run(["uv", "cache", "dir"], work).stdout.strip()
    scaffold = (generate.EVALS / name / "scaffold.sh").as_posix()
    laid = run([bash, scaffold], work, ARMATURE_EVAL_UV_CACHE=cache)
    assert laid.returncode == 0, laid.stdout + laid.stderr
    ran = run(["uv", "run", "--frozen", "python", "run_all.py"],
              work / "analysis" / "model")
    return name, work, ran


@pytest.mark.slow
def test_the_planted_derivation_passes_derives_own_gates(assembled):
    name, _, ran = assembled
    assert ran.returncode == 0, (f"{name}: run_all.py failed\n"
                                 f"{ran.stdout}\n{ran.stderr}")
    assert "All self-tests passed across all milestones." in ran.stdout
    assert "Layout: the gates" in ran.stdout  # the truth gate ran too


@pytest.mark.slow
def test_the_planted_number_is_outside_the_window_and_the_golden_inside(
        assembled):
    name, work, _ = assembled
    case = generate.CASES[name]
    answer = ANSWERS[case.answer]
    report = (work / case.planted).read_text(encoding="utf-8")
    found = re.search(case.claim, report)
    assert found, f"{name}: no claim in {case.planted}"
    planted = math.inf if found[1] == "∞" else float(found[1])
    assert not answer.inside(planted), (name, planted, answer.bounds)
    assert answer.inside(answer.value)
    assert re.search(generate.window(answer),
                     f"{answer.value:.4g} {answer.unit}")


@pytest.mark.slow
def test_the_answer_is_nowhere_in_the_planted_derivation(assembled):
    """The catch's window runs on the review: a number inside it that the
    derivation already printed could be copied rather than recomputed."""
    name, work, ran = assembled
    case = generate.CASES[name]
    pattern = generate.window(ANSWERS[case.answer])
    planted = generate.EVALS / name / "planted"
    texts = {"run_all.py's output": ran.stdout}
    texts.update({p.relative_to(planted).as_posix(): p.read_text(
        encoding="utf-8") for p in planted.rglob("*") if p.is_file()})
    assert (work / case.planted).is_file()
    leaks = {where: m[0] for where, text in texts.items()
             if (m := re.search(pattern, text))}
    assert not leaks, f"{name}: the answer is printed in {leaks}"
