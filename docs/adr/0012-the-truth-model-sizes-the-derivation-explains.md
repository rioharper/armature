# ADR 0012 — The truth model sizes a part; the derivation explains it and checks it

2026-10-23 — Status: accepted (amends ADR 0004's split of what the engine holds and what the project keeps)

A sizing number comes from the truth model. Every `Margin` the derivation
declares evaluates the compiled full description at every search point, and
the derivation's own expression is the second evaluation at the worst point
and the pre-polish best. The drive margins already worked this way. `SIGMA`
and `HOLDING` now do too:
- `SIGMA` is the SVD of `s.jacobian`;
- `HOLDING` is `s.inverse(loads=...)`, with the load case applied as a force
  at its site and the `settle` hold kept as its confirmation.

A margin's second evaluation is `check=`, renamed from `truth=`, since it is
now usually the derivation. Its result is `Worst.check`, and `agree=` stays.
The truth gate (`references/model-layout.md`) reads: every module-level
`Margin` passes `check=` and `agree=`, and the truth model is on one side of
it.

**The symbolic derivation stays mandatory at every size.** Milestone 2's
equations are formed for every mechanism. They are what the dynamics truth
check compares against, and they are what a person reads. What changes is who
forms them and how:

- **The engine forms them.** `armature.equations(variant, params)` builds a
  `sympy.physics.mechanics` `System` on the symbolic view's frames. It uses
  Kane's method with the generalized speeds set to q̇, so M is Lagrange's M.
  The view's closures become holonomic constraints, and joint springs and
  elastic cables become `LinearSpring` actuators. It returns:
  - M;
  - the forcing, as C·q̇ and g separately;
  - the coordinates;
  - `numeric(expr, rates=...)`, which runs `xreplace`, then `lambdify(...,
    cse=True)`, with the banded parameters kept as keywords;
  - `christoffel()`, the C matrix, on demand only.
- **Nothing in the build path simplifies.** The report modules simplify what
  they print, entry by entry under an operation cap. An entry over the cap
  prints as the coordinates it depends on. A symbolic identity the build used
  to assert becomes a numeric check at sampled states.
- **Contact is never symbolic.** A variant reduces it away, and its release
  check sizes the cost. Rotor inertia, N²J, stays the derivation's to add.
- **A floating base answers in the view's coordinates.** The view writes a free
  joint's turns as Euler angles, and MuJoCo's rates are the body's angular
  velocity. The engine maps between them, so a truth-model state can answer
  `inverse()` in the view's coordinates.
- **A subsystem is a variant.** Ibex's leg alone is `reduce(mechanism,
  lock(base), ...)`. There is no second notion.

The project's `dynamics/lagrangian.py` becomes `dynamics/equations.py`. It
calls the engine verb and adds what only this machine has. The note keeps its
Euler-Lagrange presentation: T and V, the structure, the limiting cases.

**Why.** On 2026-10-11 the template's Lagrangian timed out at four links, and
the proposal was to drop symbolic dynamics above three joints. Re-measured on
2026-10-23 (Python 3.14, SymPy 1.14, MuJoCo 3.15), the cost was the template's
shape, not SymPy:

| Chain | Template (Lagrange + simplify) | Kane via `System`, no simplify, `xreplace`+`cse` |
|---|---|---|
| planar 4 | 93 s | ~2 s |
| planar 6 | timed out at 300 s | ~15 s |
| spatial 4R | its assert failed after ~290 s | ~2.5 s |
| spatial 6R | timed out | ~31 s (26 s of it the Christoffel C) |
| wheel_leg | 184 s, open tree, its loop ignored | 0.8 s, with the loop |

Every method that finished matched `mj_fullM` and `qfrc_bias` to 1e-14, and
both rewrites passed the template's 1e-12 closed-form check. The template's
copy also ignored the view's closures. So on wheel_leg it formed open-tree
equations, and on cable_platform a platform in free fall with no cables. Each
project copies that file once and never receives a fix, which is the reason
ADR 0004 puts machinery in the pinned engine.

The derivation reads the reduced variant, and the truth model compiles the full
description. A part sized from the variant misses whatever a reduction removed,
so the full description sizes it. That is also faster at size: an `at()` plus
`inverse()` costs 55–115 µs, against 128–273 µs for the lambdified M, C and g
of a spatial 6R.

**Rejected:**
- **Symbolic dynamics only up to N joints:** the cost that motivated it is gone.
- **Leaving each project's `lagrangian.py` to form the equations:** the closure
  bug would ship in every copy.
- **`LagrangesMethod`:** 5.1 s against Kane's 0.8 s on wheel_leg, with the
  same M.
- **Always forming the Christoffel C:** the dynamics truth check needs only C·q̇.
- **A disk cache of symbolic results:** the gate's content-keyed stamps
  (ADR 0011) already skip an unchanged run.
- **A seventh golden mechanism for the 6R:** a golden mechanism is a row
  against every verb (ADR 0008). An engine fixture test holds the 6R instead,
  and `equations` gets its own row across the six golden mechanisms.

**Consequences:**
- `Margin`'s `truth=` becomes `check=`, so the release is a major (4.0.0).
- Editing the derive skill re-gates the release (`evals/README.md`).
- A project on 3.x meets the change as `behind … (major)` at its next
  checkpoint.
