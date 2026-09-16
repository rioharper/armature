"""
truth/equilibrium_checks.py — self-tests for equilibrium.py.

Internal to the package: that settling reaches rest, reports when it does not,
and leaves nothing applied behind it. Whether a *derivation's* equilibrium
numbers survive it is the statics milestone's check, one package over.
"""

import numpy as np

from params import N
from truth.chain import build
from truth.envelope import DEFAULT_SEED, sample
from truth.equilibrium import settle


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
