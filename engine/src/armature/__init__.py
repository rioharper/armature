"""Armature's engine: a mechanism description, compiled through MuJoCo and
queried on explicit, named states.

    def mechanism(p):
        return [body(...), joint(...), site(...), cable(...)]

    m = armature.compile(mechanism, PARAMS)
    s = m.at(q={"z": 0.01})
    s.linearise()

`m.model` is the compiled `MjModel`, for code that needs raw arrays.
"""

from .compiler import Compiled, compile
from .description import Description, describe
from .elements import (DescriptionError, body, cable, gravity, joint, site)
from .state import Linearised, State

__all__ = ["Compiled", "Description", "DescriptionError", "Linearised",
           "State", "body", "cable", "compile", "describe", "gravity",
           "joint", "site"]
