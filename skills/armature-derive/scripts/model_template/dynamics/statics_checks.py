"""
dynamics/statics_checks.py — self-tests for statics.py, 02_dynamics.md §3.
"""

import numpy as np
import sympy as sp

import armature
from armature.sampler import DEFAULT_SEED

from dynamics.statics import static_torques
from mechanism import commands, named, numeric, truth, vector, view

HOLD_STEPS = 500

# The assumption the moment-arm closed form rests on, named once and quoted by
# both checks below. A closed form is a theorem about a class of mechanism, and
# the only question that matters about one in a derivation is whether *this*
# mechanism is in that class — so the assumption is written down, and the
# failure message hands it to whoever reads the red bar.
MOMENT_ARM_ASSUMES = (
    "an open chain of hinges, so each joint carries the weight of every body "
    "outboard of it and nothing else does; a loop, a contact or a cable that "
    "shares the load, or a slide, leaves the class")


def _outboard(description, joint):
    """The bodies a joint carries: its child and everything jointed below."""
    below = {}
    for j in description.joints:
        below.setdefault(j.parent, []).append(j.child)
    child = {j.name: j.child for j in description.joints}[joint]
    carried, stack = [], [child]
    while stack:
        carried.append(stack.pop())
        stack += below.get(carried[-1], [])
    return carried


def moment_arm_form():
    """Holding torque by lever arms, the closed form 02_dynamics.md §3 cites.

    Each joint carries every weight outboard of it times that weight's lever
    arm about the joint's axis: tau_j = -a_j . sum_b (c_b - p_j) x m_b g, with
    a_j and p_j the joint's axis and a point on it, and c_b each outboard
    body's COM, all read off the description's symbolic view. Replace it with
    the closed form your note cites, and MOMENT_ARM_ASSUMES with the class of
    mechanism yours is a theorem about.
    """
    v = view()
    rows = []
    for name in v.q:
        moment = sum((v.com[b].pos_from(v.anchors[name]).cross(
            v.mass[b] * v.gravity) for b in _outboard(v.description, name)),
            0 * v.world.x)
        rows.append(-v.axes[name].dot(moment))
    return sp.Matrix(rows)


_moment_arm_num = numeric(moment_arm_form())


def moment_arm_torques(q_vals):
    """`moment_arm_form` at `q_vals` [N m], one per coordinate."""
    return np.asarray(_moment_arm_num(*q_vals), dtype=float).flatten()


def test_truth_moment_arm_form(n=24, seed=DEFAULT_SEED, tol=1e-9):
    """The closed form against the truth model, before the note cites it.

    A formula out of a book is the cheapest wrong number a derivation can
    produce: the arithmetic is somebody else's and it reproduces, the units are
    right, and the only thing that can be wrong is whether this mechanism is in
    the class the formula is a theorem about — a bifilar yaw stiffness on
    converging rather than parallel cables, a taut-cable pendulum mode on a
    cable that goes slack, a small-angle form past its range. So the form is
    checked against the truth model's gravity torque, `s.inverse()` at rest,
    at sampled configurations rather than at the tidy posture where the cosines
    are all one, and the assumption it rests on is named in the failure.
    """
    samples = armature.sample(truth(), n, seed)
    worst, worst_at = 0.0, None
    for s in samples:
        qv = vector(s.q)
        held = vector(s.inverse().generalised)
        gap = float(np.max(np.abs(moment_arm_torques(qv) - held)))
        if gap > worst:
            worst, worst_at = gap, qv
        assert gap < tol, (
            f"the moment-arm form reads {moment_arm_torques(qv)} N m where the "
            f"truth model reads {held} N m at q={np.round(qv, 4)}. The form "
            f"assumes {MOMENT_ARM_ASSUMES}")
    print(f"  [PASS] the moment-arm closed form matches the truth model over "
          f"{samples}")
    print(f"         worst |dtau| {worst:.2e} N m at q = {np.round(worst_at, 4)}; "
          f"the form assumes {MOMENT_ARM_ASSUMES.split(',')[0]}")


