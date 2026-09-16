"""
truth/envelope.py — the envelope, and the seeded sampler every check draws from.

One sampler, used by every milestone, so "over the envelope" means the same set
of configurations in the kinematics check, the dynamics check and the
worst-case search. Self-tests in envelope_checks.py.
"""

import numpy as np

from params import N, Q_LIMITS

LOW = np.array([lo for lo, _ in Q_LIMITS], dtype=float)
HIGH = np.array([hi for _, hi in Q_LIMITS], dtype=float)

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
