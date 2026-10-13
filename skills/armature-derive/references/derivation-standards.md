# Derivation Notes — Standards

The target register: a sharp senior engineer's design notebook — the findings they'd actually leave for later-you to pick the project back up from, the story of what they expected, what they tried, and what the numbers said, told alongside the hard math. Not a journal paper. No result gets skipped, but nothing gets padded to look thorough either. If a sentence doesn't carry information later-you would need, cut it.

## File layout

Each project's derivation is four files, not one — the layout and per-milestone content live in SKILL.md. Every file:

- opens with a one-line header: project name, milestone, rev/date, and which module or package accompanies it
- ends with a short revision note: what changed since the last rev and why — this is what makes re-derivations traceable
- stays one continuous argument. The module splits along the note's sections; the note itself never splits, and carries no size gate — `layout.py` reports its length for information only

## Writing rules

1. **Prose carries the argument; equations punctuate it.** Every equation gets a sentence saying what we're about to do and *why*; a significant result gets one sentence of physical interpretation after it. Bullets are for the parameter table and checklists only — not for the derivation steps themselves.
2. **Number every displayed equation** (1), (2), … and refer back by number.
3. **No skipped leaps, but compression is fine.** "Expanding and collecting q̇₁q̇₂ terms" is fine; a step that can't be named is a step that got skipped. If SymPy did an ugly simplification, say so briefly rather than presenting the tidy output as if you did it by hand.
4. **Notation discipline.** Define every symbol at first use, use it consistently, match the project's symbol table exactly. State the rotation/frame convention once and don't restate it every section.
5. **Units on every number.** A number without a unit is a typo.
6. **Interpret, don't just derive — but in one sentence, not a paragraph.** After the Jacobian: which postures are singular, and would this robot ever be near them? After gravity terms: which joint carries the worst static load? The one exception to lean is `03_results.md`: findings get the room they need (SKILL.md's Milestone 3 defines what they must contain).
7. **Honest uncertainty, briefly flagged.** An assumption that materially affects results (ignoring friction in a high-reduction gearbox) gets one flag with the expected direction and rough size of the error — in `03_results.md`, not scattered as hedges throughout.
8. **Sanity checks are shown, not claimed.** "Setting l₂ → 0 reduces (12) to the single-pendulum result (13)" — with (13) actually shown. One line is enough: "verified" without the verification fails one way, three sentences of narration around a one-line check fails the other.
9. **Every sentence carries information.** A section opens on its first new fact and ends when its content does. If cutting a sentence loses no information, cut it.
10. **LaTeX in markdown** ($...$, $$...$$). **A long symbolic result is printed, never pasted.** Present its structure ("M₁₂ has the form a + b cos q₂ where a = …") and cite the report module that prints the full expression. A result longer than a line of the note is the report module's to carry.
11. **Say what you expected before you computed it.** Every significant result carries the prediction made before the numbers ran — a hand estimate, a limiting case, a hunch with its reason — and whether the result confirmed or surprised it. A confirmed result and a surprising one read differently, and later-you needs to know which this was.
12. **A truth-checked result says whether the truth model confirmed it or surprised it.** Rule 11 in the register the truth model works in: the prediction was the analytic result, the number came from a model that never saw it, and the note says which way it went — "the settle agrees to 0.2 mrad" reads differently from "the settle tilts the platform 5°, and the level-platform assumption is what was wrong". Name the check, its sample size and its seed, and where it surprised you, the paragraph that follows is the finding, not a hedge. A truth check reported as "passed" with no number is rule 8's *claimed, not shown*.
13. **An abandoned approach gets one sentence on why it died.** "Newton-Euler first; dropped because the reaction forces weren't needed and the recursion hid the structure of M." Later-you doesn't re-walk a path already ruled out.

## Evidence over an envelope

