"""The golden mechanisms (ADR 0008), each a project-form directory.

Each directory's `mechanism.py` does `from params import ...`, as a project's
does, so this loads each one in-process with its own `params.py` standing in
as `params`, under unique module names: `golden.arm_2r` is that directory's
mechanism module, its `params` the parameter module. A project with a
`missions.py` and a `drive.py` has them loaded the same way, as its
`missions` and `drive`. The known answers are in
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


PARTS = ("params", "mechanism", "missions", "drive")  # in import order


def load(name):
    """The golden project `name`'s mechanism module, its params module as
    `.params`, and its missions and drive modules, where it has them, as
    `.missions` and `.drive`."""
    shadowed = {part: sys.modules.get(part) for part in PARTS}
    loaded = {}
    try:
        for part in PARTS:
            path = HERE / name / f"{part}.py"
            if path.is_file():
                own = f"golden.{name}" + ("" if part == "mechanism"
                                          else f".{part}")
                loaded[part] = sys.modules[part] = _module(path, own)
    finally:
        for part, module in shadowed.items():
            if module is None:
                sys.modules.pop(part, None)
            else:
                sys.modules[part] = module
    mechanism = loaded.pop("mechanism")
    for part, module in loaded.items():
        setattr(mechanism, part, module)
    return mechanism


arm_2r, cable_platform, wheel_leg, parallelogram, spring_cable = map(load,
                                                                    NAMES)
