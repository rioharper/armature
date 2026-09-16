"""
truth/equilibrium.py — settling the truth model to rest.

Every equilibrium number a note prints — a holding torque, a resting pose, a
cable tension, a reaction at a foot — is a claim that the machine *stays there*.
The analytic version of that claim is an algebraic balance written in the
coordinates the derivation kept, and it is silent about the ones it froze: a
platform assumed level, a base assumed rigid, a gearbox assumed stiff. Settling
makes the claim in the coordinates the machine actually has, so a degree of
freedom that was frozen on paper and is free in the machine moves here and the
check fails. That is the whole point.

Self-tests in equilibrium_checks.py.
"""

from collections import namedtuple

import mujoco
import numpy as np

# `pose` is where it came to rest, `forces` the generalised constraint forces
# there (a joint limit pressed against, a tendon against its limit) — a cable
# modelled as a deadband spring is a passive force and is not among them, so a
# builder that has cables reads their tension its own way. `stable` is whether
# it came to rest at all, and `steps` how long it took — printed beside a
# result, so a settle that only just converged is visible rather than
# indistinguishable from one that converged at once.
Settled = namedtuple("Settled", "pose forces stable steps")

MAX_STEPS = 20000
REST_SPEED = 1e-6       # rad/s or m/s
REST_ACCEL = 1e-4       # rad/s^2 or m/s^2


def settle(model, data, q0, hold=None, wrench=None, damping=0.0,
           min_steps=0, max_steps=MAX_STEPS, rest=REST_SPEED,
           rest_accel=REST_ACCEL):
    """Release the model at `q0` under held commands and let it find rest.

    `hold` is the generalised force held constant throughout — the actuator
    command the derivation says holds this pose. `wrench` is an optional
    {body name: 6-vector} of world-frame force and torque applied at that
    body's frame origin: a payload, a wind load, a tether pull.

    Energy leaves by **quench**, not by damping: whenever the model turns back
    on itself (`q̇ · q̈ < 0`, so it has passed a minimum) its velocity is zeroed.
    That drains kinetic energy without putting a damping constant into the
    model, which would be a claim about the machine the parameter block never
    made — and which would then be in every dynamics check too. It also has no
    tuning: an overdamped mechanism relaxes at k/c and can take minutes of
    simulated time to reach rest, while quench converges in a few hundred steps
    whatever the stiffness. `damping` is there for a mechanism that needs it and
    defaults to none.

    `min_steps` is for the case where the start is *already* an equilibrium:
    release there under a `hold` that balances it exactly and the rest test
    passes on the first step, having proved nothing about whether it would
    stay. Holding for a few hundred steps is what turns "it is balanced here"
    into "it stays here" — and it is the difference between the two that a
    frozen degree of freedom shows up in.

    Returns `Settled(pose, forces, stable, steps)`. A settle that diverges or
    runs out of steps returns `stable=False` rather than raising: "it would not
    stay" is an answer the caller has to be able to assert on, not an error in
    the check that asked.
    """
    data.qpos[:] = np.asarray(q0, dtype=float)
    data.qvel[:] = 0.0
    data.qacc[:] = 0.0
    data.qfrc_applied[:] = 0.0
    data.xfrc_applied[:] = 0.0
    held = (np.zeros(model.nv) if hold is None
            else np.asarray(hold, dtype=float).flatten())
    for name, six in (wrench or {}).items():
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        assert bid >= 0, f"no body named {name!r} to apply a wrench to"
        data.xfrc_applied[bid] = np.asarray(six, dtype=float)

    stable, steps = False, max_steps
    for step in range(1, max_steps + 1):
        data.qfrc_applied[:] = held - damping * data.qvel
        mujoco.mj_step(model, data)
        if not (np.all(np.isfinite(data.qpos)) and np.all(np.isfinite(data.qvel))):
            steps = step
            break
        if float(data.qvel @ data.qacc) < 0.0:
            data.qvel[:] = 0.0
        if (step >= min_steps
                and np.max(np.abs(data.qvel)) < rest
                and np.max(np.abs(data.qacc)) < rest_accel):
            stable, steps = True, step
            break

    pose = np.array(data.qpos)
    forces = np.array(data.qfrc_constraint)
    data.qfrc_applied[:] = 0.0
    data.xfrc_applied[:] = 0.0
    return Settled(pose, forces, stable, steps)
