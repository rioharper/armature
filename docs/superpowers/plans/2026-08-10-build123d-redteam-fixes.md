# Plan: build123d executable-recipe red-team fixes

Fix the 17 findings from the red-team review of the build123d executable
build recipes in `skills/armature-cad/scripts/part_template/`.

Baseline commit: `31677ce`. Branch: `armature/build123d-recipes`.

## Context

`skills/armature-cad/scripts/part_template/` is a **template** that
`armature-cad` instructs Claude to copy into a robotics project's
`cad/parts/`. Four Python files plus a README:

- `check.py` — library: SI mass properties, `_parallel_axis`,
  `compare_to_target`, `contained`, `rebuild_sweep`, `interference`,
  `sweep_clearance`, `write_views`, `report`. Holds the unit contract.
- `part.py` — template for `cad/parts/<PART-ID>.py`; worked example ARM-BRK-001.
- `sweep.py` — planning-stage interference sweep; worked example planar 2R arm.
- `stubs.py` — COTS placeholders with enforced datasheet provenance.

The review's through-line: **seven findings are one bug wearing seven hats —
a check that returns green when it checked nothing.** The unit arithmetic,
`_parallel_axis`, and the 2R FK were all independently verified correct and
must not be disturbed.

## Global Constraints

These bind every task. Violating one is a defect regardless of what a task
brief says.

1. **The unit contract is law and is already correct.** build123d geometry
   is mm; everything `check.py` returns is SI (m, kg, kg·m²). `mm()` is the
   only place a factor of 1000 appears. Conversions: volume `mm³ × 1e-9 × ρ`
   → kg; COM `mm × 1e-3` → m; inertia `mm⁵ × ρ × 1e-15` → kg·m².
   **Do not change any conversion factor.** Verified correct against
   closed-form; a regression here is the worst possible outcome.
2. **`_parallel_axis` is verified correct.** Do not modify its math.
3. **`sweep.py::pose`'s 2R forward kinematics is verified correct** (it had a
   double-rotation bug that is fixed). Do not modify the FK.
4. **Fail loud, never green-on-nothing.** A check given empty, absent,
   zero-volume, malformed, or renamed input must raise or report failure —
   never silently pass. This is the review's central theme.
5. **Every `.py` file keeps a runnable `demo()` self-check** that exits 0 on
   pass and nonzero on failure, runnable as
   `uv run --with 'build123d~=0.11' python <file>`. Every fix in these tasks
   adds an assertion to the relevant `demo()` that fails if the fix is
   reverted. No test frameworks, no fixtures.
6. **ASCII only in any string that gets printed.** Em dashes are fine in
   docstrings and comments; they garble on a Windows cp1252 console when
   printed. `report()`, `index_rows()`, error messages, `main()` output.
7. **Docs and code must agree.** If a fix changes behavior, update the
   docstring, `part_template/README.md`, and any claim in
   `skills/armature-cad/SKILL.md` that the change makes false. Never leave
   an overclaim standing — overclaiming is the failure mode already caught
   twice in this review.
8. **Honor "earn the parameter."** Per `skills/armature-cad/SKILL.md`: only
   dimensions traced to `params.py` or an interface contract are driven
   (function arguments); everything else is a typed module constant. Do not
   add parameters; remove ones that aren't earned.
9. **Never restate a number that lives in `params.py` or an interface
   table** — import it. This is the templates' own stated cardinal rule.
10. **Testing:** run the file's own `demo()` plus any file that imports it.
    `check.py` is imported by `part.py` and `sweep.py`, so a change to
    `check.py` requires running all three. Use
    `uv run --with 'build123d~=0.11' python <file>`; add `--with sympy` for
    a file that imports `params.py`. Note: piping to `tail` masks the exit
    code — verify exit codes with `$?` directly or `PIPESTATUS`.

---

## Task 1: Fix `check.py` — the library's green-on-nothing paths

**File:** `skills/armature-cad/scripts/part_template/check.py`

Task 1 must land first: `part.py` and `sweep.py` both import `check.py`.

### F2 (BLOCKER) — `compare_to_target` passes with the axial inertia 20× wrong

