# Review Checklist — Gap Taxonomy

The families below are where robotics designs actually fail review. Work them in roughly this order — the early ones are cheap to check and expensive to miss. For every probe the rule from the agent prompt holds: do the check, show the evidence, rank by severity. A probe you can't resolve because an input is missing becomes a **Question**, not a silent pass.

## 1. Requirements

The spec's foundation; a flaw here propagates into everything downstream.

- Is every requirement **quantified** (number + unit) and **verifiable** (a stated test / analysis / inspection / demo)? "Fast", "robust", "user-friendly" are aspirations, not requirements.
- Do any requirements **contradict** each other — mass budget vs. stiffness, top speed vs. runtime, precision vs. cost? A contradiction resolved by silence has been resolved against the user.
- What's **missing**? The requirements that get forgotten until they bite: thermal limits, duty cycle, EMI/noise, ingress (dust/water), maintenance access, storage and transport, regulatory/safety, and end-of-travel / e-stop behavior.
- Do the success criteria capture the **actual mission**, or just the easy-to-measure proxy for it? A robot that passes every metric and still doesn't do the job means the metrics were wrong.

## 2. Traceability

- Does every **Must** requirement map to a design element that satisfies it *and* a test that proves it? A Must with no verification is a wish.
- Any **orphan design** — subsystems or features that trace to no requirement? Each is either a missing requirement or gold-plating; both cost time and mass.
- Do the numbers **survive the chain** mission → requirement → feasibility calc → chosen part → BOM? Each hop should preserve the number or explain why it changed.

## 3. Physics & math

- **Re-run the feasibility math** with the artifact's own numbers. Does it close — or does it close at nominal and blow up at the edge of the envelope?
- **Margins**: is each sized to its stakes? Actuator torque, structural stress, thermal, power, current. State the margin you'd expect for the consequence and compare to what's there.
- **Assumptions vs. envelope**: every assumption the derivation names (rigid links, neglected friction, lumped rotor inertia) — does the real operating range cross the line where that assumption breaks?
- **Singularities & workspace**: does any singularity sit *inside* the region the robot must actually work in?
- **Units and signs**: the boring killers. Check them explicitly; they don't announce themselves.
- **Datasheet reality**: are the numbers driving the design confirmed from datasheets, or assumed? An assumed number inside a load-bearing calculation is a Question at best and a Blocker at worst — never a quiet pass.

## 4. Interfaces

The seams between subsystems, where integration failures live. For every interface, check it's defined **on both sides** and that the two sides **agree**:

- **Mechanical** — mounting patterns, tolerances, load paths, clearance, and service access. Can you assemble it, and get a tool on every fastener afterward?
- **Electrical** — voltage, continuous *and* peak current, connector pinouts, grounding. Does the driver's rating cover the motor's worst-case draw, not its nominal?
- **Data** — protocol, rate, latency, timing, and the units and coordinate frames carried across the boundary. A frame convention that flips between two documents is a real, shipping bug.
- **Thermal** — where does the heat actually go? Is there a path, or does a component cook in a sealed bay nobody drew airflow into?

## 5. Failure modes (FMEA-lite)

- For each major part: what happens **when** it fails, not if? Graceful, or catastrophic?
- Where are the **single points of failure**, and is that acceptable given the stakes?
- Behavior on **power loss, comms loss, e-stop, and out-of-range command** — defined, or undefined-and-dangerous?
- Is there a **maintenance and repair path**, or does one worn bearing mean a full teardown?

## 6. Scope vs. capability

- Does the scope still match the **builder's honest capability, weekly hours, and deadline** (the spec's capability assessment states these)? Ambition that outruns the shop is the most common way projects die at 80% complete.
- Is there **iteration reserve**? The first build is a hypothesis. A plan with no slack to revise the worst mechanism is a plan to ship the first guess.

## 7. Cross-document consistency

Run this last, because it needs every artifact in view at once. Projects accumulate drift as documents update at different rates.

- Do the **derivation's parameters match the spec's** — link lengths, masses, payload, gravity?
- Does the **plan's BOM match the spec's chosen parts**, or has one been revised without the other?
- Do **frames, symbols, and naming agree** across spec, derivation, and plan? The mathematician consumes the spec's symbol table verbatim; if they've diverged, something is being computed on stale definitions.
- Are the documents at **revs that reference each other correctly**, or is the derivation dutifully validating a spec two revisions old?
