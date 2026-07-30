#!/usr/bin/env python3
"""
check_inertia.py — close the loop between modeled geometry and assumed dynamics.

The mathematician *assumed* a mass, COM, and inertia for each body; CAD
*realizes* them. This compares the two and fails when they diverge, so a link
that came out 40% heavier than the derivation believed turns red here rather
than at actuator bring-up.

    python check_inertia.py --repo .
    python check_inertia.py --repo . --part IBEX-LNK-002 --verbose
    python check_inertia.py --self-test

Reads cad/mass-properties/<PART-ID>.json (exported from CAD, schema in
references/cad-repo-layout.md) and analysis/*_model/params.py.

The comparison is only meaningful if both sides are about the same point and
expressed in the same axes. A CAD report taken about the COM will disagree with
a correct derivation taken about the joint origin for reasons that have nothing
to do with the part, so this script transforms rather than assuming: parallel
axis for the point, a supplied rotation for the axes. When it can't reconcile
them, that is a finding, not a silent pass.

Standard library only — it runs wherever Python does, without the model's deps.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import sys
from pathlib import Path

Matrix = list[list[float]]
Vector = list[float]

DEFAULT_TOL = {"mass_rel": 0.02, "com_abs_m": 0.001, "inertia_rel": 0.05}


# ── 3x3 linear algebra, kept explicit so there are no dependencies ────────────


def identity() -> Matrix:
    return [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]


def mat_sub(a: Matrix, b: Matrix) -> Matrix:
    return [[a[i][j] - b[i][j] for j in range(3)] for i in range(3)]


def mat_add(a: Matrix, b: Matrix) -> Matrix:
    return [[a[i][j] + b[i][j] for j in range(3)] for i in range(3)]


def mat_scale(a: Matrix, s: float) -> Matrix:
    return [[a[i][j] * s for j in range(3)] for i in range(3)]


def mat_mul(a: Matrix, b: Matrix) -> Matrix:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def transpose(a: Matrix) -> Matrix:
    return [[a[j][i] for j in range(3)] for i in range(3)]


def outer(d: Vector) -> Matrix:
    return [[d[i] * d[j] for j in range(3)] for i in range(3)]


def dot(d: Vector) -> float:
    return sum(x * x for x in d)


def parallel_axis(inertia_com: Matrix, mass: float, offset: Vector) -> Matrix:
    """
    Inertia about a point displaced from the COM by `offset`.

        I_P = I_com + m * ((d . d) * I3  -  d (x) d)

    Sanity: a uniform rod of length L about its centre is m*L^2/12; shifting to
    the end (d = L/2) gives m*L^2/12 + m*L^2/4 = m*L^2/3, which is the textbook
    value. The --self-test asserts exactly that.
    """
    correction = mat_scale(mat_sub(mat_scale(identity(), dot(offset)), outer(offset)), mass)
    return mat_add(inertia_com, correction)


def inverse_parallel_axis(inertia_point: Matrix, mass: float, offset: Vector) -> Matrix:
    """Inertia about the COM, given it about a point displaced by `offset`."""
    correction = mat_scale(mat_sub(mat_scale(identity(), dot(offset)), outer(offset)), mass)
    return mat_sub(inertia_point, correction)


def rotate_inertia(inertia: Matrix, R: Matrix) -> Matrix:
    """Express an inertia tensor in rotated axes: I' = R I R^T."""
    return mat_mul(mat_mul(R, inertia), transpose(R))


# ── parsing ──────────────────────────────────────────────────────────────────


def as_matrix(value) -> Matrix | None:
    """Accept a 3x3 nested list, a 6-vector [Ixx,Iyy,Izz,Ixy,Iyz,Ixz], or a dict."""
    if isinstance(value, dict):
        keys = {k.lower(): float(v) for k, v in value.items() if isinstance(v, (int, float))}
        if {"ixx", "iyy", "izz"} <= keys.keys():
            ixy = keys.get("ixy", 0.0)
            iyz = keys.get("iyz", 0.0)
            ixz = keys.get("ixz", keys.get("izx", 0.0))
            return [
                [keys["ixx"], ixy, ixz],
                [ixy, keys["iyy"], iyz],
                [ixz, iyz, keys["izz"]],
            ]
        return None
    if isinstance(value, (list, tuple)):
        if len(value) == 3 and all(isinstance(r, (list, tuple)) and len(r) == 3 for r in value):
            return [[float(x) for x in row] for row in value]
        if len(value) == 6 and all(isinstance(x, (int, float)) for x in value):
            ixx, iyy, izz, ixy, iyz, ixz = (float(x) for x in value)
            return [[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]]
    return None