In the inertia loop, the near-zero branch
(`if abs(want) < 0.01 * scale`) is applied to **all nine** tensor entries
including the diagonal. Its justification ("products of inertia are
routinely ~0") holds only off-diagonal. A slender body — every robot link —
has a diagonal term below `0.01 × max(diagonal)`, so its moment of inertia
gets an absolute tolerance of `0.10 × Iyy`, which can exceed the term itself
by orders of magnitude.

Demonstrated: a 400×8×8 mm bar target (`Ixx = 7.37e-07`) vs a realized
30 mm-OD tube (`Ixx = 1.49e-05`) — 20× wrong — returns `[]` (pass).

**Fix:** apply the `scale`-relative branch only when `i != j`. Diagonal
terms always get the fractional test. A diagonal target that is legitimately
zero needs a separate absolute floor rather than falling into the
off-diagonal branch.

**Test:** add a `demo()` assertion using the bar-vs-tube case above (or an
equivalent slender-body pair) that fails if the `i != j` guard is removed.

### F3 (MAJOR) — empty or mistyped target passes silently

`compare_to_target(props, {}) -> []` and
`compare_to_target(props, {"masss": 0.0001}) -> []`. Every branch is
`if "<key>" in target`, so a typo is a permanently green gate.

**Fix:** raise on an empty target; raise on unknown keys. Recognized keys
are `mass`, `com`, `com_tol`, `inertia`, `about`.

**Test:** `demo()` asserts both raise.

### F4 (MAJOR) — `contained()` returns True for any zero-volume `inner`

`contained` sums `leak.solids()`. A face, wire, or sketch has none, so the
sum is 0 and it returns True regardless of position — including 500 mm away.
The docstring makes this worse by instructing "call it on the feature's
**footprint**", which reads as a sketch or face.

**Fix:** raise (do not return True) when `inner.volume <= 0`. Fix the
docstring to say a **solid** probe.

**Test:** `demo()` asserts a zero-volume `inner` raises.

### F8 (MAJOR) — `write_views` draws each view at a different scale

`extent` is recomputed inside the per-view loop, so each view is
independently normalized to 100 units. Measured: the same 6 mm plate is
7.50 mm in the front view and 8.00 mm in the right view; an 80 mm plate
declares `width="100.09mm"`. The files declare `Unit.MM` and are wrong by
25%, inconsistently between views.

This matters because `references/documentation-standards.md` now promotes
these views from "crude is fine" to "better than crude", which invites a
reader to measure.

**Fix:** compute `extent` once across all requested views so the set shares
one scale. Preferred: export true 1:1 (drop the `scale=` normalization) so
the declared millimetres are real millimetres.

**Test:** `demo()` asserts two views of the same part report the same scale
for a shared feature (or that a known dimension exports at its true size).

### F14 (MINOR) — two more silent-partial paths in `compare_to_target`

- `compare_to_target(props, {"com": (0.0,)}) -> []` — `zip` truncates, so y
  and z are never compared and nothing says so. **Fix:** require
  `len(target["com"]) == 3`.
- `about` is compared as a **formatted string**, so
  `about=(50.0, 0, 0)` yields `'point (50.0, 0, 0) mm'` and a target written
  `"point (50, 0, 0) mm"` false-FAILs. `part.py`'s own commented template
  suggests exactly that string. **Fix:** compare structurally — store the
  tuple (or `None` for COM) in the returned dict and compare that; keep a
  human-readable label for `report()` output.

**Test:** `demo()` asserts the short-`com` case raises and that a structural
`about` round-trips without a false failure.

### F15 (MINOR) — `min_volume` does nothing at its default

`sweep_clearance(min_volume=1e-6)` is documented as a "tangency noise
floor", but exact face tangency returns **exactly 0.0** and a 0.0001 mm
interpenetration returns 0.01 mm³ — 10⁴× the floor. Nothing real lands in
between.

**Fix:** either raise the default to something physically meaningful for
envelope work (~1 mm³) or reword the docstring to state that tangency reads
as exactly zero and this only filters slivers. Pick one and make the
docstring match the behavior.

### F17 (QUESTION) — is `contained(tol=1e-6)` calibrated against OCC sliver noise?

Unresolved by the review: the worked example never drives the probe near
the R6 filleted corners, which is where OCC booleans leave slivers.

**Fix:** add one deliberately tangent case to `demo()` — a probe tangent to
a filleted corner — and confirm `tol=1e-6` mm³ sits above the noise. If it
does not, raise `tol` to a value that does and document the measured basis
in the docstring.

### Task 1 acceptance

- `uv run --with 'build123d~=0.11' python check.py` exits 0.
- `part.py` and `sweep.py` still exit 0 (Task 1 must not break its consumers;
  if a signature change requires it, update the call sites minimally and say
  so in the report — Tasks 2 and 3 own the deeper changes to those files).
- Every fix above has a `demo()` assertion that fails if the fix is reverted.

---

## Task 2: Fix `part.py` — the exemplar's false-provenance and silent-wrong paths

**File:** `skills/armature-cad/scripts/part_template/part.py`
**Depends on:** Task 1 (imports `check.py`).

This is the file users copy. Every defect here is a defect propagated to
every project that uses the template.

### F1 (BLOCKER) — a renamed `params.py` key silently reverts and prints a false provenance line

`except (ImportError, KeyError)` swallows exactly the two events that mean
the loop is broken. With `params.py` present but the key renamed (the most
likely re-derivation event), the tool prints
`target from budgets.md; no analysis/model/params.py yet` — factually false,
`params.py` is right there — substitutes the hardcoded `0.105`, and **exits
0**. A missing `PARAMS` attribute raises `AttributeError`, which is not
caught, so the failure modes are inconsistent.

This inverts the file's own stated rationale ("when the derivation is re-run
the target moves with it, which is the entire reason not to type the number
here") and launders a fabricated number into an engineering record — the
exact thing `skills/armature-cad/SKILL.md`'s no-fabricated-inputs gate forbids.

**Fix:**
- Catch `ModuleNotFoundError` for the `params` module **only**. Let
  `KeyError`, an `ImportError` raised from inside `params.py`, and
  `AttributeError` propagate.
- Make the fallback opt-in and unmistakable.
- `PROVENANCE` must state what actually happened — never claim `params.py`
  is absent when it is present.

**Test:** `demo()` (or a `__main__` self-check) asserting that a present-but-
renamed key raises rather than falling back. Construct the scenario with a
temporary directory and `sys.path` manipulation; do not write into the repo.

### F5 (MAJOR) — the worked example demonstrates the defect it warns about

Two silent-wrong paths in the file that teaches the pattern:

**(a)** `BOSS_OD = BORE + 2*6.0` is frozen at module scope from the
module-level `BORE`, not derived from the `bore` argument. Sweeping `bore`
erodes the documented "6 mm wall around the bearing seat" with no complaint:
`bore=28.60` → wall 2.70 mm, and `rebuild_sweep` reports PASS. The only
guard, `bore >= BOSS_OD`, fires at wall ≤ 0.

**Fix:** derive `BOSS_OD` inside `build()` from the `bore` argument, and
assert the wall against its stated 6 mm intent.

**(b)** `_assert_pattern_fits` runs against the blank **before the bore is
cut**, so it never tests clearance to the bore. Measured: `bc=26.0` → bolt
holes break into the bore; `bc=22.0` → bolt holes sit **entirely inside**
the bearing bore. Both build fine. The docstring claims "Every bolt in the
pattern must sit on metal."

**Fix:** run the edge-distance probe against the **final** solid, or include
the bore in the probe.

**Test:** `demo()` assertions that `bc=22.0` and `bc=26.0` now raise, and
that a `bore` sweep eroding the boss wall below 6 mm raises.

### F6 (MAJOR) — Z-extent probe bug still live on the parameter path, with a wrong diagnosis

`_assert_pattern_fits` uses module `PLATE_T` while `build()` takes a
`plate_t` argument. Measured: `build(plate_t=3.0)` raises
`"bolt circle 45.0 mm: pattern runs off the plate"` — blaming the bolt
circle for a plate-thickness problem — and `build(plate_t=12.0)` passes
while the probe tests only the bottom 6 mm. The docstring's claim "the probe
is exactly plate-thick" is false whenever `plate_t != PLATE_T`.

The root cause is doctrinal: `plate_l`, `plate_w`, `plate_t` are exposed as
keyword arguments although the file's own comments class them as **typed**
numbers, and `main()` explicitly says sweeping them "tests nothing the
design promises." Global Constraint 8 forbids this.

**Fix (preferred):** drop `plate_l`, `plate_w`, `plate_t` from `build()`'s
signature — they are typed constants. This is the shorter diff and the
doctrinally correct one. If any must stay a parameter, thread it into the
probe and fix the docstring.

**Test:** `demo()` asserting the probe's diagnostics name the right cause.

### F12 (MINOR) — unsourced and mislabeled numbers

- `EDGE_DIST = 2.0 * 4.0  # 2x bolt dia to a free edge, standard practice` —
  "standard practice" is not provenance in a skill that demands citation. It
  also hardcodes M4's nominal diameter a second time (`BOLT_CLEARANCE = 4.5`
  already encodes M4). And the code applies it from the hole **edge** (probe
  radius `BOLT_CLEARANCE/2 + EDGE_DIST` = 10.25 mm from bolt centre) while
  the comment reads centre-to-edge — docs and code disagree on the rule.
