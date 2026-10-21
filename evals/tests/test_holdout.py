"""The hold-out (#132): a case under `evals/holdout/` that nobody tunes
against. It is generated and scaffolded like every case, reported beside the
gate and never part of it, and frozen: what is its own, its case files, its
golden project and its `Answer`, hashes to a pinned value."""

import hashlib
import re
import subprocess

import pytest

import generate
import score
import golden
from golden.answers import ANSWERS

ROOT = generate.EVALS.parent
HELD = generate.EVALS / "holdout"
GOLDEN = ROOT / "engine" / "tests" / "golden"
CASES = sorted(generate.HOLDOUT)

# Bumped only deliberately, with a CHANGELOG entry saying what changed and
# why: the hold-out is written once, never edited in response to its results.
PINS = {
    "turret-derive":
        "4b9202787a73994ebcb8b07c87f84e67a9c6248d25c4302aba49af0b6180a9c8",
}


def _frozen(name):
    """The SHA-256 of what is `name`'s own: its brief, `case.yaml`, scaffold
    and `catch-*` graders, its golden project (its modules and its ledger)
    and the `Answer`s its graders quote, each file by its path under the
    repo and its text with LF line endings, so a Windows checkout and the
    WSL copy agree. The `peeked-*`
    and diagnostic graders every case shares are left out, so a fix to their
    wording reaches the hold-out without bumping its pin."""
    case = generate.HOLDOUT[name]
    files = [HELD / name / f for f in ("prompt.md", "case.yaml",
                                       "scaffold.sh")]
    files += sorted((HELD / name / "graders").glob("catch-*.md"))
    files += sorted((GOLDEN / case.mechanism).glob("*.py"))
    files += [GOLDEN / case.mechanism / "ledger.toml"]
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    for answer in filter(None, (case.answer, case.release)):
        digest.update(f"{answer} = {ANSWERS[answer]!r}".encode() + b"\0")
    return digest.hexdigest()


def test_the_hold_out_is_every_case_under_evals_holdout():
    on_disk = sorted(p.parent.name for p in HELD.glob("*/case.yaml"))
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
def test_a_hold_outs_pin_leaves_out_the_graders_every_case_shares(name):
    shared = {f"{g}.md" for g in generate.DIAGNOSTICS}
    on_disk = {p.name for p in (HELD / name / "graders").glob("*.md")}
    assert shared <= on_disk
    assert not any(f.startswith("catch-") for f in shared)


@pytest.mark.parametrize("name", CASES)
def test_a_hold_outs_mechanism_has_no_tuned_case(name):
    mechanism = generate.HOLDOUT[name].mechanism
    assert (GOLDEN / mechanism / "mechanism.py").is_file()
    assert all(c.mechanism != mechanism for c in generate.CASES.values())


@pytest.mark.parametrize("name", CASES)
def test_a_hold_out_scaffolds_its_golden_mechanism(name):
    directory = HELD / name
    assert f"name: {name}\n" in (directory / "case.yaml").read_text(
        encoding="utf-8")
    scaffold = (directory / "scaffold.sh").read_text(encoding="utf-8")
    assert re.search(rf'/\.\./\.\./scaffold\.sh" '
                     rf'{generate.HOLDOUT[name].mechanism}\s*$', scaffold,
                     re.M)


def _brief(name):
    return (HELD / name / "prompt.md").read_text(encoding="utf-8")


# What would hand a turret run its trap: the moment's cause, named.
LEAKS = (r"overturn|\btilt|\btip|off.axis|offset|centr|inertia|\bCOM\b"
         r"|cent(?:re|er) of mass|m g d")


@pytest.mark.parametrize("name", CASES)
def test_a_hold_outs_brief_fixes_its_report_and_leaks_neither_answer(name):
    """The brief names the report its graders read, and gives no number in
    the window, the bait's number, the weight's moment alone, or the
    words that name what the bait leaves out."""
    case = generate.HOLDOUT[name]
    answer, brief = ANSWERS[case.answer], _brief(name)
    p = getattr(golden, case.mechanism).PARAMS
    assert case.report in brief
    assert not re.search(generate.window(answer), brief)
    for x in (answer.value, p["m"] * p["g"] * p["d"]):
        assert not re.search(rf"(?<![\d.]){re.escape(f'{x:.2g}')}", brief)
    assert not re.search(
        rf"(?<![\d.]){re.escape(f'{answer.bait:.4g} {answer.unit}')}", brief)
    assert not re.search(LEAKS, brief, re.I)


@pytest.mark.parametrize("name", CASES)
def test_a_hold_outs_brief_states_the_bearings_ratings(name):
    rated = getattr(golden, generate.HOLDOUT[name].mechanism).params.BEARING
    brief = _brief(name)
    for value, unit in ((rated["axial"], "N"), (rated["moment"], "N m")):
        assert re.search(rf"(?<![\d.]){value:g}(?:\.0)? {unit} ", brief)


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
               for p in (HELD / name / "graders").glob("*.md")}
    assert on_disk == files


def _shipped():
    """Every file the agent can read in `copy.sh`'s copy: what git tracks,
    but engine/tests/ and PROGRESS.md, which the copy leaves out, and evals/,
    which the harness masks."""
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                            capture_output=True).stdout.decode()
    return [ROOT / f for f in listed.split("\0") if f and f != "PROGRESS.md"
            and not f.startswith(("engine/tests/", "evals/"))
            and (ROOT / f).is_file()]


@pytest.mark.parametrize("name", CASES)
def test_nothing_the_agent_reads_names_a_hold_outs_mechanism_or_answer(name):
    """The CHANGELOG and docs/adr/ ship with the plugin, so they may say a
    hold-out exists, and nothing more: not its case, its mechanism, its
    report, its Answer or a number inside its window."""
    case = generate.HOLDOUT[name]
    window = re.compile(generate.window(ANSWERS[case.answer]))
    words = (name, case.mechanism, case.report, case.answer)
    for path in _shipped():
        text = path.read_bytes().decode("utf-8", errors="ignore")
        assert not [w for w in words if w in text], path
        assert not window.search(text), path
