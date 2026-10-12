"""Calling a mechanism description, and validating what it returns.

Validation runs before the first MjSpec call: a keyword MjSpec rejects leaves a
half-built element behind that breaks the next compile, and an error it reports
names an MJCF element rather than the description's. Every problem found is
reported at once, each naming the element at fault.
"""

from dataclasses import dataclass, fields, replace
from types import MappingProxyType

import numpy as np
import sympy as sp

from .elements import (FREE_COMPONENTS, JOINT_KINDS, WORLD, Actuator, Body,
                       Cable, DescriptionError, Gravity, Joint, Loop, Site)
from .variants import Couple, Lock, Variant

ELEMENTS = (Body, Joint, Site, Cable, Loop, Actuator, Gravity)

DEFAULT_GRAVITY = (0.0, 0.0, -9.81)
UNIT_TOL = 1e-9        # |‖axis‖ − 1| allowed, so (0, √½, √½) written in floats passes
INERTIA_TOL = 1e-12    # relative to the trace, for symmetry and the triangle inequality
LOOP_HOME_BOUND = 1e-6  # m: how far apart a loop's sites may be written at home,
    # the slack a settle allows; a metre-scale drawing rounded to six digits
    # passes, a typo does not


@dataclass(frozen=True)
class Description:
    """A validated mechanism description: its elements, by kind, in the order
    written. A variant's description also carries its name, its reductions,
    its locks keyed by coordinate, and its couples."""
    bodies: tuple
    joints: tuple
    sites: tuple
    cables: tuple
    loops: tuple
    actuators: tuple
    gravity: tuple
    params_used: frozenset
    variant: str = None
    reductions: tuple = ()
    locks: MappingProxyType = MappingProxyType({})
    couples: tuple = ()


def coordinate_joints(description):
    """Every name a lock can hold, mapped to (joint, component): a hinge or
    slide's own name with component None, and each free joint's six
    `name:component` names."""
    out = {}
    for j in description.joints:
        if j.kind == "free":
            out.update({f"{j.name}:{c}": (j, c) for c in FREE_COMPONENTS})
        else:
            out[j.name] = (j, None)
    return out


def tree_order(description):
    """The bodies parent before child, depth first, siblings in the order
    written: the order MuJoCo numbers them, and so the order of the
    coordinates."""
    parent = {j.child: j.parent for j in description.joints}
    children = {}
    for b in description.bodies:
        children.setdefault(parent[b.name], []).append(b)
    order, stack = [], list(reversed(children.get(WORLD, [])))
    while stack:
        b = stack.pop()
        order.append(b)
        stack.extend(reversed(children.get(b.name, [])))
    return order


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

    `mechanism` may be a variant, whose reductions are then checked and
    recorded. Raises `DescriptionError` listing every problem, each naming its
    element.
    """
    if isinstance(mechanism, Variant):
        return _reduce(describe(mechanism.mechanism, params), mechanism)
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
        if not isinstance(element, ELEMENTS):
            problems.append(f"{element!r} is not a mechanism element")
            continue
        for f in fields(element):
            for name in sorted(_symbols_in(getattr(element, f.name))
                               & p.undefined):
                problems.append(f"{_label(element)}: {f.name} uses parameter "
                                f"{name!r}, which is not defined")
    elements = [e for e in elements if isinstance(e, ELEMENTS)]

    by_kind = {kind: tuple(e for e in elements if isinstance(e, kind))
               for kind in ELEMENTS}
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
    sites = {s.name: s for s in by_kind[Site]}
    for loop in by_kind[Loop]:
        problems += _check_loop(loop, sites)
    joints = {j.name: j for j in by_kind[Joint]}
    for a in by_kind[Actuator]:
        problems += _check_actuator(a, joints)
    problems += [f"parameter {n!r} is defined but never used; the description "
                 f"lacks the element that reads it, or it is stale"
                 for n in sorted(set(p) - p.used)]
    if problems:
        raise DescriptionError(problems)

    gravity = by_kind[Gravity][0].vector if by_kind[Gravity] else DEFAULT_GRAVITY
    return Description(bodies=by_kind[Body], joints=by_kind[Joint],
                       sites=by_kind[Site], cables=by_kind[Cable],
                       loops=by_kind[Loop], actuators=by_kind[Actuator],
                       gravity=gravity,
                       params_used=frozenset(p.used))


def _reduce(description, variant):
    """`description` with the variant's reductions checked and recorded."""
    problems, locks, couples = [], {}, []
    held = coordinate_joints(description)
    for r in variant.reductions:
        owner = f"{r} in variant {variant.name!r}"
        if isinstance(r, Couple):
            problems += _check_couple(r, owner, held, couples)
            couples.append(r)
        if isinstance(r, Lock):
            joint, _ = held.get(r.coordinate, (None, None))
            if joint is None:
                problems.append(f"{owner}: no coordinate named "
                                f"{r.coordinate!r}; the description has "
                                f"{sorted(held)}")
                continue
            if r.coordinate in locks:
                problems.append(f"{owner}: {r.coordinate!r} is already locked")
            at = _num(r.at)
            lo, hi = ((None, None) if joint.range is None
                      else (_num(v) for v in joint.range))
            if at is None:
                problems.append(f"{owner}: the locked value must be a number")
            elif None not in (lo, hi) and not lo <= at <= hi:
                problems.append(f"{owner}: {at} lies outside the joint's "
                                f"range ({lo}, {hi})")
            locks[r.coordinate] = r
        if r.assumption is None or r.assumption == "":
            problems.append(f"{owner}: carries no assumption number")
    for c in couples:
        for name in (c.a, c.b):
            if name in locks:
                problems.append(f"{c} in variant {variant.name!r}: {name!r} "
                                f"is locked")
    if problems:
        raise DescriptionError(problems)
    return replace(description, variant=variant.name,
                   reductions=variant.reductions,
                   locks=MappingProxyType(locks), couples=tuple(couples))


