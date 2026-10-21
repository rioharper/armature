"""The golden mechanisms' known answers, one `Answer` per question.

Every value is computed here from a golden project's parameters by a closed
form or in mpmath, never by the engine. This file sits beside the project
directories and never inside one, so a scaffold that copies a project cannot
leak them, and no golden project imports it.
"""

import math
from dataclasses import dataclass

from mpmath import mp

from golden import cable_platform, spring_cable, wheel_leg
from golden import parallelogram, turret


@dataclass(frozen=True)
class Answer:
    """A known answer: `value` in `unit`, accepted within ±`window` of
    itself (a fraction), `how` the formula as the rubric quotes it, and
    `bait` the value the case's bait gives, which must fall outside."""
    value: float
    unit: str
    how: str
    bait: float
    window: float = 0.02

    @property
    def bounds(self):
        """The window as (low, high)."""
        return tuple(sorted((self.value * (1 - self.window),
                             self.value * (1 + self.window))))

    def inside(self, x):
        low, high = self.bounds
        return low <= x <= high


# --- the cable platform: its tilt at the edge midpoint -----------------------

def _rotation(v):
    """Rodrigues: the rotation by the rotation vector `v`."""
    theta = mp.sqrt(sum(c ** 2 for c in v))
    k = mp.matrix([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    if theta == 0:
        return mp.eye(3) + k
    return (mp.eye(3) + mp.sin(theta) / theta * k
            + (1 - mp.cos(theta)) / theta ** 2 * k * k)


def _platform_rest(params):
    """The platform's rest at its POSE: where the cables, unilateral springs
    of stiffness EA / l0, balance its weight in force and in moment about
    its point. Returns the rotation.

    Newton from level overshoots the soft tilt, so the pitch is bracketed
    first, the stiff translation solved inside it, and the rest then
    polished in all six coordinates from there."""
    p, m = params.PARAMS, mp.mpf(params.PARAMS["m"])
    anchors = [mp.matrix([mp.mpf(float(c)) for c in a]) for a in params.ANCHORS]
    attach = [mp.matrix([mp.mpf(float(c)) for c in a]) for a in params.ATTACH]
    com = mp.matrix([mp.mpf(float(c)) for c in params.COM])
    weight = mp.matrix([0, 0, -m * params.G])

    def balance(*x):
        point, turn = mp.matrix(x[:3]), _rotation(x[3:])
        force, moment = mp.matrix(weight), mp.matrix(3, 1)
        for i in range(4):
            arm = turn * attach[i]
            span = anchors[i] - (point + arm)
            length = mp.norm(span)
            rest = mp.mpf(p[f"l0_{i + 1}"])
            pull = params.EA / rest * max(length - rest, 0) * span / length
            force += pull
            moment += _cross(arm, pull)
        moment += _cross(turn * com, weight)
        return [*force, *moment]

    pose = [mp.mpf(float(c)) for c in params.POSE]

    def placed(pitch):
        return list(mp.findroot(lambda *x: balance(*x, 0, pitch, 0)[:3], pose))

    def pitching(pitch):
        return balance(*placed(pitch), 0, pitch, 0)[4]

    pitch = mp.findroot(pitching, (-1, 1), solver="anderson")
    rest = mp.findroot(balance, placed(pitch) + [0, pitch, 0])
    return _rotation(list(rest)[3:])


def _cross(a, b):
    return mp.matrix([a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
                      a[0] * b[1] - a[1] * b[0]])


with mp.workdps(30):
    _rest = _platform_rest(cable_platform.params)
    _tilt = float(mp.degrees(mp.acos(_rest[2, 2])))

PLATFORM_TILT = Answer(
    value=_tilt, unit="°", bait=0.0,
    how="the angle between the platform's axis and the vertical, "
        "acos(R_zz), at the rest where Σ T_i u_i = m g ẑ and "
        "Σ (R a_i) × T_i u_i + (R c) × (−m g ẑ) = 0, each T_i = EA/l0_i · "
        "(|span_i| − l0_i) while taut, hung at "
        f"{tuple(float(c) for c in cable_platform.params.POSE)} m on the "
        "level-platform law's rest lengths")


# --- the wheel leg: its skid pad's worst clearance ---------------------------

def _leg(ya, ye):
    """The knee B and the pin C in the torso's frame, the hips turned by ya
    and ye, on home's branch of the loop."""
    pts = {k: [mp.mpf(c) for c in xy]
           for k, xy in wheel_leg.params.POINTS.items()}

    def turned(pivot, point, t):
        dx, dy = point[0] - pivot[0], point[1] - pivot[1]
        return [pivot[0] + mp.cos(t) * dx - mp.sin(t) * dy,
                pivot[1] + mp.sin(t) * dx + mp.cos(t) * dy]

    def dist(u, v):
        return mp.sqrt((u[0] - v[0]) ** 2 + (u[1] - v[1]) ** 2)

    b = turned(pts["A"], pts["B"], ya)
    d = turned(pts["E"], pts["D"], ye)
    r2, r4, bd = dist(pts["B"], pts["C"]), dist(pts["D"], pts["C"]), dist(b, d)
    along = (r2 ** 2 - r4 ** 2 + bd ** 2) / (2 * bd)
    height = mp.sqrt(r2 ** 2 - along ** 2)
    ex = [(d[0] - b[0]) / bd, (d[1] - b[1]) / bd]
    return b, [b[0] + along * ex[0] + height * ex[1],
               b[1] + along * ex[1] - height * ex[0]]


HIPS = wheel_leg.params.WORKSPACE


def skid_clearance(ya, ye):
    """The skid pad's height above the floor, the hub on it: the knee B above
    the pin C, plus the wheel's radius, less the pad's."""
    b, c = _leg(mp.mpf(ya), mp.mpf(ye))
    return b[1] - c[1] + wheel_leg.PARAMS["r"] - wheel_leg.params.R_SKID


def _hips_x():
    a, e = wheel_leg.params.POINTS["A"], wheel_leg.params.POINTS["E"]
    return (mp.mpf(a[0]) + mp.mpf(e[0])) / 2


def _worst_clearance(n=41):
    """The least clearance over the hips' WORKSPACE, and the hips (A, E)
    where it falls: a dense grid, then a grid as dense over the cells round
    its least point."""
    (a0, a1), (e0, e1) = HIPS["A"], HIPS["E"]

    def least(a_lo, a_hi, e_lo, e_hi):
        return min((skid_clearance(a, e), a, e)
                   for a in mp.linspace(a_lo, a_hi, n)
                   for e in mp.linspace(e_lo, e_hi, n))

    _, a, e = least(a0, a1, e0, e1)
    da, de = (mp.mpf(a1) - a0) / (n - 1), (mp.mpf(e1) - e0) / (n - 1)
    return least(max(a - da, a0), min(a + da, a1),
                 max(e - de, e0), min(e + de, e1))


def _clearance_at_alpha_zero(n=41):
    """The least clearance where the leg stands straight below the hips,
    α = 0, inside the WORKSPACE: for each A, the E that puts the pin under
    the hips' midpoint, walked out from home so each root seeds the next."""
    (a0, a1), (e0, e1) = HIPS["A"], HIPS["E"]
    found = [skid_clearance(0, 0)]
    for end in (a0, a1):
        ye = mp.mpf(0)
        for ya in mp.linspace(0, end, n)[1:]:
            ye = mp.findroot(lambda e: _leg(ya, e)[1][0] - _hips_x(), ye)
            if e0 <= ye <= e1:
                found.append(skid_clearance(ya, ye))
    return min(found)


with mp.workdps(30):
    (_worst, *_hips), _straight = _worst_clearance(), _clearance_at_alpha_zero()

SKID_CLEARANCE = Answer(
    value=float(_worst) * 1e3, unit="mm", bait=float(_straight) * 1e3,
    how="min over the hips' working range, A ∈ {} and E ∈ {} rad, of "
        "B_y − C_y + r − r_skid, the knee B above the five-bar's pin C plus "
        "the wheel's radius less the skid pad's, over a dense grid and then "
        "one as dense over the cells round its least point; the bait is the "
        "least over α = 0 alone".format(list(HIPS["A"]), list(HIPS["E"])))
SKID_WORST_AT = tuple(float(h) for h in _hips)  # the hips (A, E) it falls at


# --- the mass on a cable -----------------------------------------------------

G = 9.81  # the engine's default gravity, which the bob hangs in [m/s^2]
_m, _k = spring_cable.PARAMS["m"], spring_cable.PARAMS["k"]

CABLE_FREQUENCY = Answer(
    value=math.sqrt(_k / _m) / (2 * math.pi), unit="Hz", bait=math.inf,
    how="f = √(k/m) / 2π, k = EA / l0 the cable's stiffness; an inextensible "
        "cable has no stretch mode, its frequency unbounded")

CABLE_SAG = Answer(
    value=_m * G / _k * 1e3, unit="mm", bait=0.0,
    how="m g / k, the cable's stretch under the bob's weight; an "
        "inextensible cable does not stretch")

# An accelerometer on the bob, which is pulled 4 mm below its rest and let go:
# inside the sag, so the cable stays taut through the swing. At the bottom
# the bob accelerates up at (k/m)·δ, and the accelerometer reads that plus g.
_PULL = 0.004  # [m]

IMU_PEAK = Answer(
    value=_k / _m * _PULL + G, unit="m/s²", bait=_k / _m * _PULL,
    how="(k/m)·δ + g, the specific force an accelerometer on the bob reads "
        "at the bottom of its swing, δ = 4 mm the pull below rest, inside "
        "the cable's m g / k sag so the cable stays taut; the bob's own "
        "acceleration there, (k/m)·δ, is that reading less g")

# --- the parallelogram: its stop's peak bus voltage --------------------------

def _stop():
    """The stop's terms, in mpmath: J1's inertia J11, and J2's holding
    torque from the coupling M12 = (m2 a r2 + m4 r4 c) cos(θ1 − φ), with φ
    held, so J2 must supply M12 θ̈1 + ∂M12/∂θ1 θ̇1²."""
    p, s = parallelogram.PARAMS, parallelogram.missions
    mp_ = {k: mp.mpf(v) for k, v in p.items()}
    j11 = (2 * mp_["I"] + mp_["m1"] * mp_["r1"] ** 2
           + mp_["m4"] * mp_["r4"] ** 2 + mp_["m2"] * mp_["a"] ** 2
           + mp_["N1"] ** 2 * mp_["J_m"])
    k = mp_["m2"] * mp_["a"] * mp_["r2"] + mp_["m4"] * mp_["r4"] * mp_["c"]
    w0, rate = mp.mpf(s.SLEW_SPEED), mp.mpf(s.SLEW_SPEED) / s.STOP_TIME
    phi = mp.mpf(s.HELD) + mp.pi / 2

    def held(t):
        """J2's motor torque at t into the stop (N m)."""
        theta = s.START + w0 * t - rate * t * t / 2
        omega = w0 - rate * t
        return k * (mp.cos(theta - phi) * -rate
                    - mp.sin(theta - phi) * omega ** 2) / mp_["N2"]

    return j11, w0, rate, held


def stop_returned(t):
    """The energy (J) the stop has returned to the bus by `t` (s): the
    kinetic energy J1 gives up, ½J11(ω0² − ω²), less the copper loss
    R_φ ∫(i1² + i2²), i = τ/Kt in d-q. The driver and gearbox are lossless,
    and J2 does no work, φ held, so its current is all loss."""
    drive = parallelogram.params.DRIVE
    j11, w0, rate, held = _stop()
    kt = mp.mpf(drive["kt"]) / mp.sqrt(3)  # d-q, from per A_rms, wye
    r = mp.mpf(drive["r"]) / 2              # per phase, from line to line
    i1 = j11 * rate / parallelogram.PARAMS["N1"] / kt
    t = mp.mpf(t)
    copper = r * (i1 ** 2 * t + mp.quad(lambda u: (held(u) / kt) ** 2,
                                        [0, t]))
    return j11 * (w0 ** 2 - (w0 - rate * t) ** 2) / 2 - copper


def _most_returned():
    """The most net energy the stop returns, and when (s): where J1's
    returned power J11 α ω falls to the copper loss, just short of rest."""
    stop = parallelogram.missions.STOP_TIME
    turn = mp.findroot(lambda t: mp.diff(stop_returned, t), 0.95 * stop)
    assert 0 < turn < stop
    return stop_returned(turn), turn


with mp.workdps(20):
    _drive = parallelogram.params.DRIVE
    _e, STOP_TURN = _most_returned()
    STOP_RETURNED = float(_e)
    _v0, _c = mp.mpf(_drive["v_bus"]), mp.mpf(_drive["c_bus"])
    _peak = mp.sqrt(_v0 ** 2 + 2 * _e / _c)
    STOP_CAPACITANCE = float(2 * _e / (_drive["v_max"] ** 2 - _v0 ** 2))

PEAK_BUS_VOLTAGE = Answer(
    value=float(_peak), unit="V", bait=_drive["v_bus"],
    how="V = √(V₀² + 2E/C) on the capacitance alone, the source a PSU that "
        "cannot sink: E the most the stop returns, ½J11(ω0² − ω²) less the "
        "copper loss R_φ ∫(i1² + i2²) dt, J11 = 2I + m1 r1² + m4 r4² + m2 a² "
        "+ N1² J_m, J2's current holding φ against the coupling "
        "(m2 a r2 + m4 r4 c) cos(θ1 − φ); the bait is the PSU's own V₀, a "
        "bus that never rises")

BUS_CAPACITANCE = Answer(
    value=STOP_CAPACITANCE * 1e3, unit="mF", bait=_drive["c_bus"] * 1e3,
    how="C = 2E / (V_trip² − V₀²), the least capacitance that holds the "
        "stop's peak under the drivers' trip, E as for the peak bus voltage; "
        "the bait is the drivers' own capacitance, nothing added")

# --- the turret: its bearing's peak moment in the slew -------------------------

_t, _limits = turret.PARAMS, turret.missions.LIMITS
# The slew is a jerk-limited quarter turn that reaches its acceleration and
# rate limits. It ends its constant acceleration a at ω₁ = v − a²/2j, and
# there the moment across the axis, the weight's and the COM's inertial
# loads at its height, is the largest the slew puts on the bearing.
_w1 = _limits.v - _limits.a ** 2 / (2 * _limits.j)

BEARING_MOMENT = Answer(
    value=_t["m"] * _t["d"] * math.hypot(_t["g"] + _t["h"] * _w1 ** 2,
                                         _t["h"] * _limits.a),
    unit="N m", bait=0.0,
    how="M = m d √((g + h ω₁²)² + (h a)²) across the bearing's axis, where "
        "the slew ends its constant acceleration a at ω₁ = v − a²/2j: the "
        "weight's moment m g d, the COM d off the axis, with the centrifugal "
        "m d ω² and tangential m d a loads at the COM's height h; the bait "
        "is the bearing checked on its axial load alone, the weight m g, "
        "which puts no moment on it")

ANSWERS = {name: value for name, value in globals().items()
           if isinstance(value, Answer)}
