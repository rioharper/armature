"""Armature's engine: a mechanism description, compiled through MuJoCo and
queried on explicit, named states.

    def mechanism(p):
        return [body(...), joint(...), site(...), actuator(...)]

    m = armature.compile(mechanism, PARAMS)
    s = m.at(q={"elbow": 0.4})
    s.inverse(), s.settle(hold), s.linearise()

A closed chain adds `loop(name, a, b)`; `m.independent` names what `at()`
takes, and it solves the rest so every loop closes. A wheel or a foot adds
`contact(name, body=..., shape=shape(...), against=shape("plane", ...),
mu=...)`; `s.inverse()` reports what each touching contact carries.

    rigid = armature.reduce(mechanism, lock("elbow", 0.0, assumption="A3"))
    armature.compile(rigid, PARAMS).at().release(hold)
    armature.symbolic(rigid, PARAMS)

The reductions are `lock`, `couple`, `planar`, `lump` and `rigid`;
`release(hold, quantity=...)` sizes each one by name, and
`armature.account(m, coordinates)` fails a derivation whose coordinates are
not its variant's.

`m.model` is the compiled `MjModel`, for code that needs raw arrays.

`armature.sample(m, n, seed)` draws states uniformly over the independent
coordinates, loops closed and floating bodies inside a `pose_envelope`;
`sample_states` adds rates and accelerations within given limits. Each
result prints n and the seed.

A margin is slack, available minus required, over a named space:
`Margin(name, fn, unit, over=Space(q1=Interval(lo, hi), load=Direction("xy"),
case=Choice(CASES)))`, where `fn(point)` reads each axis by name and raises
`Infeasible(reason)` at a point outside the space. `armature.search(margin)`
returns its `Worst`: the least slack over a seeded Sobol set, every corner and
a Powell polish, with where, n, the seed, the pre-polish best and the coverage.
`Band("m2", BANDS)` searches a parameter's tolerance band, and
`state=Coordinates(mechanism, PARAMS, within=, poses=)` gives `fn` a ready
`p.state`, compiled with the point's band values; a point that cannot close
is rejected under the loop that refused it.

A spec-stage description writes its bodies as `point`, `rod`, `box`,
`cylinder` and `sphere`, joined by `compose`. `armature.review(mechanism,
PARAMS, directory, states)` writes the Milestone 0 review artifact: the
frames table and skeleton renders.
"""

from .assembly import ClosureError
from .coarse import box, compose, cylinder, point, rod, sphere
from .compiler import Compiled, compile
from .contact import ContactForce
from .description import Description, describe
from .elements import (DescriptionError, actuator, body, cable, contact,
                       gravity, joint, loop, shape, site)
from .review import Frames, Review, frames, render, review
from .sampler import (PoseEnvelope, Rejected, Samples, clearance,
                      pose_envelope, sample, sample_states)
from .search import (Band, Budget, Case, Choice, Coordinates, Direction,
                     Infeasible, Interval, Margin, Point, Space, Worst, search)
from .state import (Inverse, Jacobian, Linearised, Placement, Pose, Released,
                    Settled, State, Wrench)
from .symbolic import Symbolic, symbolic
from .variants import (AccountingError, Variant, account, couple, lock, lump,
                       massless, planar, reduce, rigid)

__all__ = ["Compiled", "Description", "DescriptionError", "Inverse",
           "Jacobian", "Linearised", "Placement", "Pose", "Released",
           "Settled", "State", "Symbolic", "Variant", "Wrench", "actuator",
           "body", "cable", "compile", "couple", "describe", "gravity", "joint",
           "lock", "loop", "reduce", "site", "symbolic"]
__all__ += ["Frames", "Review", "box", "compose", "cylinder", "frames", "point",
            "render", "review", "rod", "sphere"]
__all__ += ["AccountingError", "account", "lump", "massless", "planar",
            "rigid"]
__all__ += ["ContactForce", "contact", "shape"]
__all__ += ["ClosureError", "PoseEnvelope", "Rejected", "Samples", "clearance",
            "pose_envelope", "sample", "sample_states"]
__all__ += ["Budget", "Case", "Choice", "Direction", "Infeasible", "Interval",
            "Margin", "Point", "Space", "Worst", "search"]
__all__ += ["Band", "Coordinates"]
