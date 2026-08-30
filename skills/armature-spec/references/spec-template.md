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

This section does not itself choose a kinematic convention (mDH/sDH/
PoE) or name coordinate frames; that's **armature-plan**'s job.

## 7. System Architecture
Subsystem breakdown, interfaces between subsystems (mechanical, electrical,
data), and driving requirements allocated to each subsystem.

## 8. Feasibility Calculations
Back-of-envelope checks that the physics closes: actuator sizing, energy
budget, mass rollup, structural sanity, bandwidth/latency if relevant.
Show arithmetic with units.

## 9. Risk Register
| Risk | Likelihood | Impact | Mitigation | Revisit trigger |

## 10. Open Questions
Numbered, each with a plan to resolve (prototype, calculation, vendor query).

## 11. Out of Scope / Version 2
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
