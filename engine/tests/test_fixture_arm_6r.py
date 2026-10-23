"""Fixture: a spatial 6R arm, UR-shaped, and a spatial 4R, for `equations`
at size (ADR 0012).

Not a golden mechanism: it is a row of the `equations` verb alone. The
template's Lagrangian timed out on the 6R and failed its Christoffel assert on
the 4R after ~290 s; the engine forms both without simplifying.

Answer: MuJoCo's `mj_fullM` and `qfrc_bias`, through `State.inverse`, at 20
sampled states. Each link's inertia is a full tensor, so no product of
inertia is zero by accident. The build time is printed and not asserted.
"""

import math
import time

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

import armature
from armature import body, joint, site
from mujoco_equations import assert_agree, sampled

SEED = 20261023
# Each joint's axis and where it sits at home; link i runs from joint i to
# joint i + 1, the last to the tool.
UR = (((0, 0, 1), (0, 0, 0)), ((0, 1, 0), (0, 0.09, 0.09)),
      ((0, 1, 0), (0.42, 0.09, 0.09)), ((0, 1, 0), (0.81, 0, 0.09)),
      ((0, 0, 1), (0.81, 0.11, 0.09)), ((0, 1, 0), (0.81, 0.11, -0.01)))
TOOL_AT = (0.81, 0.19, -0.01)
SPATIAL_4R = (((0, 0, 1), (0, 0, 0)), ((0, 1, 0), (0, 0, 0.1)),
              ((1, 0, 0), (0.3, 0, 0.1)), ((0, 1, 0), (0.55, 0.05, 0.1)))
TOOL_4R = (0.7, 0.05, 0.05)


def params(joints, tool):
    """Each link's mass, its COM a third of the way along it, and a full
    inertia tensor about the COM, from the seed: a box's principal moments,
    turned by a random rotation."""
    rng = np.random.default_rng(SEED)
    out = {}
    ends = [point for _, point in joints[1:]] + [tool]
    for i, ((_, start), end) in enumerate(zip(joints, ends)):
        mass, (a, b, c) = rng.uniform(1.0, 4.0), rng.uniform(0.05, 0.4, 3)
        turn = Rotation.random(random_state=rng).as_matrix()
        principal = mass / 12 * np.diag([b * b + c * c, a * a + c * c,
                                         a * a + b * b])
        out[f"m{i}"] = float(mass)
        out[f"c{i}"] = np.asarray(start) + (np.asarray(end)
                                            - np.asarray(start)) / 3
        out[f"I{i}"] = turn @ principal @ turn.T
    return out


def chain(joints, tool):
    def mechanism(p):
        out = []
        for i, (axis, point) in enumerate(joints):
            out += [body(f"link{i}", mass=p[f"m{i}"], com=p[f"c{i}"],
                         inertia=p[f"I{i}"]),
                    joint(f"q{i}", "hinge", parent="world" if i == 0
                          else f"link{i - 1}", child=f"link{i}", axis=axis,
                          point=point, range=(-math.pi, math.pi))]
        return out + [site("tool", body=f"link{len(joints) - 1}", pos=tool)]
    return mechanism


@pytest.mark.parametrize("joints, tool", [(UR, TOOL_AT), (SPATIAL_4R, TOOL_4R)],
                         ids=["6R", "4R"])
def test_the_equations_are_mujocos_at_size(joints, tool):
    mechanism, p = chain(joints, tool), params(joints, tool)
    start = time.perf_counter()
    e = armature.equations(mechanism, p)
    print(f"\n  {len(joints)}R: equations formed in "
          f"{time.perf_counter() - start:.1f} s")
    assert e.coordinates == tuple(f"q{i}" for i in range(len(joints)))
    m = armature.compile(mechanism, p)
    assert_agree(e, sampled(m, 20, SEED), tol=1e-10)
