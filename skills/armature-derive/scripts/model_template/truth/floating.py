"""
truth/floating.py — the floating-body builder: a MuJoCo model of a mechanism
whose own body is a coordinate, read off the same parameter block chain.py reads.

The chain builder beside this one covers a mechanism bolted to the world, every
coordinate a row in a table. A platform on cables, a legged or a wheeled body
has no such row: its pose in {W} is six coordinates of its own, links hang off
it by their joints, and what holds it up is constraints. That is the plan
glossary's **floating base plus joints** — a convention in its own right rather
than a chain missing its DH table, so it gets its own builder under the same
public surface.

A cable is **unilateral**, which is why this is not two lines of chain.py: it
pulls when stretched past its unstretched length and does nothing at all when it
is not, so a pose a bilateral tension solve calls feasible can be one where a
cable hangs slack and the load it was assumed to carry goes elsewhere. Each
cable here is a spatial tendon with a rest-length deadband from zero to that
length, and its tension is read by `cable_forces` — not from `Settled.forces`,
which carries what the solver enforced, where a deadband spring is passive.

Nothing here imports kinematics.py or dynamics/, for the reason chain.py gives.
A project is one convention or the other: delete the builder this mechanism does
not use, its checks module, and its line in `__init__.py`.

Self-tests in floating_checks.py.
"""

from collections import namedtuple

import mujoco
import numpy as np
import sympy as sp

import params
from params import GRAVITY_VEC, SUB_P

# --- the convention, as the parameter block declares it ---
# `kind` is "hinge" or "slide"; `axis` and `pos` are in the joint's own body's
# frame, `range` the coordinate's (lo, hi) — the envelope, as Q_LIMITS is for a
# chain.
Joint = namedtuple("Joint", "name kind axis pos range")

# One rigid body. `parent` None is the floating body itself, which MuJoCo gives
# a free joint; every other body hangs off its parent by `joint`. `pos` is the
# body origin in the parent's frame, `com`, `sites` and the joint's geometry in
# this body's own; `inertia` is a 3x3 about the COM — every axis of it, for the
# reason params.py gives. `sites` is ((name, xyz), ...): the frames a milestone
# queries the model at, a tool frame among them, the cables' own automatic.
Body = namedtuple("Body", "name mass com inertia parent pos joint sites",
                  defaults=(None, (0.0, 0.0, 0.0), None, ()))

# One cable. `anchor` is the fixed end in {W}, `attach` the moving end in
# `body`'s frame, `ea` the axial stiffness EA [N] and `length` the unstretched
# length [m] — the two numbers a cable is specified by, rather than a spring
# rate, which is EA/L and is derived here.
Cable = namedtuple("Cable", "name body anchor attach ea length")

Floating = namedtuple("Floating", "bodies cables name",
                      defaults=("truth-floating",))


def _f(expr):
    """A parameter-block expression as a float, with PARAMS substituted in.

    The same helper chain.py opens with, repeated rather than shared so either
    builder can be deleted whole. It carries no constants — substituting them
    is all it does.
    """
    return float(sp.sympify(expr).subs(SUB_P))


def _flat(values):
    """`values` as a flat list of floats, row-major, symbols substituted."""
    items = (list(values) if isinstance(values, sp.MatrixBase)
             else np.ravel(np.asarray(values, dtype=object)).tolist())
    return [_f(v) for v in items]


def _fmt(values):
    """MJCF wants space-separated numbers, and wants all the digits."""
    return " ".join(f"{v:.17g}" for v in _flat(values))


def stiffness(cable):
    """The cable's spring rate EA/L [N/m], from the two numbers it is spec'd by."""
    ea, length = _f(cable.ea), _f(cable.length)
    assert length > 0, \
        f"cable {cable.name!r} has unstretched length {length}, which is not one"
    return ea / length


def check_spec(spec):
    """Everything the builder needs of a spec, checked once, here where it can
    be read. Returns the floating body, which the model is built out from.

    The reachability check is the one that is not bookkeeping: `mjcf` writes the
    tree by walking down from the floating body, so a body parented into a cycle
    would be dropped from the model silently, and every check after it would run
    against a mechanism missing a link.
    """
    roots = [b for b in spec.bodies if b.parent is None]
    assert len(roots) == 1, \
        f"a floating model has one floating body; this one declares {len(roots)}"
    assert roots[0].joint is None, \
        (f"the floating body {roots[0].name!r} declares a joint; its six "
         f"coordinates are the free joint the builder gives it")
    names = {b.name for b in spec.bodies}
    assert len(names) == len(spec.bodies), "two bodies share a name"
    for body in spec.bodies:
        if body.parent is None:
            continue
        assert body.parent in names, \
            f"body {body.name!r} hangs off {body.parent!r}, which is not declared"
        assert body.joint is not None, \
            (f"body {body.name!r} hangs off {body.parent!r} by no joint; fold a "
             f"welded body into its parent's mass and inertia instead")
    for cable in spec.cables:
        assert cable.body in names, \
            f"cable {cable.name!r} attaches to {cable.body!r}, not declared"

    reached, frontier = {roots[0].name}, [roots[0].name]
    while frontier:
        parent = frontier.pop()
        children = [b.name for b in spec.bodies if b.parent == parent]
        reached.update(children)
        frontier += children
    assert reached == names, \
        f"bodies {sorted(names - reached)} hang off no path to {roots[0].name!r}"
    return roots[0]


