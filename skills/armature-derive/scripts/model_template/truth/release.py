"""
truth/release.py — releasing an assumption in the truth model.

A numbered assumption that *fixes a coordinate* — the platform stays level, the
base is rigid, the elbow is locked, the gearbox has no wind-up — is the one
class of error the rest of this package cannot reach on its own, because the
coordinate it fixes is absent from the derivation's equations and so absent
from both sides of every comparison made with them. The only way to size it is
to let the coordinate go in a model that has it, and look.

Releasing is the absence of a command, not the addition of one. The derivation
assumed the coordinate away, which means it named nothing that holds it there:
so the release settles the truth model with the analytic command held on every
*other* coordinate and **nothing at all** on the released one, and reports how
far it travels from the value the assumption fixed it at. A few microradians is
an assumption sized and kept; five degrees is the assumption that was wrong,
with the number that says so.

What it cannot do is release a compliance the parameter block never described.
A base assumed rigid is released by giving the block the base's stiffness and
the joint that carries it — the truth model can only free a coordinate it has.
An assumption in that position is the one the setup note owes a sentence for
instead, and the derive skill's Step 0 says what the sentence has to say.

Self-tests in release_checks.py.
"""

from collections import namedtuple

import mujoco
import numpy as np

from truth.equilibrium import settle

# `moved` is the answer: the displacement of each released coordinate from the
# value the assumption fixed it at, in that coordinate's own units. `rest` is
# where the whole model ended up, carried out so a caller can see what else
# went with it, and `stable` says whether it came to rest at all — an
# assumption whose release never settles is a worse finding than one that
# settles somewhere else.
Released = namedtuple("Released", "freed assumed rest moved stable steps")


def dof_index(model, name):
    """The velocity-coordinate index of a named joint, for indexing a hold."""
    jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
    assert jid >= 0, (
        f"no joint named {name!r} in the truth model; a coordinate the model "
        f"does not have cannot be released, and the assumption that fixes it "
        f"owes the setup note a sentence instead")
    return int(model.jnt_dofadr[jid])


def release(model, data, q0, freed, hold=None, **settle_kw):
    """Settle with `freed` carrying no command, and report what it does.

    `freed` is a joint name or a list of them. `hold` is the generalised force
    the derivation says holds this configuration — whatever the analytic model
    produced, over the coordinates it kept. The released coordinates are zeroed
    out of it before the settle, because that is what the assumption claims:
    that nothing needs to hold them.

    Returns `Released(freed, assumed, rest, moved, stable, steps)`, where
    `assumed` is the released coordinates' starting values and `moved` their
    signed displacement. Sign is kept: which way an assumption fails is half of
    what sizes the fix.
    """
    names = [freed] if isinstance(freed, str) else list(freed)
    dofs = [dof_index(model, name) for name in names]
    command = (np.zeros(model.nv) if hold is None
               else np.array(hold, dtype=float).flatten())
    command[dofs] = 0.0

    q0 = np.asarray(q0, dtype=float)
    out = settle(model, data, q0, hold=command, **settle_kw)
    assumed = q0[dofs]
    return Released(names, assumed, out.pose, out.pose[dofs] - assumed,
                    out.stable, out.steps)
