"""
layout_checks.py — the gates layout.py defines, as checks: the code-line
budget, every checks module paired, the truth gate on checks modules and on
margins, and the gate's teeth against fixtures it builds. `run_all.py` runs
them as layout.py's, and `python layout.py` prints the gate table and runs
them. Standard library only, as layout.py is.
"""

import tempfile
from pathlib import Path

from layout import (BUDGET, DESCRIPTION, EXEMPT, HERE, TRUTH_PREFIX,
                    is_review_checks, model_files, size_table,
                    unchecked_claims, unconfirmed_margins)
from layout import TRUTH_EXEMPT as TRUTH_GATE

# The gates read source files and nothing else, so there is no claim about the
# machine here for a truth model to be asked about; their teeth are the
# fixtures test_the_truth_gate_has_teeth builds and sees fail.
TRUTH_EXEMPT = ("the gates read source files, not the machine; their teeth "
                "are the fixtures the last check builds and sees fail")


def test_modules_within_budget():
    over = [f"{row.where} ({row.lines} code lines)" for row in size_table()
            if row.lines > BUDGET and row.exempt is None]
    assert not over, (
        f"over the {BUDGET}-code-line budget: {', '.join(over)}; split along "
        f"the note's sections, or declare {EXEMPT} with the reason it cannot")
    print(f"  [PASS] every module within {BUDGET} code lines or exempt with a reason")


def test_checks_modules_are_paired():
    """A checks module whose module was renamed away — or is a report
    renderer, which discovery never collects — never runs; say so. A
    review's checks file pairs with nothing, and runs on its own."""
    orphans = []
    for path in model_files():
        if path.stem.endswith("_checks") and not is_review_checks(path):
            stem = path.stem[:-len("_checks")]
            if (stem == "report" or stem.startswith("report_")
                    or not path.with_name(stem + ".py").is_file()):
                orphans.append(path.relative_to(HERE).as_posix())
    assert not orphans, f"checks modules no discovered module pairs with: {orphans}"
    print("  [PASS] every checks module pairs with a module")


def test_milestone_checks_carry_a_truth_check():
    """
    Every checks module beside a mechanism description defines a
    `test_truth_*`, or says why it does not.

    A milestone's self-consistency checks are blind to the assumption sitting
    on both sides of them, so a milestone whose only evidence is
    self-consistency has shown its equations consistent and nothing about this
    machine. This gate is what stops the truth model being skipped in silence,
    which is the only way it ever gets skipped.
    """
    rows = size_table()
    if all(row.truth_checks is None for row in rows):
        print("  [PASS] no mechanism description here; the truth gate is n/a")
        return
    missing = unchecked_claims(rows)
    assert not missing, (
        f"checks modules with no {TRUTH_PREFIX}* check: {', '.join(missing)}; "
        f"add one, or declare {TRUTH_GATE} with the reason this module's "
        f"claims need none")
    found = sum(len(row.truth_checks or []) for row in rows)
    excused = [row.where for row in rows
               if row.truth_checks == [] and row.truth_exempt]
    print(f"  [PASS] {found} truth check(s) across the gated checks modules"
          + (f"; exempt with a reason: {', '.join(excused)}" if excused else ""))


def test_every_margin_carries_a_check():
    """
    Every margin declared beside a mechanism description passes `check=` and
    `agree=`, or its module says why its claims need none.

    A margin is evaluated twice, the truth model on one side and, usually,
    the derivation on the other, and the worst point the search found is the
    one place a wrong equation costs the most. `run_all.py` holds the two
    together there, within the margin's `agree`; this gate is what stops a
    margin being declared without its second evaluation in silence. Which
    side the truth model is on, the source cannot say: the review asks.
    """
    rows = size_table()
    if all(row.bare is None for row in rows):
        print("  [PASS] no mechanism description here; the margin gate is n/a")
        return
    missing = unconfirmed_margins(rows)
    assert not missing, (
        f"margins without check= and agree=: {', '.join(missing)}; pass both, "
        f"or declare {TRUTH_GATE} in the module with the reason its claims "
        f"need none")
    excused = [f"{row.where}: {name}" for row in rows if row.truth_exempt
               for name in row.bare or []]
    drive = [f"{row.where}: {name}" for row in rows for name in row.drive]
    print("  [PASS] every margin carries a check and agree="
          + (f"; the drive margins' is the resolution check: "
             f"{', '.join(drive)}" if drive else "")
          + (f"; exempt with a reason: {', '.join(excused)}" if excused else ""))


