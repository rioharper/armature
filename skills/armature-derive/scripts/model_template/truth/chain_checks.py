"""
truth/chain_checks.py — self-tests for chain.py.

These are round-trip checks, and round-trip is all they can be: they hold the
built model against the parameter block it was built from, which is the one
thing a builder *can* get wrong on its own. Whether the model then agrees with
the derivation is every other milestone's check, not this one's.
"""

import mujoco
import numpy as np

from params import (COM_LOCAL, GRAVITY_VEC, INERTIA, MASSES, N, Q_LIMITS,
                    WORKSPACE)
from truth.chain import TOOL_SITE, as_float, build, joint_kind
from truth.envelope import DEFAULT_SEED, sample_workspace
from truth.equilibrium import settle

KINDS = {"hinge": mujoco.mjtJoint.mjJNT_HINGE,
         "slide": mujoco.mjtJoint.mjJNT_SLIDE}


def test_builder_round_trips_the_parameter_block(tol=1e-12):
    """Link count, masses, COMs and gravity, read back out of the model.

    A parameter that reaches MuJoCo wrong makes every truth check that follows
    a check against the wrong machine, and it would still pass self-consistency
    — so this runs first, and the whole package sorts first in the run.
    """
    model, _data = build()
    assert model.nq == N and model.nv == N, \
        f"truth model has nq={model.nq}, nv={model.nv} for {N} coordinates"
    assert model.nbody == N + 1, \
        f"truth model has {model.nbody - 1} links beside the world, not {N}"

    for i in range(N):
        body = i + 1        # body 0 is the world
        assert abs(model.body_mass[body] - as_float(MASSES[i])) < tol, \
            f"link {i + 1} mass {model.body_mass[body]} != {as_float(MASSES[i])}"
        com = [as_float(v) for v in COM_LOCAL[i]]
        assert np.allclose(model.body_ipos[body], com, atol=tol), \
            f"link {i + 1} COM {model.body_ipos[body]} != {com}"
        J = np.array([[as_float(INERTIA[i][r, c]) for c in range(3)]
                      for r in range(3)])
        principal = np.sort(np.linalg.eigvalsh(J))
        assert np.allclose(np.sort(model.body_inertia[body]), principal,
                           atol=1e-10), \
            (f"link {i + 1} principal inertias {model.body_inertia[body]} "
             f"!= {principal} — check the fullinertia ordering")

    gravity = [as_float(v) for v in GRAVITY_VEC]
    assert np.allclose(model.opt.gravity, gravity, atol=tol), \
        f"truth model gravity {model.opt.gravity} != {gravity}"
    print(f"  [PASS] truth model round-trips {N} links from the parameter block")


def test_joints_match_the_table_and_the_envelope(tol=1e-12):
    """Each joint's type comes from its DH row, its range from Q_LIMITS."""
    model, _data = build()
    for i in range(N):
        want = KINDS[joint_kind(i)]
        assert model.jnt_type[i] == want, \
            f"joint {i + 1} is {model.jnt_type[i]}, not {joint_kind(i)}"
        assert bool(model.jnt_limited[i]), f"joint {i + 1} left unlimited"
        assert np.allclose(model.jnt_range[i], Q_LIMITS[i], atol=tol), \
            f"joint {i + 1} range {model.jnt_range[i]} != {Q_LIMITS[i]}"
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, TOOL_SITE)
    assert sid >= 0, f"the truth model has no {TOOL_SITE!r} site to check against"
    print("  [PASS] joint types, ranges and the tool site match the block")


def test_the_workspace_stays_clear_of_the_joint_limits(n=64, seed=DEFAULT_SEED,
                                                       tol=1e-9):
    """The intended workspace, against the joint ranges the builder gave the model.

    `WORKSPACE` is a claim about the machine — *this is where it works* — and
    every later result leans on it: the singular-value bound, the IK's
    convergence set, the posture each worst case is found at. The builder reads
    `Q_LIMITS` into the model as its joint ranges, so this file is where the two
    can be held against each other.

    The difference is not cosmetic. On a limit MuJoCo adds a constraint force,
    and every truth check downstream then reads the limit's torque rather than
    the mechanism's — Milestone 3's worst-case check would confirm a number the
    end-stop is carrying. It sits here, after the round-trip above, because a
    check of the model is only worth its line once the model itself has been
    held against the block.
    """
    model, data = build()
    for q0 in sample_workspace(n, seed):
        out = settle(model, data, q0, max_steps=1)
        assert np.max(np.abs(out.forces)) < tol, (
            f"a joint limit carries {out.forces} at q={np.round(q0, 4)}, inside "
            f"WORKSPACE {WORKSPACE}; every truth check at that pose would read "
            f"the end-stop's force rather than the mechanism's")
    print(f"  [PASS] {n} sampled workspace poses sit clear of every joint limit "
          f"the truth model carries (seed {seed})")
