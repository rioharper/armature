"""The typed elements a mechanism description is built from.

Every number is written in the base frame at the home posture: a joint is an
axis direction and a point on it, a COM, site or cable end is a position, and an
inertia is a full tensor about the COM in base axes. The compiler derives the
body-local frames MuJoCo needs.

Values are whatever the description's parameters were: floats when the truth
model compiles it, SymPy symbols when the derivation reads it. Nothing here
converts them, so the constructors check shape only; `describe` checks values.
"""

from dataclasses import dataclass

WORLD = "world"
JOINT_KINDS = ("hinge", "slide")


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
        object.__setattr__(self, "axis", _vector(owner, "axis", self.axis))
        object.__setattr__(self, "point", _vector(owner, "point", self.point))
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
class Gravity:
    vector: tuple

    def __post_init__(self):
        object.__setattr__(self, "vector",
                           _vector("gravity", "vector", self.vector))


def body(name, *, mass, com, inertia):
    """A rigid body: its mass, its COM, and its inertia about the COM in base
    axes, all at home."""
    return Body(name, mass, com, inertia)


def joint(name, kind, *, parent, child, axis, point, range, home=0.0,
          stiffness=None, rest=None):
    """A hinge or a slide from `parent` (a body or "world") to `child`.

    `axis` is a unit direction and `point` a point on it, at home. The joint's
    coordinate, named `name`, reads `home` at the home posture and is kept
    inside `range` (radians or metres; never degrees). A physical spring of
    `stiffness` (N·m/rad or N/m) rests at `rest`, which defaults to `home`.
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


def gravity(vector):
    """The gravity vector in the base frame. Default: (0, 0, -9.81) m/s²."""
    return Gravity(vector)
