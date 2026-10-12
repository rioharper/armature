"""Contact: a wheel on a 10° incline, held by its hub motor.

A wheel on a chassis rides an x-y carriage down a 10° incline, its hub motor
holding it against rolling. The chassis hangs from the hub and rocks; the
carriage's x cart rides a rail and carries none of its own weight onto the
wheel. Answer: a reference in rolling coordinates (the hub's travel s down
the slope and the chassis's angle φ), written here in SymPy, independent of
the engine. It gives the hub torque, the contact's normal and friction forces
(M g cos α and M g sin α, with M the mass the wheel carries) and the rocking
mode. Trap: `mj_inverse`, which reads the normal force off the solver's
penetration stiffness and drops static friction, and the contact solver's
own roots, which a full linearisation reports as modes.
"""

import math

import mujoco
import numpy as np
import pytest
import sympy as sp

import armature
from armature import (DescriptionError, actuator, body, contact, gravity,
                      joint, shape)

ALPHA = math.radians(10)
NORMAL = (math.sin(ALPHA), math.cos(ALPHA), 0.0)   # the incline's, outward
DOWNHILL = (math.cos(ALPHA), -math.sin(ALPHA), 0.0)
PARAMS = {"r": 0.1, "w": 0.02, "m_w": 1.0, "m_cx": 0.1, "m_cy": 0.1,
          "m_c": 2.0, "l": 0.06, "I_c": 0.0248, "N": 10.0, "J": 1e-5,
          "mu": 0.8, "g": 9.81}
CARRIED = ("m_cy", "m_c", "m_w")  # the x cart's weight goes into its rail


def incline(p, tyre="cylinder", hub_spring=None, compliance=None):
    """The wheel's hub is at the origin at home, touching the incline;
    gravity is −y and every hinge turns about z. Its chassis hangs `l`
    below the hub."""
    r, i_w = p["r"], p["m_w"] * p["r"] ** 2
    if tyre == "cylinder":
        wheel = shape("cylinder", pos=(0, 0, 0), axis=(0, 0, 1), radius=r,
                      half_length=p["w"])
    else:
        wheel = shape("sphere", pos=(0, 0, 0), radius=r)
    span = (-1.0, 1.0)
    out = [
        body("cart_x", mass=p["m_cx"], com=(0, 0, 0),
             inertia=np.diag([1e-4] * 3)),
        body("cart_y", mass=p["m_cy"], com=(0, 0, 0),
             inertia=np.diag([1e-4] * 3)),
        body("chassis", mass=p["m_c"], com=(0, -p["l"], 0),
             inertia=np.diag([p["I_c"]] * 3)),
        body("wheel", mass=p["m_w"], com=(0, 0, 0),
             inertia=np.diag([i_w / 2, i_w / 2, i_w / 2])),
        joint("x", "slide", parent="world", child="cart_x", axis=(1, 0, 0),
              point=(0, 0, 0), range=span),
        joint("y", "slide", parent="cart_x", child="cart_y", axis=(0, 1, 0),
              point=(0, 0, 0), range=span),
        joint("pitch", "hinge", parent="cart_y", child="chassis",
              axis=(0, 0, 1), point=(0, 0, 0), range=(-math.pi, math.pi)),
        joint("hub", "hinge", parent="chassis", child="wheel", axis=(0, 0, 1),
              point=(0, 0, 0), range=(-100.0, 100.0),
              stiffness=None if hub_spring is None else p[hub_spring]),
        actuator("hub_motor", joint="hub", gear=p["N"], rotor_inertia=p["J"]),
        contact("tyre", body="wheel", shape=wheel,
                against=shape("plane", pos=tuple(-r * n for n in NORMAL),
                              axis=NORMAL),
                mu=p["mu"],
                stiffness=None if compliance is None else p[compliance[0]],
                damping=None if compliance is None else p[compliance[1]]),
        gravity((0, -p["g"], 0)),
    ]
    return out


def servo(p):
    """The same wheel, its hub stiffened by a spring: a servo's P gain."""
    return incline(p, hub_spring="k_hub")


def tyre(p):
    """A sphere tyre, compliant, on a servoed hub, so rolling is not a
    neutral direction that a 10 nm imbalance can drift along."""
    return incline(p, tyre="sphere", hub_spring="k_hub",
                   compliance=("k_tyre", "c_tyre"))


