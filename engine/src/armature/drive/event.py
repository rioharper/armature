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

Under a mission's actuation seam the actuators are its `transmission`'s,
which drive no joint: each pulls the mechanism with g·T, T its tension at
the motor, and its rotor turns as J_m·ω̇_m = Kt·i − s·T, the modes
setting i. The gearbox's share s is the electrical model's: η_b
back-driven, where T·ω_m < 0, and 1/η_f where the motor drives its load;
a torque profile's torque is its rotor's, lossless. A bilateral one turns
at ω_m = g·q̇, so T carries a short's damping, c = Kt·Ke/(R_φ·s), and the
rotor's J_m/s. A cable that pulls only carries T ≥ 0: where its motor
would push, it goes slack, its rotor turning on its own under its mode,
and its slack, in motor radians, growing as g·q̇ − ω_m. Each step solves
the tensions as one complementarity problem, a short's damping implicit
in each rotor's own row, and applies them as a generalised force; a joint
limit or a contact sees the mechanism's own inertia alone, so a taut
cable against one may open or close by a step's error, which the next
step takes up. A slack cable whose slack closes within a step at the
speeds it starts with snaps taut first, as a plastic impact, an impulse
that matches its rotor to its cable, so the samples carry no impulse/h:
`Run.snaps` reports each one. The trace reads each transmitted motor's
current at its sample's speed, so `electrical` reads the mode's current
back from the tension and the rotor exactly; a torque profile's, through
a gearbox, it reads with the gearbox's loss, as it does a joint's.

The bus is stepped with the mechanics, since a coasting motor's diodes and
a braking driver's flux brake both act on the bus voltage as it is: each
step, every actuator's bus power at the step's start, through the
electrical model, is held over the step and integrated with the clamps
exactly, as `charge` integrates a substep. The bus starts where the mission
left it (`trace` charges the segments before the event), or at V_s.

A driver whose bus reaches its `max_voltage`, in any mode, a short's
included, trips at the first step that starts at or above it, latched: its
motor coasts from that step on, its flux brake off. The source trips at its
`overvoltage` the same way, and then neither sources nor sinks. One that
tripped earlier in the mission, as `trace` charges it, is off from the
event's start. `Run.tripped` names those that trip in the event, and
halving the timestep measures the step's lag in the trip.

Every event is run at its timestep and at half of it; `trace` carries the
first in its samples and reports both as a `Simulated`, whose run at half
the timestep runs when it is first read.
"""

import copy
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from types import MappingProxyType
from typing import NamedTuple

import mujoco
import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import nnls

from ..assembly import tangent
from ..contact import from_solver
from ..state import State, _frozen, _load_force
from .bus import (BRAKE, SOURCE, TRIPPED_SOURCE, _brake_capacity,
                  _flux_capacity, _levels, _substep)
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
    solver. `tripped` gives the time (s, from the event's start) at which
    each driver, by its actuator's name, or the source, as `"source"`,
    tripped in this run; one that tripped before it is not named. For each
    actuator whose cable pulls only, `slack` says at each sample whether
    its cable carried nothing, and `snaps` gives each time it snapped taut,
    as `Snap`s in order."""
    timestep: float
    trace: object
    v: np.ndarray
    contacts: tuple
    tripped: MappingProxyType = MappingProxyType({})
    slack: MappingProxyType = MappingProxyType({})
    snaps: MappingProxyType = MappingProxyType({})


class Snap(NamedTuple):
    """A slack cable snapped taut at `t` (s, from the event's start), as a
    plastic impact: the `impulse` (N·m·s, motor side) that matched its
    rotor to its cable, and its share of the kinetic energy `lost` (J) in
    the impact, which it splits with any other cable that snapped in it as
    each one's impulse times its closing speed. A rigid cable's peak
    tension in the snap depends on its stiffness, which the event does not
    model; size the snap from the impulse."""
    t: float
    impulse: float
    lost: float


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
    whose samples the mission's trace carries) and at half of it (`half`),
    which runs when it is first read: nothing but the resolution check
    reads it, and it costs twice the run."""
    segment: int
    run: Run
    halved: Callable = field(repr=False, compare=False)

    @cached_property
    def half(self):
        """The event run at half its timestep, a `Run`."""
        return self.halved()

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
    its driver is on}), bus voltage `v` and `contacts`; the time (s) each
    driver or the source `tripped` in it; and, for each actuator whose
    cable pulls only, whether it was `slack` at each sample and its
    `snaps`."""
    t: np.ndarray
    rows: list
    driven: list
    v: np.ndarray
    contacts: tuple
    tripped: dict
    slack: dict
    snaps: dict


