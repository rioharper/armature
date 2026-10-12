"""Armature's engine: a mechanism description, compiled through MuJoCo and
queried on explicit, named states.

    def mechanism(p):
        return [body(...), joint(...), site(...), actuator(...)]

    m = armature.compile(mechanism, PARAMS)
    s = m.at(q={"elbow": 0.4})
    s.inverse(), s.settle(hold), s.linearise()

    rigid = armature.reduce(mechanism, lock("elbow", 0.0, assumption="A3"))
    armature.compile(rigid, PARAMS).at().release(hold)
    armature.symbolic(rigid, PARAMS)

`m.model` is the compiled `MjModel`, for code that needs raw arrays.
"""

from .compiler import Compiled, compile
from .description import Description, describe
from .elements import (DescriptionError, actuator, body, cable, gravity, joint,
                       site)
from .state import (Inverse, Jacobian, Linearised, Placement, Pose, Released,
                    Settled, State, Wrench)
from .symbolic import Symbolic, symbolic
from .variants import Variant, lock, reduce

__all__ = ["Compiled", "Description", "DescriptionError", "Inverse",
           "Jacobian", "Linearised", "Placement", "Pose", "Released",
           "Settled", "State", "Symbolic", "Variant", "Wrench", "actuator",
           "body", "cable", "compile", "describe", "gravity", "joint", "lock",
           "reduce", "site", "symbolic"]
