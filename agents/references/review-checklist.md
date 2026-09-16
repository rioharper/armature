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

- **Re-run the feasibility math** with the artifact's own numbers. Does it close at the edge of the envelope, or only at nominal?
- **Margins**: is each sized to its stakes? Actuator torque, structural stress, thermal, power, current. State the margin the consequence warrants and compare to what is there.
- **Budgets** (`docs/01-spec/budgets.md`): current estimates against each budget, and whether recent changes were debited at all.
- **Reserves**: a reserve row holds a Must requirement, so its margin is a pass/fail, not a reading — negative means the reserve is breached and that REQ has failed. Recompute it: ceiling minus every other line's current estimate, against what the REQ demands. A breach the prose above the table admits while the row's margin and `docs/01-spec/traceability.md` still read healthy is a Blocker; so is a debit that grew a line item and left the reserve untouched.
- **Price staleness**: a cost row is only as fresh as the `Retrieved` date of the `docs/datasheets/index.md` row it cites — that date is the price's date, and the only thing that says it has gone off. Check it against today's. Over six months with nothing re-read is a Minor; a cost margin that closes only on a price over a year old, or that is thinner than the drift its category has shown (a Jetson dev kit's list price rose 60 % in nineteen months), is a Major; a purchase authorised on one is a Blocker. Route the fix to the `armature-librarian` agent — re-reading a vendor page needs the web, which you do not have.
- **Assumptions vs. envelope**: for every assumption the derivation names (rigid links, neglected friction, lumped rotor inertia), does the real operating range cross the line where it breaks? A report's *Assumptions under strain* owes each one the **direction and size** its model gives — swept, with what the result reads at each end, and the task that closes it named. One listed without that is one nobody swept.
- **Singularities & workspace**: does any singularity sit *inside* the region the robot must work in?
- **Units and signs**: check them explicitly.
- **Printed, not typed**: every table in a derivation note or report is printed by a report module under `analysis/model/` (`report_*.py`). Run it and match the tables against what it prints; a number with no module printing it was typed by hand, and a typed number goes stale in silence when the model moves under it.
- **Datasheet reality**: are the numbers driving the design confirmed from datasheets (`docs/datasheets/index.md` rows), or assumed? An assumed number inside a load-bearing calculation is a Question at best and a Blocker at worst. A row's **Clauses read** cell bounds what was verified — probe what it leaves open, and take as answered what it covers. A row marked **CANDIDATE, pending user confirmation** is unconfirmed: a design resting on one is a Blocker.
- **Book data**: a constant tagged `standard` in `params.py` — fatigue endurance points, finite-life tables, friction pairs, form factors — has no index row to cite, so it names its book, edition, and the table or figure it sits in, and carries a **second independent source** with the design sized to the conservative of the two. A book named without its table is memory. One source is a margin resting on one fit: shot-peened spring-wire endurance points differ by 30 % between two standard sources that agree within 6 % unpeened.

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
