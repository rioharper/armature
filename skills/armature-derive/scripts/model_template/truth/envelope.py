"""
truth/envelope.py — the envelope, the intended workspace, and the seeded
sampler every check draws from.

One sampler, used by every milestone, so "over the envelope" means the same set
of configurations in the kinematics check, the dynamics check and the
worst-case search. Self-tests in envelope_checks.py.
"""

import numpy as np

from params import N, QD_LIMITS, QDD_LIMITS, Q_LIMITS, WORKSPACE

LOW = np.array([lo for lo, _ in Q_LIMITS], dtype=float)
HIGH = np.array([hi for _, hi in Q_LIMITS], dtype=float)
WORK_LOW = np.array([lo for lo, _ in WORKSPACE], dtype=float)
WORK_HIGH = np.array([hi for _, hi in WORKSPACE], dtype=float)
RATE = np.array(QD_LIMITS, dtype=float)
ACCEL = np.array(QDD_LIMITS, dtype=float)

# What a check draws when it is asked for "the envelope" and says nothing more.
# Small enough that a milestone's checks stay seconds, large enough that a
# posture off every symmetry plane is certain rather than likely.
DEFAULT_SAMPLES = 24
DEFAULT_SEED = 20260915


def sample(n=DEFAULT_SAMPLES, seed=DEFAULT_SEED, low=LOW, high=HIGH):
    """`n` configurations drawn uniformly from the envelope, reproducibly.

    Random, never named. The postures a derivation reaches for — home, fully
    outstretched, a workspace corner, q = 0 — are the mechanism's symmetry
    planes, and a symmetry plane is exactly where a wrong assumption is
    invisible: the moment that makes the platform tilt cancels there, the rank
    the structure matrix loses there is the rank it has everywhere. A check
    that only visits them reports a pass it did not earn.

    Seeded, so a reviewer re-running this file gets the configurations the note
    was written from. Print `n` and the seed beside any result this backs —
    a sampled claim whose sample size is not stated is not reproducible.

    Returns an (n, N) array of configurations inside `params.Q_LIMITS`, or
    inside whatever box `low` and `high` name.
    """
    rng = np.random.default_rng(seed)
    low, high = np.asarray(low, dtype=float), np.asarray(high, dtype=float)
    return low + (high - low) * rng.random((int(n), N))


def sample_workspace(n=DEFAULT_SAMPLES, seed=DEFAULT_SEED):
    """`n` configurations from `params.WORKSPACE`, the region the machine is
    required to work in.

    The envelope is what the joints can reach; the workspace is what the
    requirements ask for, and a singularity is allowed to sit in the gap. A
    claim the derivation makes *everywhere* — the Jacobian has full rank, the
    IK converges, a torque stays under a rating — is a claim about this set,
    not about the envelope, and asserting it over the envelope instead is how
    a bound gets quietly relaxed to whatever the joints happen to allow.
    """
    return sample(n, seed, WORK_LOW, WORK_HIGH)


def inside(configs, tol=0.0, low=LOW, high=HIGH):
    """Whether every row of `configs` lies within the envelope (or `low`/`high`)."""
    Q = np.atleast_2d(np.asarray(configs, dtype=float))
    return bool(np.all(Q >= np.asarray(low) - tol)
                and np.all(Q <= np.asarray(high) + tol))


def sample_states(n=DEFAULT_SAMPLES, seed=DEFAULT_SEED):
    """`n` full states: (configurations, velocities, accelerations).

    A dynamics claim checked at rest is a statics claim. The velocities and
    accelerations are drawn from the rate envelope in the parameter block,
    both signs, so the Coriolis and inertial terms a posture-only check never
    exercises are the ones a sampled state hits hardest.

    Returns three (n, N) arrays, from one generator so the seed reproduces the
    whole state and not just its posture.
    """
    rng = np.random.default_rng(seed)
    n = int(n)
    Q = LOW + (HIGH - LOW) * rng.random((n, N))
    QD = RATE * rng.uniform(-1.0, 1.0, (n, N))
    QDD = ACCEL * rng.uniform(-1.0, 1.0, (n, N))
    return Q, QD, QDD
