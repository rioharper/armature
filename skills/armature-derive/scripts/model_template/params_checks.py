"""
params_checks.py — self-tests for the parameter block, 00_setup.md.

The block is data, so its checks are about the shape of that data rather than
about physics: that the load-case table has not lost a sign, that every row
names a direction set, and that the block writes no number of its own. Each of
those is a whole class of downstream result quietly sized against the wrong
thing. The numbers themselves, their units and bands among them, are
`ledger check`'s, which `run_all.py` runs first. The workspace and the rate
envelope are held against the description's coordinates in
mechanism_checks.py, which owns the joint envelope they sit inside.

It carries no truth check and says why below: the block's constants are held
against the truth model where they are *used*, and there is nothing in a shape
for a simulator to be asked about.
"""

import ast
from pathlib import Path

import params
from params import LOAD_CASES, PLANE_XY

# The parameter block is data, the ledger's. Every mechanism entry reaches
# the truth model through mechanism(p), which the engine validates when it
# compiles — a value defined and never read fails there, naming it, as does
# one read and never defined — and each is then checked where a milestone
# uses it; the load-case table is confirmed at the posture Milestone 3's
# search finds. What is left here is the *shape* of the data, and a shape has
# nothing a simulator can be asked about.
#
# This is the argued exemption the truth gate takes, and it is written out
# rather than waved at because the red team challenges every one of them. If
# your parameter block grows a claim — a derived inertia, a reduction ratio
# computed from a tooth count — that claim belongs in a module with a truth
# check beside it, not behind this sentence.
TRUTH_EXEMPT = ("the parameter block is data; its constants reach the truth "
                "model through mechanism(p), which the engine validates when "
                "it compiles, and are checked against it where they are used")


def test_every_signed_load_case_appears_in_both_signs():
    """A signed class with one row is a case read in one sign.

    This is the check that would have caught the first project through this
    plugin: a 0.5 g vertical acceleration was written once, read as upward, and
    the downward reading — the one that binds the floor — was never sized. The
    fix is not care at the reading; it is that the sign lives in a table where
    its absence is a failing test.
    """
    signed = {}
    for case in LOAD_CASES:
        assert case.sign in (-1, 0, 1), \
            f"load case {case.name!r} has sign {case.sign}, not -1, 0 or +1"
        if case.sign:
            signed.setdefault(case.kind, set()).add(case.sign)
    one_sided = {kind: sorted(signs) for kind, signs in signed.items()
                 if signs != {-1, 1}}
    assert not one_sided, (
        f"signed load classes carrying one sign only: {one_sided}; every "
        f"signed case is sized in both, and the row that is missing is the "
        f"one nobody read")
    print(f"  [PASS] {len(signed)} signed load class(es), both signs present, "
          f"over {len(LOAD_CASES)} rows")


def test_every_load_case_names_a_direction_set():
    """A magnitude with no direction set is a load nobody has to answer over."""
    for case in LOAD_CASES:
        assert case.magnitude >= 0.0, (
            f"load case {case.name!r} carries a negative magnitude; sign is a "
            f"column of its own")
        if case.direction == PLANE_XY:
            continue
        assert len(case.direction) == 3, \
            f"load case {case.name!r} direction {case.direction} is not a " \
            f"3-vector or {PLANE_XY!r}"
    print(f"  [PASS] {len(LOAD_CASES)} load cases each name a direction set")


def numeric_literals(source):
    """Each number written into `source` other than 0 and 1 (and so −1), as
    (line, value): a number that belongs in the ledger. A sign, an index, a
    count of rows is structure, and these three cover them."""
    return sorted((node.lineno, node.value)
                  for node in ast.walk(ast.parse(source))
                  if isinstance(node, ast.Constant)
                  and isinstance(node.value, (int, float, complex))
                  and not isinstance(node.value, bool)
                  and node.value not in (0, 1))


def test_the_parameter_block_writes_no_number():
    """Every number params.py uses is a ledger entry's (ADR 0010), so it is
    written once, with its unit, band and source, and `ledger check` holds
    it. A literal here is a number nobody checks, and a copy of the ledger's
    the moment it agrees with one. Its teeth first: a literal is found and
    a sign is not."""
    assert numeric_literals("x = (0, 1.0, -1, +1)\ny = -0.5\n") == [(2, 0.5)]
    source = Path(params.__file__).read_text(encoding="utf-8")
    found = numeric_literals(source)
    assert not found, (
        f"params.py writes numbers {found} (line, value); each belongs in "
        f"ledger.toml as an entry, read here by its name")
    print("  [PASS] params.py writes no number but 0 and +-1; the rest are "
          "ledger.toml's")
