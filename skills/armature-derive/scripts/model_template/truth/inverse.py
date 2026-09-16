"""
truth/inverse.py — the truth model's inverse dynamics, on one backend or two.

What the Lagrangian is checked against. MuJoCo computes the generalised forces
from its own body tree with its own recursive algorithm, having never seen T, V
or the equations that came out of them, so a term missing from the hand
derivation has nothing on this side to hide behind.

**Pinocchio is an optional second backend**, and only ever optional: it has no
Windows pip wheel and no unilateral constraints, so it can never be the model a
checkpoint depends on. Where it imports — a conda environment, WSL, a Linux
box — it builds the same chain from the same parameter block and runs its own
RNEA, and the Milestone 2 truth check runs against both and says which ran. A
third independent implementation is worth having free; it is not worth a conda
requirement. `scripts/env-probe.sh` reads it into the project's environment
record beside MuJoCo, and a machine whose record says `PINOCCHIO=absent` runs
this file on MuJoCo alone and prints the fallback rather than failing.

Self-tests in inverse_checks.py.
"""

import mujoco
import numpy as np

from params import COM_LOCAL, INERTIA, MASSES, N, GRAVITY_VEC

MUJOCO = "mujoco"
PINOCCHIO = "pinocchio"

# Built once and kept: the second backend's model is a pure function of the
# parameter block, and rebuilding it per call would dominate the check.
_SECOND = {}


def available():
    """The inverse-dynamics backends importable on this machine, in order.

    MuJoCo is always among them — it is a required dependency of the model, and
    a machine that cannot import it cannot pass a derivation checkpoint at all.
    """
    found = [MUJOCO]
    try:
        import pinocchio  # noqa: F401
    except Exception:
        return found
    return found + [PINOCCHIO]


def resolve(backend):
    """The backend that will actually run, which is MuJoCo when the asked-for
    one is not installed. A caller prints this rather than the name it asked
    for: "checked against Pinocchio" when Pinocchio never imported is the kind
    of claim a checkpoint exists to prevent."""
    return backend if backend in available() else MUJOCO


def pinocchio_chain():
    """The same serial chain, built for Pinocchio from the same parameter block.

    Same joint order, same placements, same inertias, same gravity vector, read
    through `truth.chain`'s own DH reduction — so the two backends differ in
    their algorithm and their code and in nothing else. Returns
    `(pinocchio.Model, pinocchio.Data)`.

    `truth.chain` is imported here rather than at module level, and that is a
    layout rule rather than a style choice: this module is a **query**, and a
    query takes the `(model, data)` pair *either* builder returns. A floating
    project deletes `chain.py`, and a module-level import of it would take
    `inverse_dynamics` down with it. Only this function needs the chain, and
    only a chain project calls it.
    """
    import pinocchio as pin

    from truth.chain import as_float, body_placement, joint_kind

    model = pin.Model()
    model.name = "truth-chain"
    parent = 0
    for i in range(N):
        pos, quat = body_placement(i)
        rot = np.zeros(9)
        mujoco.mju_quat2Mat(rot, np.asarray(quat, dtype=float))
        joint = pin.JointModelRZ() if joint_kind(i) == "hinge" else pin.JointModelPZ()
        parent = model.addJoint(parent, joint,
                                pin.SE3(rot.reshape(3, 3), np.asarray(pos)),
                                f"q{i + 1}")
        com = np.array([as_float(v) for v in COM_LOCAL[i]])
        tensor = np.array([[as_float(INERTIA[i][r, c]) for c in range(3)]
                           for r in range(3)])
        model.appendBodyToJoint(parent, pin.Inertia(as_float(MASSES[i]), com,
                                                    tensor), pin.SE3.Identity())
    model.gravity.linear = np.array([as_float(v) for v in GRAVITY_VEC])
    return model, model.createData()


def inverse_dynamics(model, data, q_vals, qd_vals, qdd_vals, backend=MUJOCO):
    """Generalised forces that produce `qdd_vals` at the state (q, qd) [N m].

    Same coordinate ordering as the parameter block whichever backend runs,
    because the joints were added in DH-row order and both engines keep them
    that way. `backend` falls back to MuJoCo when the one asked for is not
    installed — `resolve` says which will run, and the caller prints that.

    On MuJoCo, asserts that no constraint is active. With the joint ranges
    taken from `Q_LIMITS` a sampled configuration sits strictly inside them and
    MuJoCo adds nothing; a configuration *on* a limit would have the limit's
    force folded into the answer, and a comparison against an analytic tau that
    knows nothing about limits would then fail for the wrong reason. Pinocchio
    has no joint limits in its dynamics at all, which is one of the reasons it
    cannot be the mandatory model.
    """
    if resolve(backend) == PINOCCHIO:
        import pinocchio as pin
        if PINOCCHIO not in _SECOND:        # `setdefault` would rebuild it every call
            _SECOND[PINOCCHIO] = pinocchio_chain()
        pin_model, pin_data = _SECOND[PINOCCHIO]
        return np.array(pin.rnea(pin_model, pin_data,
                                 np.asarray(q_vals, dtype=float),
                                 np.asarray(qd_vals, dtype=float),
                                 np.asarray(qdd_vals, dtype=float)))

    data.qpos[:] = np.asarray(q_vals, dtype=float)
    data.qvel[:] = np.asarray(qd_vals, dtype=float)
    data.qacc[:] = np.asarray(qdd_vals, dtype=float)
    mujoco.mj_inverse(model, data)
    assert data.nefc == 0, (
        f"{data.nefc} constraint(s) active at q={np.round(q_vals, 4)} — a "
        f"configuration on a joint limit; sample strictly inside Q_LIMITS")
    return np.array(data.qfrc_inverse)