def _actuated(m, ev, drive, actuators, temperature):
    """Each actuator's `_Actuated`, checked against the drive data; one
    driven through a transmission has no joint, and its dof is None."""
    off = [a for a in actuators if a not in drive.bus.actuators]
    if off:
        raise ValueError(f"the drive's bus does not carry {off}; an event "
                         f"runs every actuator on its motor and driver, so "
                         f"add them to Bus(actuators=...)")
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
        dof = (None if joint is None
               else int(model.jnt_dofadr[model.joint(joint).id]))
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


class _Transmitted(NamedTuple):
    """A transmitted actuator at one step: `g`, its motor speed per rate of
    each of the dofs, as an array; `bias`, its ω̇_m at q̈ = 0 (rad/s²);
    `j_m`, its rotor's inertia (kg·m²); and `pulls`, whether its cable
    pulls only."""
    g: np.ndarray
    bias: float
    j_m: float
    pulls: bool


def _row(g, bias, j_m, pulls=False):
    return dict(g), float(bias), float(j_m), pulls


def _transmitted(m, transmission, state, t):
    """The transmission at `state`, `t` into the event: each actuator's
    `_Transmitted`."""
    out = transmission(state, t)
    try:
        rows = {a: _row(*row) for a, row in dict(out).items()}
    except (TypeError, ValueError):
        rows = None
    if not rows:
        raise TypeError(f"a transmission returns {{actuator: (rates, bias, "
                        f"inertia)}}, or (rates, bias, inertia, pulls), "
                        f"rates a mapping by dof; got {out!r}")
    known = set(m.dofs)
    out = {}
    for a, (g, bias, j_m, pulls) in rows.items():
        unknown = sorted(set(g) - known)
        if unknown:
            raise KeyError(f"the transmission's {a!r} turns with {unknown}, "
                           f"which are not among the dofs {list(m.dofs)}")
        if not isinstance(pulls, (bool, np.bool_)):
            raise TypeError(f"the transmission's {a!r} pulls is True, a "
                            f"cable that pulls only, or False; got "
                            f"{pulls!r}")
        if pulls and j_m <= 0:
            raise ValueError(f"the transmission's {a!r} pulls only, and its "
                             f"rotor turns on its own while its cable is "
                             f"slack; give its inertia, J_m > 0")
        out[a] = _Transmitted(np.array([float(g.get(d, 0.0))
                                        for d in m.dofs]), bias, j_m,
                              bool(pulls))
    return out


def _share(a, omega, sign):
    """The share of its tension T a transmitted actuator's rotor takes, T of
    `sign`, as `electrical` reads its gearbox: 1/η_f where T·ω_m ≥ 0, the
    motor driving its load, else η_b, back-driven. A torque profile's
    torque is its rotor's, lossless."""
    if callable(a.mode):
        return 1.0
    if sign * omega >= 0:
        return 1.0 / (1.0 if a.gearbox is None else a.gearbox.forward)
    return a.eta


def _through(model, data, acts, through, t, v, step, own, gaps, signs):
    """The generalised force, added to what MuJoCo applies, of each
    transmitted actuator's tension T on the mechanism through g, over
    `step`. Each rotor turns as J_m·ω̇_m = Kt·i − s·T, s its gearbox's
    share (`_share`), a short's damping implicit in it. A bilateral one
    turns at ω_m = g·q̇, its T's sign taken from `signs`, the step
    before's, and solved again where it turns out the other. One that
    pulls only turns at its `own` ω_m, carrying T ≥ 0 where its cable's
    slack, in `gaps` (motor rad), would otherwise go negative. With each
    actuator's (τ, ω_m, rotor), its current read at the step's start, as
    `electrical` reads it back; its T; and each rotor's ω_m at the step's
    end. Constraints see the mechanism's own inertia alone."""
    mujoco.mj_fwdActuation(model, data)
    mujoco.mj_fwdAcceleration(model, data)  # qfrc_smooth, loads included
    mass = np.zeros((model.nv, model.nv))
    mujoco.mj_fullM(model, data, mass)
    turning = {}  # each one's (actuator, row, ω_m, drive, damping)
    for a in acts:
        if a.dof is not None:
            continue
        row = through[a.name]
        omega = own[a.name] if row.pulls else float(row.g @ data.qvel)
        if callable(a.mode):
            drive, damping = float(a.mode(t)), 0.0
        else:
            damped, offset = _current(a, a.c.ke * omega, v)
            drive = a.c.kt * offset
            damping = a.c.kt * a.c.ke / a.r if damped else 0.0
        turning[a.name] = (a, row, omega, drive, damping)
    for _ in range(2):  # again, where a bilateral tension changed its sign
        tension, spun = _tensions(mass, data.qfrc_smooth, data.qvel, turning,
                                  step, gaps, signs)
        changed = {name: math.copysign(1.0, tension[name])
                   for name, (_, row, *_) in turning.items()
                   if not row.pulls and tension[name] != 0
                   and math.copysign(1.0, tension[name])
                   != signs.get(name, 1.0)}
        signs.update(changed)
        if not changed:
            break
    force, out = np.zeros(model.nv), {}
    for name, (a, row, omega, drive, damping) in turning.items():
        force += row.g * tension[name]
        motor = drive - damping * omega  # Kt·i, at the step's start
        rotor = motor - _share(a, omega, tension[name]) * tension[name]
        out[name] = (tension[name] + rotor, omega, rotor)
    return force, out, tension, spun


