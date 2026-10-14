"""Events: uncommanded motion, forward-simulated (ADR 0006).

An event is a mission's segment that is simulated, not prescribed: a fall,
an e-stop, braking at speed, a power loss. It starts from a state, or from
partway through the segment before it, and runs for its `duration` with
each actuator in a mode:

    event(after(lift, 0.4), {"hip": "short", "knee": "coast"}, 0.5)

The simulation runs on a copy of the compiled model with the integrator
`implicitfast` at the event's `timestep`; the engine's own model keeps Euler,
which `settle` needs. Contact is MuJoCo's own, through the compiled pairs,
and loads are forces at named sites, applied where they act each step.

Each mode is a d-q current i in the winding, from the motor's back-EMF
E = Ke·ω_m and the bus voltage V, with R_φ at the winding's temperature
(Lee et al.'s power-invariant convention, as `electrical` reads it), so the
motor's torque is Kt·i:

- **short**: the phases tied together, i = −E/R_φ, a joint damping
  c = N²·Kt·Ke/(R_φ·η_b), the gearbox's back-driven friction included (see
  below). Its heat is all the winding's; none reaches the bus.
- **coast**: the bridge off. No current flows until E passes k_mod·V, where
  the bridge's diodes conduct, i = −(|E| − k_mod·V)/R_φ against the motion,
  and the motor regenerates into the bus whether its driver is on or not,
  through the driver's efficiency, as the electrical model reads any
  regeneration.
- **flux_brake**: the driver brakes as hard as it can without drawing on
  the bus: the short's current up to its limit, the lower of the motor's
  and the driver's `i_peak`, and the diodes' past that. At speed, where the
  short's current would pass the limit, the rest of the back-EMF drives
  power into the bus, which rises to the driver's flux-brake onset, and its
  flux brake holds it there while its capacity lasts. The switch is on
  current, not on the bus: a short's current puts no power on the bus, so
  a mode that braked as a short until the onset could never reach it.
- **a torque profile**: `τ(t)`, a callable of the time into the event, or
  a number, the motor torque as a trace reports it, applied through the
  gear as `qfrc_applied`.

A short's or a coasting motor's driver is off, so its flux brake cannot
act: `Trace.driven` says so per sample, and `charge` reads it. The braking
modes reach the joint through the gearbox back-driven, at N/η_b, so the
damping a short puts on its joint is N²·Kt·Ke/(R_φ·η_b), and the electrical
model, which takes the load's share of the rotor's torque at η_b/N, reads
back the current the mode set: a short reads 0 V at its winding, and puts
nothing on the bus. Only the rotor's own inertia torque, which the engine
reflects through a lossless gear, crosses the gearbox unscaled: the current
read back is off by (1 − η_b)·J_m·ω̇_m/Kt. A self-locking gearbox, η_b = 0,
does not back-drive at all; lock its joint for the event instead.

The bus is stepped with the mechanics, since a coasting motor's diodes and
a braking driver's flux brake both act on the bus voltage as it is: each
step, every actuator's bus power at the step's start, through the
electrical model, is held over the step and integrated with the clamps
exactly, as `charge` integrates a substep. The bus starts where the mission
left it (`trace` charges the segments before the event), or at V_s.

Every event is run twice, at its timestep and at half of it; `trace`
carries the first in its samples and reports both as a `Simulated`.
"""

import copy
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

import mujoco
import numpy as np

from ..assembly import tangent
from ..contact import from_solver
from ..state import State, _frozen, _load_force
from .bus import (BRAKE, SOURCE, _brake_capacity, _flux_capacity, _levels,
                  _substep)
from .electrical import (_current_limit, _electrical, _hot, _positive,
                         _resolve)

EVENT_STEP = 1e-4  # s: an event's timestep, unless it gives one; a shorted
    # flywheel whose time constant is 1 s reads exp(−t) to 5e-5 at 1 s
MODES = ("coast", "short", "flux_brake")
PASSIVE = ("coast", "short")  # modes whose driver is off