- `BOLT_CLEARANCE = 4.5  # M4 close clearance` — per **ISO 273**, M4
  clearance holes are close 4.3 / medium 4.5 / free 4.8. 4.5 is **medium
  (normal)**, mislabeled as close.

**Fix:** cite ISO 273 by name for the clearance hole and fix the label; give
edge distance a named basis; make the comment describe what the code
actually computes; derive both from a single M4 nominal-diameter constant.

### F13 (MINOR) — cold start fails loudly for the templates' own reason

`PARAM_KEY = "m1"` points at the 2R arm's link-1 mass (1.20 kg) in
`skills/armature-math/scripts/model_template/params.py`, while the worked
part is a 0.104 kg bracket. Copying both templates as instructed yields a
91% failure the user did not cause — the first-run experience that teaches
people a tool is noisy.

**Fix:** set `PARAM_KEY` to a placeholder that clearly does not resolve
(e.g. `"<params key for this body>"`) so the fallback path is obviously the
fallback. Only meaningful after F1 makes that path honest — do F1 first.

### Task 2 acceptance

- `uv run --with 'build123d~=0.11' python part.py` exits 0 from the template
  directory.
- The renamed-key scenario raises rather than false-passing.
- `bc=22.0`, `bc=26.0`, and a boss-wall-eroding `bore` all raise.
- No dimension is both a `build()` parameter and a typed constant.

