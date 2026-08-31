# Review Checklist — Gap Taxonomy

The families where robotics designs fail review, in working order: the early ones are cheap to check and expensive to miss. Interfaces (4) and cross-document consistency (7) earn more attention than they seem to deserve; they are where projects quietly die.

## 1. Requirements

- Is every requirement **quantified** (number + unit) and **verifiable** (a stated test / analysis / inspection / demo)? "Fast", "robust", "user-friendly" are aspirations.
- Do any requirements **contradict** each other — mass budget vs. stiffness, top speed vs. runtime, precision vs. cost?
- What is **missing**? The ones forgotten until they bite: thermal limits, duty cycle, EMI/noise, ingress (dust/water), maintenance access, storage and transport, regulatory/safety, end-of-travel and e-stop behavior.
- Do the success criteria capture the **actual mission**, or an easy-to-measure proxy for it?

## 2. Traceability

- Does every **Must** requirement map to a design element that satisfies it *and* a test that proves it? In `docs/01-spec/traceability.md`, a Must REQ with no analysis or test row is a hole.
- Any **orphan design** — subsystems or features that trace to no requirement? Each is a missing requirement or gold-plating.
- Do the numbers **survive the chain** mission → requirement → feasibility calc → chosen part → BOM? Each hop preserves the number or explains why it changed.

## 3. Physics, math, and budgets

- **Re-run the feasibility math** with the artifact's own numbers. Does it close at the edge of the envelope, or only at nominal?
- **Margins**: is each sized to its stakes? Actuator torque, structural stress, thermal, power, current. State the margin the consequence warrants and compare to what is there.
- **Budgets** (`docs/01-spec/budgets.md`): current estimates against each budget, and whether recent changes were debited at all.
- **Assumptions vs. envelope**: for every assumption the derivation names (rigid links, neglected friction, lumped rotor inertia), does the real operating range cross the line where it breaks?
- **Singularities & workspace**: does any singularity sit *inside* the region the robot must work in?
- **Units and signs**: check them explicitly.
- **Datasheet reality**: are the numbers driving the design confirmed from datasheets (`docs/datasheets/index.md` rows), or assumed? An assumed number inside a load-bearing calculation is a Question at best and a Blocker at worst.

## 4. Interfaces

For every seam between subsystems, check it is defined **on both sides** and that the two sides **agree**:

- **Mechanical** — mounting patterns, tolerances, load paths, clearance, service access. Can it be assembled, with a tool on every fastener afterward?
- **Electrical** — voltage, continuous *and* peak current, connector pinouts, grounding. Does the driver's rating cover the motor's worst-case draw?
- **Data** — protocol, rate, latency, timing, and the units and coordinate frames carried across the boundary. A frame convention that flips between two documents is a shipping bug.
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
