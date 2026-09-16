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
    build_floating(spec)       the same, for a mechanism whose body floats
    sample(n, seed)            configurations drawn from the envelope
    site_pose(...)             where the tool frame actually ends up
    site_jacobian(...)         the tool frame's Jacobian, MuJoCo's own

    sample_states(n, seed)     configurations, velocities and accelerations
    inverse_dynamics(...)      torques at a state and an acceleration
    available()                which inverse-dynamics backends this machine has

    settle(...)                static equilibrium under held commands and loads
    cable_forces(...)          the tension each cable carries there

    linearise(...)             stiffness, mass, and mode frequencies there

    release(...)               an assumption let go: what moves, and how far

Two builders cover the conventions a mechanism arrives in, and which one a
project uses follows the topology the plan glossary settled, not a preference:
`chain.py` for a serial chain on a fixed base, read off the DH or PoE table,
and `floating.py` for a floating base plus joints — a platform on cables, a
legged or a wheeled body — where the body's own pose is six coordinates and
what holds it up is constraints. Both name their builder `build`; the template
ships both, so the floating one is surfaced under a second name below.

**A project is one or the other**: delete the builder this mechanism does not
use, its checks module, and its line below, and `truth.build` is the builder
that remains. Every query takes the `(model, data)` pair either one returns,
which is what keeps this one surface.

The exception, and it is worth knowing before the first milestone: `sample` and
`sample_states` are not queries. They read `Q_LIMITS` and the rate limits out of
the parameter block, one row per generalized coordinate, and a floating body's
pose is not a box in its seven `qpos` — three positions and a quaternion. A
floating project decides at Milestone 0 what its pose envelope is and samples
from that; the sampler here is the chain's.

**MuJoCo is the backend; Pinocchio is optional and only ever optional.** Where
it imports — conda, WSL, a Linux box — `inverse_dynamics(..., backend=...)`
builds the same chain from the same parameter block and runs its own RNEA, and
Milestone 2's truth check runs against both and prints which ran. Where it does
not, the call falls back to MuJoCo and says so. It has no Windows pip wheel and
no unilateral constraints, so it can never be the model a checkpoint depends on;
`scripts/env-probe.sh` reads it into the project's environment record beside
MuJoCo, and the `PINOCCHIO` line there is what says whether this machine has it.

Check the package alone: `python run_all.py truth`.
"""

# Run order and heading for `run_all.py`. Zero: the truth model is built before
# the first analytic claim, not after it, so that Milestone 1 has something to
# be checked against on the day it is written.
MILESTONE = (0, "Milestone 0: truth model")

from truth.chain import build, site_jacobian, site_pose   # noqa: E402,F401
from truth.envelope import sample, sample_states          # noqa: E402,F401
from truth.equilibrium import Settled, settle             # noqa: E402,F401
from truth.floating import build as build_floating        # noqa: E402,F401
from truth.floating import cable_forces                   # noqa: E402,F401
from truth.inverse import available, inverse_dynamics     # noqa: E402,F401
from truth.modes import Linearised, linearise             # noqa: E402,F401
from truth.release import Released, release               # noqa: E402,F401
