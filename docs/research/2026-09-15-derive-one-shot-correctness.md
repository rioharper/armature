# Why armature-derive gets the math wrong one-shot, and what would fix it

2026-09-15 — research note for the plugin, from the Plumb project's two red-team
reviews (`Plumb/docs/reviews/2026-09-13-spec-rev1.1-review.md`,
`Plumb/docs/reviews/2026-09-13-m1-kinematics-review.md`).

## 1. What the reviews actually caught

The Milestone 1 review is explicit: the structure matrix, the inverse kinematics,
the closed-form max-min floor, the distribution law and the feasibility predicate
were "all correct and independently reproduced". Nothing in either review disputes
a printed number. Every finding is about **which physics the model included**, not
whether the arithmetic was right. Sorted by family:

| Family | Findings | The mistake |
|---|---|---|
| **A DOF assumed fixed that is free** | M1 F1 (blocker), M1 F2 | Assumption A5 held the platform level. The anchor square is a scaled copy of the attachment square, so W has rank 3 at every level pose and all three rotations are free; gravity sets the tilt (5–26°). K_e's diagonal was read as a tilt stiffness when the matrix is rank 3 and its null directions are the rotations. |
| **Worst case over a set evaluated at a few samples** | spec F1, spec F3, M1 F4, M1 F6 | Tension sized at the room centre only; peak tension at mid-height only; "worst horizontal direction" as +x alone (the true intersection over directions is 39 %, not 75 %); continuity on four hand-picked paths. |
| **Load-case sign or enumeration** | M1 F3, M1 F5, spec F4, spec F5 | "0.5 g vertical" read as upward only, when downward halves every tension and is the floor-binding case; brake-at-speed and single-cable regen missing from the case set. |
| **Textbook formula outside its assumptions** | M1 F2, spec F7 | Bifilar-pendulum yaw stiffness (parallel wires) used on converging cables: 27× low. A 0.3 Hz pendulum mode named for a platform on four taut cables. |
| **Material or component data** | spec F6, F10, F11, F14 | EA under-stated 4×; axial vs total pole load; termination knock-down. |

Two things stand out. First, the derivation's own checks are all
**self-consistency checks of one model**: W against finite differences of the
same length function, the LP against the closed form of the same law. A check
of that shape cannot see a wrong assumption, because the assumption is on both
sides. Second, every named pose in the note sits on a symmetry plane of the rig
(room centre, edge midpoints, low corner), and on the symmetry planes the
realised tensions stay within 0.3 N of the law's. The reviewer found F1 by
sampling random poses.

## 2. The experiment: the truth model already existed

The reviewer built the equilibrium solve by hand in SciPy (unilateral springs,
potential minimised over six pose coordinates). Plumb pins MuJoCo 3.13.0 and has
had a passing spatial-tendon smoke test since T0.1. MuJoCo tendons take a
two-value `springlength` deadband, which is exactly a slack-capable cable
(zero force below the rest length, linear spring above it).

Forty lines (`scratchpad/mj_settle.py`, recorded below) command the cable
lengths from the Rev 1.0 level-platform IK, hang the platform on four such
tendons with k_i = EA/ℓ0_i, step to rest, and read the pose:

```
room centre 1.2      tilt   0.0 deg   |dp|   0.0 mm   T [12.16 12.16 12.16 12.16]
edge midpoint        tilt  20.8 deg   |dp|  26.8 mm   T [16.71  3.93  3.93 16.71]
top edge midpoint    tilt  14.7 deg   |dp|  13.0 mm   T [35.73 35.73  8.84  8.84]
low corner 2.5 kg    tilt  26.3 deg   |dp|  52.3 mm   T [22.61  0.    7.72  0.  ]
```

That is the review's F1 table to the printed precision (20.8° / 27 mm /
16.71–3.93 N; 14.7°; 26° / 52 mm / 22.6–0–7.7–0 N), in one second of wall time.
Had Milestone 1 carried a "settle the rig in MuJoCo at ten random envelope
poses and compare tilt and tensions to the law" check, A5 would have failed at
the first checkpoint run instead of at review.