@dataclass(frozen=True, eq=False)
class After:
    """Partway through `segment`: at `fraction` of its duration, in [0, 1];
    make one with `after`."""
    segment: object
    fraction: float


def after(segment, fraction):
    """The state `fraction` (0 to 1, as an `Interval` axis gives it) of the
    way through `segment`, posture and rates both, for an event to start
    from: an e-stop partway through a move inherits its rates. In a mission,
    `segment` is the one just before the event, which then stops there; an
    event first in a mission may start after a segment outside it, which is
    run on its own."""
    if isinstance(segment, Event) or not hasattr(segment, "_profile"):
        raise TypeError(f"after takes a move, a hold or a followed q(t); got "
                        f"{segment!r}")
    fraction = float(fraction)
    if not 0 <= fraction <= 1:
        raise ValueError(f"after's fraction lies in [0, 1]; got {fraction}")
    return After(segment, fraction)


@dataclass(frozen=True, eq=False)
class Event:
    """A forward-simulated segment; make one with `event`."""
    start: object
    modes: Mapping
    duration: float
    loads: Mapping
    timestep: float


def event(start, modes, duration, loads=None, timestep=EVENT_STEP):
    """`duration` (s) of motion forward-simulated from `start`, each
    actuator in its mode under `loads`, at `timestep` (s).

    `start` is a `State`, a mapping of independent coordinates (at rest), or
    `after(segment, fraction)`. `modes` maps every actuator of the compiled
    model to `"coast"`, `"short"`, `"flux_brake"`, or a torque profile: a
    callable of the time into the event, or a number, the motor torque
    (N·m, motor side) as a trace gives it."""
    if not isinstance(modes, Mapping):
        raise TypeError(f"an event's modes map each actuator to a mode; got "
                        f"{modes!r}")
    for name, mode in modes.items():
        if not (mode in MODES or callable(mode)
                or isinstance(mode, (int, float))):
            raise ValueError(f"actuator {name!r}'s mode is one of "
                             f"{', '.join(repr(m) for m in MODES)}, or a "
                             f"torque profile, a callable of t or a number; "
                             f"got {mode!r}")
    timestep = _positive(timestep, "an event's timestep")
    duration = _positive(duration, "an event's duration")
    return Event(start, MappingProxyType(dict(modes)), duration,
                 MappingProxyType(dict(loads or {})), timestep)


@dataclass(frozen=True)
class Run:
    """One run of an event at `timestep` (s): `trace`, a `Trace` of the
    event alone, its t from the event's start; and at each of its samples
    the bus voltage `v` (V) the simulation stepped with it, and `contacts`,
    what each touching contact carried, as `ContactForce`s from MuJoCo's
    solver."""
    timestep: float
    trace: object
    v: np.ndarray
    contacts: tuple


class Moved(NamedTuple):
    """How far halving an event's timestep moved it, at the coarser run's
    samples: each actuator's largest change in `torque` (N·m) and in
    `speed` (rad/s), both motor side, and the bus's in `v` (V)."""
    torque: Mapping
    speed: Mapping
    v: float


@dataclass(frozen=True)
class Simulated:
    """Mission segment `segment`, an event, run at its timestep (`run`,
    whose samples the mission's trace carries) and at half of it
    (`half`)."""
    segment: int
    run: Run
    half: Run

    @property
    def moved(self):
        coarse, fine = self.run.trace, self.half.trace
        k = slice(None, None, 2)  # the finer run's samples at the coarser's

        def largest(a, b):
            return float(np.max(np.abs(a - b[k])))

        return Moved(
            MappingProxyType({a: largest(coarse.torque[a], fine.torque[a])
                              for a in coarse.torque}),
            MappingProxyType({a: largest(coarse.speed[a], fine.speed[a])
                              for a in coarse.speed}),
            largest(self.run.v, self.half.v))