def _check_couple(c, owner, held, earlier):
    problems = []
    for name in (c.a, c.b):
        joint, component = held.get(name, (None, None))
        if joint is None:
            problems.append(f"{owner}: no coordinate named {name!r}")
        elif component is not None:
            problems.append(f"{owner}: {name!r} is a floating body's "
                            f"component; a couple ties a hinge or a slide")
    if c.a == c.b:
        problems.append(f"{owner}: a coordinate cannot follow itself")
    if any(e.a == c.a for e in earlier):
        problems.append(f"{owner}: {c.a!r} already follows another "
                        f"coordinate")
    ratio = _num(c.ratio)
    if ratio is None or ratio == 0:
        problems.append(f"{owner}: the ratio must be a nonzero number")
    return problems


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
    if j.kind == "free":
        return problems + _check_free(j)
    if j.axis is None:
        problems.append(f"{owner}: a {j.kind} needs an axis")
    else:
        axis = _array(j.axis)
        if axis is not None and abs(np.linalg.norm(axis) - 1) > UNIT_TOL:
            problems.append(f"{owner}: axis {tuple(axis)} is not a unit vector "
                            f"(norm {np.linalg.norm(axis):.6g})")
    if j.range is None:
        problems.append(f"{owner}: a {j.kind} needs a range, its envelope")
        return problems
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


def _check_free(j):
    owner, problems = _label(j), []
    if j.parent != WORLD:
        problems.append(f"{owner}: a free joint hangs from the world, not "
                        f"{j.parent!r}; MuJoCo keeps free joints at the top "
                        f"level")
    for label, given in (("axis", j.axis is not None),
                         ("range", j.range is not None),
                         ("home value", _num(j.home) != 0.0),
                         ("spring", j.stiffness is not None
                          or j.rest is not None)):
        if given:
            problems.append(f"{owner}: a free joint takes no {label}; its "
                            f"home is the description's posture, and its "
                            f"envelope is the sampler's")
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


def _check_actuator(a, joints):
    owner, problems = _label(a), []
    if a.joint not in joints:
        problems.append(f"{owner}: joint {a.joint!r} is not declared")
    elif joints[a.joint].kind == "free":
        problems.append(f"{owner}: joint {a.joint!r} is free; an actuator "
                        f"drives a hinge or a slide")
    for label, value, allow_zero in (("gear", a.gear, False),
                                     ("rotor_inertia", a.rotor_inertia, True),
                                     ("torque_limit", a.torque_limit, False)):
        v = _num(value) if value is not None else None
        if v is not None and not (v >= 0 if allow_zero else v > 0):
            problems.append(f"{owner}: {label} {v} must be "
                            f"{'non-negative' if allow_zero else 'positive'}")
    return problems


def _check_loop(loop, sites):
    owner, problems = _label(loop), []
    ends = []
    for label, name in (("a", loop.a), ("b", loop.b)):
        if name not in sites:
            problems.append(f"{owner}: site {label} {name!r} is not declared")
        else:
            ends.append(sites[name].body)
    if len(ends) == 2 and ends[0] == ends[1]:
        problems.append(f"{owner}: both sites are on {ends[0]!r}; a loop "
                        f"closes two different bodies")
    if len(ends) == 2:  # written at home, the two sites must already meet
        a, b = _array(sites[loop.a].pos), _array(sites[loop.b].pos)
        gap = None if a is None or b is None else np.linalg.norm(a - b)
        if gap is not None and not gap <= LOOP_HOME_BOUND:
            problems.append(f"{owner}: does not close at home; sites "
                            f"{loop.a!r} and {loop.b!r} are {gap:.6g} m apart "
                            f"(bound {LOOP_HOME_BOUND:g} m)")
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