```python
# mj_settle.py (run from Plumb with PYTHONPATH=analysis/model)
import numpy as np, mujoco
from scipy.spatial.transform import Rotation
from params import A_ROOM, B_ATTACH, C_P, EA, G
from kinematics.lengths import cable_geometry, unstretched_length
from kinematics.distribution import distribute

def level_l0(p, m):
    d = distribute(p, np.eye(3), m, np.zeros(3))
    l, _, _ = cable_geometry(p, np.eye(3))
    return unstretched_length(l, d.T)

def mjcf(p, l0, m):
    k = EA / l0
    anchors = "".join(f'<site name="a{i}" pos="{a[0]} {a[1]} {a[2]}"/>' for i, a in enumerate(A_ROOM))
    batt = "".join(f'<site name="b{i}" pos="{b[0]} {b[1]} {b[2]}"/>' for i, b in enumerate(B_ATTACH))
    tend = "".join(f'<spatial name="c{i}" stiffness="{k[i]}" springlength="0 {l0[i]}" damping="2.0">'
                   f'<site site="a{i}"/><site site="b{i}"/></spatial>' for i in range(4))
    return f"""<mujoco><option timestep="0.0005" gravity="0 0 -{G}"/>
    <worldbody>{anchors}<body name="plat" pos="{p[0]} {p[1]} {p[2]}"><freejoint/>
    <inertial pos="{C_P[0]} {C_P[1]} {C_P[2]}" mass="{m}" diaginertia="0.02 0.02 0.02"/>{batt}</body>
    </worldbody><tendon>{tend}</tendon></mujoco>"""

def settle(p, m=2.0, t_end=20.0):
    l0 = level_l0(p, m)
    model = mujoco.MjModel.from_xml_string(mjcf(p, l0, m))
    data = mujoco.MjData(model)
    model.dof_damping[:] = [0.5] * 3 + [0.05] * 3
    for _ in range(int(t_end / model.opt.timestep)):
        mujoco.mj_step(model, data)
    q = data.qpos[3:7]
    R = Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_matrix()
    tilt = np.degrees(np.arccos(R[2, 2]))
    T = EA / l0 * np.maximum(data.ten_length - l0, 0)
    return tilt, np.linalg.norm(data.qpos[:3] - p) * 1e3, T
```

## 3. Libraries and reference structures

Verified on 2026-09-15; platform notes matter because Plumb's sim host is
Windows with a WSL Ubuntu 24.04 beside it.

| Library | What it gives the derivation | Fit | Platform |
|---|---|---|---|
| **MuJoCo** (already pinned) | Independent equilibrium, constraint forces, unilateral cables via `springlength="0 l0"`, `mjd_transitionFD` for linearisation and modes, `mj_inverse` for Newton-Euler torques | The truth model for every static and modal claim; the one library the fix needs | pip, all platforms |
| **Pinocchio** (`pin`) | Featherstone rigid-body algorithms: RNEA, ABA, CRBA, frame Jacobians, analytical derivatives, floating base, Lie-group integration | An independent Newton-Euler model to check a SymPy Lagrangian against; serial and tree robots, floating base | pip wheels Linux and macOS only (4.1.0, July 2026); Windows via conda-forge `win-64` or WSL |
| **`sympy.physics.mechanics`** | `ReferenceFrame`, `Point` with the two-point velocity theorem, `KanesMethod` / `LagrangesMethod` with holonomic and nonholonomic constraints, auxiliary speeds for constraint forces | Replaces the template's hand-rolled Euler-Lagrange loop; frames and velocities are built by the library, so a wrong ω or a missed term is not possible by construction | already a dependency |
| **spatialmath-python**, **roboticstoolbox-python** | SE3/SO3/UnitQuaternion with stated conventions; DH and ETS models, Jacobians, RNE dynamics, manipulability | Serial-chain projects and frame-convention hygiene; v1.4.0 (Aug 2026), moved to the RAI-Opensource org in April 2026 | pip |
| **Drake** (`pydrake`) | MultibodyPlant with symbolic support, exact linearisation, MathematicalProgram | The strongest verification stack, but heavy | Linux and macOS only; WSL on this host |
| **WireX** (Pott, Fraunhofer GitLab, MIT) | CDPR-specific: workspace, force distribution, stiffness, singularities | The reference implementation for cable-robot algorithms; C++ with WireCenter GUI, no maintained Python package (23 commits since 2019) | source build |
| **CASPR** (Lau) | CDPR analysis and simulation | MATLAB only | n/a |
| **Brax** | Batched differentiable rollouts on GPU | Rejected: its README (0.13.0) says only `brax/training` is maintained and directs physics users to MJX or MuJoCo Warp; batching solves a training problem, and four settles take one second on CPU | JAX |
| **MJX** | JAX reimplementation of MuJoCo | Rejected as a truth model: same engine, not independent; partial tendon support (broke in 3.3.3) | JAX |