def test_the_truth_gate_has_teeth():
    """
    The gate against fixtures: it fails a bare checks module and a margin with
    no check or no agree, passes an argued exemption for each, refuses an unargued one,
    and stands down with no mechanism description.

    Built in a temporary directory rather than asserted against this one,
    because a gate is only evidence once it has been seen to fail, and this
    directory is meant never to make it fail.
    """
    bare = "def test_something():\n    pass\n"
    argued = 'TRUTH_EXEMPT = "alpha fixes a naming convention, not a claim"\n'
    margin = "A = armature.Margin('a', f, 'N', S{})\nB = 1\n"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        checks = root / "alpha_checks.py"
        module = root / "alpha.py"
        module.write_text(margin.format(""), encoding="utf-8")
        checks.write_text(bare, encoding="utf-8")
        assert all(row.truth_checks is None and row.bare is None
                   for row in size_table(root)) \
            and not unchecked_claims(size_table(root)), \
            "the truth gate fired in a directory with no mechanism description"

        (root / DESCRIPTION).write_text("def mechanism(p):\n    return []\n",
                                        encoding="utf-8")
        assert unchecked_claims(size_table(root)) == ["alpha_checks.py"], \
            "a checks module with no truth check and no exemption passed"
        for unchecked in ("", ", check=None", ", None, None", ", check=t",
                          ", t", ", check=t, agree=None", ", agree=1e-9"):
            module.write_text(margin.format(unchecked), encoding="utf-8")
            assert unconfirmed_margins(size_table(root)) == ["alpha.py: A"], \
                f"a margin declared with {unchecked or 'no check'} passed"
        for confirmed in (", check=t, agree=1e-9", ", t, 1e-9",
                          ", t, agree=1e-9"):
            module.write_text(margin.format(confirmed), encoding="utf-8")
            assert not unconfirmed_margins(size_table(root)), \
                f"a margin declared with {confirmed} did not clear the gate"
        module.write_text(argued + margin.format(""), encoding="utf-8")
        assert not unconfirmed_margins(size_table(root)), \
            "an argued TRUTH_EXEMPT did not clear a margin"
        for imported in ("from armature.drive import margins\nD = margins(",
                         "from armature.drive import margins as m\nD = m(",
                         "from armature import drive\nD = drive.margins(",
                         "import armature\nD = armature.drive.margins("):
            module.write_text(imported + "drive, missions)\n", encoding="utf-8")
            assert not unconfirmed_margins(size_table(root)) and [
                row.drive for row in size_table(root)
                if row.where == "alpha.py"] == [["D"]], \
                f"armature.drive's margins, {imported.splitlines()[0]!r}, " \
                f"were not read as carrying their resolution check"
        for lookalike in ("def margins(*a):\n    return ()\nD = margins(",
                          "import helpers\nD = helpers.margins(",
                          "D = armature.drive.margins("):
            module.write_text(lookalike + "drive, missions)\n", encoding="utf-8")
            assert unconfirmed_margins(size_table(root)) == ["alpha.py: D"], \
                f"a look-alike margins(), {lookalike.splitlines()[0]!r}, " \
                f"cleared the gate as armature.drive's"

        checks.write_text(argued + bare, encoding="utf-8")
        assert not unchecked_claims(size_table(root)), \
            "an argued TRUTH_EXEMPT did not clear the gate"

        checks.write_text(f"{TRUTH_PREFIX}settle = None\n"
                          f"def {TRUTH_PREFIX}settle_():\n    pass\n",
                          encoding="utf-8")
        assert [row.truth_checks for row in size_table(root) if row.where ==
                "alpha_checks.py"] == [[f"{TRUTH_PREFIX}settle_"]], \
            "the gate counted a name that is not a callable"

        for unargued in ("TRUTH_EXEMPT = True\n", 'TRUTH_EXEMPT = ""\n'):
            checks.write_text(unargued + bare, encoding="utf-8")
            try:
                size_table(root)
            except ValueError:
                continue
            raise AssertionError(f"{unargued.strip()} passed as a reason")
    print("  [PASS] the truth gate fails a bare checks module and a margin with "
          "no check or no agree, passes an argued exemption, and is n/a with no mechanism "
          "description")
