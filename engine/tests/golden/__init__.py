"""The golden mechanisms (ADR 0008), each a project-form directory.

Each directory's `mechanism.py` does `from params import ...`, as a project's
does, so this loads each one in-process with its own `params.py` standing in
as `params`, under unique module names: `golden.arm_2r` is that directory's
mechanism module, its `params` the parameter module. The known answers are in
`answers.py`, beside the directories and never inside one.
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ("arm_2r", "cable_platform", "wheel_leg", "parallelogram",
         "spring_cable")


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load(name):
    """The golden project `name`'s mechanism module, its params module as
    `.params`."""
    params = _module(HERE / name / "params.py", f"golden.{name}.params")
    shadowed = sys.modules.get("params")
    sys.modules["params"] = params
    try:
        mechanism = _module(HERE / name / "mechanism.py", f"golden.{name}")
    finally:
        if shadowed is None:
            del sys.modules["params"]
        else:
            sys.modules["params"] = shadowed
    mechanism.params = params
    return mechanism


arm_2r, cable_platform, wheel_leg, parallelogram, spring_cable = map(load,
                                                                    NAMES)
