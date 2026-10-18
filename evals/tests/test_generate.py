"""`generate.py`: each case's graders, generated from its golden `Answer`."""

import re
from decimal import Decimal

import pytest

import generate
from golden.answers import ANSWERS, CABLE_FREQUENCY, SKID_CLEARANCE, Answer


def found(answer, text):
    return re.search(generate.window(answer), text) is not None


@pytest.mark.parametrize("text", [
    "f = 7.118 Hz", "about 7.12 Hz", "7 Hz", "7.1176Hz", "7.25 Hz,",
    "7.117625 Hz", "(6.98 Hz)", "7.2 Hz"])
def test_the_window_finds_a_number_inside_it_with_its_unit(text):
    assert found(CABLE_FREQUENCY, text)


@pytest.mark.parametrize("text", [
    "6.9 Hz", "7.3 Hz", "17.1 Hz", "7.118 mm", "-7.1 Hz", "7.118",
    "inf Hz", "71.18 Hz", "0.7118 Hz", "7.1.2 Hz"])
def test_the_window_finds_nothing_outside_it(text):
    assert not found(CABLE_FREQUENCY, text)


def test_the_window_is_exact_on_every_three_decimal_number_near_it():
    low, high = CABLE_FREQUENCY.bounds
    for n in range(6500, 7700):
        x = Decimal(n) / 1000
        assert found(CABLE_FREQUENCY, f"{x} Hz") == (low <= x <= high), x


def test_a_negative_answer_needs_its_sign():
    assert SKID_CLEARANCE.value < 0
    assert found(SKID_CLEARANCE, f"{SKID_CLEARANCE.value:.2f} mm")
    assert found(SKID_CLEARANCE, f"−{-SKID_CLEARANCE.value:.1f} mm")
    assert not found(SKID_CLEARANCE, f"{-SKID_CLEARANCE.value:.2f} mm")
    assert not found(SKID_CLEARANCE, f"{SKID_CLEARANCE.bait:.2f} mm")


def test_the_checked_in_graders_are_what_generate_writes():
    """The freshness test: a change to a golden project's parameters, or to
    a case in CASES, fails here until `generate.py` is re-run."""
    assert generate.CASES
    assert generate.stale() == [], (
        "stale graders; run `uv run --project engine python "
        "evals/generate.py`")


@pytest.mark.parametrize("name", generate.CASES)
def test_each_brief_fixes_the_path_its_graders_read(name):
    case = generate.CASES[name]
    brief = (generate.EVALS / name / "prompt.md").read_text(encoding="utf-8")
    assert case.report in brief
    assert (generate.EVALS / name / "scaffold.sh").is_file()


def _family(kind):
    return [n for n, c in generate.CASES.items() if isinstance(c, kind)]


@pytest.mark.parametrize("name", _family(generate.Derive))
def test_each_catch_grader_reads_the_report_and_quotes_the_answer(name):
    case, files = generate.CASES[name], generate.graders(name)
    answer = ANSWERS[case.answer]
    assert {"catch-window.md", "catch-bait.md"} <= set(files)
    assert generate.window(answer) in files["catch-window.md"]
    rubric = files["catch-bait.md"]
    assert case.report in rubric and answer.how in rubric
    assert "PASS" in rubric and "FAIL" in rubric
    assert {"peeked-read.md", "peeked-grep.md", "peeked-glob.md",
            "peeked-bash.md"} <= set(files)


def test_there_are_red_team_cases():
    assert len(_family(generate.Review)) >= 2


@pytest.mark.parametrize("name", _family(generate.Review))
def test_a_red_team_case_is_caught_on_a_located_finding_with_its_number(name):
    """The catch: a BLOCKER or MAJOR finding naming the planted location
    with a recomputed number, and the window, both on the review."""
    case, files = generate.CASES[name], generate.graders(name)
    answer = ANSWERS[case.answer]
    assert {"catch-finding.md", "catch-window.md"} <= set(files)
    assert not any(f.startswith("catch-bait") for f in files)
    assert case.report in files["catch-window.md"]
    assert generate.window(answer) in files["catch-window.md"]
    rubric = files["catch-finding.md"]
    assert case.report in rubric and case.planted in rubric
    assert answer.how in rubric
    assert all(where in rubric for where in case.where)
    assert "BLOCKER or MAJOR" in rubric and "MINOR or QUESTION" in rubric
    assert (generate.EVALS / name / "planted" / case.planted).is_file()


@pytest.mark.parametrize("name", _family(generate.Review))
def test_a_red_team_cases_false_alarm_grader_is_a_diagnostic(name):
    """`false-alarm` is named outside `catch-*`, so score.py never gates on
    it, and it lists what the golden derivation shows correct."""
    case, files = generate.CASES[name], generate.graders(name)
    rubric = files["false-alarm.md"]
    assert "type: llm" in rubric and case.report in rubric
    assert all(sound in rubric for sound in case.sound)
    assert "peeked-read.md" in files and "red-team-dispatched.md" in files


def test_a_window_across_a_power_of_ten_reads_both_sides():
    answer = Answer(value=10.0, unit="°", how="", bait=0.0)
    assert all(found(answer, f"{x} °") for x in ("9.81", "10", "10.19"))
    assert not any(found(answer, f"{x}°") for x in ("9.7", "10.3", "1.0"))
