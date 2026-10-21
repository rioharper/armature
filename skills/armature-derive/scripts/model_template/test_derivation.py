"""
The derivation's self-tests, exposed to pytest.

The checks themselves live one file over from the equations they check, in
each module's sibling checks module (`kinematics_checks.py`), so a red-team
pass on one milestone reads two small files rather than one large one. This
file only makes pytest run them: pytest collects `test_*.py`, and neither
`kinematics.py` nor `kinematics_checks.py` matches.

The ledger's check, `run_all.ledger_check`, runs first here as it does in
`run_all.py`. *Which* checks follow is `run_all.py`'s discovery, imported
rather than repeated. So `pytest` and `run_all.py` cannot disagree about
what the model's self-tests are, and a module added later is collected by
both without either file being edited. A margin a milestone declares is one
of those checks, `margin[<name>]`: searched, held to passing, and confirmed
in its truth model, the same check `run_all.py` runs.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_all  # noqa: E402  (needs the sys.path line above)

MILESTONES = run_all.discover_milestones()
LEDGER_CHECK = run_all.ledger_check()

CHECKS = ([pytest.param(LEDGER_CHECK, id="ledger")] if LEDGER_CHECK
          else []) + [
    pytest.param(check, id=f"{module.__name__}.{check.__name__}")
    for _title, module, checks in MILESTONES
    for check in checks
]


def test_discovery_found_the_milestone_modules():
    """
    The guard on everything below.

    An empty parametrize list is a green pytest run that checked nothing —
    the same silence this file exists to end, one level up. A failure here
    means discovery broke, not the model.
    """
    assert MILESTONES, (
        f"run_all.discover_milestones() found no milestone modules in "
        f"{Path(__file__).resolve().parent}")
    assert CHECKS, (
        f"milestone modules {[m.__name__ for _t, m, _c in MILESTONES]} "
        f"expose no test_* callables")


@pytest.mark.parametrize("check", CHECKS)
def test_milestone_self_test(check):
    """Run one self-test from one milestone module."""
    check()
