"""
truth/modes.py — linearising the truth model, and the modes that come out.

A mode frequency is the most quotable number a derivation produces and one of
the easiest to produce wrongly. The two ways it goes wrong are a matrix
diagonal read as a mode — an entry of K is a stiffness against one coordinate
moving alone, and a mode is an eigenvalue of (K, M), which is a different
number whenever M is not diagonal — and a closed form named for a mode the
mechanism does not have. Neither survives a linearisation of a model that was
never told what the modes were supposed to be.

Self-tests in modes_checks.py.
"""

from collections import namedtuple

import mujoco
import numpy as np
from scipy.linalg import eigh

# `eps` is carried out with the answer because a finite-difference stiffness is
# only as good as its step: too large and the nonlinearity leaks in, too small
# and round-off does, and a mode frequency quoted without it cannot be redone.
Linearised = namedtuple("Linearised", "mass stiffness frequencies eps")

EPS = 1e-6


def mass_matrix(model, data):
    """MuJoCo's M(q), dense.

    `mj_fullM` changed argument order in MuJoCo 3.3 — it takes `data` now,
    where it used to take `data.qM` — so both are accepted and the template
    runs on whatever `pip install mujoco` put on this machine.
    """
    dense = np.zeros((model.nv, model.nv))
    try:
        mujoco.mj_fullM(model, data, dense)
    except TypeError:
        mujoco.mj_fullM(model, dense, data.qM)
    return dense


def linearise(model, data, q0, eps=EPS):
    """Mass and stiffness about `q0`, and the mode frequencies they give.

    `stiffness` is the gradient of the generalised bias force at rest,
    K = ∂(qfrc_bias)/∂q at q̇ = 0, by central differences of the simulator —
    which is what a restoring force is. `mass` is MuJoCo's own M(q0). The
    frequencies solve K v = ω² M v, **signed**: a negative frequency is a
    divergent mode, the mechanism falling away from this configuration rather
    than oscillating about it, and a linearisation that reports it as a
    magnitude turns an instability into a number that looks fine.

    A constant held force shifts which configuration is an equilibrium; it does
    not change ∂/∂q, so it does not appear here.
    """
    nv = model.nv
    data.qvel[:] = 0.0
    data.qacc[:] = 0.0
    data.qfrc_applied[:] = 0.0

    data.qpos[:] = np.asarray(q0, dtype=float)
    mujoco.mj_forward(model, data)
    assert data.nefc == 0, (
        f"{data.nefc} constraint(s) active at q={np.round(q0, 4)}; a "
        f"linearisation on a joint limit is the limit's stiffness, not the "
        f"mechanism's")
    mass = mass_matrix(model, data)

    stiffness = np.zeros((nv, nv))
    for j in range(nv):
        step = np.zeros(nv)
        step[j] = eps
        bias = []
        for offset in (step, -step):
            data.qpos[:] = np.asarray(q0, dtype=float) + offset
            data.qvel[:] = 0.0
            mujoco.mj_forward(model, data)
            bias.append(np.array(data.qfrc_bias))
        stiffness[:, j] = (bias[0] - bias[1]) / (2 * eps)

    data.qpos[:] = np.asarray(q0, dtype=float)
    mujoco.mj_forward(model, data)
    lam = eigh(stiffness, mass, eigvals_only=True)
    freq = np.sign(lam) * np.sqrt(np.abs(lam)) / (2 * np.pi)
    return Linearised(mass, stiffness, freq, eps)
