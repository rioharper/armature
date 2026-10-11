"""A named state of a compiled mechanism, and the queries asked of it.

Every query builds its own `MjData` from the state, so no query reads what
another call left behind.
"""

from dataclasses import dataclass
from types import MappingProxyType

import mujoco
import numpy as np
from scipy.linalg import eigh

EPS = 1e-6


@dataclass(frozen=True, eq=False)
class State:
    """Coordinates `q` and rates `qd`, keyed by coordinate name. Immutable;
    make one with `Compiled.at()`."""
    compiled: object
    q: MappingProxyType
    qd: MappingProxyType

    def _data(self):
        model = self.compiled.model
        data = mujoco.MjData(model)
        for name in self.compiled.coordinates:
            joint = model.joint(name)
            data.qpos[model.jnt_qposadr[joint.id]] = self.q[name]
            data.qvel[model.jnt_dofadr[joint.id]] = self.qd[name]
        mujoco.mj_forward(model, data)
        return data

    def linearise(self, eps=EPS):
        """Stiffness K, mass M and the mode frequencies about this state.

        K = ∂f/∂q for f = M q̈ + bias − passive at q̈ = 0, by MuJoCo's
        `mjd_inverseFD`. The passive force carries joint springs and cables,
        which a gradient of the bias force alone reads as zero. `mjd_inverseFD`
        differences one-sidedly, which leaves an error of order `eps` wherever
        K varies with q, so it runs at +eps and at −eps and K is their mean, a
        central difference. M is MuJoCo's own, exactly. The frequencies solve
        K v = ω² M v and are signed: a negative one is a divergent mode, the
        mechanism falling away from this state.
        """
        model, data = self.compiled.model, self._data()
        if data.nefc:
            rows = sorted({_constraint(model, data, i) for i in range(data.nefc)})
            raise RuntimeError(
                f"{data.nefc} constraint row(s) active at this state "
                f"({', '.join(rows)}); a linearisation here would read the "
                f"solver's constraint stiffness, not the mechanism's")
        data.qacc[:] = 0.0  # mj_forward overwrote it with the free acceleration
        nv = model.nv
        sides = []
        for step in (eps, -eps):
            dfdq = np.zeros((nv, nv))
            mujoco.mjd_inverseFD(model, data, step, False, dfdq, None, None,
                                 None, None, None, None)
            sides.append(dfdq.T)  # MuJoCo returns it transposed
        stiffness = (sides[0] + sides[1]) / 2
        mass = np.zeros((nv, nv))
        mujoco.mj_fullM(model, data, mass)
        if nv:
            lam = eigh((stiffness + stiffness.T) / 2, mass, eigvals_only=True)
        else:
            lam = np.zeros(0)
        freq = np.sign(lam) * np.sqrt(np.abs(lam)) / (2 * np.pi)
        return Linearised(self.compiled.coordinates, _frozen(stiffness),
                          _frozen(mass), _frozen(freq), LINEARISE_METHOD, eps)


LINEARISE_METHOD = ("K: mjd_inverseFD at qacc = 0, central (mean of +eps and "
                    "-eps); M: mj_fullM")


@dataclass(frozen=True, eq=False)
class Linearised:
    """The linearisation record. Rows and columns of `stiffness` (N/m, N·m/rad)
    and `mass` follow `coordinates`; `frequencies` are in Hz, signed and
    ascending. `method` and `eps`, the finite-difference step, say how it was
    computed, since a finite-difference stiffness is only as good as its step."""
    coordinates: tuple
    stiffness: np.ndarray
    mass: np.ndarray
    frequencies: np.ndarray
    method: str
    eps: float

    def __str__(self):
        freqs = ", ".join(f"{f:.6g}" for f in self.frequencies)
        return (f"modes [{freqs}] Hz over {list(self.coordinates)}; "
                f"{self.method}, eps = {self.eps:g}")


def _constraint(model, data, row):
    kind = mujoco.mjtConstraint(data.efc_type[row]).name.removeprefix("mjCNSTR_")
    if kind == "LIMIT_JOINT":
        return f"limit on joint {model.joint(data.efc_id[row]).name!r}"
    return kind.lower()


def _frozen(array):
    array = np.array(array, dtype=float)
    array.flags.writeable = False
    return array