def as_vector(value) -> Vector | None:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        if all(isinstance(x, (int, float)) for x in value):
            return [float(x) for x in value]
    return None


def literals_from_python(path: Path) -> dict[str, object]:
    """
    Pull module-level literal assignments out of params.py without importing it,
    so this runs without sympy, numpy, or the project installed.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return {}

    found: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                continue
            found[target.id] = value
            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(k, str):
                        found.setdefault(k, v)
    return found


# ── comparison ───────────────────────────────────────────────────────────────


class Finding:
    def __init__(self, part: str, severity: str, message: str):
        self.part, self.severity, self.message = part, severity, message

    def __str__(self) -> str:
        return f"  {self.severity:<8} {self.part}: {self.message}"


def compare_part(report: dict, params: dict[str, object], tol: dict, verbose: bool) -> list[Finding]:
    part = report.get("part_id", "<unnamed>")
    out: list[Finding] = []

    keys = report.get("params_keys") or {}
    if not keys:
        return [Finding(part, "MAJOR", "no params_keys mapping — nothing to compare against")]

    realized_mass = report.get("mass_kg")
    realized_com = as_vector(report.get("com_m"))
    realized_I = as_matrix(report.get("inertia_kg_m2"))

    # ── mass ──
    mass_key = keys.get("mass")
    if mass_key and realized_mass is not None:
        assumed = params.get(mass_key)
        if not isinstance(assumed, (int, float)):
            out.append(Finding(part, "MAJOR", f"params key '{mass_key}' not found or not numeric"))
        else:
            rel = abs(realized_mass - assumed) / max(abs(assumed), 1e-12)
            if rel > tol["mass_rel"]:
                out.append(Finding(
                    part, "BLOCKER" if rel > 4 * tol["mass_rel"] else "MAJOR",
                    f"mass realized {realized_mass:.4f} kg vs assumed {assumed:.4f} kg "
                    f"({rel * 100:.1f}% off, tolerance {tol['mass_rel'] * 100:.0f}%) — "
                    "actuator sizing rode on the assumed value",
                ))
            elif verbose:
                print(f"    mass ok: {realized_mass:.4f} kg vs {assumed:.4f} kg ({rel * 100:.2f}%)")

    # ── COM ──
    com_key = keys.get("com")
    if com_key and realized_com:
        assumed_com = as_vector(params.get(com_key))
        if assumed_com is None:
            scalar = params.get(com_key)
            if isinstance(scalar, (int, float)):
                # A 1-D derivation often carries COM as a single offset along the link.
                along = max(range(3), key=lambda i: abs(realized_com[i]))
                delta = abs(realized_com[along] - float(scalar))
                if delta > tol["com_abs_m"]:
                    out.append(Finding(
                        part, "MAJOR",
                        f"COM offset along axis {'xyz'[along]} realized "
                        f"{realized_com[along]:.4f} m vs assumed {float(scalar):.4f} m "
                        f"({delta * 1000:.2f} mm off)",
                    ))
                elif verbose:
                    print(f"    com ok (scalar): {realized_com[along]:.4f} m vs {float(scalar):.4f} m")
            else:
                out.append(Finding(part, "MAJOR", f"params key '{com_key}' not found or not a 3-vector"))
        else:
            delta = math.sqrt(sum((a - b) ** 2 for a, b in zip(realized_com, assumed_com)))
            if delta > tol["com_abs_m"]:
                out.append(Finding(
                    part, "MAJOR",
                    f"COM realized {[round(v, 4) for v in realized_com]} vs assumed "
                    f"{[round(v, 4) for v in assumed_com]} ({delta * 1000:.2f} mm apart)",
                ))
            elif verbose:
                print(f"    com ok: {delta * 1000:.3f} mm apart")

    # ── inertia, after reconciling point and axes ──
    inertia_key = keys.get("inertia")
    if not (inertia_key and realized_I):
        return out

    assumed_I = as_matrix(params.get(inertia_key))
    if assumed_I is None:
        out.append(Finding(part, "MAJOR", f"params key '{inertia_key}' not found or not an inertia tensor"))
        return out

    cad_about = str(report.get("inertia_about", "com")).lower()
    expects = report.get("dynamics_expects") or {}
    dyn_about = str(expects.get("about", cad_about)).lower()
    cad_axes = report.get("inertia_axes")
    dyn_axes = expects.get("axes", cad_axes)

    working = realized_I

    # Axes first: rotating then translating is not the same as the reverse.
    if cad_axes != dyn_axes:
        R = as_matrix(report.get("rotation_to_dynamics_axes"))
        if R is None:
            out.append(Finding(
                part, "MAJOR",
                f"CAD reports inertia in axes '{cad_axes}' but the dynamics use "
                f"'{dyn_axes}', and no rotation_to_dynamics_axes was supplied — "
                "an inertia tensor in the wrong frame is not comparable",
            ))
            return out
        working = rotate_inertia(working, R)
        if verbose:
            print(f"    rotated inertia from {cad_axes} to {dyn_axes}")

    if cad_about != dyn_about:
        offset = as_vector(report.get("joint_to_com_m")) or realized_com
        if offset is None or realized_mass is None:
            out.append(Finding(
                part, "MAJOR",
                f"inertia is about '{cad_about}' but the dynamics use '{dyn_about}', "
                "and the offset needed for a parallel-axis shift is missing "
                "(supply joint_to_com_m)",
            ))
            return out
        if cad_about == "com" and dyn_about in {"joint", "origin"}:
            working = parallel_axis(working, realized_mass, offset)
        elif cad_about in {"joint", "origin"} and dyn_about == "com":
            working = inverse_parallel_axis(working, realized_mass, offset)
        else:
            out.append(Finding(
                part, "QUESTION",
                f"cannot reconcile inertia reference points '{cad_about}' -> '{dyn_about}'",
            ))
            return out
        if verbose:
            print(f"    parallel-axis shifted inertia from {cad_about} to {dyn_about}")

    scale = max(abs(assumed_I[i][j]) for i in range(3) for j in range(3))
    scale = max(scale, 1e-12)
    worst, where = 0.0, ""
    for i in range(3):
        for j in range(3):
            rel = abs(working[i][j] - assumed_I[i][j]) / scale
            if rel > worst:
                worst, where = rel, f"I[{i}][{j}]"

    if worst > tol["inertia_rel"]:
        out.append(Finding(
            part, "MAJOR",
            f"inertia diverges by {worst * 100:.1f}% at {where} (tolerance "
            f"{tol['inertia_rel'] * 100:.0f}%), compared about '{dyn_about}' in "
            f"axes '{dyn_axes}' — the dynamics are validating a body this part is not",
        ))
    elif verbose:
        print(f"    inertia ok: worst component {worst * 100:.2f}% at {where}")

    return out


# ── self-test ────────────────────────────────────────────────────────────────


def self_test() -> int:
    """Verify the transforms against closed-form results before trusting them."""
    m, L = 2.5, 0.4

    I_com = [[0.0, 0.0, 0.0], [0.0, m * L**2 / 12, 0.0], [0.0, 0.0, m * L**2 / 12]]
    I_end = parallel_axis(I_com, m, [L / 2, 0.0, 0.0])
    expected = m * L**2 / 3
    assert abs(I_end[2][2] - expected) < 1e-12, f"rod about end: {I_end[2][2]} != {expected}"
    assert abs(I_end[0][0]) < 1e-12, "axial inertia must not change under an axial shift"
    print(f"  parallel axis, uniform rod: I_end = {I_end[2][2]:.6f} = m*L^2/3 = {expected:.6f}  ok")

    back = inverse_parallel_axis(I_end, m, [L / 2, 0.0, 0.0])
    assert all(abs(back[i][j] - I_com[i][j]) < 1e-12 for i in range(3) for j in range(3))
    print("  inverse parallel axis round-trips  ok")

    # A 90-degree rotation about z swaps the xx and yy moments.
    Rz = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    I_aniso = [[1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0]]
    rotated = rotate_inertia(I_aniso, Rz)
    assert abs(rotated[0][0] - 2.0) < 1e-12 and abs(rotated[1][1] - 1.0) < 1e-12
    assert abs(rotated[2][2] - 3.0) < 1e-12
    print("  rotation swaps xx/yy under Rz(90 deg)  ok")

    # Trace is a rotational invariant.
    assert abs(sum(rotated[i][i] for i in range(3)) - sum(I_aniso[i][i] for i in range(3))) < 1e-12
    print("  trace invariant under rotation  ok")

    for parser, value, label in [
        (as_matrix, {"Ixx": 1, "Iyy": 2, "Izz": 3, "Ixy": 0.1}, "dict form"),
        (as_matrix, [1, 2, 3, 0.1, 0, 0], "6-vector form"),
        (as_matrix, [[1, 0.1, 0], [0.1, 2, 0], [0, 0, 3]], "3x3 form"),
    ]:
        got = parser(value)
        assert got is not None and abs(got[0][0] - 1.0) < 1e-12, label
        assert abs(got[0][1] - got[1][0]) < 1e-12, f"{label} must be symmetric"
    print("  inertia parsers agree across dict / 6-vector / 3x3 forms  ok")

    print("\n  self-test passed.")
    return 0


# ── entry point ──────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--part", help="check one PART-ID only")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--self-test", action="store_true", help="verify the transforms and exit")
    ap.add_argument("--mass-tol", type=float, default=DEFAULT_TOL["mass_rel"])
    ap.add_argument("--com-tol", type=float, default=DEFAULT_TOL["com_abs_m"])
    ap.add_argument("--inertia-tol", type=float, default=DEFAULT_TOL["inertia_rel"])
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    repo = Path(args.repo).resolve()
    mp_dir = repo / "cad" / "mass-properties"
    if not mp_dir.is_dir():
        print(f"no {mp_dir.relative_to(repo)} — export mass properties from CAD first "
              "(schema in references/cad-repo-layout.md)", file=sys.stderr)
        return 2

    params: dict[str, object] = {}
    model_files = sorted(repo.glob("analysis/*_model/params.py"))
    for path in model_files:
        params.update(literals_from_python(path))
    if not params:
        print("no readable analysis/*_model/params.py — nothing to compare against", file=sys.stderr)
        return 2

    reports = sorted(mp_dir.glob("*.json"))
    if args.part:
        reports = [p for p in reports if p.stem == args.part]
        if not reports:
            print(f"no mass-properties export for {args.part}", file=sys.stderr)
            return 2

    tol = {"mass_rel": args.mass_tol, "com_abs_m": args.com_tol, "inertia_rel": args.inertia_tol}
    findings: list[Finding] = []

    print(f"inertia loop — {repo}\n")
    for path in reports:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(Finding(path.stem, "BLOCKER", f"mass-properties export does not parse: {exc}"))
            continue
        if args.verbose:
            print(f"  {path.stem}:")
        per_part = dict(tol)
        per_part.update({k: v for k, v in (report.get("tolerances") or {}).items() if k in tol})
        findings.extend(compare_part(report, params, per_part, args.verbose))

    if not findings:
        print(f"  {len(reports)} part(s) checked — realized geometry agrees with the derivation.")
        return 0

    order = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2, "QUESTION": 3}
    findings.sort(key=lambda f: order.get(f.severity, 9))
    for f in findings:
        print(f)
    blocking = sum(1 for f in findings if f.severity != "QUESTION")
    print(f"\n  {len(findings)} finding(s) across {len(reports)} part(s).")
    if blocking:
        print("  Route to armature-mathematician with the realized values and re-run the dynamics.")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
