"""
truth — Milestone 0: the **truth model**, an independent simulator model of
this mechanism, generated from params.py and sharing none of the derivation's
simplifying assumptions.

It exists because every other check in this model is a check of one model
against itself: a Jacobian against finite differences of the same length
function, an energy against the same mass matrix. A check of that shape cannot
see a wrong assumption, because the assumption sits on both sides. What it can
see is arithmetic — which is why derivations arrive with every printed number
reproducing and the physics wrong: a degree of freedom frozen that is actually
free, a textbook formula used outside its assumptions, a worst case evaluated
at the symmetric postures where the error is invisible.

So this package builds the mechanism a second time, in MuJoCo, from the same
parameter block — the same block, so the two models cannot drift apart when a
parameter changes — and every milestone checks its claims against it at
randomly sampled configurations.

The public surface is backend-neutral and small, so a second backend changes
nothing above it:

    build()                    the simulator model of this mechanism
    sample(n, seed)            configurations drawn from the envelope
    site_pose(...)             where the tool frame actually ends up
    site_jacobian(...)         the tool frame's Jacobian, MuJoCo's own

    sample_states(n, seed)     configurations, velocities and accelerations
    inverse_dynamics(...)      torques at a state and an acceleration

    settle(...)                static equilibrium under given loads
    linearise(...)             stiffness, mass, and mode frequencies there

The first six are here. The last two arrive with the milestones that need them
— settle with the statics claim, linearise with the modes — each in its own
submodule beside `chain.py`, keeping this surface the one place to read for
what the truth model can be asked.

Two builders cover the conventions a mechanism arrives in: `chain.py` for a
serial chain read off the DH or PoE table, and a floating-body builder for a
body on cables, legs or wheels. Check the package alone:
`python run_all.py truth`.
"""

# Run order and heading for `run_all.py`. Zero: the truth model is built before
# the first analytic claim, not after it, so that Milestone 1 has something to
# be checked against on the day it is written.
MILESTONE = (0, "Milestone 0: truth model")

from truth.chain import build, site_jacobian, site_pose   # noqa: E402,F401
from truth.envelope import sample, sample_states          # noqa: E402,F401
from truth.inverse import inverse_dynamics                # noqa: E402,F401
