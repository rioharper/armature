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

ANSWERS = {name: value for name, value in globals().items()
           if isinstance(value, Answer)}
