"""The hold-out (#132): a case under `evals/holdout/` that nobody tunes
against. It is generated and scaffolded like every case, reported beside the
gate and never part of it, and frozen: its files, its golden project and its
`Answer` hash to a pinned value."""

import hashlib
import re

import pytest

import generate
import score
from golden.answers import ANSWERS

HOLDOUT = generate.EVALS / "holdout"
GOLDEN = generate.EVALS.parent / "engine" / "tests" / "golden"
CASES = sorted(generate.HOLDOUT)

# Bumped only deliberately, with a CHANGELOG entry saying what changed and
# why: the hold-out is written once, never edited in response to its results.
PINS = {
    "turret-derive":
        "9d2724ec692aa4df5fd66954efa0c9cd696606f8827975f25706f8d6754015f8",
}


def _frozen(name):
    """The SHA-256 of `name`'s case files, its golden project and the
    `Answer`s its graders quote, each file by its path under the repo and its
    text with LF line endings, so a Windows checkout and the WSL copy agree."""
    case = generate.HOLDOUT[name]
    root = generate.EVALS.parent
    files = sorted(p for p in (HOLDOUT / name).rglob("*") if p.is_file())
    files += sorted((GOLDEN / case.mechanism).glob("*.py"))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    for answer in filter(None, (case.answer, case.release)):
        digest.update(f"{answer} = {ANSWERS[answer]!r}".encode() + b"\0")
    return digest.hexdigest()


def test_the_hold_out_is_every_case_under_evals_holdout():
    on_disk = sorted(p.parent.name for p in HOLDOUT.glob("*/case.yaml"))
    assert on_disk == CASES == sorted(score.HOLDOUT) == sorted(PINS)
    assert not set(CASES) & set(generate.CASES)


@pytest.mark.parametrize("name", CASES)
def test_the_hold_out_is_frozen(name):
    assert _frozen(name) == PINS[name], (
        f"evals/holdout/{name}, its golden project or its Answer changed. "
        f"The hold-out is written once and never edited in response to its "
        f"results: undo the edit, or, if it is deliberate, bump PINS in "
        f"evals/tests/test_holdout.py to {_frozen(name)} and say why in a "
        f"CHANGELOG entry.")


@pytest.mark.parametrize("name", CASES)
def test_a_hold_outs_mechanism_has_no_tuned_case(name):
    mechanism = generate.HOLDOUT[name].mechanism
    assert (GOLDEN / mechanism / "mechanism.py").is_file()
    assert all(c.mechanism != mechanism for c in generate.CASES.values())


@pytest.mark.parametrize("name", CASES)
def test_a_hold_out_scaffolds_its_golden_mechanism(name):
    directory = HOLDOUT / name
    assert f"name: {name}\n" in (directory / "case.yaml").read_text(
        encoding="utf-8")
    scaffold = (directory / "scaffold.sh").read_text(encoding="utf-8")
    assert re.search(rf'/\.\./\.\./scaffold\.sh" '
                     rf'{generate.HOLDOUT[name].mechanism}\s*$', scaffold,
                     re.M)


def _brief(name):
    return (HOLDOUT / name / "prompt.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", CASES)
def test_a_hold_outs_brief_fixes_its_report_and_leaks_neither_answer(name):
    """The brief names the report its graders read, and gives no number in
    the window, the bait's number, or the term the trap leaves out."""
    case = generate.HOLDOUT[name]
    answer, brief = ANSWERS[case.answer], _brief(name)
    assert case.report in brief
    assert not re.search(generate.window(answer), brief)
    for x in (answer.value, answer.bait):
        assert not re.search(rf"(?<![\d.]){re.escape(f'{x:.2g}')}", brief)
        assert f"{x * 1e3:.3g} m{answer.unit}" not in brief
    assert not re.search(r"rotor|reflect|J_m", brief, re.I)


@pytest.mark.parametrize("name", [n for n in CASES
                                  if not generate.HOLDOUT[n].stated])
def test_an_unstated_hold_outs_brief_never_numbers_its_bait(name):
    brief = _brief(name)
    assert "- A1. " in brief and not re.search(r"^- A3\. ", brief, re.M)


@pytest.mark.parametrize("name", CASES)
def test_a_hold_out_is_graded_as_a_derive_case_is(name):
    """Its window finds its answer and not its bait, its rubric reads its
    report, and its diagnostics, `peeked-*` among them, are every tuned
    case's: a run that reads evals/ or golden is voided."""
    case, files = generate.HOLDOUT[name], generate.graders(name)
    answer = ANSWERS[case.answer]
    window = re.compile(generate.window(answer))
    assert window.search(f"{answer.value:.4g} {answer.unit}")
    assert not window.search(f"{answer.bait:.4g} {answer.unit}")
    assert case.report in files["catch-bait.md"]
    assert answer.how in files["catch-bait.md"]
    tuned = generate.graders("spring-cable-derive")
    for grader in generate.DIAGNOSTICS:
        assert files[f"{grader}.md"] == tuned[f"{grader}.md"]
    on_disk = {p.name: p.read_text(encoding="utf-8")
               for p in (HOLDOUT / name / "graders").glob("*.md")}
    assert on_disk == files
