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

`armature.equations(rigid, PARAMS)` forms M q̈ + C q̇ + g = τ on that view
by Kane's method (ADR 0012): closures as holonomic constraints, the
equations reduced onto the independent coordinates, springs and elastic
cables carried, nothing simplified; `numeric` lambdifies an expression and
`christoffel()` forms C on demand.

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
`state=Coordinates(mechanism, PARAMS, within=, poses=, rest_on=)` gives `fn`
a ready `p.state`, compiled with the point's band values and each `rest_on`
contact touching; a point that cannot close is rejected under the loop that
refused it. A margin's `check=`, its second evaluation, is evaluated at the
worst point and the pre-polish best, and `worst.check` says whether it agrees
with `fn` within `agree=`.

`armature.drive` sizes actuators from a mission (ADR 0006). A `Motor`
names the basis of every constant: `Kt(1.22, per="A_rms", side="output")`,
`Ke(9.6, per="V_rms/krpm", between="line", side="motor")`,
`Resistance(0.55, between="line")` and its `wiring`. `drive.check(motor,
n)` fails a Kt that disagrees with Ke by more than 2 %, or an envelope that
misses a published `Curve`. `drive.electrical(tau, omega, n, motor,
gearbox, driver)` takes one actuator's output samples to current, voltage,
copper loss and bus power, in Lee et al.'s power-invariant d-q convention.
`drive.envelope(motor, n, v_bus)` is the torque–speed envelope at a bus
voltage, and `drive.repeat` integrates the winding's thermal RC over a duty.
A mission's `drive.event` is forward-simulated on a copy of the model, each
motor coasting, shorted, flux-braking or following a torque profile, with
the bus stepped alongside.

`armature.ledger` reads a project's `ledger.toml` (ADR 0010), where every
input number lives once with its unit, band, status and provenance:
`ledger.load("mechanism")` is a plain SI dict for `compile`, and
`py -m armature.ledger check` reports each entry whose `as_written`
disagrees with its value, whose unit is not SI, or whose citation is
missing. It is imported on its own, never from here, and so is
`armature.gate` (ADR 0011). Every name here is imported the first time it
is read, so neither of them loads MuJoCo.

A spec-stage description writes its bodies as `point`, `rod`, `box`,
`cylinder` and `sphere`, joined by `compose`. `armature.review(mechanism,
PARAMS, directory, states)` writes the Milestone 0 review artifact: the
frames table and skeleton renders.
"""

import importlib
import sys
import types

# Each public name, by the submodule it comes from. A name is imported the
# first time it is read, so `import armature.ledger` or `armature.gate`
# loads neither MuJoCo nor SymPy, and the hook that calls the gate stays
# fast (#155). `drive` is a subpackage, bound by its own name.
_FROM = {
    "drive": ["drive"],
    "assembly": ["ClosureError"],
    "coarse": ["box", "compose", "cylinder", "point", "rod", "sphere"],
    "compiler": ["Compiled", "compile"],
    "contact": ["ContactForce"],
    "description": ["Description", "describe"],
    "elements": ["DescriptionError", "actuator", "body", "cable", "contact",
                 "gravity", "joint", "loop", "shape", "site"],
    "equations": ["Equations", "equations"],
    "review": ["Frames", "Review", "frames", "render", "review"],
    "sampler": ["PoseEnvelope", "Rejected", "Samples", "clearance",
                "pose_envelope", "sample", "sample_states"],
    "search": ["Band", "Budget", "Case", "Choice", "Confirmed",
               "Coordinates", "Direction", "Infeasible", "Interval",
               "Margin", "Point", "Space", "Worst", "search"],
    "state": ["Inverse", "Jacobian", "Linearised", "Placement", "Pose",
              "Released", "Settled", "State", "Wrench"],
    "symbolic": ["Symbolic", "symbolic"],
    "variants": ["AccountingError", "Variant", "account", "couple", "lock",
                 "lump", "massless", "planar", "reduce", "rigid"],
}
_SOURCE = {name: module for module, names in _FROM.items() for name in names}
# Submodules sharing a name with a function: `armature.search` and
# `armature.contact` are functions, as they were when this file imported
# every name, so the module the import system binds here on loading one is
# dropped.
_SHADOWED = (_FROM.keys() & _SOURCE.keys()) - {"drive"}


class _Package(types.ModuleType):
    """This package, its names imported as they are first read."""

    def __getattr__(self, name):
        if name not in _SOURCE:
            raise AttributeError(f"module {__name__!r} has no attribute "
                                 f"{name!r}")
        module = importlib.import_module(f".{_SOURCE[name]}", __name__)
        value = module if name == "drive" else getattr(module, name)
        self.__dict__[name] = value
        return value

    def __setattr__(self, name, value):
        if name in _SHADOWED and isinstance(value, types.ModuleType):
            return
        super().__setattr__(name, value)

    def __dir__(self):
        return sorted({*self.__dict__, *_SOURCE})


sys.modules[__name__].__class__ = _Package

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
__all__ += ["Band", "Confirmed", "Coordinates"]
__all__ += ["Equations", "equations"]
