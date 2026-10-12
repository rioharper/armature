"""Armature's engine: a mechanism description, compiled through MuJoCo and
queried on explicit, named states.

    def mechanism(p):
        return [body(...), joint(...), site(...), actuator(...)]

    m = armature.compile(mechanism, PARAMS)
    s = m.at(q={"elbow": 0.4})
    s.inverse(), s.settle(hold), s.linearise()

A closed chain adds `loop(name, a, b)`; `m.independent` names what `at()`
takes, and it solves the rest so every loop closes.

    rigid = armature.reduce(mechanism, lock("elbow", 0.0, assumption="A3"))
    armature.compile(rigid, PARAMS).at().release(hold)
    armature.symbolic(rigid, PARAMS)

The reductions are `lock`, `couple`, `planar`, `lump` and `rigid`;
`release(hold, quantity=...)` sizes each one by name, and
`armature.account(m, coordinates)` fails a derivation whose coordinates are
not its variant's.

`m.model` is the compiled `MjModel`, for code that needs raw arrays.

A spec-stage description writes its bodies as `point`, `rod`, `box`,
`cylinder` and `sphere`, joined by `compose`. `armature.review(mechanism,
PARAMS, directory, states)` writes the Milestone 0 review artifact: the
frames table and skeleton renders.
"""

from .coarse import box, compose, cylinder, point, rod, sphere
from .compiler import Compiled, compile
from .description import Description, describe
from .elements import (DescriptionError, actuator, body, cable, gravity, joint,
                       loop, site)
from .review import Frames, Review, frames, render, review
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
