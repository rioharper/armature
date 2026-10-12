# Engineering Spec Template

Use this structure. Omit sections only when genuinely inapplicable; say so rather than silently dropping them. Target length: whatever the content demands — a hobby arm might be 3 pages, an autonomous platform 12. Never pad.

```markdown
# [Project Name] — Engineering Design Specification
Rev 0.1 — [date] — Status: Draft

## 1. Problem Statement & Mission
One paragraph: what problem, for whom, and what the machine must accomplish
as observable outcomes. No mechanisms in this section. If an
armature-pitch brief exists, this is that brief's problem and
audience restated in engineering terms, not re-derived from scratch —
name the brief and its rev.

## 2. Concept of Operations
A day in the life of the robot: how it's deployed, operated, maintained,
stored. Who touches it and when.

## 3. Requirements
### 3.1 Functional
| ID | Requirement | Value / Threshold | Priority | Verification |
|----|-------------|-------------------|----------|--------------|
| REQ-001 | ... | ... | Must/Should/Could | Test/Analysis/Inspection/Demo |

### 3.2 Non-functional (constraints)
Mass, envelope, budget, timeline, power, environment (IP rating, temp),
safety, noise, maintainability. Same table format.

## 4. Builder Capability Assessment
Honest statement of fabrication access, skills, hours, and prior experience,
and how the chosen scope reflects it.

## 5. Concept Alternatives & Trade Study
### 5.1 Concepts considered
2-4 distinct architectures, each with a paragraph and a rough sketch
description.
### 5.2 Trade-off matrix
Weighted criteria (weights from user), scored 1-5, with a sentence
justifying any non-obvious score.
### 5.3 Selected concept & rationale
Why the winner won AND why each loser lost.

## 6. Kinematic & Motion Envelope
Skip only if the mechanism has no meaningful DOF (a static fixture, say) —
say so explicitly rather than omitting the section silently.

**Platform mapping.** The fields below read directly for a mechanism on a
fixed base; a machine that moves its own body answers the translated
reading, and says which one it used. *Topology* (6.1) opens with the
body's 6 DOF as its first row, `Type` reading `F` for a free body, then
the joints that body carries.
*Workspace* (6.2) becomes the flight or stride envelope: apex height and
ground range for a hopper or a drone, stride length and step height for a
legged platform, turning radius and footprint for a wheeled base.
*Motion profile* (6.4) becomes the event that sizes the loads — touchdown
speed and landing attitude for anything that leaves the ground, top speed
and braking deceleration for a wheeled base — in place of a cycle time.
*Mounting* (6.5) becomes the attitude envelope: which way gravity points
across the poses the body actually holds, and the worst of them.

### 6.1 Topology
| Joint | Type (R/P) | Approx. axis / location | Range of motion |
|-------|-----------|--------------------------|------------------|
DOF count stated in one line above the table.

### 6.2 Workspace target
Reach envelope the mechanism must cover: min/max radius, angular sweep,
or linear travel, with units.

### 6.3 Payload envelope
Mass *range* (min/max, not one nominal number), and where it sits
relative to the tool point (offset, or "treat as point mass at the
flange" if unknown).

### 6.4 Motion profile
Target peak/continuous velocity and acceleration (per axis or overall),
and duty cycle beyond cycle time, if the motion itself — not just holding
a loaded pose — is expected to drive the loads. State "static case
dominates, motion profile TBD" if genuinely unknown at this stage rather
than leaving the field blank.

### 6.5 Mounting & gravity orientation
How the base is mounted and which way gravity points relative to the
mechanism (horizontal reach, vertical stack, tilted, mobile-on-a-slope).

This section does not itself choose a kinematic convention (mDH/sDH/PoE,
or a floating base plus joints) or name coordinate frames; that's
**armature-plan**'s job.

## 7. System Architecture
Subsystem breakdown, interfaces between subsystems (mechanical and
electrical: mounting, load paths, connectors, rails, worst-case current),
and driving requirements allocated to each subsystem. Every **data** path
between subsystems is a link in §8 instead, so a protocol appears once.

## 8. Software & Compute Architecture
Scale to consequence — a servo rig on one microcontroller is three rows and
a paragraph; an autonomous platform is the full set. Answer every block;
"n/a" needs one honest clause of why.

### 8.1 Compute units
| Unit | Runtime host | Responsibilities | Driving requirements |
|------|--------------|------------------|----------------------|

A **runtime host** is hardware the robot runs on in the field. The
development machines that never ship — sim host, GPU box, bench laptop —
are **armature-plan**'s machine split, built from this column.

### 8.2 Links
Every data path between units, named. A link with no numbers is not an
interface.

| Link | From → To | Transport | Budget | Verification |
|------|----------|-----------|--------|--------------|

*Transport* names the physical medium and the protocol riding it
("UART2 TELEM2 → Pi PL011, 921600 baud, MAVLink v2"; "Wi-Fi 2.4 GHz,
ROS 2 DDS"). *Budget* is rate, latency, and loss tolerance, with the REQ
that sets it. *Verification* is a seam level — `unit`, `sim`, or `bench`
— plus the measurement: "bench: round-trip latency under load, ≤ 40 ms
p99". A budget only a physical measurement can settle reads `bench`, which
is what **armature-test** will record as a bench seam.

### 8.3 Data artifacts
Files and blobs that cross between units: mission file, trajectory,
calibration, map. A link is live traffic with a latency budget; an
artifact is a file with a schema and a compatibility story.

| Artifact | Written by | Read by | Schema | Versioned? |
|----------|-----------|---------|--------|------------|

### 8.4 Relocation
Which unit could move to another host, what would force the move (a link
that misses its budget, a compute ceiling), and what it costs. Design the
interface so a move is a relocation, not a rewrite — and say here which
moves that buys.

### 8.5 ROS 2 graph
Only when there is one. A robot without a ROS graph names its equivalent
instead — firmware task list, serial command set — and says so.

| Node | Host | Publishes | Subscribes | QoS |
|------|------|-----------|------------|-----|

QoS only where a topic carries a deadline or a reliability requirement.
Services, actions, and parameters stay out until one of them carries a
requirement of its own.

This section does not organise the source tree. Packages, firmware
targets, and repo split are implementation decisions the plan's software
tasks make; the seams **armature-test** agrees are the links above.

## 9. Feasibility Calculations
Back-of-envelope checks that the physics closes: actuator sizing, energy
budget, mass rollup, structural sanity, and the loop-latency rollup across
§8.2's links where a control loop crosses one. Show arithmetic with units.
Each check states its worst case over the envelope; where the arithmetic is
by hand, it names the posture, direction, sign and band value it assumed.

## 10. Risk Register
| Risk | Likelihood | Impact | Mitigation | Revisit trigger |

## 11. Open Questions
Numbered, each with a plan to resolve (prototype, calculation, vendor query).

## 12. Out of Scope / Version 2
What was deliberately excluded, so nobody re-litigates it weekly.

## Mechanical safety

Scale to consequence — a desk toy is not a cobot. Answer each; "n/a" needs
one honest clause of why.

- **Pinch/crush points:** where, and what keeps fingers out during operation
  and maintenance.
- **Stored energy on power loss:** springs, gravity loads, flywheels — what
  moves when power drops, and what arrests it.
- **Tip-over stability:** worst-case CG excursion vs. support polygon,
  including payload and acceleration.
- **Payload drop path:** if the gripper/holder fails, what does the payload
  hit.
- **Sharp edges / hot surfaces** near any human touchpoint.

## Revision History
| Rev | Date | Notes |
```
