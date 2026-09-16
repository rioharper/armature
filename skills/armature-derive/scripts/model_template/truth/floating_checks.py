"""
truth/floating_checks.py — self-tests for floating.py, on a minimal fixture.

The shipped parameter block is a 2R arm on a fixed base, so there is no floating
mechanism here to build; the fixture below is one, small enough that its
equilibrium is a line of algebra and rich enough to carry the error the builder
exists to expose — a body on three unilateral cables, two taut and one slack.

Everything the fixture borrows from the parameter block it reads rather than
copies: the mass, and gravity, whichever way the block points it. Its own
geometry — the span, the anchor height, the cable stiffnesses — is the
fixture's and belongs to no mechanism.

Round-trips, as in chain_checks.py: these hold the built model against what it
was built from. Whether a *derivation* then agrees with it is every other
milestone's check, not this one's.
"""

import mujoco
import numpy as np

from params import GRAVITY_VEC, m1
from truth.equilibrium import settle
from truth.floating import (Body, Cable, Floating, Joint, _f, build,
                            cable_forces, spec_from_params, stiffness)

# --- the fixture's own geometry ---
SPAN = 0.20          # half the distance between the two taut cables [m]
HEIGHT = 0.50        # anchor plane above the body's release pose, along up [m]
RISE = 0.05          # attachment points above the COM, along up [m]
EA = 1000.0          # cable axial stiffness [N]
TAUT_LENGTH = 0.40   # unstretched length of the taut pair [m]
SLACK_LENGTH = 0.80  # and of the third, twice the gap it spans [m]
# The fixture body's inertia. It does not enter the equilibrium below — the
# cables pull through a plane containing the COM and the hang is symmetric — and
# it is here because a rigid body cannot be built without one.
INERTIA = np.diag([0.004, 0.004, 0.008])

MASS = _f(m1)
G = float(np.linalg.norm([_f(v) for v in GRAVITY_VEC]))
# Up is against gravity, whichever way the parameter block points it, and the
# span lies along any direction across it — so the algebra below is the same in
# a z-up block as in this one's y-up.
UP = -np.array([_f(v) for v in GRAVITY_VEC]) / G
SIDE = np.cross(UP, np.eye(3)[int(np.argmin(np.abs(UP)))])
SIDE = SIDE / np.linalg.norm(SIDE)

# Where the body is released: at the anchor plane's origin, unrotated, with the
# taut pair already stretched, so it has somewhere to settle *to*.
RELEASE_POSE = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])


def fixture():
    """A body hung on two taut cables and one slack one."""
    body = Body(name="platform", mass=m1, com=(0.0, 0.0, 0.0), inertia=INERTIA)
    cables = tuple(
        Cable(name=name, body="platform",
              anchor=HEIGHT * UP + side * SPAN * SIDE,
              attach=RISE * UP + side * SPAN * SIDE,
              ea=EA, length=length)
        for name, side, length in (("left", -1.0, TAUT_LENGTH),
                                   ("right", 1.0, TAUT_LENGTH),
                                   ("middle", 0.0, SLACK_LENGTH)))
    return Floating(bodies=(body,), cables=cables, name="truth-floating-fixture")


def hanging():
    """The hand-computed equilibrium: (body position, cable tensions).

    Both taut cables run along up, and stay along up as the body rises, so each
    carries half the weight:

        T = m g / 2,  and  T = (EA / L0) (L - L0),  so  L = L0 (1 + T / EA)

    and the body ends up where that length puts it, HEIGHT - RISE - L below the
    anchor plane. The third cable spans the same L against an unstretched length
    twice as long — slack, and carrying nothing.
    """
    tension = MASS * G / 2
    length = TAUT_LENGTH * (1 + tension / EA)
    return (HEIGHT - RISE - length) * UP, np.array([tension, tension, 0.0])


def test_builder_round_trips_the_fixture(tol=1e-12):
    """The body, its free joint and every cable, read back out of the model.

    A cable that reaches MuJoCo with the wrong stiffness or the wrong deadband
    makes every check that follows a check against the wrong machine, and a
    deadband that arrived as a plain spring would hold the body up in
    compression — which is why the deadband's own bounds are asserted here and
    why `cable_forces` reports a push rather than clamping it away.
    """
    spec = fixture()
    model, _data = build(spec)
    assert model.nq == 7 and model.nv == 6, \
        f"a floating body has nq=7, nv=6; this model has {model.nq}, {model.nv}"
    assert model.nbody == 2, f"{model.nbody - 1} bodies beside the world, not 1"
    assert abs(model.body_mass[1] - MASS) < tol, \
        f"body mass {model.body_mass[1]} != {MASS}"
    assert np.allclose(np.sort(model.body_inertia[1]),
                       np.sort(np.diag(INERTIA)), atol=1e-10), \
        f"principal inertias {model.body_inertia[1]} != {np.diag(INERTIA)}"
    assert np.allclose(model.opt.gravity, [_f(v) for v in GRAVITY_VEC], atol=tol)

    assert model.ntendon == len(spec.cables), \
        f"{model.ntendon} tendons for {len(spec.cables)} cables"
    for i, cable in enumerate(spec.cables):
        assert abs(model.tendon_stiffness[i] - stiffness(cable)) < 1e-9, \
            f"cable {cable.name!r} stiffness {model.tendon_stiffness[i]}"
        assert np.allclose(model.tendon_lengthspring[i],
                           [0.0, _f(cable.length)], atol=tol), \
            (f"cable {cable.name!r} deadband {model.tendon_lengthspring[i]} is "
             f"not zero to its unstretched length — it can push")
    print(f"  [PASS] the floating model round-trips one body and "
          f"{model.ntendon} cables from the fixture")


