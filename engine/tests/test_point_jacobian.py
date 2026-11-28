"""A body point's Jacobian (#204).

Answer: the site Jacobian of a site on the same body at the same point, on an
open chain and on a free body, whose dofs carry `tangent`'s turn.
Trap: a site fixed on a wheel, which rolls away from the contact point.
"""

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

import armature
from golden import arm_2r, cable_platform

SEED = 20261127


@pytest.mark.parametrize("golden, body", [(arm_2r, "fore"),
                                          (cable_platform, "platform")])
def test_a_body_point_is_its_sites_jacobian(golden, body):
    m = armature.compile(golden.mechanism, golden.PARAMS)
    if golden is arm_2r:
        states = armature.sample(m, 4, SEED)
    else:  # a floating body: turned and moving, so `tangent` matters
        rng = np.random.default_rng(SEED)
        states = [m.at(q={"hang": (rng.uniform(-0.1, 0.1, 3),
                                   Rotation.random(random_state=k).as_matrix())},
                       qd={d: rng.uniform(-1, 1) for d in m.dofs})
                  for k in range(4)]
    for s in states:
        site = s.jacobian(golden.TOOL)
        point = s.jacobian(body=body, point=s.pose(golden.TOOL).position)
        assert point.linear == pytest.approx(site.linear, abs=1e-12)
        assert point.angular == pytest.approx(site.angular, abs=1e-12)
        assert point.method == "mj_jac"


@pytest.mark.parametrize("kwargs", [{}, {"body": "fore"},
                                    {"site": "tip", "body": "fore",
                                     "point": (0, 0, 0)}])
def test_a_jacobian_takes_a_site_or_a_body_and_a_point(kwargs):
    s = armature.compile(arm_2r.mechanism, arm_2r.PARAMS).at()
    with pytest.raises(TypeError, match="a site, or a body and a point"):
        s.jacobian(**kwargs)