def _tensions(mass, smooth, qvel, turning, step, gaps, signs):
    """`_through`'s tensions, each bilateral one's sign as `signs` gives
    it, and each rotor's ω_m at the step's end."""
    smooth, rows, tension, spun = smooth.copy(), [], {}, {}
    for name, (a, row, omega, drive, damping) in turning.items():
        share = _share(a, omega, 1.0 if row.pulls else signs.get(name, 1.0))
        held = row.j_m + step * damping
        if held == 0:  # a massless rotor, undamped: T is what drives it
            tension[name] = drive / share
            smooth += row.g * tension[name]
            continue
        rows.append((name, row.g, row.bias + gaps.get(name, 0.0) / step ** 2,
                     row.pulls, (row.j_m * omega + step * drive) / held,
                     step * share / held))
    if rows:
        names, g, bias, pulls, w, k = zip(*rows)
        g, w, k = np.array(g).T, np.array(w), np.array(k)  # g by column
        moved = np.linalg.solve(mass, np.column_stack([smooth, g]))
        coupled = step * g.T @ moved[:, 1:] + np.diag(k)
        unforced = (g.T @ (qvel + step * moved[:, 0])
                    + step * np.array(bias) - w)
        found = _complementary(coupled, unforced, np.array(pulls))
        for i, name in enumerate(names):
            tension[name] = float(found[i])
            spun[name] = float(w[i] - k[i] * found[i])
    return tension, spun


def _complementary(matrix, b, unilateral):
    """x with b + A·x zero on the bilateral rows and, on the `unilateral`,
    x ≥ 0 and b + A·x ≥ 0, one of the two zero, for A, `matrix`, symmetric
    positive definite: the unilateral rows' Schur complement solved
    exactly, as a non-negative least squares on its Cholesky factor."""
    pulled = np.flatnonzero(unilateral)
    held = np.flatnonzero(~unilateral)
    x = np.zeros(len(b))
    solved = np.linalg.solve(matrix[np.ix_(held, held)], np.column_stack(
        [b[held], matrix[np.ix_(held, pulled)]])) if len(held) else (
            np.zeros((0, 1 + len(pulled))))
    reduced = (matrix[np.ix_(pulled, pulled)]
               - matrix[np.ix_(pulled, held)] @ solved[:, 1:])
    offset = b[pulled] - matrix[np.ix_(pulled, held)] @ solved[:, 0]
    if len(pulled) and np.any(offset < 0):
        lower = np.linalg.cholesky(reduced)
        x[pulled] = nnls(lower.T, -solve_triangular(lower, offset,
                                                    lower=True))[0]
    x[held] = -(solved[:, 0] + solved[:, 1:] @ x[pulled])
    return x


