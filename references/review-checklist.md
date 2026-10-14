# Review Checklist — Gap Taxonomy

The families where robotics designs fail review, in working order: the early ones are cheap to check and expensive to miss. Interfaces (4) and cross-document consistency (7) earn more attention than they seem to deserve; they are where projects quietly die.

## 1. Requirements

- Is every requirement **quantified** (number + unit) and **verifiable** (a stated test / analysis / inspection / demo)? "Fast", "robust", "user-friendly" are aspirations.
- Do any requirements **contradict** each other — mass budget vs. stiffness, top speed vs. runtime, precision vs. cost?
- Does any single requirement **contradict itself**? A sweep that reads requirements against each other misses the one whose own clauses cannot both hold — usually a term of art whose definition forbids the clause beside it ("open source, non-commercial": the OSI definition forbids field-of-use restrictions, so nothing satisfies both). Quantified and verifiable is not satisfiable, and a Must written this way is unbuildable rather than tight.
- What is **missing**? The ones forgotten until they bite: thermal limits, duty cycle, EMI/noise, ingress (dust/water), maintenance access, storage and transport, regulatory/safety, end-of-travel and e-stop behavior.
- Do the success criteria capture the **actual mission**, or an easy-to-measure proxy for it?

## 2. Traceability

- Does every **Must** requirement map to a design element that satisfies it *and* a test that proves it? In `docs/01-spec/traceability.md`, a Must REQ with no analysis or test row is a hole.
- Any **orphan design** — subsystems or features that trace to no requirement? Each is a missing requirement or gold-plating.
- Do the numbers **survive the chain** mission → requirement → feasibility calc → chosen part → BOM? Each hop preserves the number or explains why it changed.
- **Routed items**: a decision report's *Items routed here* table is the exit ledger for everything sent to that task. Read it against the sources that did the routing — the plan leaf's issue body, the Route lines of earlier reports in `docs/reviews/`, the TBDs of the milestone notes — and name every item with no row. An item with no row is an item lost, and it was routed because someone judged it load-bearing.

## 3. Physics, math, and budgets

**Five families of error leave the arithmetic right and the model wrong**: every printed number reproduces and every self-consistency check passes, because the mistake sits on both sides of each. They are the bold-led probes in the second half of this list, and a finding that names its family routes itself. The rule behind each is in `${CLAUDE_PLUGIN_ROOT}/skills/armature-derive/references/derivation-standards.md` — *The assumption table*, *Evidence over an envelope*, *A closed form from a book* — and all five were found on the first real project through this plugin, in one review, after its checkpoint had passed.

