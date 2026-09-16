"""
truth/modes_checks.py — self-tests for modes.py.

Internal to the package: that the linearisation is of the right thing and that
its finite-difference step is not where the answer comes from. Whether the
*derivation's* modes survive it is Milestone 2's check, one package over.
"""

import numpy as np

from params import N
from truth.chain import build
from truth.envelope import DEFAULT_SEED, sample
from truth.modes import linearise


def test_linearised_mass_matches_inverse_dynamics(seed=DEFAULT_SEED, tol=1e-9):
    """The mass matrix is M(q), so a unit acceleration costs its column."""
    from truth.inverse import inverse_dynamics
    model, data = build()
    q0 = sample(1, seed)[0]
    lin = linearise(model, data, q0)
    assert np.allclose(lin.mass, lin.mass.T, atol=tol), "M not symmetric"
    gravity = inverse_dynamics(model, data, q0, np.zeros(N), np.zeros(N))
    for j in range(N):
        e = np.zeros(N)
        e[j] = 1.0
        tau = inverse_dynamics(model, data, q0, np.zeros(N), e)
        assert np.allclose(tau - gravity, lin.mass[:, j], atol=tol), \
            f"linearised mass column {j} disagrees with inverse dynamics"
    print("  [PASS] linearised mass matches the inverse dynamics")


def test_stiffness_is_insensitive_to_the_step(seed=DEFAULT_SEED, tol=1e-6):
    """Two steps a decade apart must give the same K.

    If they do not, the answer is coming from the step size rather than the
    mechanism, and every mode frequency downstream is a function of `eps`.
    """
    model, data = build()
    q0 = sample(1, seed)[0]
    coarse = linearise(model, data, q0, eps=1e-5)
    fine = linearise(model, data, q0, eps=1e-6)
    gap = float(np.max(np.abs(coarse.stiffness - fine.stiffness)))
    scale = max(float(np.max(np.abs(fine.stiffness))), 1e-12)
    assert gap / scale < tol, \
        f"K moved by {gap / scale:.2e} between eps=1e-5 and 1e-6"
    print(f"  [PASS] stiffness stable across a decade of step (rel {gap / scale:.1e})")


def test_a_divergent_mode_reads_negative():
    """The upright 2R arm is an inverted pendulum: it must not read as a mode.

    Reported as a magnitude, a falling configuration produces a perfectly
    plausible frequency — this is the failure the sign exists to prevent.
    """
    model, data = build()
    lin = linearise(model, data, np.array([np.pi / 2, 0.0]))
    assert np.min(lin.frequencies) < 0, \
        f"balanced upright, the frequencies read {lin.frequencies} — all stable"
    print(f"  [PASS] the upright arm's divergent mode reads "
          f"{np.min(lin.frequencies):.3f} Hz, signed")