---

## Task 3: Fix `sweep.py` — the hidden-collision and advisory-exit paths

**File:** `skills/armature-cad/scripts/part_template/sweep.py`
**Depends on:** Task 1 (imports `check.py`).

**Do not modify `pose()`'s forward kinematics** (Global Constraint 3).

### F7 (MAJOR) — blanket `ignore` makes the dominant self-collision class invisible

`ignore` suppresses a pair at **every** posture, not just where they overlap
at the shared joint. For the worked 2R arm the elbow limit — the single most
likely finding for a 2R arm — cannot be found:

```
q2= 180.0 deg: link1<->link2 overlap 300000 mm^3 | reported: [('base','link2')]
q2= 160.4 deg: link1<->link2 overlap  69575 mm^3 | reported: NOTHING
q2= 114.6 deg: link1<->link2 overlap  18689 mm^3 | reported: NOTHING
```

At q2 = 114.6° the hidden overlap is **3.5× larger** than the base↔link2
overlap the sweep does report. The tool loudly reports the smaller collision
and silently ignores the bigger one.

This is now load-bearing: `skills/armature-math/SKILL.md`'s new Milestone 3
bullet routes joint-limit derivation to this script, and as configured it
cannot derive the elbow limit.

**Fix:** replace the blanket pair-ignore with something that excuses only
the joint region — a per-pair overlap threshold sized to the design overlap,
or envelopes trimmed back from the shared joint. Whichever is chosen,
document the residual blind spot explicitly in `sweep_clearance`'s `ignore`
docstring (in `check.py`) and in `sweep.py`.

**Test:** `demo()` asserting the elbow collision at a mid-range posture
(e.g. q2 ≈ 115°) is now reported.

### F9 (MINOR) — `sweep.py` exits 0 with 18 interfering postures

`main()` returns 0 unconditionally. The README groups all four files under
one runnable block and `part.py`'s header states the exit-code contract for
the set, so a CI job running `sweep.py` sees green on a colliding mechanism.