- **Re-run the feasibility math** with the artifact's own numbers. Does it close at the edge of the envelope, or only at nominal? A spec's §9 hand check (energy, mass, structure, latency; its actuator and bus checks are run, below) states its worst case over the envelope, or names the posture, direction, sign and band value its hand arithmetic assumed (`${CLAUDE_PLUGIN_ROOT}/skills/armature-spec/references/spec-template.md`, §9); one that names none was checked at nominal.
- **Margins**: is each sized to its stakes? Actuator torque, structural stress, thermal, power, current. State the margin the consequence warrants and compare to what is there.
- **Budgets** (`docs/01-spec/budgets.md`): current estimates against each budget, and whether recent changes were debited at all.
- **Reserves**: a reserve row holds a Must requirement, so its margin is a pass/fail, not a reading — negative means the reserve is breached and that REQ has failed. Recompute it: ceiling minus every other line's current estimate, against what the REQ demands. A breach the prose above the table admits while the row's margin and `docs/01-spec/traceability.md` still read healthy is a Blocker; so is a debit that grew a line item and left the reserve untouched.
- **Price staleness**: a cost row is only as fresh as the `Retrieved` date of the `docs/datasheets/index.md` row it cites — that date is the price's date, and the only thing that says it has gone off. Check it against today's. Over six months with nothing re-read is a Minor; a cost margin that closes only on a price over a year old, or that is thinner than the drift its category has shown (a Jetson dev kit's list price rose 60 % in nineteen months), is a Major; a purchase authorised on one is a Blocker. Route the fix to the `armature-librarian` agent — re-reading a vendor page needs the web, which you do not have.
- **Assumptions vs. envelope**: for every assumption the derivation names (rigid links, neglected friction, lumped rotor inertia), does the real operating range cross the line where it breaks? A report's *Assumptions under strain* owes each one the **direction and size** its model gives — swept, with what the result reads at each end, and the task that closes it named. One listed without that is one nobody swept.
- **Frozen degree of freedom** — an assumption that fixes a coordinate the machine leaves free: the platform stays level, the base is rigid, the elbow is locked, the gearbox has no wind-up, the cable is inextensible. Each one is a reduction in the derivation's variant, carrying its assumption number. Read `00_setup.md`'s assumption table: each such row's **Released?** cell carries the check that released it in the truth model (`s.release(hold=...)`, keyed by reduction) and what moved, with units and sign, or one sentence on why the coordinate is not in the mechanism description and what adding it would take. Re-run the release with Bash; `armature.account` in each derivation module's checks is what stops a coordinate leaving the equations with no reduction. A blank cell is a Major; a released value the note reports and then designs past is a Question; a coordinate a release shows moving past the margin is a **Blocker**.
- **Dynamics checked against nothing but itself**: M symmetric positive-definite, Ṁ − 2C skew-symmetric and energy conserved are self-consistency, so a term missing from T or V is missing from all of them. Ask for the **independent inverse-dynamics check** — `s.inverse(qdd=...).generalised` against M q̈ + C q̇ + g at states from `armature.sample_states` with nonzero velocity — and re-run it with Bash. A note whose only dynamics evidence is self-consistency is a Major; one that sizes an actuator from it is a Blocker.
- **A mode named without a linearisation behind it**: a mode is an eigenvalue of (K, M), and a diagonal entry of K is one only when both matrices are diagonal; a stiffness matrix of rank 3 has three modes, whatever its diagonal shows. Ask what was linearised, at which configuration, with what step, and what rank the note claims for K; re-run `s.linearise()` with Bash. No linearisation is a Major; a mode sizing a controller bandwidth or a structural member is a Blocker.
- **Worst case at named configurations** — a claim evidenced at home, q = 0, fully outstretched, a workspace corner, the symmetric load case. Those are symmetry planes, where a wrong assumption cancels. Evidence over a set is a seeded random sample, `armature.sample`, with its size and seed stated; re-run the check with Bash at your own seed. A claim whose configurations are all named is a Major; one whose requirement says "anywhere" is a Blocker.
- **Worst case by a handful of samples**: "worst", "any direction", "anywhere in the workspace" name a set, and the set is a `Margin`'s space, searched by `armature.search` (the standards, *Evidence over an envelope*). Read the margin's `Worst` row against its requirement:
  - **The space** names every axis the requirement does: posture, each load-case row and sign, the heading of a direction set, every band the margin can move.
  - **`coverage`** says how thin the margin is. A coverage the note quotes against a figure owes what the same section of the standards asks of a quoted coverage.
  - **`pre_polish` against `value`**: a polish that moved the worst far says the global set was thin there.
  - **The truth's agreement** at the worst point and the pre-polish best. For a holding margin the truth holds the worst under its load as a force, `s.settle(hold=..., loads={site: force})`; a worst only recomputed from the truth model's Jacobian is checked against itself.

  Re-run it with Bash at your own seed, `armature.search(margin, seed=...)`: the value must hold, while `at` may swap between mirror-image ties. A worst case from named postures, random samples or a search the project wrote itself is a Major; one that sizes an actuator, a structural member or a reserve is a Blocker.
- **Unswept singular values** — a Jacobian pseudo-inverted for IK, a structure matrix solved for tensions, a stiffness matrix inverted for compliance. Ask for the margin bounding σ_min, and **over which set** it is searched: the envelope is what the joints reach and `WORKSPACE` is what the requirement names, so a bound searched over the wrong one is a bound relaxed to whatever the joints allow. No margin is a Major; a rank claimed and never computed, or a singularity inside the intended workspace, is a Blocker.
- **Load-case sign read one way** — a deceleration, a base acceleration, a cable pull, a wind load, a thermal excursion. Check `params.py`'s `LOAD_CASES` has both signs of every signed class, that a requirement naming a *set* of directions has a row that says so, and that each margin sized from the table carries every row as a `Choice` and a direction set as a `Direction`. One sign in the table is a Major; a part sized from the gentler sign is a Blocker.
- **Formula outside its assumptions** — a closed form with no truth check comparing it at **sampled** configurations (the template's moment-arm form against `s.inverse()` at rest is the pattern), or a check that does not name the assumption the form rests on. No such check is a Major; a form sizing a part is a **Blocker**. Separately, a method taken whole from a book is tagged `standard` and cited by book and chapter in `00_setup.md`: cited without its chapter is a Minor, and a book that assumes a geometry this machine does not have is a Blocker.
- **Actuators and the bus**: sized by the drive margins in `analysis/model/drive.py` over `missions.py` (`${CLAUDE_PLUGIN_ROOT}/skills/armature-derive/references/derivation-standards.md`, *Actuators and the bus*). Run `uv run python run_all.py` and read the rows. An actuator or bus number worked by hand, or at one named posture, is a Major; a purchase resting on one is a Blocker. Four probes, each re-run with Bash:
  - **Regen into a source that cannot sink.** A PSU, a PSU behind a diode, or an unmated pack takes nothing back, so every returned joule lands on the capacitance and the clamps. Check that `Source(sinks=...)` matches the part, that an unmated pack is a bus configuration with `source=None`, that a mission with an e-stop, a lowering or a braking stop is among the missions, and that the bus's peak-V row reads its least capacitance and highest source voltage. A sinking source assumed for a PSU is a Blocker.
  - **The lowest trip on the bus.** The peak-V margin is held to the lowest of every driver's `max_voltage`, the source's `overvoltage`, and the bus's `ratings`, the parts on it no driver carries: a capacitor bank, a power board, a BEC's input. Its row names the part that binds. A part on the bus whose voltage rating is neither a driver's `max_voltage` nor in `Bus(ratings=...)` is a Major.
  - **The duty actually integrated.** Winding temperature is integrated over a written mission's duty, period and session, not a hold's own length. Check that the duty matches §6.4, and that a winding with no thermal RC falls back to RMS torque or stands UNCHECKED. An exemption whose reason fails the standards' test is a Major.
  - **Constant bases.** Every Kt, Ke, resistance and current in `params.py` names its basis, and that basis matches its `docs/datasheets/index.md` row: A_rms or A_peak, line or phase, motor or output side, 8.27/Kv or 9.55/Kv. A basis that disagrees with its sheet is a Blocker where it sizes a part; an efficiency the vendor does not publish carried as a point rather than a band is a Major.
- **Singularities & workspace**: does any singularity sit *inside* the region the robot must work in?
- **Units and signs**: check them explicitly.
- **Printed, not typed**: every table in a derivation note or report is printed by a report module under `analysis/model/` (`report_*.py`). Run it and match the tables against what it prints; a number with no module printing it was typed by hand, and a typed number goes stale in silence when the model moves under it.
- **Datasheet reality**: are the numbers driving the design confirmed from datasheets (`docs/datasheets/index.md` rows), or assumed? An assumed number inside a load-bearing calculation is a Question at best and a Blocker at worst. A row's **Clauses read** cell bounds what was verified — probe what it leaves open, and take as answered what it covers. A row marked **CANDIDATE, pending user confirmation** is unconfirmed: a design resting on one is a Blocker.
- **Book data**: a constant tagged `standard` in `params.py` names its book, edition, and the table or figure it sits in, and carries a **second independent source** with the design sized to the conservative of the two (the standards, *Design data from a book*). A book named without its table is memory; one source is a margin resting on one fit.

## 4. Interfaces

For every seam between subsystems, check it is defined **on both sides** and that the two sides **agree**:

- **Mechanical** — mounting patterns, tolerances, load paths, clearance, service access. Can it be assembled, with a tool on every fastener afterward?
- **Electrical** — voltage, continuous *and* peak current, connector pinouts, grounding. Does the driver's rating cover the motor's worst-case draw?
- **Data** — protocol, rate, latency, timing, and the units and coordinate frames carried across the boundary. A frame convention that flips between two documents is a shipping bug. Read these off the spec's §8 link table and name what is missing: a link with no budget, a budget with no verification method, a data artifact crossing units with no named schema owner, or a compute unit on a host no requirement forces it onto.
- **Thermal** — where does the heat go? Is there a path, or does a component cook in a sealed bay?

## 5. Failure modes and safety (FMEA-lite)

- For each major part: what happens **when** it fails? Graceful, or catastrophic?
- Where are the **single points of failure**, and is each acceptable given the stakes?
- Behavior on **power loss, comms loss, e-stop, and out-of-range command** — defined, or undefined?
- **Safety coverage**: the spec's mechanical-safety section, item by item, against the actual design.
- Is there a **maintenance and repair path**, or does one worn bearing mean a full teardown?

## 6. Scope vs. capability

- Does the scope still match the **builder's honest capability, weekly hours, and deadline** (the spec's capability assessment states these)?
- Is there **iteration reserve**? A plan with no slack to revise the worst mechanism ships the first guess.

## 7. Cross-document consistency

Run last; it needs every artifact in view at once.

- Do the **derivation's parameters match the spec's** — link lengths, masses, payload, gravity?
- Does the **plan's BOM match the spec's chosen parts**, or has one been revised without the other?
- Do **frames, symbols, and naming agree** across spec, derivation, and plan? The derivation consumes the spec's symbol table verbatim.
- Are the documents at **revs that reference each other correctly**, or is the derivation validating a spec two revisions old?
