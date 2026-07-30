# Design Foundations

Adapted and generalized from FIRST Robotics Competition "Design 101" (The Compass Alliance, 2019) for general robotics projects. These are the load-bearing ideas; internalize them before interviewing or recommending.

## Level 0: The initial plan

**Time is almost always the binding constraint.** With infinite time you'd build every candidate design and test them all. You can't, so the earliest decisions — what to build, what *not* to build — carry the most leverage. Front-load the thinking.

**What before how.** The first deliverable of any design effort is the goal set: what should the machine *do*, stated as outcomes. Strategic design is the process of answering this before any mechanism talk. A team that starts sketching grippers before defining the pick task is designing a solution to an unstated problem.

**Honest capability assessment.** Scope must match the builder. Take on too many challenges and the machine underperforms at all of them; too few and potential is wasted. This assessment is hard and uncomfortable — do it anyway, explicitly, in writing. Inputs: available hours, fabrication access, prior experience, budget, and how much of the work is genuinely novel to the builder.

**Group tasks into mechanisms.** Once the task list exists, cluster tasks into candidate mechanisms. One mechanism sometimes serves several tasks (an intake that also feeds a shooter; a leg that also manipulates), but combined mechanisms buy complexity, coupling, and single points of failure. Default to separation unless the combination clearly pays for itself.

**Steal before you invent.** For every mechanism class — drivetrains, arms, lifts, intakes, grippers, legged mechanisms — someone has solved a similar problem. Search prior art first: existing robots (research platforms, competition robots, commercial products), open-source designs, supplier application notes, published CAD, teardown videos, academic papers. Commercial products outside robotics are fair inspiration too: aircraft structures for light stiffness, automotive for cost-driven design, industrial automation for reliability.

**Simplicity, repeatability, accuracy.** The most effective designs maximize all three. When in doubt, the simpler design that does the job at 95% beats the elegant one that does it at 100% but only after three more months of debugging.

**Deciding among conflicting ideas.** Build a trade-off matrix: candidate designs as rows, weighted requirements as columns. It surfaces the pros/cons of every option and often illuminates the answer. If the group still can't agree: either the designated lead designer decides, or vote — but decide. An adequate design executed early beats an optimal design chosen late.

**Overall layout — stay in touch with reality.** Conceptual design drifts from physics. Every machine has size, mass, and envelope constraints; keep them in view for the whole process. Draw the machine to scale (front, side, top) early. Do not forget the unglamorous components: batteries, electronics, wiring, connectors, structure, and *access for repair*. Every component needs not just space but reachability. 3D CAD (or even careful scaled sketching) is the cheapest place to discover interference.

## Level 1: Mechanism design workflow

The flow: prototype → detail design → iterate. Steps are not rigid — some mechanisms need no prototype, some never stop being prototyped — but the flow applies almost everywhere.

### Prototyping doctrine
- Prototypes exist to *fail informatively*. The more failure modes you extract cheaply, the fewer you'll meet expensively.
- Iterate fast: cheap materials (wood, screws, cardboard, printed brackets), hand-drill-powered actuators, zip ties. Mount prototypes on an existing chassis or rolling frame to test motion.
- Spend a little complexity to buy adjustability (slots instead of holes, clamped instead of bolted) — a prototype you can tune in minutes is worth ten you can't.
- Do not polish prototypes. Full CAD of a prototype is usually wasted time.

### Detail design
- Translating a working prototype into a robust, manufacturable mechanism is its own challenge with no universal recipe. Common construction methods are the starting point:
  - **Structure:** extruded aluminum tube/profile with gussets and standard hole patterns is light, strong, and extensible. Standardize patterns so parts interchange.
  - **Bend, don't break:** for mechanisms that take abuse (anything extending beyond the chassis, anything humans touch), prefer materials that flex and return — polycarbonate is the usual answer.
  - **Don't scorn plywood/simple materials:** easy to work, light, often strong enough; match-drilled plywood can replace a whole CNC workflow for one-offs.
  - **COTS-first:** know the commercial off-the-shelf ecosystem (fasteners, bearings, wheels, gearboxes, actuators, rails). Suppliers publish 3D models — design around real parts from the start. Custom parts are for where COTS genuinely fails.
- **Power sources:** all motion traces back to a battery/motor, compressed gas, a spring, or gravity. Converting stored energy to the motion you want is the core difficulty.
  - Rotary motion almost always needs significant reduction; COTS gearboxes are usually the right answer — custom gearboxes are rewarding but expensive in time.
  - Pneumatics excel at short, two-position linear motion.
  - Springs: coil springs (compression/tension), surgical tubing (tension only, easy to reroute with cables/pulleys), gas shocks (very high force, compact).
- **Sensors — design notes:**
  - Put encoders on the fastest shaft available (pre-reduction) for maximum resolution.
  - Optical/shaft-mounted encoders self-center on the shaft; the mount's only job is to prevent rotation — make it *flexible* (e.g., a polycarb z-bend) so you don't overconstrain and snap the shaft.
  - Magnetic encoders don't touch the shaft, so the mount must fully constrain them at constant distance from the magnet — at least two points of contact, no flex.
  - Every sensor must be accessible for replacement without disassembling the mechanism.

### Iteration
The most important step. **A mechanism is never done.** After it works, test it, find the weaknesses, generate concepts, and run the loop again. Budget for at least one full iteration in any plan; the first version is a hypothesis.

## Level 2: Additional tools

- **Design calculations:** motor/gearbox sizing from torque-speed curves is non-negotiable before committing to actuators. Use published motor curves and a sizing calculator or spreadsheet; check stall torque margins, thermal duty cycle, and current draw against the power budget.
- **3D printing:** viable for real structural parts if you know your printer's limits (orientation-dependent strength, tolerances, warp). Great for brackets, guides, ducting, and quick iterations; learn tolerance test prints, embedded nuts for fastener strength, and design features that print well.
- **Design for controllability:** as software ambition grows, mechanisms must get more precise. Backlash, compliance, and friction that a human driver tolerates will wreck a controller. Rigid transmissions, quality sensing on the right shafts, and predictable dynamics are design-time decisions, not software patches.