**Fix:** `return 1 if hits else 0`. If advisory-only behavior is wanted
instead, say so explicitly in the docstring and the README — but the default
should not be a green gate on a collision.

### F10 (MINOR) — the sampling grid is 4× coarser than the collision band

The docstring's "ALWAYS include the joint limits" advice **is** followed. But
at n=9 over ±π the step is 45°, while a 1°-resolution scan shows the actual
collision band is **11.0° wide**. It is found only because the band abuts
the sampled ±180° endpoint; any band narrower than 45° in the interior is
missed. This is arithmetic, not speculation. Also
`joint_limits_and_interior(1)` raises `ZeroDivisionError`.

**Fix:** guard `n < 2`; raise the default resolution; and document the
resolution limit honestly beside the `rebuild_sweep` limit the docs already
handle well (Global Constraint 7).

### F11 (MINOR) — `sweep.py` restates `params.py` numbers

```python
L1 = mm(0.30)  # params.PARAMS["l1"]
L2 = mm(0.25)  # params.PARAMS["l2"]
```

Both `part_template/README.md` and `skills/armature-cad/SKILL.md` state the
cardinal rule: the `.py` never restates a dimension from `params.py`, it
imports it. `part.py` goes to real trouble to do this; `sweep.py` types the
number and names the key it should have imported in a comment. They agree
with `model_template/params.py` today — which is how drift starts.
Violates Global Constraint 9.

**Fix:** import from `params.py` using the same guard pattern Task 2
establishes for F1 (honest provenance, no silent fallback).

### Task 3 acceptance

- `uv run --with 'build123d~=0.11' python sweep.py` exits nonzero when the
  worked example collides, 0 when it does not.
- The elbow collision at a mid-range posture is reported.
- `pose()`'s FK is byte-identical to the baseline.

---

## Task 4: Fix `stubs.py` and reconcile the documentation

**Files:** `skills/armature-cad/scripts/part_template/stubs.py`,
`skills/armature-cad/scripts/part_template/README.md`,
`skills/armature-cad/SKILL.md`,
`skills/armature-cad/references/documentation-standards.md`,
`skills/armature-math/SKILL.md`, `.claude-plugin/marketplace.json`
**Depends on:** Tasks 1-3 (documents their outcomes).

### F16 (MINOR) — `stubs.py`'s release gate is vacuous by default

`_REGISTRY` is populated only by builders called in the current process, so
a release check that imports `stubs` without building any stub gets `[]` and
passes. It is also append-only, so building the same stub twice duplicates
it in `index_rows()`. (The `source` gate itself is well designed and
correctly rejects `source=""` — that is not at issue.)

**Fix:** dedupe `_REGISTRY`; document in `still_placeholder()`'s docstring
that it is only meaningful in a process that has built every part, and that
an empty list from a process that built nothing is not evidence of a clean
release.

**Test:** `demo()` asserting the dedupe.

### Documentation reconciliation

Per Global Constraint 7, update every claim the Tasks 1-3 fixes made stale.
At minimum:

- **`skills/armature-math/SKILL.md`** — the Milestone 3 self-collision
  bullet routes joint-limit derivation to `sweep.py`. Add the caveat that
  the sweep's resolution bounds what it can find (F10) and that ignored
  pairs are blind spots (F7). This is the finding that most needs a
  downstream caveat.
- **`skills/armature-cad/references/documentation-standards.md` §1** —
  currently promotes the SVG views to "better than crude, and it can't fall
  out of step with the recipe." State that the views are for orientation and
  are not dimensioned (F8).
- **`skills/armature-cad/SKILL.md`** — verify the "recipe, executable"
  section and the "Close the loop" paragraph still describe what the code
  does after Tasks 1-3.
- **`part_template/README.md`** — same check, including the exact `uv run`
  commands and the tested-version note.
- **`.claude-plugin/marketplace.json`** — version says `1.0.0` while
  `plugin.json` says `1.1.0`. Make them match.

### Task 4 acceptance

- All four `.py` files exit 0 on their `demo()`.
- No documentation claim contradicts the code after Tasks 1-3.
- `plugin.json` and `marketplace.json` versions match.
