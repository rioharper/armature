"""
truth/equilibrium_checks.py — self-tests for equilibrium.py.

Internal to the package: that settling reaches rest, reports when it does not,
and leaves nothing applied behind it. Whether a *derivation's* equilibrium
numbers survive it is the statics milestone's check, one package over.
"""

import mujoco
import numpy as np

from params import N
from truth.chain import TOOL_SITE, at, build
from truth.envelope import DEFAULT_SEED, sample
from truth.equilibrium import settle, site_wrench


def test_released_model_comes_to_rest(seed=DEFAULT_SEED):
    """Released under no held force, gravity wins and the model stops."""
    model, data = build()
    q0 = sample(1, seed)[0]
    out = settle(model, data, q0)
    assert out.stable, f"released at {np.round(q0, 4)} it never came to rest"
    assert out.pose.shape == (N,) and np.all(np.isfinite(out.pose))
    assert np.max(np.abs(out.pose - q0)) > 1e-3, \
        "released under gravity with nothing holding it, and it did not move"
    print(f"  [PASS] released model settles in {out.steps} steps")


def test_settle_leaves_nothing_applied(seed=DEFAULT_SEED):
    """A held force or a wrench is the caller's for one settle, not for good.

    A settle that leaves `qfrc_applied` set turns the next check's result into
    a silent function of the order the checks happened to run in.
    """
    model, data = build()
    settle(model, data, sample(1, seed)[0], hold=np.ones(N),
           wrench={"link1": [0, 0, 0, 0, 0, 1.0]})
    assert np.allclose(data.qfrc_applied, 0.0), "held force left applied"
    assert np.allclose(data.xfrc_applied, 0.0), "wrench left applied"
    print("  [PASS] settle leaves no force applied behind it")


def test_divergence_reports_false_rather_than_raising(seed=DEFAULT_SEED):
    """A settle that cannot converge says so; the caller decides what it means."""
    model, data = build()
    out = settle(model, data, sample(1, seed)[0], hold=np.full(N, 1e4),
                 damping=0.0, max_steps=50)
    assert out.stable is False, "a 50-step settle under 10 kN m reported stable"
    print("  [PASS] a settle that will not converge returns stable=False")


def test_a_site_force_reaches_the_joints_as_the_site_jacobian_says(
        seed=DEFAULT_SEED, tol=1e-9):
    """The site-to-body wrench conversion, through MuJoCo's own application path.

    A force f at a site reaches the joints as J_site^T f. `site_wrench` claims
    to deliver exactly that through `xfrc_applied`, which is a claim about
    *where MuJoCo applies a body wrench* — its centre of mass, not its frame
    origin, and the two differ by a moment that is silently wrong if you pick
    the wrong one.

    So the comparison runs the wrench through `mj_forward` and reads the
    acceleration MuJoCo actually produces, against the acceleration from the
    same generalised force applied directly. Recomputing the wrench's effect
    with a body Jacobian and the same lever would agree with itself whichever
    origin the lever was measured from, which is the shape of check this package
    exists to stop trusting.
    """
    model, data = build()
    q0 = sample(1, seed)[0]
    force = np.array([3.0, -7.0, 0.0])
    at(model, data, q0)

    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, TOOL_SITE)
    jacp, jacr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    mujoco.mj_jacSite(model, data, jacp, jacr, sid)
    wrench = site_wrench(model, data, TOOL_SITE, force)
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, *wrench)

    accels = {}
    for label, apply_to in (("wrench", "xfrc"), ("J_site^T f", "qfrc")):
        data.qpos[:], data.qvel[:] = q0, 0.0
        data.qfrc_applied[:] = 0.0
        data.xfrc_applied[:] = 0.0
        if apply_to == "xfrc":
            data.xfrc_applied[bid] = next(iter(wrench.values()))
        else:
            data.qfrc_applied[:] = jacp.T @ force
        mujoco.mj_forward(model, data)
        accels[label] = np.array(data.qacc)
    data.qfrc_applied[:] = 0.0
    data.xfrc_applied[:] = 0.0

    assert np.allclose(accels["wrench"], accels["J_site^T f"], atol=tol), (
        f"a {force} N force at the tool accelerates the model "
        f"{accels['wrench']} through site_wrench and "
        f"{accels['J_site^T f']} through J_site^T f; the wrench is being "
        f"applied about the wrong point")
    print(f"  [PASS] a site force and its body wrench move the truth model "
          f"identically at q = {np.round(q0, 4)}")