A claim about a *set* of configurations — the Jacobian has full rank, the torque stays under the rating, the platform holds level — is evidenced by a **seeded random sample of that set, with the sample size and the seed stated beside the result**. Every checks module draws from the engine's one sampler (`armature.sample`, `armature.sample_states`, and `within=WORKSPACE` for the intended workspace), so "over the envelope" means the same set of configurations in the kinematics check, the dynamics check and the worst-case search, and a reviewer re-running the file gets the configurations the note was written from. A sampled claim whose sample size and seed are not in the note is not reproducible, and rule 8 calls it claimed rather than shown.

**A named configuration is never the evidence.** Home, fully outstretched, q = 0, a workspace corner, the symmetric load case: these are the mechanism's symmetry planes, and a symmetry plane is where a wrong assumption cancels — the moment that would tilt the platform is zero there, the rank the structure matrix loses there is the rank it has everywhere. Named configurations are for the reader, printed by the report module (`report_results.py`) beside the searched worsts, and the note quotes them as landmarks. The first real project through this plugin passed every check at its named postures and failed at the first randomly sampled one.

**Every matrix the derivation inverts or pseudo-inverts has its smallest singular value bounded away from zero** everywhere the derivation needs full rank, by a margin (below) whose slack is σ_min less the bound, and the report module prints the envelope's smallest beside it. Which set that is, is a decision: the envelope is what the joints reach and the **intended workspace** is what the requirements name, a singularity is allowed to live in the gap between them, and the model carries both — the joint ranges in `mechanism.py`, `WORKSPACE` in `params.py` — so the bound is asserted on the set the requirement is about. Say which matrix, which set, and what the bound is worth physically — σ_min is a rate, and its reciprocal is the joint speed and joint force one unit of Cartesian motion costs at the worst posture. A rank assumed and never computed is how a rank-3 matrix gets read as four modes.

**"Worst", "any" and "anywhere" are searched, never sampled or picked.** A requirement that says *any direction*, *anywhere in the workspace*, *both signs* or *worst case* names a set, and a handful of configurations is not an answer about a set. Declare it as a **margin**, a module-level `armature.Margin(name, fn, unit, over=Space(...))` in the milestone module that owns the claim. `fn(p)` returns slack: available minus required, against the limit with its derating applied, the derating and its reason in `fn`'s docstring. The space names every axis the set has: posture as `Coordinates` (`within=WORKSPACE` for the intended workspace), load case and sign as a `Choice` of the load-case rows, a heading as a `Direction`, every tolerance band the margin can move as a `Band`, anything else as an `Interval`. Constants that are not searched, a load case's numbers or a platform model, reach `fn` by closure. The search is `armature.search` and no other; `run_all.py` discovers each margin, searches it, and fails it below zero. A margin computed from the derivation carries `truth=` and `agree=`, the truth model's own slack at the same point (the truth gate, in the plugin's `references/model-layout.md`). Where the set has an exact answer, a check holds the search to it: the worst tip force over a circle of headings is the norm of the Jacobian column projected onto its plane. `verification.HOLDING` is the worked example.

**Every tolerance the design grants is a band**, `(low, high)` in `params.BANDS` around its nominal, and every margin it can move carries it as a `Band`. The search evaluates every corner of the bands' product and polishes between them, so the worst tolerance corner is in the same row as the worst posture, never a separate sweep, and a margin stated at nominal alone is unproven.

**The note cites the `Worst` row `run_all.py` prints**: value, where, n, seed, pre-polish best, coverage, and the truth's agreement. Four things about reading it:

- **Where the worst sits is not a fact about the design when it ties.** Mirror-image points with the same slack swap places with the seed. Cite the value, and each load case's worst from `cases`, not `at` alone.
- **`at` carries no units.** Each axis's value is written as `fn` reads it: a hinge in radians, an interval in the unit its ends were given. Convert in the note.
- **Coverage is a volume fraction**: the share of the Sobol points `fn` could evaluate that pass, good to about ±1–2 points at the default 64 per dimension. Raise `Budget(global_points=...)` before quoting it against a figure, and do not compare it with the fraction of a grid's points, which weighs a box's edges differently.
- **Coverage is pooled over every `Choice` combination**, and a `Case` carries none. A coverage claimed per load case or per sign is a search per case: one margin with that `Choice` fixed.

