"""
Mass properties as a rigid body's (m, COM, I about the COM), summed by the
parallel-axis rule. SI throughout: kg, m, kg m^2. Pure Python.

The tensor is I = sum of m (r.r 1 - r r^T): its off-diagonals are minus the
products of inertia. SOLIDWORKS's `IBody2.GetMassProperties` returns the
products themselves (Pxy = sum of m x y), so `from_solidworks` negates them;
the sign was checked against an independent recipe's tensor of the same
asymmetric body, and `smoke.py` checks it again on an L-shaped section.
"""
from __future__ import annotations


def from_solidworks(p):
    """`IBody2.GetMassProperties(density)`'s 12 values, [cx, cy, cz, volume, area, mass,
    Ixx, Iyy, Izz, Pxy, Pzx, Pyz] about the COM in the part's axes, to (m, com, I)."""
    m, c = p[5], list(p[0:3])
    ixx, iyy, izz, pxy, pzx, pyz = p[6:12]
    return m, c, [[ixx, -pxy, -pzx], [-pxy, iyy, -pyz], [-pzx, -pyz, izz]]


def combine(parts):
    """Bodies (m, com, I about its com) to the whole: (m, com, I about the whole's com)."""
    m = sum(p[0] for p in parts)
    c = [sum(p[0] * p[1][i] for p in parts) / m for i in range(3)]
    tot = [[0.0] * 3 for _ in range(3)]
    for mi, ci, ii in parts:
        d = [ci[k] - c[k] for k in range(3)]
        dd = sum(x * x for x in d)
        for a in range(3):
            for b in range(3):
                tot[a][b] += ii[a][b] + mi * ((dd if a == b else 0.0) - d[a] * d[b])
    return m, c, tot


def about(body, point):
    """(m, com, I about com) to the tensor about `point`, same axes: I + m (d.d 1 - d d^T)."""
    m, c, i = body
    d = [c[k] - point[k] for k in range(3)]
    dd = sum(x * x for x in d)
    return [[i[a][b] + m * ((dd if a == b else 0.0) - d[a] * d[b]) for b in range(3)] for a in range(3)]


def box(m, size, centre=(0.0, 0.0, 0.0)):
    """A solid box of mass m and edge lengths `size` (m), axis-aligned: (m, com, I)."""
    a, b, c = size
    return m, list(centre), [[m * (b * b + c * c) / 12, 0.0, 0.0],
                             [0.0, m * (a * a + c * c) / 12, 0.0],
                             [0.0, 0.0, m * (a * a + b * b) / 12]]