# --- the reference, in rolling coordinates ------------------------------------
# s is the hub's travel down the slope and φ the chassis's turn from hanging;
# rolling turns the wheel by −s/r, so the hub joint reads −s/r − φ.
_s, _phi, _sd, _phid = sp.symbols("s phi sd phid", real=True)


def _reference(params, k_hub=0.0):
    p = {k: sp.nsimplify(v) if k != "mu" else v for k, v in params.items()}
    a = sp.pi / 18
    e = sp.Matrix([sp.cos(a), -sp.sin(a)])
    hub = _s * e
    chassis = hub + sp.Matrix([p["l"] * sp.sin(_phi), -p["l"] * sp.cos(_phi)])
    weight = sum(p[m] for m in CARRIED)
    held = weight * p["g"] * p["r"] * sp.sin(a)  # N τ, so ∂V/∂s = −N τ / r
    phi = sp.asin(-held / (p["m_c"] * p["g"] * p["l"]))
    q_hub = phi - _s / p["r"] - _phi  # zero at the rest the tests take
    potential = (p["g"] * (p["m_cy"] + p["m_w"]) * hub[1]
                 + p["g"] * p["m_c"] * chassis[1] + k_hub * q_hub ** 2 / 2)
    rate = lambda v: v.diff(_s) * _sd + v.diff(_phi) * _phid  # noqa: E731
    i_w = p["m_w"] * p["r"] ** 2 / 2
    kinetic = (p["m_cx"] * rate(hub[0]) ** 2 + p["m_cy"] * rate(hub).dot(rate(hub))
               + p["m_w"] * rate(hub).dot(rate(hub))
               + p["m_c"] * rate(chassis).dot(rate(chassis))
               + i_w * (_sd / p["r"]) ** 2 + p["I_c"] * _phid ** 2
               + p["N"] ** 2 * p["J"] * rate(q_hub) ** 2) / 2
    # the static balance, checked: ∂(V − N τ q_hub)/∂(s, φ) = 0 there
    for y in (_s, _phi):
        assert abs(float((potential - held * q_hub).diff(y).subs(
            {_s: 0, _phi: phi}))) < 1e-12
    at = {_s: 0, _phi: phi}
    stiffness = sp.hessian(potential, (_s, _phi)).subs(at)
    mass = sp.hessian(kinetic, (_sd, _phid)).subs(at)
    lam = sorted(complex(v).real for v in (mass.inv() * stiffness).evalf().eigenvals())
    freqs = [math.copysign(math.sqrt(abs(v)), v) / (2 * math.pi) for v in lam]
    return {"torque": float(held / p["N"]), "phi": float(phi),
            "weight": float(weight * p["g"]), "freqs": freqs}


REF = _reference(PARAMS)
M_G = REF["weight"]
TYRE = {k: v for k, v in PARAMS.items() if k != "w"} | {"k_tyre": 2e4,
                                                       "c_tyre": 30.0, "k_hub": 300.0}


@pytest.fixture(scope="module")
def m():
    return armature.compile(incline, PARAMS)


@pytest.fixture(scope="module")
def rest(m):
    return m.at(q={"pitch": REF["phi"]})


def test_the_reference_is_the_box(m):
    assert REF["freqs"][0] == pytest.approx(0.0, abs=1e-9)  # rolling: neutral
    assert round(REF["freqs"][1], 2) == 0.96                # rocking


# --- compiling ----------------------------------------------------------------
def test_the_contact_compiles_as_one_pair_with_noslip(m):
    model = m.model
    assert model.npair == 1 and model.pair(0).name == "tyre"
    assert model.opt.cone == mujoco.mjtCone.mjCONE_PYRAMIDAL
    assert model.opt.noslip_iterations == 20
    assert model.pair_dim[0] == 3
    assert model.pair_friction[0][:2] == pytest.approx([0.8, 0.8])
    assert all(model.geom_contype == 0) and all(model.geom_conaffinity == 0)
    wheel = model.geom("tyre")
    assert wheel.type[0] == mujoco.mjtGeom.mjGEOM_CYLINDER
    assert model.geom_bodyid[wheel.id] == model.body("wheel").id
    floor = model.geom("tyre:against")
    assert floor.type[0] == mujoco.mjtGeom.mjGEOM_PLANE
    assert model.geom_bodyid[floor.id] == 0


