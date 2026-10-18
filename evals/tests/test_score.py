"""`score.py` on hand-made `--json` documents, shaped as `claude plugin eval`
writes them: `cases[].arms.with[].graders[].passed`."""

import json

import score


def run(*passed, error=None):
    """A run whose graders are `name` (passed) or `!name` (failed)."""
    return {"error": error, "graders": [
        {"name": g.lstrip("!"), "passed": not g.startswith("!")}
        for g in passed]}


CAUGHT = run("catch-window", "catch-bait", "!peeked-read", "skill-derive")
MISSED = run("catch-window", "!catch-bait", "!peeked-read", "skill-derive")
PEEKED = run("catch-window", "catch-bait", "peeked-bash", "skill-derive")


def doc(*cases, partial=False):
    return {"partial": partial, "cases": [
        {"name": name, "arms": arms} for name, arms in cases]}


def test_a_run_that_peeked_is_not_caught():
    [row] = score.score(doc(("c", {"with": [CAUGHT, PEEKED, CAUGHT]})))
    assert (row.caught, row.runs, row.peeked) == (2, 3, 1)


def test_a_run_with_one_catch_grader_failed_or_none_graded_is_not_caught():
    ungraded = run(error="ended on an API error")
    [row] = score.score(doc(("c", {"with": [CAUGHT, MISSED, ungraded]})))
    assert (row.caught, row.runs) == (1, 3)


def test_the_baseline_is_reported_beside_with_its_delta():
    [row] = score.score(doc(("c", {"with": [CAUGHT, CAUGHT, MISSED],
                                   "without": [MISSED, CAUGHT, MISSED]})))
    assert (row.base_caught, row.base_runs) == (1, 3)
    assert row.delta == 2 / 3 - 1 / 3


def test_a_single_arm_run_has_no_baseline_and_no_delta():
    [row] = score.score(doc(("c", {"with": [CAUGHT]})))
    assert (row.base_runs, row.delta) == (0, None)


def test_the_diagnostics_are_counted_and_never_part_of_the_catch():
    [row] = score.score(doc(("c", {"with": [CAUGHT, MISSED, PEEKED]})))
    assert row.diagnostics == {"skill-derive": 3}


def test_a_red_team_runs_false_alarm_is_counted_and_never_part_of_the_catch():
    """`false-alarm` passes when the review raised no BLOCKER or MAJOR that
    the golden derivation shows wrong; a run where it failed is a false
    alarm, counted beside the catch and never voiding it."""
    alarmed = run("catch-finding", "catch-window", "!false-alarm")
    quiet = run("catch-finding", "catch-window", "false-alarm")
    [row] = score.score(doc(("c", {"with": [alarmed, quiet, alarmed]})))
    assert (row.caught, row.false_alarms) == (3, 2)
    assert "false-alarm" not in row.diagnostics


def test_false_alarms_are_reported_and_never_gate(tmp_path, capsys):
    alarmed = run("catch-finding", "catch-window", "!false-alarm")
    code, out = _main(tmp_path, doc(("r", {"with": [alarmed] * 3})), capsys)
    assert code == 0
    assert "false alarms 3/3" in out


def test_a_derive_case_reports_no_false_alarm_count(tmp_path, capsys):
    _, out = _main(tmp_path, doc(("a", {"with": [CAUGHT] * 3})), capsys)
    assert "false alarm" not in out


def _main(tmp_path, document, capsys):
    path = tmp_path / "out.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    code = score.main([str(path)])
    return code, capsys.readouterr().out


def test_every_case_at_two_thirds_passes(tmp_path, capsys):
    code, out = _main(tmp_path, doc(
        ("a", {"with": [CAUGHT, CAUGHT, MISSED]}),
        ("b", {"with": [CAUGHT, CAUGHT, CAUGHT]})), capsys)
    assert code == 0
    assert "a" in out and "2/3" in out and "skill-derive 3/3" in out


def test_a_case_below_two_thirds_fails_the_suite(tmp_path, capsys):
    code, out = _main(tmp_path, doc(
        ("a", {"with": [CAUGHT, CAUGHT, CAUGHT]}),
        ("b", {"with": [CAUGHT, PEEKED, MISSED]})), capsys)
    assert code == 1
    assert "1/3" in out and "peeked 1" in out


def test_a_partial_result_fails_however_well_it_caught(tmp_path, capsys):
    code, out = _main(tmp_path, doc(("a", {"with": [CAUGHT] * 3}),
                                    partial=True), capsys)
    assert code == 1
    assert "partial" in out


def test_a_result_with_no_runs_fails(tmp_path, capsys):
    code, _ = _main(tmp_path, doc(("a", {"with": []})), capsys)
    assert code == 1