def _impact(model, data, acts, through, own, gaps, step, signs):
    """Snap taut, as one plastic impact, each slack cable whose gap closes
    within `step` at the speeds the step starts with, the taut cables and
    the bilateral actuators holding through it, each rotor taking its
    gearbox's share of its impulse (a bilateral one's at the sign `signs`
    gives), on `data.qvel` and the `own` rotors. Returns each snapped
    cable's (impulse, lost) by name: its impulse (N·m·s, motor side) and
    its share of the kinetic energy the impact lost (J), split among the
    snapped cables as each one's impulse times its closing speed. Reads
    the mass matrix `mj_step1` left; contacts and joint limits take no
    part in the impact."""
    closing = {a.name for a in acts if gaps.get(a.name, 0.0) > 0
               and gaps[a.name] + step * (through[a.name].g @ data.qvel
                                          - own[a.name]) < 0}
    if not closing:
        return {}
    rows = []
    for a in acts:
        if a.dof is not None:
            continue
        row = through[a.name]
        if row.j_m == 0 or (row.pulls and gaps[a.name] > 0
                            and a.name not in closing):
            continue  # a massless rotor takes no impulse, a slack cable none
        omega = own[a.name] if row.pulls else float(row.g @ data.qvel)
        sign = 1.0 if row.pulls else signs.get(a.name, 1.0)
        rows.append((a.name, row.g, row.j_m, row.pulls,
                     _share(a, omega, sign)))
    names, g, j_m, pulls, share = zip(*rows)
    g, j_m, share = np.array(g).T, np.array(j_m), np.array(share)
    mass = np.zeros((model.nv, model.nv))
    mujoco.mj_fullM(model, data, mass)
    moved = np.linalg.solve(mass, g)

    def kinetic():
        omega = np.array([own[n] if p else g[:, i] @ data.qvel
                          for i, (n, p) in enumerate(zip(names, pulls))])
        return 0.5 * (data.qvel @ mass @ data.qvel + j_m @ omega ** 2)

    before = kinetic()
    closes = np.array([g[:, i] @ data.qvel - own[n] if p else 0.0
                       for i, (n, p) in enumerate(zip(names, pulls))])
    impulse = _complementary(g.T @ moved + np.diag(share / j_m), closes,
                             np.array(pulls))
    data.qvel[:] += moved @ impulse
    for i, name in enumerate(names):
        if pulls[i]:
            own[name] -= share[i] * impulse[i] / j_m[i]
    snapped = [i for i, name in enumerate(names)
               if name in closing and impulse[i] > 0]
    weight = -impulse[snapped] * closes[snapped]  # each one's share
    lost = (before - kinetic()) * weight / np.sum(weight)
    return {names[i]: (float(impulse[i]), float(part))
            for i, part in zip(snapped, lost)}


