"""Reductions, and the variants that group them.

A reduction is one of the derivation's simplifications, written against the
full description and carrying the number of the assumption in `00_setup.md`
that makes it. A variant is a named set of reductions; the derivation owns it,
and a milestone names the variant it reads. The truth model always compiles the
full description, and `State.release` sizes each assumption against it: a lock,
a couple or `planar` by how far the coordinates it holds move when the full
description settles, a `lump` or a `rigid` by how much a quantity the
derivation names changes without it. `account` checks that a derivation's
coordinates are its variant's, so none leaves the equations unnamed.
"""

from dataclasses import dataclass

import sympy as sp
from sympy.core.function import AppliedUndef


@dataclass(frozen=True)
class Lock:
    coordinate: str
    at: object
    assumption: object

    def __str__(self):
        return (f"lock {self.coordinate!r} at {self.at} "
                f"(assumption {self.assumption})")


@dataclass(frozen=True)
class Couple:
    a: str
    b: str
    ratio: object
    assumption: object

    def __str__(self):
        return (f"couple {self.a!r} to {self.b!r} at {self.ratio} "
                f"(assumption {self.assumption})")


@dataclass(frozen=True)
class Planar:
    plane: str
    assumption: object

    def __str__(self):
        return f"planar {self.plane!r} (assumption {self.assumption})"


class _Massless:
    def __repr__(self):
        return "massless"


massless = _Massless()


@dataclass(frozen=True)
class Lump:
    body: str
    into: object
    assumption: object

    def __str__(self):
        return (f"lump {self.body!r} into {self.into!r} "
                f"(assumption {self.assumption})")


@dataclass(frozen=True)
class Rigid:
    element: str
    assumption: object

    def __str__(self):
        return f"rigid {self.element!r} (assumption {self.assumption})"


REDUCTIONS = (Lock, Couple, Planar, Lump, Rigid)
DISPLACED = (Lock, Couple, Planar)   # released by how far they let things move
QUANTIFIED = (Lump, Rigid)           # released by how much a quantity changes


@dataclass(frozen=True)
class Variant:
    name: str
    mechanism: object
    reductions: tuple


class AccountingError(AssertionError):
    """A derivation's coordinates are not its variant's; each problem names
    the coordinate."""

    def __init__(self, problems):
        self.problems = list(problems)
        lines = "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(f"coordinate accounting failed with "
                         f"{len(self.problems)} problem(s):\n{lines}")


def lock(coordinate, at, *, assumption):
    """Hold `coordinate` at `at`. It compiles as a weld: the joint is deleted
    and its child posed at `at`, which is exact, never a soft joint equality."""
    return Lock(coordinate, at, assumption)


def couple(a, b, ratio, *, assumption):
    """Tie coordinate `a` to `b`: a moves `ratio` times as far from its home
    as b does from its own, as through a belt or a gear pair. It compiles as
    a joint equality, and the queries carry it as a constraint row: `a` is
    then solved from `b`, and its force, the generalised force the coupling
    applies on `a`, is reported under `a`'s name."""
    return Couple(a, b, ratio, assumption)


def planar(plane, *, assumption):
    """Keep the mechanism in `plane` ("xy", "xz" or "yz", in base axes) by
    locking, at home, every coordinate that would leave it: each hinge whose
    axis is not the plane's normal, each slide with a component along it,
    and a floating body's translation along the normal and its turns about
    the two in-plane axes, so the body keeps two slides and one hinge.
    Whether a joint lies in the plane is judged at home. A coordinate
    another reduction already holds is left to it."""
    return Planar(plane, assumption)


def lump(body, into, *, assumption):
    """Move `body`'s mass elsewhere, leaving `body` massless.

    `into` is a neighbouring body (joined to `body` by a joint), which takes
    the mass and the inertia, rigidly, by the parallel-axis theorem: total
    mass and the COM at home are unchanged. A site makes it a point mass at
    that point, carried by the site's body (`body` itself or a neighbour),
    and its inertia about its own COM goes. `massless` drops it altogether.

    MuJoCo refuses a moving body without mass or inertia, so a body left
    without either compiles with `MASS_FLOOR` of its own, and the compiled
    variant is flagged `approximate`. The symbolic view is exact.
    """
    return Lump(body, into, assumption)


def rigid(element, *, assumption):
    """Make `element` rigid: a cable inextensible, or a joint with a spring
    locked where the spring rests.

    A rigid cable is held at its rest length, both ways, as a constraint row
    like a loop's: `at()` solves it, and `inverse` reports its tension under
    the cable's name, positive pulling; a negative tension says it would go
    slack there. A rigid joint compiles as a lock's weld.
    """
    return Rigid(element, assumption)


def reduce(mechanism, *reductions, name=None):
    """The variant of `mechanism` with `reductions` applied.

    `compile` and `symbolic` take a variant wherever they take a mechanism.
    Reducing a variant adds to its reductions. `name` defaults to the
    reductions, written out.
    """
    for r in reductions:
        if not isinstance(r, REDUCTIONS):
            raise TypeError(f"{r!r} is not a reduction")
    if isinstance(mechanism, Variant):
        mechanism, reductions = (mechanism.mechanism,
                                 mechanism.reductions + reductions)
    if name is None:
        name = "; ".join(str(r) for r in reductions)
    return Variant(name, mechanism, tuple(reductions))


def account(compiled, coordinates):
    """Check a derivation's `coordinates` against `compiled`'s, by name, and
    raise `AccountingError`, naming each coordinate at fault, unless they
    match.

    `coordinates` are names, SymPy symbols or dynamicsymbols, such as the
    symbolic view's `q`. Every independent coordinate of the variant must be
    there and nothing else may be; a coordinate a loop, couple or rigid
    cable solves may be left out, since its closure eliminates it. A
    coordinate leaves the equations only through a reduction.
    """
    names = [_name(c) for c in coordinates]
    d = compiled.description
    variant = f"variant {d.variant!r}" if d.variant else "the description"
    problems = [f"the derivation names {n!r} more than once"
                for n in sorted({n for n in names if names.count(n) > 1})]
    have, solved = set(names), set(compiled.dependent)
    for n in compiled.dofs:
        if n not in have and n not in solved:
            problems.append(
                f"{n!r} is a coordinate of {variant} but not of the "
                f"derivation; a coordinate leaves the equations only through "
                f"a reduction (lock, couple, planar or rigid), so add one or "
                f"put {n!r} back")
    for n in sorted(have - set(compiled.dofs)):
        if n in d.locks:
            problems.append(f"the derivation has {n!r}, which {variant} holds "
                            f"by {d.locked_by[n]}")
        else:
            problems.append(f"the derivation has {n!r}, which is not a "
                            f"coordinate of {variant}; it has "
                            f"{list(compiled.dofs)}")
    if problems:
        raise AccountingError(problems)


def _name(coordinate):
    if isinstance(coordinate, str):
        return coordinate
    if isinstance(coordinate, sp.Symbol):
        return coordinate.name
    if isinstance(coordinate, AppliedUndef):
        return coordinate.func.__name__
    raise TypeError(f"{coordinate!r} is not a coordinate: give a name, a "
                    f"SymPy symbol or a dynamicsymbol")
