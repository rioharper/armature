"""
mechanism.py — golden mechanism 3: a five-bar leg on a wheel, Ibex-shaped.

A torso rides an x-y carriage; its five-bar leg, driven at the hip by two
motors, carries a wheel at the pin, and the wheel's hub motor drives it
against the leg's link. The wheel rolls on a level floor and carries the
weight of everything but the carriage's rail cart. Self-tests in
mechanism_checks.py.
"""

import functools
import math

import numpy as np

import armature
from armature import actuator, body, contact, gravity, joint, loop, shape, site

from params import COM_AT, LEDGER, LINKS, PARAMS, PUSH_AT, TORSO_COM

# The mechanism's tolerance bands: its ledger section's.
BANDS = LEDGER.bands("mechanism")
MILESTONE = (0, "Milestone 0: the mechanism description")


def mechanism(p):
    """Ground is the floor, y = Cy − r. The torso rides slides x then y; the
    hip pivots A and E are on it; l2 and l4 meet at the pin C, where the
    wheel turns on l2. Gravity is −y and every hinge turns about z."""
    def at(name):
        return (p[f"{name}x"], p[f"{name}y"], 0)

    def com(start, end):
        return tuple(a + COM_AT * (b - a) for a, b in zip(at(start), at(end)))

    out = [body("cart", mass=p["m_cart"], com=(0, 0, 0),
                inertia=np.diag([1e-4] * 3)),
           body("torso", mass=p["m_torso"], com=TORSO_COM,
                inertia=np.diag([p["I_torso"]] * 3))]
    for name, (start, end, _, _) in LINKS.items():
        i = p[f"I_{name}"]
        out.append(body(name, mass=p[f"m_{name}"], com=com(start, end),
                        inertia=np.diag([i, i, i])))
    i_w = p["m_wheel"] * p["r"] ** 2 / 2
    out.append(body("wheel", mass=p["m_wheel"], com=at("C"),
                    inertia=np.diag([i_w, i_w, i_w])))
    span, rail = (-math.pi, math.pi), (-0.5, 0.5)
    floor = (0, p["Cy"] - p["r"], 0)
    out += [
        joint("x", "slide", parent="world", child="cart", axis=(1, 0, 0),
              point=(0, 0, 0), range=rail),
        joint("y", "slide", parent="cart", child="torso", axis=(0, 1, 0),
              point=(0, 0, 0), range=rail),
        joint("A", "hinge", parent="torso", child="l1", axis=(0, 0, 1),
              point=at("A"), range=span),
        joint("B", "hinge", parent="l1", child="l2", axis=(0, 0, 1),
              point=at("B"), range=span, stiffness=p["kB"]),
        joint("E", "hinge", parent="torso", child="l3", axis=(0, 0, 1),
              point=at("E"), range=span),
        joint("D", "hinge", parent="l3", child="l4", axis=(0, 0, 1),
              point=at("D"), range=span),
        joint("hub", "hinge", parent="l2", child="wheel", axis=(0, 0, 1),
              point=at("C"), range=(-100.0, 100.0)),
        site("C2", body="l2", pos=at("C")),
        site("C4", body="l4", pos=at("C")),
        site("push", body="torso", pos=PUSH_AT),
        loop("pin", "C2", "C4"),
        actuator("motor_A", joint="A", gear=p["N"], rotor_inertia=p["J"]),
        actuator("motor_E", joint="E", gear=p["N"], rotor_inertia=p["J"]),
        actuator("hub_motor", joint="hub", gear=p["N_hub"],
                 rotor_inertia=p["J"]),
        contact("tyre", body="wheel",
                shape=shape("cylinder", pos=at("C"), axis=(0, 0, 1),
                            radius=p["r"], half_length=p["w"]),
                against=shape("plane", pos=floor, axis=(0, 1, 0)),
                mu=p["mu"]),
        gravity((0, -p["g"], 0)),
    ]
    return out


@functools.cache
def truth():
    """The truth model: the description, compiled."""
    return armature.compile(mechanism, PARAMS)
