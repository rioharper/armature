"""Rotations: a turn about an axis, a floating body's orientation from the
turns its chain applies, and the angular velocity of those turns' rates."""

import numpy as np

AXES = np.eye(3)


def floating_rotation(held, free):
    """A floating body's orientation from its turns, keyed by component: the
    `held` ones first, then the `free` ones, each in x, y, z order about the
    body's own axes, as the compiled chain applies them."""
    rot = np.eye(3)
    for turns in (held, free):
        for i, c in enumerate(("rx", "ry", "rz")):
            if c in turns:
                rot = rot @ turn(AXES[i], turns[c])
    return rot


def turn(axis, angle):
    """The rotation by `angle` about unit `axis` (Rodrigues)."""
    k = np.array([[0, -axis[2], axis[1]],
                  [axis[2], 0, -axis[0]],
                  [-axis[1], axis[0], 0]])
    return np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * k @ k


def turn_axes(angles):
    """E, with ω = E φ̇ the angular velocity (base axes) of turns `angles`
    about the body's own x, y, z in order, at rates φ̇: each column is its
    turn's axis, carried by the turns before it."""
    axes, rot = np.zeros((3, 3)), np.eye(3)
    for i, angle in enumerate(angles):
        axes[:, i] = rot @ AXES[i]
        rot = rot @ turn(AXES[i], angle)
    return axes


def turn_drift(angles, rates):
    """Ė φ̇, so ω̇ = E φ̈ + Ė φ̇: each turn's axis swings with the angular
    velocity of the turns before it."""
    axes, omega, drift = turn_axes(angles), np.zeros(3), np.zeros(3)
    for i, rate in enumerate(rates):
        drift += rate * np.cross(omega, axes[:, i])
        omega = omega + rate * axes[:, i]
    return drift