**On assuming Anaconda:** it buys Pinocchio on Windows, and Pinocchio would not
have caught Plumb's blocker, which needed a free body on unilateral springs.
Pinocchio is a chain library with no constraints or tendons. Keep MuJoCo
mandatory (pip, every platform, both topologies, `mj_inverse` and
`mjd_transitionFD`) and let the environment probe enable Pinocchio as an
optional second model where conda or WSL provides it.
| **SciPy** `linprog`, `ConvexHull`, **pycddlib** | Exact wrench-feasible workspace by the hyperplane-shifting or convex-hull method on the available wrench set | Answers "feasible in every horizontal direction" exactly instead of by sampling directions | pip |

The CDPR algorithms the M1 note should have cited by chapter rather than
reinvented: Pott, *Cable-Driven Parallel Robots* (Springer 2018), chapter 3 for
the structure matrix, architecture singularities and the "similar platforms"
degenerate case that is exactly Plumb's rank-3 result; chapter 4 for the
closed-form and improved closed-form force distributions; chapter 5 for the
wrench-feasible workspace by the hyperplane-shifting method (Bouchard, Gosselin
and Moore 2010; Gouttefarde and Krut 2010) and the elastic-plus-geometric
stiffness matrix whose geometric term is what F2 missed.

What would not have helped: a units library (`pint`) catches dimension errors,
and none of the findings were dimension errors; more SymPy simplification
catches algebra errors, and the algebra was right.

## 4. Proposed changes to armature-derive

Ordered by how many of the findings each would have caught.

1. **Truth model before the first analytic claim.** Milestone 0 writes the
   simulator model (MJCF for a floating body, Pinocchio or MuJoCo for a chain)
   from `params.py`, and every equilibrium, tension, stiffness and mode number
   in a note carries a check against a settle or a linearisation of that model.
   Plumb's plan puts the MuJoCo models (T1.10) after the dynamics milestone
   (T1.3) and the dynamics report (T1.7); invert that order in `armature-plan`'s
   phase template so the simulator is an input to the derivation, not a
   consumer of it.
2. **An assumption that removes a DOF is tested by releasing it.** The
   `00_setup.md` assumption list gets a rule: any assumption that fixes a
   coordinate (orientation given, link rigid, anchor fixed) gets a check that
   frees it in the truth model and reports the size of what moves. A5 was the
   one assumption in Plumb's list never sized; the seven others were.
3. **Random poses, never only named ones.** Checks sample the envelope with a
   seeded RNG (or `hypothesis`); named symmetric poses are printed for the
   reader but are not the evidence. Both blockers hide on symmetry planes.
4. **Singular values of every matrix that gets inverted, swept.** Not "rank of
   the force rows" but the full singular-value profile of W (or J) over random
   envelope poses, printed by the report module, with a check that the smallest
   is bounded away from zero where the derivation needs full rank.
5. **Worst case over a set is computed, not sampled.** A requirement that says
   "any direction", "anywhere in the workspace", or "worst" is answered with an
   exact set method (convexity, LP, a zonotope), an optimiser, or a dense sweep
   whose grid step is stated with the result; a handful of directions is a
   finding at review. Every signed load case is enumerated in both signs.
6. **A textbook formula carries its applicability check.** A closed form
   (bifilar yaw, pendulum mode, moment-arm statics) is checked against the
   numeric Hessian or the simulator at three poses before the note cites it,
   and the check names the assumption the formula rests on.
7. **Two independent models for dynamics.** Milestone 2's Lagrangian (SymPy
   mechanics, not the hand loop) is checked against Newton-Euler from
   Pinocchio RNEA or MuJoCo `mj_inverse` at random states. Symmetry, skew
   symmetry and energy conservation stay, but they are self-consistency, not
   correctness.
8. **Reference algorithms cited by chapter, tagged `standard`.** The existing
   book-data rule extends to algorithms: a workspace, distribution or stiffness
   method names its source and chapter in `00_setup.md`, so the red team can
   read the derivation against the book's assumptions.

Items 2 to 6 are rules in `SKILL.md` and `derivation-standards.md` plus a probe
each in `agents/references/review-checklist.md`. Item 1 changes the model
template (a `truth/` package with the MJCF generator and a settle helper) and
the plan's phase ordering. Item 7 changes the dynamics template.

## 5. Spec

Published as [Truth model: an independent simulator check at every derive milestone](https://github.com/rioharper/armature/issues/48), labelled `ready-for-agent`. Test seam: the model template's own `run_all.py` and `pytest` run; Plumb Milestone 1 is the manual acceptance case.
