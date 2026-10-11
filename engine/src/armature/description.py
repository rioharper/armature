"""Calling a mechanism description, and validating what it returns.

Validation runs before the first MjSpec call: a keyword MjSpec rejects leaves a
half-built element behind that breaks the next compile, and an error it reports
names an MJCF element rather than the description's. Every problem found is
reported at once, each naming the element at fault.
"""

from dataclasses import dataclass, fields

import numpy as np
import sympy as sp

from .elements import (JOINT_KINDS, WORLD, Body, Cable, DescriptionError,
                       Gravity, Joint, Site)

DEFAULT_GRAVITY = (0.0, 0.0, -9.81)
UNIT_TOL = 1e-9        # |‖axis‖ − 1| allowed, so (0, √½, √½) written in floats passes
INERTIA_TOL = 1e-12    # relative to the trace, for symmetry and the triangle inequality


@dataclass(frozen=True)
class Description:
    """A validated mechanism description: its elements, by kind, in the order
    written."""
    bodies: tuple
    joints: tuple
    sites: tuple
    cables: tuple
    gravity: tuple
    params_used: frozenset


class _Params:
    """The parameters as the description sees them.

    A name the parameters do not define reads as a SymPy symbol of that name
    rather than raising, so the element that used it can be named afterwards.
    """

    def __init__(self, values):
        self._values = dict(values)
        self.used, self.undefined = set(), set()

    def __getitem__(self, key):
        if key in self._values:
            self.used.add(key)
            return self._values[key]
        self.undefined.add(key)
        return sp.Symbol(key)

    def __contains__(self, key):
        return key in self._values

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return self._values.keys()


def _label(element):
    return f"{type(element).__name__.lower()} {getattr(element, 'name', '')!r}"


def _symbols_in(value):
    if isinstance(value, sp.Basic):
        return {s.name for s in value.free_symbols}
    if isinstance(value, (tuple, list, np.ndarray)):
        return set().union(*(_symbols_in(v) for v in value)) if len(value) else set()
    return set()


