"""One scratch `MjData` per compiled model.

Answer: each query's record from a fresh compile, which shares no data with
anything, compared to the last bit. Trap: a scratch that carries into the next
query what the last one left behind (a settle's velocity and commands, a
wrench's applied forces), and a nested query that writes over the data the
query around it is still reading.
"""

import statistics
import timeit
from collections.abc import Mapping
from dataclasses import fields, is_dataclass

import mujoco
import numpy as np

import armature
from test_fixture_2r_arm import PARAMS as ARM_PARAMS
from test_fixture_2r_arm import arm
from test_fixture_five_bar import PARAMS as FIVE_BAR_PARAMS
from test_fixture_five_bar import five_bar

JACOBIAN_BOUND = 100e-6  # s per call, against about 35 µs measured
INVERSE_BOUND = 300e-6   # s per call, against about 100 µs measured, nearly
                         # all of it the NumPy of the least-squares solve. Both
                         # leave room for a slower or busier machine; an
                         # allocation per call costs more than either
REPEATS = 15
CALLS = 200


def _same(a, b):
    """`a` and `b` are the same record, to the last bit (NaN matches NaN)."""
    if is_dataclass(a):
        assert type(a) is type(b)
        for f in fields(a):
            _same(getattr(a, f.name), getattr(b, f.name))
    elif isinstance(a, Mapping):
        assert a.keys() == b.keys()
        for k in a:
            _same(a[k], b[k])
    elif isinstance(a, tuple):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            _same(x, y)
    else:
        np.testing.assert_array_equal(a, b)


def _per_call(query):
    """The median over `REPEATS` runs of `query`'s cost per call (s)."""
    return statistics.median(timeit.timeit(query, number=CALLS) / CALLS
                             for _ in range(REPEATS))


def test_inverse_and_jacobian_reuse_the_scratch():
    """A query that allocated its own `MjData` cost the allocation, about
    1 ms of a 1.2 ms `inverse` here; each now costs a fraction of one."""
    m = armature.compile(arm, ARM_PARAMS)
    s = m.at(q={"shoulder": 0.3, "elbow": -0.7}, qd={"shoulder": 0.1})
    load = {"tip": (0.0, -20.0, 0.0)}
    allocation = _per_call(lambda: mujoco.MjData(m.model))
    inverse = _per_call(lambda: s.inverse(loads=load))
    jacobian = _per_call(lambda: s.jacobian("tip"))
    for name, cost, bound in (("inverse", inverse, INVERSE_BOUND),
                              ("jacobian", jacobian, JACOBIAN_BOUND)):
        said = (f"{name}: {cost * 1e6:.1f} µs per call, against "
                f"{allocation * 1e6:.1f} µs to allocate")
        assert cost < bound, said
        assert cost < allocation / 2, said


ARM_Q = ({"shoulder": 0.3, "elbow": -0.7}, {"shoulder": -1.2, "elbow": 1.9})
ARM_QD = ({"shoulder": 0.1}, {"elbow": -0.4})
ARM_QUERIES = (  # (state, query) in the order run: the two states alternate
    (0, lambda s: s.inverse(qdd={"shoulder": 0.5},
                            loads={"tip": (0.0, -20.0, 0.0)})),
    (1, lambda s: s.settle({"shoulder_motor": 0.2})),
    (0, lambda s: s.jacobian("tip")),
    (1, lambda s: s.wrench("fore", qdd={"elbow": 1.0},
                           loads={"tip": (5.0, 0.0, 0.0)})),
    (0, lambda s: s.pose("tip")),
    (1, lambda s: s.inverse()),
    (0, lambda s: s.linearise()),
    (1, lambda s: s.jacobian("tip")),
)


def _fresh(mechanism, params, q, qd=None):
    """The state `q`, `qd` of a model compiled just now."""
    return armature.compile(mechanism, params).at(q=q, qd=qd)


def test_interleaved_queries_on_the_arm_match_fresh_compiles():
    m = armature.compile(arm, ARM_PARAMS)
    states = [m.at(q=q, qd=qd) for q, qd in zip(ARM_Q, ARM_QD)]
    for i, query in ARM_QUERIES:
        _same(query(states[i]), query(_fresh(arm, ARM_PARAMS, ARM_Q[i],
                                             ARM_QD[i])))


def test_a_nested_query_leaves_the_outer_one_its_data():
    """A query run while another holds the scratch, as when one query calls
    another, gets its own `MjData`; the outer query's data still reads its
    own state after it."""
    m = armature.compile(arm, ARM_PARAMS)
    states = [m.at(q=q, qd=qd) for q, qd in zip(ARM_Q, ARM_QD)]
    with states[0]._scratch() as outer:
        before = outer.qpos.copy(), outer.qvel.copy(), outer.site_xpos.copy()
        for i, query in ARM_QUERIES + tuple((1 - i, q) for i, q in
                                            ARM_QUERIES):
            _same(query(states[i]), query(_fresh(arm, ARM_PARAMS, ARM_Q[i],
                                                 ARM_QD[i])))
        np.testing.assert_array_equal(outer.qpos, before[0])
        np.testing.assert_array_equal(outer.qvel, before[1])
        np.testing.assert_array_equal(outer.site_xpos, before[2])
    _same(states[0].inverse(), _fresh(arm, ARM_PARAMS, ARM_Q[0],
                                      ARM_QD[0]).inverse())


FIVE_BAR_Q = ({"A": 0.3, "E": -0.2}, {"A": -0.25, "E": 0.35})
LOAD = {"C2": (3.0, -5.0, 0.0)}


def test_interleaved_queries_on_a_closed_chain_match_fresh_compiles():
    """`at()` closes the loops in the scratch too, so a state is made
    between two queries as well as queried."""
    m = armature.compile(five_bar, FIVE_BAR_PARAMS)

    def fresh(i):
        return _fresh(five_bar, FIVE_BAR_PARAMS, FIVE_BAR_Q[i])

    first = m.at(q=FIVE_BAR_Q[0])
    _same(first.inverse(loads=LOAD), fresh(0).inverse(loads=LOAD))
    states = [first, m.at(q=FIVE_BAR_Q[1])]
    _same(states[1].q, fresh(1).q)
    for i in (1, 0, 1, 0):
        _same(states[i].linearise(), fresh(i).linearise())
        _same(states[1 - i].pose("C2"), fresh(1 - i).pose("C2"))
        _same(states[i].inverse(loads=LOAD), fresh(i).inverse(loads=LOAD))
    hold = dict(states[0].inverse().torque)
    _same(states[0].settle(hold), fresh(0).settle(hold))
    _same(states[1].inverse(), fresh(1).inverse())