def test_a_frictionless_contact_needs_no_noslip():
    params = dict(PARAMS, mu=0.0)
    m = armature.compile(incline, params)
    assert m.model.opt.noslip_iterations == 0
    assert m.model.pair_dim[0] == 1


def test_at_home_the_wheel_touches(m):
    data = mujoco.MjData(m.model)
    mujoco.mj_forward(m.model, data)
    assert data.ncon == 2  # the cylinder's two rims
    assert np.max(np.abs(data.contact.dist[:2])) < 1e-15


# --- settle -------------------------------------------------------------------
def test_the_wheel_comes_to_rest_on_the_incline(m):
    settled = m.at().settle({"hub_motor": REF["torque"]})
    assert settled.stable
    tyre = settled.contacts["tyre"]
    assert tyre.normal == pytest.approx(M_G * math.cos(ALPHA), abs=1e-4)
    assert np.linalg.norm(tyre.friction) == pytest.approx(
        M_G * math.sin(ALPHA), abs=1e-4)
    assert tyre.friction @ DOWNHILL < 0  # uphill, holding the wheel
    assert tyre.margin == pytest.approx(
        M_G * (PARAMS["mu"] * math.cos(ALPHA) - math.sin(ALPHA)), abs=1e-4)
    assert tyre.penetration <= 1e-6  # within the 10 nm band it pushes from
    assert settled.q["pitch"] == pytest.approx(REF["phi"], abs=1e-6)
    assert "contact 'tyre'" in settled.constraints


def _sunk(m):
    """The compliant tyre at rest: sunk by its load over its stiffness, with
    the hub torque and chassis angle that balance friction acting where
    MuJoCo puts the contact, midway through the sink (r − δ/2 from the
    hub)."""
    sink = M_G * math.cos(ALPHA) / TYRE["k_tyre"]
    torque = M_G * (TYRE["r"] - sink / 2) * math.sin(ALPHA) / TYRE["N"]
    phi = -math.asin(TYRE["N"] * torque / (TYRE["m_c"] * TYRE["g"] * TYRE["l"]))
    q = {"x": -sink * NORMAL[0], "y": -sink * NORMAL[1], "pitch": phi}
    return m.at(q=q), torque, sink


def test_a_compliant_tyre_sinks_by_its_load_over_its_stiffness():
    m = armature.compile(tyre, TYRE)
    s, torque, sink = _sunk(m)
    inv = s.inverse()
    assert inv.torque["hub_motor"] == pytest.approx(torque, rel=1e-9)
    assert inv.contacts["tyre"].penetration == pytest.approx(sink, rel=1e-9)
    assert inv.residual < 1e-9
    settled = s.settle({"hub_motor": torque})
    assert settled.stable
    tyre_ = settled.contacts["tyre"]
    assert tyre_.normal == pytest.approx(M_G * math.cos(ALPHA), abs=1e-4)
    # to 1.4e-4 here (a sliding block without a hub read it exactly); the
    # noslip solver reshaping the pyramid's edge forces is the likely cause
    assert tyre_.penetration == pytest.approx(tyre_.normal / TYRE["k_tyre"],
                                              rel=5e-4)
    assert max(abs(settled.moved[n]) for n in ("x", "y", "pitch")) < 1e-6


def test_without_noslip_a_compliant_tyre_creeps_and_never_rests():
    """MuJoCo's friction is soft: without noslip, a resting contact slides
    at whatever speed its regularised friction balances. The old rest test,
    read after a quench, passed such a creep for rest."""
    m = armature.compile(tyre, TYRE)
    s, torque, _ = _sunk(m)
    m.model.opt.noslip_iterations = 0
    crept = s.settle({"hub_motor": torque}, max_steps=5000)
    assert not crept.stable
    assert abs(crept.moved["x"]) > 1e-3


