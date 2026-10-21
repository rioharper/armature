"""The verb matrix (ADR 0008), held to its rule.

Every cell ends as a known answer, C or I, naming the tests that check it;
covered elsewhere, naming a known-answer cell on the same code path; or not
applicable, with its reason. A cell checked only against the engine itself is
none of the three, so it cannot be written here. Every node id the matrix
names must be one pytest collects, so a test renamed or deleted fails here,
and every trap is shown failing beside the verb that catches it. A cell's
test that holds an answer's bait outside its window shows a trap, so a trap
names it.
"""

import ast
import functools
import subprocess
import sys
from pathlib import Path

import pytest

import armature
import golden
from golden.matrix import (FOOTNOTE, MATRIX, MECHANISMS, TRAPS, VERBS,
                           Covered, Known, NotApplicable)

ROOT = Path(__file__).resolve().parents[1]  # pytest's rootdir, engine/


def _named():
    """Every node id the matrix names, in its cells and its traps."""
    ids = {i for row in MATRIX.values() for cell in row.values()
           if isinstance(cell, Known) for i in cell.tests}
    return ids | {i for trap in TRAPS for i in trap.tests}


@pytest.fixture(scope="module")
def collected(request, seen):
    """Every node id pytest collects from the files the matrix names: this
    session's own where it collected those files whole, else a collection of
    its own."""
    files = sorted({i.split("::")[0] for i in _named()})
    whole = not any("::" in arg for arg in request.config.args)
    if whole and all(any(s.startswith(f + "::") for s in seen)
                     for f in files):
        return seen
    run = subprocess.run([sys.executable, "-m", "pytest", "--collect-only",
                          "-q", "-p", "no:cacheprovider", *files], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8",
                         timeout=300)
    assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-4000:]
    return frozenset(line.strip() for line in run.stdout.splitlines()
                     if "::" in line)


def test_every_cell_is_in_one_of_the_three_states():
    assert set(MATRIX) == set(MECHANISMS)
    assert set(golden.NAMES) <= set(MECHANISMS)
    for mechanism, row in MATRIX.items():
        assert list(row) == list(VERBS), mechanism
        for verb, cell in row.items():
            where = (mechanism, verb)
            assert isinstance(cell, (Known, Covered, NotApplicable)), where
            if isinstance(cell, Known):
                assert cell.code in ("C", "I"), where  # never S or P
                assert cell.tests, where
            elif isinstance(cell, Covered):
                assert cell.by != where and cell.why, where
            else:
                assert cell.why, where


def test_every_node_id_the_matrix_names_is_collected(collected):
    """A parametrised test may be named whole or by one of its cases."""
    whole = {i.split("[")[0] for i in collected}
    missing = sorted(i for i in _named()
                     if i not in collected and i not in whole)
    assert not missing, "not collected:\n" + "\n".join(missing)


def test_every_covered_cell_names_a_known_answer_cell():
    for mechanism, row in MATRIX.items():
        for verb, cell in row.items():
            if isinstance(cell, Covered):
                by_mechanism, by_verb = cell.by
                assert isinstance(MATRIX[by_mechanism][by_verb], Known), (
                    f"{mechanism} × {verb} is covered by {cell.by}, which is "
                    f"not a known answer")


def test_every_trap_is_shown_failing_beside_the_verb_that_catches_it():
    for trap in TRAPS:
        assert trap.tests, trap.trap
        cell = MATRIX[trap.mechanism][trap.verb]
        assert isinstance(cell, Known), trap.trap
        assert set(trap.tests) <= set(cell.tests), trap.trap


def _reads_a_bait(node_id):
    """Whether the test `node_id` names reads an answer's `.bait`."""
    path, name = node_id.split("[")[0].split("::")
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    test = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    return any(isinstance(n, ast.Attribute) and n.attr == "bait"
               for n in ast.walk(test))


def test_every_cell_test_that_shows_a_bait_failing_is_a_traps():
    """A test in a cell that holds an answer's bait against its window shows
    a trap failing, so a trap names it."""
    trapped = {i for trap in TRAPS for i in trap.tests}
    shown = sorted(i for row in MATRIX.values() for cell in row.values()
                   if isinstance(cell, Known) for i in cell.tests
                   if "::" in i and _reads_a_bait(i))
    assert shown
    assert not [i for i in shown if i not in trapped]


def test_every_golden_mechanism_has_a_trap():
    assert set(golden.NAMES) <= {trap.mechanism for trap in TRAPS}


def test_the_footnote_names_engine_verbs_outside_the_rows():
    for name, why in FOOTNOTE.items():
        assert why and name not in VERBS, name
        assert callable(functools.reduce(getattr, name.split("."), armature))