def _num(value):
    """`value` as a float, or None where it is not a number (a symbol)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _array(values):
    nums = [_num(v) for v in np.ravel(np.asarray(values, dtype=object))]
    if any(n is None for n in nums):
        return None
    return np.array(nums).reshape(np.shape(np.asarray(values, dtype=object)))


def describe(mechanism, params):
    """Call `mechanism(p)` on `params` and validate what it returns.

    Raises `DescriptionError` listing every problem, each naming its element.
    """
    p = _Params(params)
    try:
        elements = list(mechanism(p))
    except DescriptionError as err:
        extra = [f"parameter {n!r} is used but not defined"
                 for n in sorted(p.undefined)]
        raise DescriptionError(err.problems + extra) from None
    except Exception as err:
        if not p.undefined:
            raise
        raise DescriptionError(
            [f"parameter {n!r} is used but not defined (the description "
             f"failed on it: {type(err).__name__}: {err})"
             for n in sorted(p.undefined)]) from err

    problems = []
    for element in elements:
        if not isinstance(element, (Body, Joint, Site, Cable, Gravity)):
            problems.append(f"{element!r} is not a mechanism element")
            continue
        for f in fields(element):
            for name in sorted(_symbols_in(getattr(element, f.name))
                               & p.undefined):
                problems.append(f"{_label(element)}: {f.name} uses parameter "
                                f"{name!r}, which is not defined")
    elements = [e for e in elements
                if isinstance(e, (Body, Joint, Site, Cable, Gravity))]

    by_kind = {kind: tuple(e for e in elements if isinstance(e, kind))
               for kind in (Body, Joint, Site, Cable, Gravity)}
    problems += _check_names(elements)
    if len(by_kind[Gravity]) > 1:
        problems.append(f"gravity is declared {len(by_kind[Gravity])} times")
    bodies = {b.name: b for b in by_kind[Body]}
    for b in by_kind[Body]:
        problems += _check_body(b)
    for j in by_kind[Joint]:
        problems += _check_joint(j, bodies)
    problems += _check_tree(by_kind[Body], by_kind[Joint])
    for s in by_kind[Site]:
        if s.body not in bodies and s.body != WORLD:
            problems.append(f"site {s.name!r}: body {s.body!r} is not declared")
    for c in by_kind[Cable]:
        problems += _check_cable(c, bodies)
    if problems:
        raise DescriptionError(problems)

    gravity = by_kind[Gravity][0].vector if by_kind[Gravity] else DEFAULT_GRAVITY
    return Description(by_kind[Body], by_kind[Joint], by_kind[Site],
                       by_kind[Cable], gravity, frozenset(p.used))


def _check_names(elements):
    problems, seen = [], {}
    for e in elements:
        if isinstance(e, Gravity):
            continue
        if not isinstance(e.name, str) or not e.name:
            problems.append(f"{_label(e)}: a name must be a non-empty string")
        elif e.name == WORLD:
            problems.append(f"{_label(e)}: {WORLD!r} is reserved for the base")
        elif e.name in seen:
            problems.append(f"{_label(e)}: the name is already used by "
                            f"{_label(seen[e.name])}")
        else:
            seen[e.name] = e
    return problems


def _check_body(b):
    owner, problems = _label(b), []
    mass = _num(b.mass)
    if mass is not None and not mass > 0:
        problems.append(f"{owner}: mass {mass} must be positive")
    inertia = _array(b.inertia)
    if inertia is None:
        return problems
    scale = max(abs(np.trace(inertia)), np.finfo(float).tiny)
    if np.max(np.abs(inertia - inertia.T)) > INERTIA_TOL * scale:
        problems.append(f"{owner}: inertia is not symmetric")
        return problems
    moments = np.linalg.eigvalsh(inertia)
    if moments[0] <= 0:
        problems.append(f"{owner}: inertia is not positive-definite "
                        f"(principal moments {moments})")
    elif moments[0] + moments[1] < moments[2] * (1 - INERTIA_TOL):
        problems.append(f"{owner}: inertia's principal moments {moments} break "
                        f"the triangle inequality A + B >= C; no rigid body "
                        f"has them")
    return problems


def _check_joint(j, bodies):
    owner, problems = _label(j), []
    if j.kind not in JOINT_KINDS:
        problems.append(f"{owner}: kind {j.kind!r} is not one of {JOINT_KINDS}")
    if j.parent != WORLD and j.parent not in bodies:
        problems.append(f"{owner}: parent {j.parent!r} is not declared")
    if j.child not in bodies:
        problems.append(f"{owner}: child {j.child!r} is not a declared body")
    if j.parent == j.child:
        problems.append(f"{owner}: parent and child are both {j.child!r}")
    axis = _array(j.axis)
    if axis is not None and abs(np.linalg.norm(axis) - 1) > UNIT_TOL:
        problems.append(f"{owner}: axis {tuple(axis)} is not a unit vector "
                        f"(norm {np.linalg.norm(axis):.6g})")
    lo, hi, home = _num(j.range[0]), _num(j.range[1]), _num(j.home)
    if lo is not None and hi is not None:
        if not lo < hi:
            problems.append(f"{owner}: range ({lo}, {hi}) is empty")
        elif home is not None and not lo <= home <= hi:
            problems.append(f"{owner}: home {home} lies outside range "
                            f"({lo}, {hi})")
    k = _num(j.stiffness) if j.stiffness is not None else None
    if k is not None and k < 0:
        problems.append(f"{owner}: stiffness {k} is negative")
    if j.rest is not None and j.stiffness is None:
        problems.append(f"{owner}: rest is given but there is no spring")
    return problems


def _check_tree(bodies, joints):
    """Every body hangs from the world through one parent."""
    problems, parent = [], {}
    for b in bodies:
        into = [j for j in joints if j.child == b.name]
        parents = {j.parent for j in into}
        if not into:
            problems.append(f"body {b.name!r}: no joint connects it to anything;"
                            f" fold a welded part into its neighbour's mass "
                            f"and inertia, or give it a joint")
        elif len(parents) > 1:
            names = ", ".join(f"{j.name!r} from {j.parent!r}" for j in into)
            problems.append(f"body {b.name!r}: has more than one parent "
                            f"(joints {names})")
        else:
            parent[b.name] = parents.pop()
    for name in parent:
        seen, at = {name}, parent[name]
        while at in parent and at not in seen:
            seen.add(at)
            at = parent[at]
        if at != WORLD:
            problems.append(f"body {name!r}: unreachable from the world (its "
                            f"chain of parents ends at {at!r})")
    return problems


def _check_cable(c, bodies):
    owner, problems = _label(c), []
    for label, (on, _) in (("start", c.start), ("end", c.end)):
        if on != WORLD and on not in bodies:
            problems.append(f"{owner}: {label} body {on!r} is not declared")
    if c.start[0] == WORLD and c.end[0] == WORLD:
        problems.append(f"{owner}: both ends are on the world")
    for label, value in (("ea", c.ea), ("rest_length", c.rest_length)):
        v = _num(value)
        if v is not None and not v > 0:
            problems.append(f"{owner}: {label} {v} must be positive")
    return problems