class _Actuated(NamedTuple):
    """An actuator as an event runs it: its `mode` (one of `MODES`, or a
    callable τ(t)), its joint's dof, gear `n` and rotor inertia `j_m`, its
    resolved constants `c` and winding resistance `r`, its current limit
    `i_max` (d-q A), its gearbox's backward efficiency `eta`, its
    `gearbox` and `driver`, and its driver's flux brake as (onset V,
    capacity W) where the mode leaves the driver on, else None."""
    name: str
    mode: object
    dof: int
    n: float
    j_m: float
    c: object
    r: float
    i_max: float
    eta: float
    gearbox: object
    driver: object
    flux: tuple


class _Simulation(NamedTuple):
    """An event's samples: local times `t`, and for each its `rows` (state,
    qdd, {actuator: (τ, ω, rotor)}, residual), `driven` ({actuator: whether
    its driver is on}), bus voltage `v` and `contacts`."""
    t: np.ndarray
    rows: list
    driven: list
    v: np.ndarray
    contacts: tuple


def _actuated(m, ev, drive, actuators, temperature):
    """Each actuator's `_Actuated`, checked against the drive data."""
    modes = dict(ev.modes)
    missing = [a for a in actuators if a not in modes]
    unknown = sorted(set(modes) - set(actuators))
    if missing or unknown:
        raise KeyError(f"an event gives every actuator a mode; "
                       f"{f'missing {missing}' if missing else ''}"
                       f"{'; ' if missing and unknown else ''}"
                       f"{f'no actuator named {unknown}' if unknown else ''}"
                       f"; this mechanism has {list(actuators)}")
    model, out = m.model, []
    for a, (joint, n, j_m) in actuators.items():
        motor, driver = drive.motors[a], drive.drivers[a]
        box = drive.gearboxes.get(a)
        if box is None and n != 1:
            raise ValueError(f"{a!r} has a gear of {n:g} but no gearbox; "
                             f"give gearboxes={{{a!r}: Gearbox(forward=...)}}")
        c = _resolve(motor, n, box)
        mode = modes[a]
        if isinstance(mode, (int, float)):
            mode = _constant(float(mode))
        eta = 1.0 if box is None else box.backward
        if mode in MODES and eta == 0:
            raise ValueError(f"{a!r}'s gearbox is self-locking (backward "
                             f"efficiency 0), so it does not back-drive to "
                             f"{mode}; lock its joint for this event")
        if mode == "flux_brake" and driver.flux_brake is None:
            raise ValueError(f"{a!r}'s driver has no flux brake; give it "
                             f"Driver(flux_brake=FluxBrake(...)), or brake "
                             f"it with 'short'")
        dof = int(model.jnt_dofadr[model.joint(joint).id])
        r = float(_hot(c, temperature.get(a)))
        flux = None
        if mode not in PASSIVE and driver.flux_brake is not None:
            flux = (driver.flux_brake.onset,
                    _flux_capacity(driver, motor, r))
        out.append(_Actuated(a, mode, dof, n, j_m, c, r,
                             _current_limit(c, motor, driver), eta, box,
                             driver, flux))
    return out


def _constant(value):
    return lambda t: value


def _current(act, e, v):
    """The mode's d-q current at back-EMF `e` and bus voltage `v`, as
    (damped, offset): i = −e/R_φ where `damped`, plus `offset`."""
    if act.mode == "short":
        return True, 0.0
    held = act.c.k_mod * v  # the winding voltage past which the diodes
                            # conduct
    sign = math.copysign(1.0, e)
    conducting = (abs(e) - held) / act.r
    if act.mode == "coast":
        return (True, sign * held / act.r) if conducting > 0 else (False, 0.0)
    if abs(e) / act.r <= act.i_max:  # flux_brake: the short's current
        return True, 0.0
    if conducting > act.i_max:  # past the driver's limit, the diodes'
        return True, sign * held / act.r
    return False, -sign * act.i_max


