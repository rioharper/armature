"""
params_checks.py — self-tests for the parameter block, 00_setup.md.

The block is data, so its checks are about the shape of that data rather than
about physics: that the symbol table mirrors the numbers, that the envelope and
the intended workspace are the sets the rest of the model thinks they are, and
that the load-case table has not lost a sign. Each of those is a whole class of
downstream result quietly sized against the wrong thing.
"""

import numpy as np

from params import (LOAD_CASES, N, PARAMS, PARAM_SYMS, PLANE_XY, QDD_LIMITS,
                    QD_LIMITS, Q_LIMITS, WORKSPACE)
from truth.chain import build
from truth.envelope import DEFAULT_SEED, sample_workspace
from truth.equilibrium import settle


def test_symbols_mirror_the_numbers():
    """A symbol with no number substitutes to itself and lambdifies to a
    function of an extra argument; a number with no symbol is a constant no
    equation can reach. Either way the two representations have drifted."""
    assert set(PARAM_SYMS) == set(PARAMS), (
        f"PARAM_SYMS and PARAMS disagree: only in PARAM_SYMS "
        f"{sorted(set(PARAM_SYMS) - set(PARAMS))}, only in PARAMS "
        f"{sorted(set(PARAMS) - set(PARAM_SYMS))}")
    print(f"  [PASS] {len(PARAMS)} parameters carry both a number and a symbol")


def test_rate_envelope_is_one_row_per_coordinate():
    for name, rows in (("Q_LIMITS", Q_LIMITS), ("QD_LIMITS", QD_LIMITS),
                       ("QDD_LIMITS", QDD_LIMITS)):
        assert len(rows) == N, f"{name} has {len(rows)} rows for {N} coordinates"
    print(f"  [PASS] envelope and rate envelope are {N} rows each")


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


def test_truth_workspace_is_free_of_the_joint_limits(n=64, seed=DEFAULT_SEED):
    """The intended workspace, against the truth model's own joint ranges.

    `WORKSPACE` is a claim about the machine — *this is where it works* — and
    every later result leans on it: the singular-value bound, the IK's
    convergence set, the posture each worst case is found at. The truth model
    carries `Q_LIMITS` as its joint ranges, built from the same block, so it can
    say whether the region the requirements name is a region the machine holds
    freely or one whose edge is a hard stop pressed against.

    The difference is not cosmetic. On a limit MuJoCo adds a constraint force,
    and every truth check downstream then reads the limit's torque rather than
    the mechanism's — the Milestone 3 worst-case check would confirm a number
    the end-stop is carrying. Settling at each sampled pose under the truth
    model's own gravity torque and asserting no constraint is active is what
    says the set is clean.
    """
    model, data = build()
    for q0 in sample_workspace(n, seed):
        out = settle(model, data, q0, max_steps=1)
        assert np.max(np.abs(out.forces)) < 1e-9, (
            f"a joint limit carries {out.forces} at q={np.round(q0, 4)}, inside "
            f"WORKSPACE {WORKSPACE}; every truth check at that pose would read "
            f"the end-stop's force rather than the mechanism's")
    print(f"  [PASS] {n} sampled workspace poses sit clear of every joint limit "
          f"the truth model carries (seed {seed})")
