"""
truth/chain.py — the chain builder: a MuJoCo model of a serial chain, read off
the same parameter block the derivation reads.

Nothing here imports kinematics.py or dynamics/. That is the whole point: the
frames, the Jacobian and the equations of motion this model produces are
MuJoCo's own, computed from a body tree, so a claim checked against them is
checked by something that never saw the derivation. What the two share is
params.py — every length, mass, inertia and the gravity vector — because two
models built from two copies of the constants drift the first time one is
edited, and a check between drifted models proves nothing about either.

Self-tests in chain_checks.py.
"""

import mujoco
import numpy as np
import sympy as sp

from params import (COM_LOCAL, DH, GRAVITY_VEC, INERTIA, MASSES, N, Q_LIMITS,
                    SUB_P, T_TOOL, q)

TOOL_SITE = "tool"


def as_float(expr):
    """A parameter-block expression as a float, with PARAMS substituted in.

    Public because a second backend builds the same chain from the same block
    and must read every constant through the same substitution.
    """
    return float(sp.sympify(expr).subs(SUB_P))


def _fmt(values):
    """MJCF wants space-separated numbers, and wants all the digits."""
    return " ".join(f"{float(v):.17g}" for v in np.ravel(values))


def _rot_x(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rot_z(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _quat(R):
    """MuJoCo's (w, x, y, z) for a rotation matrix, by MuJoCo's own routine."""
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, np.asarray(R, dtype=float).flatten())
    return quat


def joint_kind(i):
    """`hinge` when q_i rides in theta_i, `slide` when it rides in d_i."""
    return "hinge" if sp.sympify(DH[i][3]).has(q[i]) else "slide"


def body_placement(i):
    """Where MuJoCo puts body {i} inside body {i-1}: (pos, quat).

    Modified DH (Craig) reads frame {i} as the parent turned by alpha about x
    then by theta about the new z, its origin a along the parent's x plus d
    along that same new z. With the joint coordinate set to zero that is a
    constant placement, because Rz and Tz commute:

        T_i(q) = [Rx(alpha) Tx(a) Rz(theta_0) Tz(d_0)] * (Rz(q) or Tz(q))

    so the whole q-dependence is the joint MuJoCo adds at the body origin, and
    the placement is exact rather than a linearisation. Change this function,
    not the caller, if the parameter block uses standard DH or PoE screws.
    """
    alpha, a, d, theta = (as_float(sp.sympify(e).subs(q[i], 0)) for e in DH[i])
    R = _rot_x(alpha) @ _rot_z(theta)
    pos = np.array([a, -d * np.sin(alpha), d * np.cos(alpha)])
    return pos, _quat(R)


def tool_placement():
    """The tool frame inside the last link frame: (pos, quat), from T_TOOL."""
    T = np.array([[as_float(T_TOOL[r, c]) for c in range(4)] for r in range(4)])
    return T[:3, 3], _quat(T[:3, :3])


def mjcf():
    """This mechanism as MJCF. Printed by report_truth.py when a note needs it.

    No geoms: a link's mass, COM and inertia come from the parameter block, so
    letting MuJoCo infer them from shapes would be a second set of numbers with
    no provenance. No damping, friction or armature either — the truth model
    carries what the parameter block says and nothing a default slipped in.
    """
    head = ['<mujoco model="truth-chain">',
            '  <compiler angle="radian" inertiafromgeom="false" '
            'autolimits="true"/>',
            f'  <option gravity="{_fmt([as_float(v) for v in GRAVITY_VEC])}"/>',
            '  <worldbody>']
    body, close = [], []
    for i in range(N):
        pad = "    " + "  " * i
        pos, quat = body_placement(i)
        com = [as_float(v) for v in COM_LOCAL[i]]
        J = [[as_float(INERTIA[i][r, c]) for c in range(3)] for r in range(3)]
        full = [J[0][0], J[1][1], J[2][2], J[0][1], J[0][2], J[1][2]]
        body += [
            f'{pad}<body name="link{i + 1}" pos="{_fmt(pos)}" '
            f'quat="{_fmt(quat)}">',
            f'{pad}  <joint name="q{i + 1}" type="{joint_kind(i)}" '
            f'axis="0 0 1" range="{_fmt(Q_LIMITS[i])}"/>',
            f'{pad}  <inertial pos="{_fmt(com)}" mass="{as_float(MASSES[i]):.17g}" '
            f'fullinertia="{_fmt(full)}"/>',
        ]
        close.insert(0, f'{pad}</body>')
    pos, quat = tool_placement()
    body.append(f'{"    " + "  " * N}<site name="{TOOL_SITE}" '
                f'pos="{_fmt(pos)}" quat="{_fmt(quat)}"/>')
    return "\n".join(head + body + close + ['  </worldbody>', '</mujoco>'])


def build():
    """The truth model of this mechanism: (model, data), ready to query."""
    model = mujoco.MjModel.from_xml_string(mjcf())
    return model, mujoco.MjData(model)


def at(model, data, q_vals):
    """Put the truth model at a configuration and let MuJoCo do the rest."""
    data.qpos[:] = np.asarray(q_vals, dtype=float)
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    return data


def site_pose(model, data, q_vals, site=TOOL_SITE):
    """(position [m], 3x3 rotation) of a site in the world, at `q_vals`."""
    at(model, data, q_vals)
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, site)
    assert sid >= 0, f"no site named {site!r} in the truth model"
    return np.array(data.site_xpos[sid]), np.array(data.site_xmat[sid]).reshape(3, 3)


def site_jacobian(model, data, q_vals, site=TOOL_SITE):
    """The site's 6xN geometric Jacobian in the world frame, MuJoCo's own.

    Rows 0-2 linear, 3-5 angular — the same stacking `kinematics.py` builds by
    hand, so the two are comparable column by column.
    """
    at(model, data, q_vals)
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, site)
    jacp, jacr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    mujoco.mj_jacSite(model, data, jacp, jacr, sid)
    return np.vstack([jacp, jacr])
