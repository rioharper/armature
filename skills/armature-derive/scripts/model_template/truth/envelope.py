"""
truth/envelope.py — the envelope, and the seeded sampler every check draws from.

One sampler, used by every milestone, so "over the envelope" means the same set
of configurations in the kinematics check, the dynamics check and the
worst-case search. Self-tests in envelope_checks.py.
"""

import numpy as np

from params import N, QD_LIMITS, QDD_LIMITS, Q_LIMITS

LOW = np.array([lo for lo, _ in Q_LIMITS], dtype=float)
HIGH = np.array([hi for _, hi in Q_LIMITS], dtype=float)
RATE = np.array(QD_LIMITS, dtype=float)
ACCEL = np.array(QDD_LIMITS, dtype=float)

# What a check draws when it is asked for "the envelope" and says nothing more.
# Small enough that a milestone's checks stay seconds, large enough that a
# posture off every symmetry plane is certain rather than likely.
DEFAULT_SAMPLES = 24
DEFAULT_SEED = 20260915


def sample(n=DEFAULT_SAMPLES, seed=DEFAULT_SEED):
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

    Returns an (n, N) array of configurations inside `params.Q_LIMITS`.
    """
    rng = np.random.default_rng(seed)
    return LOW + (HIGH - LOW) * rng.random((int(n), N))


def inside(configs, tol=0.0):
    """Whether every row of `configs` lies within the envelope."""
    Q = np.atleast_2d(np.asarray(configs, dtype=float))
    return bool(np.all(Q >= LOW - tol) and np.all(Q <= HIGH + tol))


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