def test_a_link_and_a_site_hang_off_the_floating_body():
    """A joint in the spec is a joint one body further down in the model.

    The hanging fixture is a single body, which would leave the rest of the
    convention — a link on its joint, and a named site to query the model at —
    built but never exercised, and an unexercised branch of a builder is one a
    project discovers is wrong at its first milestone instead of here.
    """
    base = fixture()
    link = Body(name="arm", mass=m1 / 4, com=(0.05, 0.0, 0.0),
                inertia=INERTIA / 10, parent="platform", pos=(0.1, 0.0, 0.0),
                joint=Joint(name="elbow", kind="hinge", axis=(0, 0, 1),
                            pos=(0, 0, 0), range=(-1.2, 1.2)),
                sites=(("tool", (0.2, 0.0, 0.0)),))
    model, _data = build(Floating(bodies=base.bodies + (link,),
                                  cables=base.cables))
    assert model.nq == 8 and model.nv == 7, \
        f"a floating body and one hinge is nq=8, nv=7, not {model.nq}, {model.nv}"
    assert model.nbody == 3, f"{model.nbody - 1} bodies beside the world, not 2"
    assert abs(model.body_mass[2] - MASS / 4) < 1e-12
    assert model.jnt_type[0] == mujoco.mjtJoint.mjJNT_FREE, \
        "the floating body did not get a free joint"
    assert model.jnt_type[1] == mujoco.mjtJoint.mjJNT_HINGE, \
        f"the link's joint is {model.jnt_type[1]}, not a hinge"
    assert bool(model.jnt_limited[1]), "the link's joint was left unlimited"
    assert np.allclose(model.jnt_range[1], link.joint.range, atol=1e-12), \
        f"joint range {model.jnt_range[1]} != {link.joint.range}"
    assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "tool") >= 0, \
        "the site the spec named is not in the model to query"
    print("  [PASS] a link on its joint, and its site, reach the model")


def test_body_settles_to_the_hand_computed_hanging_pose(tol=1e-6, steps=500):
    """Released at the anchor plane, it hangs where the algebra says it does.

    Held for `steps` after the rest test passes, for the reason equilibrium.py
    gives: an instantaneous balance is silent about every coordinate the algebra
    did not keep, and this body has six.
    """
    model, data = build(fixture())
    out = settle(model, data, RELEASE_POSE, min_steps=steps)
    assert out.stable, f"the body never came to rest in {out.steps} steps"
    position, tensions = hanging()
    assert np.allclose(out.pose[:3], position, atol=tol), \
        f"it hung at {np.round(out.pose[:3], 6)}, not {np.round(position, 6)}"
    assert np.allclose(out.pose[3:], [1, 0, 0, 0], atol=tol), \
        f"a symmetric hang tilted the body: quat {np.round(out.pose[3:], 6)}"
    forces = cable_forces(model, data, out.pose)
    assert np.allclose(forces, tensions, atol=1e-3), \
        f"cable tensions {np.round(forces, 4)} != {np.round(tensions, 4)} N"
    print(f"  [PASS] the body hangs at {np.round(out.pose[:3], 6)} m after "
          f"{out.steps} steps, carrying {np.round(forces, 4)} N")


def test_a_slack_cable_reads_zero_where_a_tension_was_expected():
    """The slack cable carries nothing, and the same cable pulls when stretched.

    Zero exactly, not nearly: the deadband produces no force inside it. So a
    derivation that shared this load over all three cables — the plausible
    assumption, and the one a bilateral tension solve makes for you — is wrong
    by half on the two that carry it, and the check that expected tension on the
    third fails outright rather than passing within a tolerance.
    """
    model, data = build(fixture())
    out = settle(model, data, RELEASE_POSE, min_steps=500)
    forces = cable_forces(model, data, out.pose)
    assert forces[2] == 0.0, \
        (f"the slack cable reads {forces[2]} N, not zero" if forces[2] > 0 else
         f"the slack cable is pushing at {forces[2]} N, which a cable cannot do")
    shared = MASS * G / 3
    assert abs(forces[0] - shared) > 1.0, \
        (f"the taut cables read {forces[0]:.4f} N, which is the three-way share "
         f"{shared:.4f} N — the fixture is no longer showing the error")

    drop = SLACK_LENGTH - (HEIGHT - RISE) + 0.1   # 0.1 m of stretch past rest
    below = np.array(RELEASE_POSE)
    below[:3] = -drop * UP
    span = HEIGHT - RISE + drop
    taut = cable_forces(model, data, below)
    assert abs(taut[2] - (EA / SLACK_LENGTH) * (span - SLACK_LENGTH)) < 1e-6, \
        f"stretched to {span:.4f} m the cable reads {taut[2]:.4f} N"
    print(f"  [PASS] the slack cable reads 0 N at the hanging pose and "
          f"{taut[2]:.4f} N stretched {span - SLACK_LENGTH:.3f} m past rest")


def test_a_block_with_no_floating_body_says_what_to_declare():
    """The shipped 2R block declares none; asking names the two declarations."""
    try:
        spec_from_params()
    except AssertionError as refusal:
        assert "FLOATING_BODIES" in str(refusal) and "FLOATING_CABLES" in str(refusal)
        print("  [PASS] a block with no floating body names what to declare")
        return
    raise AssertionError(
        "the 2R parameter block built a floating model; FLOATING_BODIES is set")