def test_rigid_contact_drops_the_compliance():
    """`rigid(contact)`: the variant's tyre is the stiff default, so it sinks
    nanometres where the compliant one sinks 1.5 mm."""
    variant = armature.reduce(tyre, armature.rigid("tyre", assumption="A9"))
    m = armature.compile(variant, TYRE)
    full = armature.compile(tyre, TYRE)
    pair = m.model.pair("tyre").id
    assert list(m.model.pair_solref[pair]) == list(
        armature.compiler.CONTACT_SOLREF)
    assert full.model.pair_solref[pair][0] < 0  # direct stiffness
    settled = m.at(q={"pitch": REF["phi"]}).settle(
        {"hub_motor": REF["torque"]})
    assert settled.stable
    assert settled.contacts["tyre"].penetration <= 1e-6


def test_rigid_needs_a_compliant_contact():
    with pytest.raises(DescriptionError, match="contact 'tyre' has no "
                                               "compliance; it is rigid"):
        armature.compile(armature.reduce(
            incline, armature.rigid("tyre", assumption="A9")), PARAMS)


def test_a_rigid_contact_sunk_past_its_bound_raises():
    m = armature.compile(incline, PARAMS)
    m.model.pair_solref[0] = (0.5, 1.0)    # as soft as a sponge
    m.model.pair_solimp[0] = (0.1, 0.2, 0.1, 0.5, 2)
    with pytest.raises(RuntimeError, match="contact 'tyre' sunk in"):
        m.at().settle({"hub_motor": REF["torque"]})


# --- inverse ------------------------------------------------------------------
def _check_at_rest(inv):
    assert inv.torque["hub_motor"] == pytest.approx(REF["torque"], rel=1e-9)
    tyre = inv.contacts["tyre"]
    assert tyre.normal == pytest.approx(M_G * math.cos(ALPHA), rel=1e-9)
    assert tyre.friction == pytest.approx(
        -M_G * math.sin(ALPHA) * np.array(DOWNHILL), abs=1e-9)
    assert tyre.margin == pytest.approx(
        M_G * (PARAMS["mu"] * math.cos(ALPHA) - math.sin(ALPHA)), rel=1e-9)
    assert (inv.rank, inv.unknowns) == (3, 3)  # the two rims are one row pair
    assert inv.residual < 1e-9


def test_inverse_at_rest_gives_the_hub_torque_and_contact_forces(rest):
    _check_at_rest(rest.inverse())


def test_inverse_at_a_settled_rest_agrees(m):
    settled = m.at().settle({"hub_motor": REF["torque"]})
    s = m.at(q={n: settled.q[n] for n in ("x", "y", "pitch", "hub")})
    inv = s.inverse()
    assert inv.torque["hub_motor"] == pytest.approx(REF["torque"], rel=1e-6)
    assert inv.contacts["tyre"].normal == pytest.approx(
        settled.contacts["tyre"].normal, abs=1e-4)


def test_a_posture_the_motor_cannot_hold_leaves_a_residual(m):
    """At home the chassis hangs plumb: nothing balances the hub torque the
    slope needs, and the solve says so rather than inventing a force."""
    inv = m.at().inverse()
    assert inv.residual > 0.1


def test_a_lifted_wheel_has_no_contact_rows(m):
    inv = m.at(q={"y": 1e-3, "pitch": REF["phi"]}).inverse()
    assert inv.contacts == {}
    assert inv.unknowns == 1


def test_mj_inverse_reads_the_solver_not_the_contact(m):
    """The trap: at the engine's own rest, MuJoCo's inverse dynamics reads
    the normal force off the penetration and has no static friction, so it
    cannot say what holds the wheel."""
    settled = m.at().settle({"hub_motor": REF["torque"]})
    data = mujoco.MjData(m.model)
    for name in ("x", "y", "pitch", "hub"):
        data.qpos[m.model.joint(name).qposadr[0]] = settled.q[name]
    mujoco.mj_forward(m.model, data)
    data.qacc[:] = 0.0
    mujoco.mj_inverse(m.model, data)
    hub = m.model.joint("hub").dofadr[0]
    assert abs(data.qfrc_inverse[hub] / PARAMS["N"] - REF["torque"]) > 1e-3


def test_mj_inverse_is_never_called(m, rest, monkeypatch):
    def refuse(*args):
        raise AssertionError("mj_inverse called on a state with contact")
    monkeypatch.setattr(mujoco, "mj_inverse", refuse)
    rest.inverse()
    rest.wrench("wheel")
    rest.settle({"hub_motor": REF["torque"]}, max_steps=600)
    rest.linearise()