**A signed load case is enumerated in both signs, in the parameter block.** Load cases live in `params.py` as a table of `(class, magnitude, direction set, sign)` rows, and every signed class carries both rows — the check that it does is a self-test, not a habit. A 0.5 g deceleration read as upward when downward is the case that binds the floor, a cable pull read inboard when outboard is the one that lifts a foot: the sign is not a detail of the reading, it is a row that exists or does not. Where the load's direction is a *set* rather than a direction, the row says so and the margin searches it as a `Direction`.

## Actuators and the bus

Every actuator and DC-bus claim is computed by `armature.drive` from **missions**, searched as margins like any other (ADR 0006), and runs from spec §9 on a coarse description before derive refines the same files (ADR 0007). The model template's `drive.py` and `missions.py` are the worked example. An actuator is sized by its drive margins' searched rows alone; a torque at a named posture, a holding torque or a peak worked by hand is a landmark beside them.

**A mission wherever there are actuators.** `missions.py` writes the spec's §6.4 as moves, holds and events with a duty. A searched mission, `mission(point)`, puts its free choices on the space's axes (start, direction, distance, an event's trigger fraction), so the worst move is found rather than named. Write the events the machine meets: an e-stop partway through a move, a power loss, a touchdown, the motors coasting, shorted or flux-braking. Where the motion is not yet known, write an assumed mission and label it as an assumption in §6.4 and `missions.py`; it stays an open question until the spec settles it.

**Every electrical constant carries its basis**, in its `params.py` comment as the datasheet states it and as a required keyword to the engine: Kt per A_rms or A_peak and on the motor or output side, Ke per V_rms or V_peak per krpm and line or phase, resistance line or phase, the wiring wye or delta, every current A_rms or A_peak. Kv converts by a stated convention, `kt_from_kv(kv, convention="sinusoidal" | "trapezoidal")`, 8.27/Kv against 9.55/Kv. `check(motor, n)` holds Kt to Ke within 2 %, and to a published torque–speed `Curve` where one exists; `drive_checks.py` calls it for every motor, since the margins do not. Both wrong torque constants in this plugin's projects were basis errors, and a basis is the one thing about a number a unit system cannot carry.

**Efficiency by direction.** A gearbox has a `forward` efficiency, motor driving load, and a `backward` one, load driving motor; a self-locking gear is `backward=0`. Motoring divides by η_f and back-driving multiplies by η_b, so a regeneration figure that used η_f is optimistic. The driver's efficiency is one constant: it divides what the driver draws from the bus and multiplies what it returns. The rotor's own J_m·ω̇_m sits outside both. Where a vendor publishes no efficiency (neither RobStride nor moteus does), carry it as a band in `params.BANDS` and the row as **Assumed** in the BOM; the search then states every margin at the band's worst end.

**The margin set** is `margins(drive, MISSIONS, over=Space(**SPACE.axes, **DRIVE_BANDS), params=DRIVE)`, the drive's own tolerances among the axes as `Band(name, BANDS, of="drive")`, one margin per check, discovered and searched by `run_all.py`:
- per actuator: every (τ, ω) sample inside the torque–speed envelope at the bus's minimum voltage with the winding hot; driver peak current; winding temperature over the duty, or RMS torque against the continuous rating where no thermal RC is published; driver RMS current where the driver gives a continuous rating;
- per bus: peak voltage against the lowest trip on the bus; minimum voltage against the highest undervoltage trip; the brake resistor's pulse energy and continuous power; the source's power.

The **peak** margins search every axis: the moves, the event triggers, the bands, the bus's capacitance and source voltage. The **duty** margins run the written missions over their duty and search only the bands and the bus configurations. Each margin's truth re-runs its worst point at 1 kHz, with each event at half its timestep, and agrees within 1 % of its limit: a resolution check, which is what `layout.py`'s truth gate accepts for the drive margins.

**UNCHECKED fails.** A margin whose data is missing — a winding with no thermal RC and no continuous rating, a duty with no written mission — reads **UNCHECKED**, names what is missing, and fails `run_all.py`. Leave unpublished data out rather than guessing it. The margin then either gets its data (a librarian dispatch, a bench measurement) or an entry in `drive.py`'s `DRIVE_EXEMPT`, `{margin name: reason}`, keyed by the name the UNCHECKED row prints. A reason argues why another margin bounds the same failure. `run_all.py` prints every exemption beside its row, fails an entry that names no margin, names a checked one or gives no reason, and the red-team challenges each.

**Perfect tracking is the accepted cost.** Moves and holds become torque through inverse dynamics, so controller effort, overshoot and disturbance rejection are absent. Add a known disturbance where it acts, as a hold's load or a band, so the margin carries it at its worst point. Inductance, iron loss, a second bus and the pack's state of charge are outside the model too. A bench measurement that disagrees with a margin beyond its band reopens ADR 0006.

**Where the engine stops short**, found sizing a cable robot and a wheeled biped. Each item is a seam the project fills itself, recorded in its notes:
- **The capacitance a bus needs.** The bus margins say whether a capacitance band holds; the least capacitance that holds is a bisection on `charge(trace, drive, capacitance=...).peak`, printed by a report module.
- **No source at all** (a pack unmated). `Source` needs `p_max > 0`, so state a non-sinking source of negligible `p_max`. In `DRIVE_MARGINS` its minimum-voltage and source-power margins would fail by construction, so keep that configuration out of them and hold its peak voltage with a margin of the project's own on `charge(...).peak`.
- **A rating on the bus that no driver carries**, such as a power board's or a capacitor bank's voltage. The lowest trip the engine sees is the drivers' `max_voltage` and the source's `overvoltage`; a lower rating is a margin the project writes on `charge(...).peak`.
- **Past a trip the bus model keeps regenerating**, so a peak above the lowest trip is a failure whose value is arithmetic, not a prediction.
- **One actuator's regeneration against its own flux brake.** The bus's peak voltage saturates at the clamp and cannot rank regeneration events. Write the per-actuator margin from `trace` and `electrical`: the winch paying out on a cable robot is the case that needs it.
- **An allocation the engine does not make** (cable tensions). Use the mission's `actuation(state, qdd, loads)` seam, which gets no time and no params: close over what it needs. Raise `Infeasible` where the allocation has no solution.
- **A searched move stays inside the envelope only if the mission keeps it there.** Clip its distance to the envelope's face, pass `within=` to its `Coordinates`, and give the joint ranges a margin past it.
- **A motion from the project's own simulation** enters as `follow(q, duration)`. Keep the q(t) behind every sizing number, not only its summary.

## The assumption table

`00_setup.md`'s numbered assumptions are a table, and it carries a **Released?** column. Every assumption that fixes a coordinate or removes a compliance — the platform stays level, the base is rigid, the elbow is locked, the gearbox has no wind-up, the cable is inextensible — is a **reduction** in the variant the derivation reads (`lock`, `couple`, `planar`, `lump` or `rigid`), carrying the assumption's number, and owes that column one of exactly two entries:

- the **name of the check that releases it** in the truth model, the **reduction** it releases, and **what moved**, with units and sign: `test_truth_release_platform_tilt — lock platform:rx (A2), 0.4 mrad at the worst sampled pose`. Release is keyed by reduction: a lock, couple or planar is sized by the displacement of what it fixed, a lump or rigid by the change in the quantity it was asked about. The `test_truth_` prefix is what the truth gate counts. That is an assumption sized and kept. `5.2° tilt, two cables slack` is an assumption sized and wrong, and the paragraph under the table is the finding.
- **one sentence saying why it cannot be released**, which is always the same reason wearing different clothes: the truth model can only free a coordinate the mechanism description gave it. "Not released: the base's compliance is not in the description; releasing it means adding the base stiffness and the joint that carries it, scoped as T2.4." A sentence that says only "reasonable for this design" is the assumption nobody sized, which is the one that bites.

A blank cell is the failure mode the column exists to make visible. Rule 7's flag — direction and rough size of the error — is what the released entry *is*, computed rather than estimated; where the release ran, the flag quotes its number.

## Which layer a sentence lives in

A note and its module each carry what the other cannot, and a sentence said in both is paid for on every read of the module. Narrative, derivation, physical argument, and revision history — the story of a correction included — live in the note. The module carries the computation and the least prose a caller needs:

- **Function docstring**: one sentence of what the function computes; the note's equation or section it implements; and anything a *caller* needs that the note does not say — units, sign conventions, failure modes, why a default is what it is.
- **Module docstring**: orientation in about ten lines — the note and sections it mirrors, where its checks live, what it imports — pointing at the note for the argument.

A derivation, a justification of the physics, or the history of a fix belongs in the note, with the docstring citing it. The test for any sentence in a docstring: would it be wrong to say this in the note? If not, it belongs in the note.

## Length is a signal, not a target

This governs the notes; the modules are held to a hard budget instead (the plugin's `references/model-layout.md`). A milestone file that's short because the mechanism is simple is correct. A milestone file that's long because every step is doing real work is also correct. A milestone file that's long because of hedging, restated interpretation, or an equation shown three ways when one would do is the failure mode to catch on re-read — trim it before moving to the next milestone, not at the end when trimming means re-touching four files instead of one.

## References

Cite the convention source (Lynch & Park, ch. 4, for the product of exponentials the symbolic view composes frames by) and anything nonstandard, once, in `00_setup.md`. No fake citations — a result from your own derivation needs none.

## Design data from a book

Numbers a design leans on that no vendor publishes — fatigue endurance points, finite-life tables, friction pairs, form factors — have no `docs/datasheets/index.md` row for the librarian to cache, so "cite index rows, never memory" gives them their own rule:

- **Tag it `standard`** in `params.py` and name the book, edition, and the table, figure, or section the number sits in — "Zimmerli's data as Shigley reports it, §10-7"; "Associated Spring finite-life table, Norton Table 14-7". A book named without its table is memory.
- **Find a second independent source and carry both.** Textbook design data is somebody's fit to somebody's tests, and two fits disagree: shot-peened spring wire endurance points differ by 30 % between two standard sources that agree within 6 % unpeened, which is the whole fatigue margin of a peened coil. Read the result against each source, state both, and design to the conservative one.
- **Pin the disagreement with a self-test**, so a later edit cannot quietly swap which source the design leans on.

### A closed form from a book

A formula is the cheapest wrong number a derivation can produce. Its arithmetic is somebody else's and it reproduces; its units are right; the only thing that can be wrong is whether *this* mechanism is in the class the formula is a theorem about — a bifilar yaw stiffness on cables that converge rather than hang parallel (27× low, on the first project through this plugin), a taut-cable pendulum mode on a cable that goes slack, a small-angle form past its range, a parallel-wire capacitance on wires that are not parallel.

- **Check it against the truth model at sampled configurations before the note cites it.** Not at the tidy posture where the cosines are all one — that posture is the symmetry plane, and it is where a formula outside its class most often happens to be right.
- **Name the assumption the form rests on, in the check**, as a module constant the failure message quotes: "every joint axis parallel to z and gravity lying in the x-y plane". When the comparison fails, the person reading the red bar needs the class, not the residual.
- **Cite it once in `00_setup.md`** — book, edition, chapter or equation — as the convention sources are cited.

### A reference algorithm from a book

A method taken whole from a book — a workspace method, a force-distribution law, an elastic-plus-geometric stiffness model, a kinematic convention — is **tagged `standard` and cited by book and chapter in `00_setup.md`**, the same rule the `standard` constants above follow, and the module docstring repeats the citation where the code implements it (`kinematics.py`'s docstring cites Lynch and Park, ch. 4). An algorithm carries its book's assumptions into the derivation silently, and the red team's whole job on it is to read the derivation against the book — which it cannot do if it does not know which book. A method named without its chapter is memory.

- **Ask the vendor for its own basis.** A vendor held to the number rates its part against data of its own; that question goes on the questionnaire or the part's specification (`armature-spec`), and its answer supersedes both books.