def _simulate(m, start, ev, drive, actuators, temperature, capacitance,
              v_source, v0, timestep):
    """`ev` run from the `State` `start` at `timestep`, the bus of `drive`
    at `capacitance` and `v_source` from `v0`: a `_Simulation`."""
    steps = max(1, math.ceil(ev.duration / timestep - 1e-9))
    step = ev.duration / steps
    acts = _actuated(m, ev, drive, actuators, temperature)
    bus = drive.bus

    model = copy.deepcopy(m.model)  # the engine's own keeps Euler
    model.opt.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    model.opt.timestep = step
    data = start._fill(mujoco.MjData(model))
    base = model.dof_damping.copy()

    half_c = 0.5 * capacitance
    braking = [a for a in acts if a.flux is not None]
    levels = _levels(bus, capacitance, v_source,
                     [(a.name, a.flux[0]) for a in braking])
    cap = {} if bus.source is None else {SOURCE: bus.source.p_max}
    cap.update({("flux", a.name): a.flux[1] for a in braking})
    energy = half_c * v0 ** 2

    free = bool(m._free)
    independent = [i for i, d in enumerate(m.dofs) if d not in m.dependent]
    driven = {a.name: a.mode not in PASSIVE for a in acts}
    contacts = bool(m.description.contacts)
    rows, volts, carried = [], [], []
    for k in range(steps + 1):
        t = k * step
        v = math.sqrt(energy / half_c)
        damping, push, torque = base.copy(), np.zeros(model.nv), {}
        for a in acts:
            if callable(a.mode):
                torque[a.name] = float(a.mode(t))
                push[a.dof] += a.n * torque[a.name]
                continue
            e = a.c.ke * a.n * float(data.qvel[a.dof])
            damped, offset = _current(a, e, v)
            current = offset - (e / a.r if damped else 0.0)
            torque[a.name] = a.c.kt * current / a.eta
            if damped:
                damping[a.dof] += a.n ** 2 * a.c.kt * a.c.ke / (a.r * a.eta)
            push[a.dof] += a.n * a.c.kt * offset / a.eta
        model.dof_damping[:] = damping
        mujoco.mj_step1(model, data)  # the passive forces, at this damping
        q = {name: start._read(data, name) for name in m.coordinates}
        rates = data.qvel.copy()
        if free:
            turned = tangent(m, data)[0]
            rates = np.linalg.solve(turned, rates)
            drift = tangent(m, data, rates)[1]
        data.qfrc_applied[:] = _load_force(model, data, ev.loads) + push
        mujoco.mj_step2(model, data)  # qacc is the continuous one, here
        if not (np.all(np.isfinite(data.qpos))
                and np.all(np.isfinite(data.qvel))):
            raise RuntimeError(f"the event diverged at t = {t:g} s into it, "
                               f"at a timestep of {step:g} s; give it a "
                               f"smaller timestep=")
        accel = data.qacc.copy()
        if free:
            accel = np.linalg.solve(turned, accel - drift)
        qd = dict(zip(m.dofs, (float(x) for x in rates)))
        state = State(m, MappingProxyType(q), MappingProxyType(qd))
        out = {a.name: (torque[a.name], a.n * float(rates[a.dof]),
                        a.j_m * a.n * float(data.qacc[a.dof]))
               for a in acts}
        rows.append((state, {m.dofs[i]: float(accel[i]) for i in independent},
                     out, 0.0))
        volts.append(v)
        carried.append(MappingProxyType(from_solver(m, data) if contacts
                                        else {}))
        if k == steps:
            break
        power = 0.0
        for a in acts:
            tau, omega, rotor = out[a.name]
            e = _electrical(a.c, a.n, a.gearbox, a.driver,
                            np.asarray(a.n * (tau - rotor)),
                            np.asarray(omega / a.n), np.asarray(rotor),
                            np.asarray(a.r))
            power += float(e.bus)
        if bus.brake is not None:
            cap[BRAKE] = _brake_capacity(bus.brake, v)
        energy, _ = _substep(energy, -(power + bus.hotel), step, levels, cap)
    times = np.arange(steps + 1) * step
    times[-1] = ev.duration
    return _Simulation(times, rows, [driven] * len(rows),
                       _frozen(np.array(volts)), tuple(carried))
