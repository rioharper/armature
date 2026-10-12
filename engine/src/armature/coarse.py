"""Coarse bodies: mass, COM and inertia from primitive solids.

A spec-stage description is written in these: each helper returns a `Body`
whose mass, COM and inertia (about the COM, in base axes, at home) come from
the solid's dimensions and either its mass or its density, and `compose`
sums several into one body by the parallel-axis theorem. The description is
refined at derive and its bodies replaced at CAD; the elements around them do
not change.

Every formula is plain arithmetic on what it is given, so the helpers work
on SymPy symbols as well as floats, and the symbolic view reads exact closed
forms. A point, and a rod on its own line, have no inertia about themselves,
so a body made of one alone fails validation: MuJoCo refuses a moving body
without positive principal moments. Compose them with a solid, or write the
link as a cylinder.
"""

import math

import numpy as np
import sympy as sp

from .elements import Body, DescriptionError, _vector

ORTHONORMAL_TOL = 1e-9  # |RᵀR − I| allowed in a box's axes


def point(name, *, at, mass):
    """A point mass at `at`. It has no inertia about itself."""
    at = _vector(f"body {name!r}", "at", at)
    return Body(name, mass, at, _diag(0, 0, 0))


def rod(name, *, start, end, mass=None, linear_density=None):
    """A slender rod from `start` to `end`, with its `mass` or its
    `linear_density` (kg/m). m L²/12 about every axis across it, nothing
    along it."""
    owner = f"body {name!r}"
    start, end = _vector(owner, "start", start), _vector(owner, "end", end)
    d = _minus(end, start)
    length2 = _dot(d, d)
    _nonzero(owner, "the rod has no length", length2)
    m = _mass(owner, mass, linear_density,
              lambda: _sqrt(length2), "linear_density")
    # m/12 (L² E − d dᵀ): the transverse moment off the axis, none along it
    inertia = tuple(tuple(m * ((length2 if i == j else 0) - d[i] * d[j]) / 12
                          for j in range(3)) for i in range(3))
    return Body(name, m, _mid(start, end), inertia)


def box(name, *, center, size, mass=None, density=None, axes=None):
    """A solid box centred at `center`, with edges `size` = (a, b, c) along
    `axes`, a rotation whose columns are the box's edge directions in base
    axes (default: the base axes). m (b² + c²)/12 about its first edge
    direction, and so on round."""
    owner = f"body {name!r}"
    center = _vector(owner, "center", center)
    a, b, c = _vector(owner, "size", size)
    m = _mass(owner, mass, density, lambda: a * b * c, "density")
    principal = _diag(m * (b ** 2 + c ** 2) / 12, m * (a ** 2 + c ** 2) / 12,
                      m * (a ** 2 + b ** 2) / 12)
    if axes is None:
        return Body(name, m, center, principal)
    rotation = _rotation(owner, axes)
    return Body(name, m, center, _turned(rotation, principal))


def cylinder(name, *, start, end, radius, mass=None, density=None):
    """A solid cylinder whose axis runs from the centre of one end face,
    `start`, to the other, `end`. m r²/2 about its axis, and
    m (3r² + h²)/12 about every axis across it through the COM."""
    owner = f"body {name!r}"
    start, end = _vector(owner, "start", start), _vector(owner, "end", end)
    d = _minus(end, start)
    h2 = _dot(d, d)
    _nonzero(owner, "the cylinder has no length", h2)
    m = _mass(owner, mass, density,
              lambda: _pi(radius, h2, density) * radius ** 2 * _sqrt(h2),
              "density")
    across = m * (3 * radius ** 2 + h2) / 12
    along = m * radius ** 2 / 2
    # across·E + (along − across) u uᵀ, with u uᵀ = d dᵀ / h²
    inertia = tuple(tuple((across if i == j else 0)
                          + (along - across) * d[i] * d[j] / h2
                          for j in range(3)) for i in range(3))
    return Body(name, m, _mid(start, end), inertia)


def sphere(name, *, center, radius, mass=None, density=None):
    """A solid sphere: 2 m r²/5 about every axis."""
    owner = f"body {name!r}"
    center = _vector(owner, "center", center)
    m = _mass(owner, mass, density,
              lambda: 4 * _pi(radius, density) * radius ** 3 / 3, "density")
    moment = 2 * m * radius ** 2 / 5
    return Body(name, m, center, _diag(moment, moment, moment))


def compose(name, *parts):
    """One body, `name`, made of `parts` (bodies, from these helpers or
    `body`), rigidly joined as they stand at home: the masses summed, the COM
    their weighted mean, and each part's inertia moved to that COM by the
    parallel-axis theorem, I + m (|r|² E − r rᵀ) with r from the COM to the
    part's. The parts' own names are labels only."""
    owner = f"body {name!r}"
    if not parts:
        raise DescriptionError([f"{owner}: compose needs at least one part"])
    for part in parts:
        if not isinstance(part, Body):
            raise DescriptionError([f"{owner}: part {part!r} is not a body"])
    total = sum((p.mass for p in parts[1:]), parts[0].mass)
    com = tuple(sum(p.mass * p.com[k] for p in parts) / total
                for k in range(3))
    inertia = [[0] * 3 for _ in range(3)]
    for p in parts:
        r = _minus(p.com, com)
        r2 = _dot(r, r)
        for i in range(3):
            for j in range(3):
                inertia[i][j] += p.inertia[i][j] + p.mass * (
                    (r2 if i == j else 0) - r[i] * r[j])
    return Body(name, total, com, tuple(tuple(row) for row in inertia))


def _mass(owner, mass, density, measure, density_label):
    """The mass, given or as density × `measure()` (a volume or a length)."""
    if (mass is None) == (density is None):
        raise DescriptionError([f"{owner}: give its mass or its "
                                f"{density_label}, not "
                                f"{'both' if mass is not None else 'neither'}"])
    return mass if mass is not None else density * measure()


def _nonzero(owner, why, value):
    try:
        zero = float(value) == 0.0
    except TypeError:  # a symbol: the numbers are checked when they compile
        return
    if zero:
        raise DescriptionError([f"{owner}: {why}"])


def _rotation(owner, axes):
    try:
        rows = tuple(tuple(r) for r in axes)
    except TypeError:
        rows = ()
    if len(rows) != 3 or any(len(r) != 3 for r in rows):
        raise DescriptionError([f"{owner}: axes must be a 3x3 rotation, got "
                                f"{axes!r}"])
    try:
        numbers = np.array(rows, dtype=float)
    except TypeError:  # symbolic
        return rows
    if (np.max(np.abs(numbers.T @ numbers - np.eye(3))) > ORTHONORMAL_TOL
            or np.linalg.det(numbers) < 0):
        raise DescriptionError([f"{owner}: axes {numbers.tolist()} are not a "
                                f"rotation; their columns are the box's edge "
                                f"directions, orthonormal and right-handed"])
    return rows


def _turned(rotation, principal):
    """R I Rᵀ, in plain arithmetic."""
    return tuple(tuple(sum(rotation[i][k] * principal[k][k] * rotation[j][k]
                           for k in range(3)) for j in range(3))
                 for i in range(3))


def _diag(a, b, c):
    return ((a, 0, 0), (0, b, 0), (0, 0, c))


def _minus(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _mid(a, b):
    return tuple((x + y) / 2 for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _symbolic(*values):
    return any(isinstance(v, sp.Basic) for v in values)


def _sqrt(value):
    return sp.sqrt(value) if _symbolic(value) else math.sqrt(value)


def _pi(*values):
    return sp.pi if _symbolic(*values) else math.pi
