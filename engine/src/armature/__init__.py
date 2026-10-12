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

`m.model` is the compiled `MjModel`, for code that needs raw arrays.
"""

from .compiler import Compiled, compile
from .description import Description, describe
from .elements import (DescriptionError, actuator, body, cable, gravity, joint,
                       loop, site)
from .state import (Inverse, Jacobian, Linearised, Placement, Pose, Released,
                    Settled, State, Wrench)
from .symbolic import Symbolic, symbolic
from .variants import Variant, couple, lock, reduce

__all__ = ["Compiled", "Description", "DescriptionError", "Inverse",
           "Jacobian", "Linearised", "Placement", "Pose", "Released",
           "Settled", "State", "Symbolic", "Variant", "Wrench", "actuator",
           "body", "cable", "compile", "couple", "describe", "gravity", "joint",
           "lock", "loop", "reduce", "site", "symbolic"]