def test_wrench_across_the_hub_counts_the_contact(rest):
    """The hub carries the motor's torque, which balances the friction's
    moment about the hub: only so once the contact's force is applied."""
    wrench = rest.wrench("wheel")
    assert wrench.torque[2] == pytest.approx(PARAMS["N"] * REF["torque"],
                                             rel=1e-9)
    assert wrench.force == pytest.approx(
        [0, PARAMS["m_w"] * PARAMS["g"] - M_G, 0], abs=1e-9)


# --- linearise ----------------------------------------------------------------
def test_linearise_keeps_the_rocking_mode_and_lists_the_solver_roots(rest):
    lin = rest.linearise()
    assert lin.stiffness is None
    assert lin.frequencies == pytest.approx([REF["freqs"][1]], rel=1e-4)
    assert round(lin.frequencies[0], 2) == 0.96
    # the solver's roots move with its stiffness: they are discarded, listed
    assert len(lin.discarded) >= 2
    stiff, soft = lin.discarded[:, 0], lin.discarded[:, 1]
    assert np.all(np.abs(stiff - soft) > 0.1 * np.abs(stiff))
    assert np.all(np.abs(stiff) > 50.0)
    # the rest: the rocking pair, and neutral directions (rolling, sliding)
    rocking = 2 * math.pi * REF["freqs"][1]
    assert sorted(abs(s) for s in lin.roots if abs(s) > 1.0) == pytest.approx(
        [rocking, rocking], rel=1e-4)
    assert len(lin.roots) + len(lin.discarded) == 2 * len(lin.dofs)


def test_the_solver_roots_move_between_solref_0_02_and_0_005(m, rest):
    """Run by hand at the two stiffnesses the box names: the rocking mode
    holds to 0.1 %, the contact's own roots move several-fold."""
    lin = rest.linearise()
    assert armature.state.LINEARISE_SOLREF == (0.005, 0.02)
    moved = np.abs(lin.discarded[:, 1]) / np.abs(lin.discarded[:, 0])
    assert np.all(np.abs(moved - 1) > 0.1)
    assert np.max(moved) > 2 or np.min(moved) < 0.5  # several-fold, mostly
    kept = [abs(s) for s in lin.roots if abs(s) > 1.0]
    assert max(kept) == pytest.approx(min(kept))  # the rocking pair alone


def test_a_servo_mode_is_kept_and_moves_only_with_its_gain():
    for k_hub in (300.0, 600.0):
        params = dict(PARAMS, k_hub=k_hub)
        expected = _reference(PARAMS, k_hub)["freqs"]
        lin = armature.compile(servo, params).at(
            q={"pitch": REF["phi"]}).linearise()
        assert lin.frequencies == pytest.approx(expected, rel=1e-4)
    assert _reference(PARAMS, 300.0)["freqs"][1] == pytest.approx(17.8, abs=0.1)


# --- validation ---------------------------------------------------------------
def _with(**change):
    def mechanism(p):
        out = incline(p)
        c = out[-2]
        fields = dict(name=c.name, body=c.body, shape=c.shape,
                      against=c.against, mu=c.mu, stiffness=c.stiffness,
                      damping=c.damping)
        fields.update(change)
        out[-2] = contact(**fields)
        return out
    return mechanism


@pytest.mark.parametrize("change, message", [
    (dict(body="ghost"), "contact 'tyre': body 'ghost' is not declared"),
    (dict(body="world"), "the world cannot be the moving body"),
    (dict(mu=-0.1), "mu -0.1 must be non-negative"),
    (dict(shape=shape("plane", pos=(0, 0, 0), axis=(0, 1, 0))),
     "a plane is fixed"),
    (dict(shape=shape("cone", pos=(0, 0, 0))), "kind 'cone' is not one of"),
    (dict(shape=shape("sphere", pos=(0, 0, 0))), "a sphere needs radius"),
    (dict(shape=shape("cylinder", pos=(0, 0, 0), axis=(0, 0, 2), radius=0.1,
                      half_length=0.02)), "axis .* is not a unit vector"),
    (dict(shape=shape("box", pos=(0, 0, 0), half_sizes=(0.1, 0, 0.1))),
     "half_sizes .* must be positive"),
    (dict(against=shape("plane", pos=(0, 0, 0), axis=(0, 1, 0), radius=1.0)),
     "against: a plane takes no radius"),
    (dict(stiffness=1e4), "a compliance acts at one point, so it takes a "
                          "sphere"),
    (dict(damping=3.0), "damping is given but there is no stiffness"),
])
def test_a_wrong_contact_is_named(change, message):
    with pytest.raises(DescriptionError, match=message):
        armature.compile(_with(**change), PARAMS)


