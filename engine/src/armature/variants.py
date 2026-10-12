"""Reductions, and the variants that group them.

A reduction is one of the derivation's simplifications, written against the
full description and carrying the number of the assumption in `00_setup.md`
that makes it. A variant is a named set of reductions; the derivation owns it,
and a milestone names the variant it reads. The truth model always compiles the
full description, and `State.release` settles it to size each assumption.
"""

from dataclasses import dataclass


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
class Variant:
    name: str
    mechanism: object
    reductions: tuple


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


def reduce(mechanism, *reductions, name=None):
    """The variant of `mechanism` with `reductions` applied.

    `compile` and `symbolic` take a variant wherever they take a mechanism.
    Reducing a variant adds to its reductions. `name` defaults to the
    reductions, written out.
    """
    for r in reductions:
        if not isinstance(r, (Lock, Couple)):
            raise TypeError(f"{r!r} is not a reduction")
    if isinstance(mechanism, Variant):
        mechanism, reductions = (mechanism.mechanism,
                                 mechanism.reductions + reductions)
    if name is None:
        name = "; ".join(str(r) for r in reductions)
    return Variant(name, mechanism, tuple(reductions))