def test_static_torques_match_moment_arms(n=24, seed=DEFAULT_SEED, tol=1e-9):
    """Self-consistency: g(q) from the Lagrangian against the same closed form.

    Worth having for the arithmetic slip it catches the moment it lands, and
    not evidence of anything else — both sides are this project's own reading
    of the same frames. The check above is what says the closed form describes
    this machine.
    """
    for s in armature.sample(truth(), n, seed):
        qv = vector(s.q)
        tau = static_torques(qv)
        assert np.allclose(tau, moment_arm_torques(qv), atol=tol), \
            f"g({np.round(qv, 4)}) = {tau} disagrees with the moment-arm " \
            f"calculation {moment_arm_torques(qv)}"
    print(f"  [PASS] static torques match the moment-arm calculation over {n} "
          f"sampled postures (seed {seed})")


def test_truth_held_posture_stays(n=8, seed=DEFAULT_SEED, tol=1e-4):
    """The mandatory equilibrium truth check: hold g(q) and see whether the
    machine actually stays there, `s.settle(hold)`.

    `g(q)` is an algebraic balance written in the coordinates this derivation
    kept. It is silent about every coordinate the derivation froze, so on paper
    it balances whatever the machine would really do. Here the torque is held
    on the actuators and the truth model is left to move in all the coordinates
    it has, for at least `HOLD_STEPS` steps — long enough that "balanced at
    this instant" has to become "still there", which is where a frozen degree
    of freedom shows up.

    For this 2R arm every coordinate is modelled and the check is a formality;
    it earns its place on the mechanism where it is not — a platform assumed
    level, a base assumed rigid — and it is written the same way here so the
    pattern is inherited rather than invented under pressure.
    """
    samples = armature.sample(truth(), n, seed)
    worst, worst_at = 0.0, None
    for s in samples:
        q0 = vector(s.q)
        out = s.settle(hold=commands(named(static_torques(q0))),
                       min_steps=HOLD_STEPS)
        assert out.stable, \
            f"held at q={np.round(q0, 4)} by g(q) it never came to rest"
        drift = max(abs(v) for v in out.moved.values())
        if worst_at is None or drift > worst:
            worst, worst_at = drift, q0
        assert drift < tol, (
            f"held by g(q) = {static_torques(q0)} the truth model drifted from "
            f"q={np.round(q0, 4)} to {dict(out.q)}")
        assert out.constraints == (), \
            f"a constraint carried load at q={np.round(q0, 4)}: {out.constraints}"
    print(f"  [PASS] g(q) holds the truth model still over {samples}, "
          f"{HOLD_STEPS} steps each")
    print(f"         worst drift {worst:.2e} rad, at q = {np.round(worst_at, 4)}")


def test_truth_wrong_torque_does_not_hold(seed=DEFAULT_SEED, moved=1e-2):
    """And the check has teeth: a torque that is not g(q) lets the arm fall.

    A check that passes is only evidence if it could have failed. Twenty per
    cent off on the shoulder is a plausible derivation error — a lever arm to
    the wrong point, a link's mass left out — and the truth model must not
    stand still under it.
    """
    s = armature.sample(truth(), 1, seed).states[0]
    q0 = vector(s.q)
    wrong = static_torques(q0) * np.array([1.2] + [1.0] * (len(q0) - 1))
    out = s.settle(hold=commands(named(wrong)), min_steps=HOLD_STEPS)
    drift = max(abs(v) for v in out.moved.values())
    assert drift > moved, (
        f"a 20% error in the shoulder torque moved the truth model only "
        f"{drift:.2e} rad — this check cannot see a wrong g(q)")
    print(f"  [PASS] a 20% wrong holding torque moves it {drift:.3f} rad")
