"""Rotations: a turn about an axis, and a floating body's orientation from
the turns its chain applies."""

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