def _simulate(m, start, ev, drive, actuators, temperature, capacitance,
              v_source, v0, timestep, seam=None, tripped=()):
    """`ev` run from the `State` `start` at `timestep`, the bus of `drive`
    at `capacitance` and `v_source` from `v0`: a `_Simulation`. Under a
    `seam`, (transmission(state, t), gear), the actuators are the
    transmission's, at the gear of each, in place of `actuators`. The
    drivers, and the source, named in `tripped` tripped before the event
    and are off from its start; each other trips at the first step that
    starts at or above its level."""
    steps = max(1, math.ceil(ev.duration / timestep - 1e-9))
    step = ev.duration / steps
    if seam is not None:
        transmission, gear = seam
        first = _transmitted(m, transmission, start, 0.0)
        names = tuple(first)
        missing = [a for a in names if a not in gear]
        if missing:
            raise KeyError(f"{missing} have no gear in the compiled model; "
                           f"an event runs them on their motors, so give "
                           f"their ratio, trace(..., gear={{...}})")
        actuators = {a: (None, float(gear[a]), 0.0) for a in names}
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
    trips = {a.name: a.driver.max_voltage for a in acts}  # V, still to reach
    if bus.source is not None and bus.source.overvoltage is not None:
        trips[TRIPPED_SOURCE] = bus.source.overvoltage
    _trip(acts, cap, trips, [key for key in tripped if key in trips])

    free = bool(m._free)
    independent = [i for i, d in enumerate(m.dofs) if d not in m.dependent]
    contacts = bool(m.description.contacts)
    rows, volts, carried, driven, latched = [], [], [], [], {}

    def observed():
        """The `State` `data` holds, its rates, and, for a floating body,
        its tangent map and drift."""
        q = {name: start._read(data, name) for name in m.coordinates}
        rates, turned, drift = data.qvel.copy(), None, None
        if free:
            turned = tangent(m, data)[0]
            rates = np.linalg.solve(turned, rates)
            drift = tangent(m, data, rates)[1]
        qd = dict(zip(m.dofs, (float(x) for x in rates)))
        return (State(m, MappingProxyType(q), MappingProxyType(qd)), rates,
                turned, drift)

    def transmitted(state, t):
        through = _transmitted(m, transmission, state, t)
        if tuple(through) != names:
            raise ValueError(f"the transmission gave {list(through)} at "
                             f"t = {t:g} s into the event, and {list(names)} "
                             f"at its start; the actuators are the same at "
                             f"every step")
        changed = [a for a in names if through[a].pulls != (a in pulling)]
        if changed:
            raise ValueError(f"the transmission's {changed} pull only at "
                             f"t = {t:g} s into the event and not at its "
                             f"start, or the other way; whether a cable "
                             f"pulls is the same at every step")
        return through

    # each pulling rotor's own ω_m (rad/s), its cable's slack (motor rad),
    # whether it carried tension over the step before, and what it reports
    pulling = set() if seam is None else {a for a in names
                                          if first[a].pulls}
    own, gaps = dict.fromkeys(pulling, 0.0), dict.fromkeys(pulling, 0.0)
    taut = dict.fromkeys(pulling, True)
    signs = {}  # each bilateral transmitted tension's sign, the step before
    slack, snaps = {a: [] for a in pulling}, {a: [] for a in pulling}
    for k in range(steps + 1):
        t = k * step
        v = math.sqrt(energy / half_c)
        reached = [key for key, level in trips.items() if v >= level]
        if reached:  # latched from this step's start
            _trip(acts, cap, trips, reached)
            latched.update(dict.fromkeys(reached, k))
        driven.append({a.name: a.mode not in PASSIVE for a in acts})
        damping, push, torque = base.copy(), np.zeros(model.nv), {}
        for a in acts:
            if a.dof is None:
                continue  # through the transmission, below
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
        state, rates, turned, drift = observed()
        if seam is not None:
            through = transmitted(state, t)
            for a in pulling:
                if taut[a]:  # its rotor turns with its cable
                    own[a] = float(through[a].g @ data.qvel)
            snapped = _impact(model, data, acts, through, own, gaps, step,
                              signs)
            if snapped:
                mujoco.mj_fwdVelocity(model, data)  # at the snapped rates
                for a, (impulse, lost) in snapped.items():
                    snaps[a].append(Snap(t, impulse, lost))
                    gaps[a] = 0.0
                state, rates, turned, drift = observed()
                through = transmitted(state, t)
        data.qfrc_applied[:] = _load_force(model, data, ev.loads) + push
        if seam is not None:
            force, carrying, tension, spun = _through(
                model, data, acts, through, t, v, step, own, gaps, signs)
            data.qfrc_applied[:] += force
        mujoco.mj_step2(model, data)  # qacc is the continuous one, here
        if not (np.all(np.isfinite(data.qpos))
                and np.all(np.isfinite(data.qvel))):
            raise RuntimeError(f"the event diverged at t = {t:g} s into it, "
                               f"at a timestep of {step:g} s; give it a "
                               f"smaller timestep=")
        accel = data.qacc.copy()
        if free:
            accel = np.linalg.solve(turned, accel - drift)
        for a in pulling:  # its slack, at the step's end
            row = through[a]
            gap = gaps[a] + step * (float(row.g @ data.qvel)
                                    + step * row.bias - spun[a])
            own[a], taut[a] = spun[a], tension[a] > 0
            gaps[a] = 0.0 if taut[a] else max(0.0, gap)
            slack[a].append(not taut[a])
        out = {}
        for a in acts:
            if a.dof is None:
                out[a.name] = carrying[a.name]
                continue
            out[a.name] = (torque[a.name], a.n * float(rates[a.dof]),
                           a.j_m * a.n * float(data.qacc[a.dof]))
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
        energy, _, _ = _substep(energy, -(power + bus.hotel), step, levels,
                                cap)
    times = np.arange(steps + 1) * step
    times[-1] = ev.duration
    return _Simulation(times, rows, driven, _frozen(np.array(volts)),
                       tuple(carried),
                       {key: float(times[k]) for key, k in latched.items()},
                       {a: _flags(slack[a]) for a in sorted(slack)},
                       {a: tuple(snaps[a]) for a in sorted(snaps)})


def _flags(values):
    flags = np.array(values, dtype=bool)
    flags.flags.writeable = False
    return flags


def _trip(acts, cap, trips, keys):
    """Trip each of `keys`, latched, so it leaves `trips`, the levels
    still to reach: the source neither sources nor sinks, and a driver's
    motor coasts, whatever its mode, a short's included, its flux brake
    off."""
    for key in keys:
        trips.pop(key, None)
        if key == TRIPPED_SOURCE:
            if SOURCE in cap:
                cap[SOURCE] = 0.0
            continue
        for i, a in enumerate(acts):
            if a.name != key:
                continue
            if a.eta == 0:
                raise ValueError(f"{key!r}'s driver trips, and its gearbox "
                                 f"is self-locking (backward efficiency 0), "
                                 f"so it does not back-drive to coast; lock "
                                 f"its joint for this event")
            if a.flux is not None:
                cap[("flux", key)] = 0.0
            acts[i] = a._replace(mode="coast", flux=None)
