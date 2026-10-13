"""
params_checks.py — self-tests for the parameter block, 00_setup.md.

The block is data, so its checks are about the shape of that data rather than
about physics: that the load-case table has not lost a sign, that every row
names a direction set, and that every tolerance band is a parameter's and holds
its nominal. Each of those is a whole class of downstream result quietly sized
against the wrong thing. The workspace and the rate envelope are
held against the description's coordinates in mechanism_checks.py, which owns
the joint envelope they sit inside.

It carries no truth check and says why below: the block's constants are held
against the truth model where they are *used*, and there is nothing in a shape
for a simulator to be asked about.
"""

from params import BANDS, DRIVE, LOAD_CASES, PARAMS, PLANE_XY

# The parameter block is data. Every constant in it reaches the truth model
# through mechanism(p), which the engine validates when it compiles — a value
# defined and never read fails there, naming it, as does one read and never
# defined — and each is then checked where a milestone uses it; the load-case
# table is confirmed at the posture Milestone 3's search finds. What is left
# here is the *shape* of the data, and a shape has nothing a simulator can be
# asked about.
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


def test_every_band_is_a_parameter_and_holds_its_nominal():
    """A band names a parameter of the block and contains its nominal.

    A band on a name the description never reads widens nothing, and a band
    that excludes its nominal is a typo whose search never visits the design
    as drawn. The engine refuses both where a margin's space compiles the
    mechanism, at import; this check holds every band, searched or not, and
    runs where that import never happens (`run_all.py params`).
    """
    known = {**PARAMS, **DRIVE}
    unknown = sorted(set(BANDS) - set(known))
    assert not unknown, (f"bands {unknown} name no parameter of PARAMS or "
                         f"DRIVE; the parameters are {sorted(known)}")
    for name, (lo, hi) in BANDS.items():
        assert lo < hi, f"band {name!r} = ({lo}, {hi}) has its low above its high"
        assert lo <= known[name] <= hi, (
            f"band {name!r} = ({lo}, {hi}) leaves its nominal {known[name]} "
            f"outside; a band is a tolerance around the value the design uses")
    print(f"  [PASS] {len(BANDS)} tolerance band(s), each a parameter's and "
          f"holding its nominal: {sorted(BANDS)}")
