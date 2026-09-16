"""
truth/envelope_checks.py — self-tests for envelope.py.
"""

import numpy as np

from params import N, Q_LIMITS
from truth.envelope import DEFAULT_SEED, HIGH, LOW, inside, sample


def test_envelope_mirrors_the_parameter_block():
    """The sampler's bounds are the parameter block's, not a second copy."""
    assert len(Q_LIMITS) == N, \
        f"Q_LIMITS has {len(Q_LIMITS)} rows for {N} generalized coordinates"
    assert np.array_equal(LOW, [lo for lo, _ in Q_LIMITS])
    assert np.array_equal(HIGH, [hi for _, hi in Q_LIMITS])
    assert np.all(HIGH > LOW), f"empty envelope in Q_LIMITS: {Q_LIMITS}"
    print(f"  [PASS] envelope reads {N} coordinates from Q_LIMITS")


def test_samples_lie_inside_the_envelope(n=200):
    Q = sample(n, seed=1)
    assert Q.shape == (n, N), f"sample({n}) returned {Q.shape}"
    assert inside(Q), "a sampled configuration fell outside Q_LIMITS"
    print(f"  [PASS] {n} sampled configurations inside the envelope")


def test_sampling_is_reproducible_and_off_the_symmetry_planes(n=64):
    """The same seed repeats; a different one does not; and no sample sits on
    a coordinate's midpoint, which is where the named postures live."""
    assert np.array_equal(sample(n, seed=DEFAULT_SEED),
                          sample(n, seed=DEFAULT_SEED)), "seed not honoured"
    assert not np.array_equal(sample(n, seed=DEFAULT_SEED),
                              sample(n, seed=DEFAULT_SEED + 1)), \
        "two seeds gave the same sample"
    midpoint = (LOW + HIGH) / 2
    assert np.min(np.abs(sample(n) - midpoint)) > 1e-6, \
        "a sample landed on a coordinate's midpoint"
    print(f"  [PASS] sampling reproducible under seed {DEFAULT_SEED}")
