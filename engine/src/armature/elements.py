"""The typed elements a mechanism description is built from.

Every number is written in the base frame at the home posture: a joint is an
axis direction and a point on it (a free joint only the point), a COM, site or
cable end is a position, and an inertia is a full tensor about the COM in base
axes. A loop closes two sites that coincide at home, and a contact sets a
body's shape against a fixed one. The compiler derives the body-local frames
MuJoCo needs.

Values are whatever the description's parameters were: floats when the truth
model compiles it, SymPy symbols when the derivation reads it. Nothing here
converts them, so the constructors check shape only; `describe` checks values.
"""

from dataclasses import dataclass
from typing import NamedTuple

WORLD = "world"
JOINT_KINDS = ("hinge", "slide", "free")
SHAPE_KINDS = ("sphere", "cylinder", "box", "plane")
# A free joint's scalar components, in the order its chain applies them: the
# point's base-frame position, then rotations about the body's own axes.
FREE_COMPONENTS = ("x", "y", "z", "rx", "ry", "rz")


class DescriptionError(ValueError):
    """The description is wrong; each problem names the element at fault."""

    def __init__(self, problems):
        self.problems = list(problems)
        lines = "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(f"the mechanism description has "
                         f"{len(self.problems)} problem(s):\n{lines}")


def _vector(owner, label, value):
    try:
        out = tuple(value)
    except TypeError:
        out = ()
    if len(out) != 3:
        raise DescriptionError([f"{owner}: {label} must be three numbers, "
                                f"got {value!r}"])
    return out


def _tensor(owner, value):
    try:
        rows = tuple(tuple(r) for r in value)
    except TypeError:
        rows = ()
    if len(rows) != 3 or any(len(r) != 3 for r in rows):
        raise DescriptionError([f"{owner}: inertia must be a full 3x3 tensor "
                                f"in base axes, got {value!r}"])
    return rows


def _end(owner, label, value):
    try:
        on, pos = value
    except (TypeError, ValueError):
        raise DescriptionError([f"{owner}: {label} must be (body, position), "
                                f"got {value!r}"]) from None
    return (on, _vector(owner, f"{label} position", pos))


@dataclass(frozen=True)
class Body:
    name: str
    mass: object
    com: tuple
    inertia: tuple

    def __post_init__(self):
        owner = f"body {self.name!r}"
        object.__setattr__(self, "com", _vector(owner, "com", self.com))
        object.__setattr__(self, "inertia", _tensor(owner, self.inertia))


@dataclass(frozen=True)
class Joint:
    name: str
    kind: str
    parent: str
    child: str
    axis: tuple
    point: tuple
    range: tuple
    home: object = 0.0
    stiffness: object = None
    rest: object = None

    def __post_init__(self):
        owner = f"joint {self.name!r}"
        if self.axis is not None:
            object.__setattr__(self, "axis", _vector(owner, "axis", self.axis))
        object.__setattr__(self, "point", _vector(owner, "point", self.point))
        if self.range is None:
            return
        try:
            lo, hi = self.range
        except (TypeError, ValueError):
            raise DescriptionError([f"{owner}: range must be (low, high), got "
                                    f"{self.range!r}"]) from None
        object.__setattr__(self, "range", (lo, hi))


@dataclass(frozen=True)
class Site:
    name: str
    body: str
    pos: tuple

    def __post_init__(self):
        object.__setattr__(self, "pos",
                           _vector(f"site {self.name!r}", "pos", self.pos))


@dataclass(frozen=True)
class Cable:
    name: str
    start: tuple
    end: tuple
    ea: object
    rest_length: object

    def __post_init__(self):
        owner = f"cable {self.name!r}"
        object.__setattr__(self, "start", _end(owner, "start", self.start))
        object.__setattr__(self, "end", _end(owner, "end", self.end))


@dataclass(frozen=True)
class Loop:
    name: str
    a: str
    b: str


class Shape(NamedTuple):
    """A contact shape at home, in the base frame. A tuple, so validation
    finds the parameters inside it."""
    kind: str
    pos: tuple
    axis: tuple = None
    radius: object = None
    half_length: object = None
    half_sizes: tuple = None


@dataclass(frozen=True)
class Contact:
    name: str
    body: str
    shape: Shape
    against: Shape
    mu: object
    stiffness: object = None
    damping: object = None

    def __post_init__(self):
        owner = f"contact {self.name!r}"
        for label in ("shape", "against"):
            if not isinstance(getattr(self, label), Shape):
                raise DescriptionError([f"{owner}: {label} must be made by "
                                        f"shape(...), got "
                                        f"{getattr(self, label)!r}"])


@dataclass(frozen=True)
class Actuator:
    name: str
    joint: str
    gear: object = 1.0
    rotor_inertia: object = 0.0
    torque_limit: object = None