def test_an_undefined_parameter_inside_a_shape_is_named():
    def mechanism(p):
        out = incline(p)
        out[-2] = contact("tyre", body="wheel",
                          shape=shape("sphere", pos=(0, 0, 0),
                                      radius=p["r_tyre"]),
                          against=out[-2].against, mu=p["mu"])
        return out
    with pytest.raises(DescriptionError,
                       match="contact 'tyre': shape uses parameter 'r_tyre'"):
        armature.compile(mechanism, PARAMS)


# --- against a fixed shape, and a load two contacts share --------------------
def ball_on_block(p):
    """A ball on an x-y carriage, resting on the top face of a fixed block
    (MuJoCo puts the ball first in the pair, as it orders by type)."""
    r = p["r"]
    return [
        body("cart", mass=p["m_cx"], com=(0, 0, 0), inertia=np.diag([1e-4] * 3)),
        body("ball", mass=p["m_w"], com=(0, 0, 0), inertia=np.diag([1e-3] * 3)),
        joint("x", "slide", parent="world", child="cart", axis=(1, 0, 0),
              point=(0, 0, 0), range=(-1, 1)),
        joint("y", "slide", parent="cart", child="ball", axis=(0, 1, 0),
              point=(0, 0, 0), range=(-1, 1)),
        contact("seat", body="ball", shape=shape("sphere", pos=(0, 0, 0),
                                                radius=r),
                against=shape("box", pos=(0, -r - 0.05, 0),
                              half_sizes=(0.2, 0.05, 0.2)),
                mu=p["mu"]),
        gravity((0, -p["g"], 0)),
    ]


def test_a_ball_on_a_fixed_block_pushes_up():
    params = {k: PARAMS[k] for k in ("r", "m_cx", "m_w", "mu", "g")}
    m = armature.compile(ball_on_block, params)
    s = m.at()
    data = s._data()
    assert data.contact.geom[0][0] == m.model.geom("seat").id  # ball first
    inv = s.inverse(loads={})
    seat = inv.contacts["seat"]
    assert seat.normal == pytest.approx(params["m_w"] * params["g"], rel=1e-12)
    assert seat.friction == pytest.approx(np.zeros(3), abs=1e-12)
    settled = s.settle()
    assert settled.contacts["seat"].normal == pytest.approx(
        params["m_w"] * params["g"], abs=1e-6)
    assert "contact 'seat'" in settled.constraints


def doubled(p):
    """The wheel declared twice on the same incline: two contacts that share
    one load in a way nothing decides."""
    out = incline(p)
    c = out[-2]
    out.insert(-1, contact("tyre2", body="wheel", shape=c.shape,
                           against=c.against, mu=c.mu))
    return out


def test_a_load_two_contacts_share_reads_nan_not_a_guess():
    inv = armature.compile(doubled, PARAMS).at(
        q={"pitch": REF["phi"]}).inverse()
    assert inv.torque["hub_motor"] == pytest.approx(REF["torque"], rel=1e-9)
    assert (inv.rank, inv.unknowns) == (3, 5)
    for name in ("tyre", "tyre2"):
        assert math.isnan(inv.contacts[name].normal)
        assert math.isnan(inv.contacts[name].margin)


def test_a_compliant_tyre_keeps_its_own_mode():
    """A compliance is physical: its bounce is kept, not varied with the
    solver's stiffness, so nothing moves and nothing is discarded."""
    s, _, _ = _sunk(armature.compile(tyre, TYRE))
    lin = s.linearise()
    assert len(lin.frequencies) == 3  # rocking, servo and the tyre's bounce
    assert lin.frequencies[-1] > 10.0
    assert len(lin.discarded) == 0