def _body_xml(spec, body, depth):
    """One body element and everything under it, MJCF, recursively."""
    pad = "    " + "  " * depth
    J = _flat(body.inertia)
    full = [J[0], J[4], J[8], J[1], J[2], J[5]]
    lines = [f'{pad}<body name="{body.name}" pos="{_fmt(body.pos)}">']
    if body.joint is None:
        lines.append(f'{pad}  <freejoint name="{body.name}_free"/>')
    else:
        joint = body.joint
        lines.append(f'{pad}  <joint name="{joint.name}" type="{joint.kind}" '
                     f'axis="{_fmt(joint.axis)}" pos="{_fmt(joint.pos)}" '
                     f'range="{_fmt(joint.range)}"/>')
    lines.append(f'{pad}  <inertial pos="{_fmt(body.com)}" '
                 f'mass="{_f(body.mass):.17g}" fullinertia="{_fmt(full)}"/>')
    for name, pos in body.sites:
        lines.append(f'{pad}  <site name="{name}" pos="{_fmt(pos)}"/>')
    for cable in spec.cables:
        if cable.body == body.name:
            lines.append(f'{pad}  <site name="{cable.name}_attach" '
                         f'pos="{_fmt(cable.attach)}"/>')
    for child in spec.bodies:
        if child.parent == body.name:
            lines += _body_xml(spec, child, depth + 1)
    return lines + [f'{pad}</body>']


def mjcf(spec):
    """This mechanism as MJCF. Printed by a report when a note needs it.

    No geoms and no damping, for the reason chain.py gives: what reaches the
    model is the parameter block and nothing a default slipped in. Each cable's
    anchor and attachment sites are generated from the cable itself, so a cable
    is one declaration rather than three that can disagree.
    """
    root = check_spec(spec)
    head = [f'<mujoco model="{spec.name}">',
            '  <compiler angle="radian" inertiafromgeom="false" '
            'autolimits="true"/>',
            f'  <option gravity="{_fmt(GRAVITY_VEC)}"/>',
            '  <worldbody>']
    for cable in spec.cables:
        head.append(f'    <site name="{cable.name}_anchor" '
                    f'pos="{_fmt(cable.anchor)}"/>')
    tendon = ['  <tendon>']
    for cable in spec.cables:
        tendon += [f'    <spatial name="{cable.name}" '
                   f'stiffness="{stiffness(cable):.17g}" '
                   f'springlength="0 {_f(cable.length):.17g}">',
                   f'      <site site="{cable.name}_anchor"/>',
                   f'      <site site="{cable.name}_attach"/>',
                   '    </spatial>']
    tendon.append('  </tendon>')
    return "\n".join(head + _body_xml(spec, root, 0) + ['  </worldbody>']
                     + tendon + ['</mujoco>'])


def _body_from(entry):
    """One `FLOATING_BODIES` dict as a `Body`, its joint dict as a `Joint`."""
    joint = entry.get("joint")
    return Body(**{**entry, "joint": Joint(**joint) if joint else None})


def spec_from_params():
    """The floating mechanism this parameter block declares.

    `FLOATING_BODIES` and `FLOATING_CABLES` are plain dicts there — the
    parameter block cannot import the types above without importing the truth
    model that reads it — and their keys are the fields above.
    """
    bodies = getattr(params, "FLOATING_BODIES", None)
    assert bodies, (
        "this parameter block declares no floating body. A floating mechanism "
        "declares FLOATING_BODIES — the floating body first, then any link hung "
        "off it by a joint — and FLOATING_CABLES, as dicts of the fields in "
        "truth/floating.py; a mechanism on a fixed base builds the chain model "
        "instead")
    cables = getattr(params, "FLOATING_CABLES", None) or ()
    return Floating(bodies=tuple(_body_from(entry) for entry in bodies),
                    cables=tuple(Cable(**entry) for entry in cables))


def build(spec=None):
    """The truth model of this floating mechanism: (model, data).

    `spec` defaults to what the parameter block declares. Named `build`, as the
    chain builder's is, so a project that keeps this builder and deletes the
    other keeps `truth.build` too and nothing above the package is rewritten;
    the template, shipping both, surfaces this one as `truth.build_floating`.
    """
    model = mujoco.MjModel.from_xml_string(mjcf(spec or spec_from_params()))
    return model, mujoco.MjData(model)


def cable_forces(model, data, pose=None):
    """Tension in each cable [N], in the order the spec declared them.

    Positive pulls, and a slack cable is **exactly** zero — the deadband
    produces no force inside it rather than a small one. **Negative is a cable
    pushing**, which no cable does: it means the deadband did not reach the
    model, and reporting it rather than clamping at zero is what keeps an
    asserted zero an assertion rather than an arithmetic certainty.

    `pose` puts the model at a configuration first — the pose a settle came to
    rest at, typically — and defaults to wherever the model already is. The
    lengths are MuJoCo's own and the deadband and the stiffness are read back
    out of the compiled model; the spring law between them is all this adds.
    """
    if pose is not None:
        data.qpos[:] = np.asarray(pose, dtype=float)
        data.qvel[:] = 0.0
        mujoco.mj_forward(model, data)
    low, high = np.asarray(model.tendon_lengthspring, dtype=float).T
    length = np.asarray(data.ten_length, dtype=float)
    stretch = np.where(length > high, length - high,
                       np.minimum(length - low, 0.0))
    return np.asarray(model.tendon_stiffness, dtype=float) * stretch