@dataclass(frozen=True)
class Gravity:
    vector: tuple

    def __post_init__(self):
        object.__setattr__(self, "vector",
                           _vector("gravity", "vector", self.vector))


def body(name, *, mass, com, inertia):
    """A rigid body: its mass, its COM, and its inertia about the COM in base
    axes, all at home."""
    return Body(name, mass, com, inertia)


def joint(name, kind, *, parent, child, point, axis=None, range=None,
          home=0.0, stiffness=None, rest=None):
    """A hinge, a slide or a free joint from `parent` (a body or "world") to
    `child`.

    For a hinge or a slide, `axis` is a unit direction and `point` a point on
    it, at home. The joint's coordinate, named `name`, reads `home` at the home
    posture and is kept inside `range` (radians or metres; never degrees). A
    physical spring of `stiffness` (N·m/rad or N/m) rests at `rest`, which
    defaults to `home`.

    A free joint makes `child` a floating body; its parent is the world.
    `point` is a point fixed on the body, and the coordinate `name` is a
    `Placement`: where that point is, and how the body is turned from home.
    Its scalar components, which a variant can lock, are `name:x`, `name:y`
    and `name:z`, the point's base-frame position, then `name:rx`, `name:ry`
    and `name:rz`, turns about the body's own axes in that order.
    """
    return Joint(name, kind, parent, child, axis, point, range, home,
                 stiffness, rest)


def site(name, *, body, pos):
    """A named point on a body, at home."""
    return Site(name, body, pos)


def cable(name, *, start, end, ea, rest_length):
    """A straight, unilateral cable from `start` to `end`, each `(body, pos)`
    with `body` a body name or "world".

    It pulls with EA/rest_length per metre of stretch and carries nothing when
    slack.
    """
    return Cable(name, start, end, ea, rest_length)


def loop(name, a, b):
    """Close the chain: sites `a` and `b`, on different bodies, coincide at
    home and are held together at every posture, like a pin through both.

    It compiles as a site-based `connect`, which enforces the two sites
    themselves; a body-anchored one would take its second anchor from the
    home posture and pass an assembly error silently. `Compiled.at` closes
    every loop exactly, and the queries carry it as a constraint row whose
    force, on `a`'s body, is reported under `name`.
    """
    return Loop(name, a, b)


def shape(kind, *, pos, axis=None, radius=None, half_length=None,
          half_sizes=None):
    """A contact shape, at home in the base frame.

    - "sphere": centre `pos` and `radius`;
    - "cylinder": centre `pos`, `axis` (a unit direction), `radius` and
      `half_length` along the axis;
    - "box": centre `pos` and `half_sizes` along the base axes;
    - "plane": a point `pos` on it and its outward unit normal `axis`. A
      plane is fixed, so it is only ever what a contact is `against`: the
      floor, or an incline.
    """
    owner = f"{kind} shape"
    return Shape(kind, _vector(owner, "pos", pos),
                 None if axis is None else _vector(owner, "axis", axis),
                 radius, half_length,
                 None if half_sizes is None
                 else _vector(owner, "half_sizes", half_sizes))


def contact(name, *, body, shape, against, mu, stiffness=None, damping=None):
    """`body`'s `shape` touching `against`, a shape fixed to the world, with
    Coulomb friction coefficient `mu` (0 for a frictionless contact).

    Without `stiffness`, the contact is rigid: the compiler sets the
    stiffest contact MuJoCo keeps stable, a settle reports how far the
    shapes interpenetrate, and raises past 1e-6 m. With `stiffness` (N/m)
    and optionally `damping` (N·s/m), the contact is a physical compliance,
    such as a tyre's: at rest it sinks in by its normal force over
    `stiffness`. A compliance acts at one point, so it takes a sphere.

    The queries carry a touching contact as explicit rows at the points
    MuJoCo finds: `inverse` reports its normal force, its friction force and
    its friction-cone margin under `name`, never the solver's own forces.
    """
    return Contact(name, body, shape, against, mu, stiffness, damping)


def actuator(name, *, joint, gear=1.0, rotor_inertia=0.0, torque_limit=None):
    """A motor driving `joint` through a reduction of ratio `gear`.

    Its torque is the motor's: the joint feels `gear` times it. The rotor's
    inertia `rotor_inertia` (kg·m²) reaches the joint reflected, as gear²·J.
    `torque_limit` bounds the motor's torque (N·m; N on a slide); None leaves
    it unbounded.
    """
    return Actuator(name, joint, gear, rotor_inertia, torque_limit)


def gravity(vector):
    """The gravity vector in the base frame. Default: (0, 0, -9.81) m/s²."""
    return Gravity(vector)
