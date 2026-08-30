---
name: armature-test
description: Test-driven development for robot software. Use when writing or modifying robot software (firmware, ROS nodes, control code) in an Armature project, and when the user asks to work test-first.
---

# Test-Driven Development

Robot software in an Armature project is written test-first: the red → green loop, at unit and simulation level. This skill is the reference that makes the loop produce tests worth keeping: what a good test is, where tests go, the anti-patterns, and the rules of the loop. Every section applies on every cycle: consult them before and during the loop, not after.

When exploring the codebase, read `CONTEXT.md` (if it exists) so test names and interface vocabulary match the project's domain language, and respect ADRs in the area you're touching.

## What a good test is

Tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't. A good test reads like a specification: "estop halts commanded motion within one control cycle" tells you exactly what capability exists, and it survives refactors because it doesn't care about internal structure.

See [testing.md](testing.md) for examples and for mocking: mock at the hardware boundary, never your own modules; simulation is the mock of the world.

## Levels: what the loop governs

The loop runs two test levels:

- **Unit**: logic against fakes at the hardware boundary — planners, estimators, protocol parsers, a driver against a fake HAL.
- **Simulation**: behavior in a simulated world — a controller tracking a trajectory, a node graph responding to a sensor stream. A sim test admitted to the suite must be **deterministic**: fixed seed, fixed timestep, no wall-clock.

Everything else is a **bench seam** — an assertion that needs a physical measurement (current draw, settling on the real arm, thermal drift), or a sim scenario that can't meet the determinism rule. Red → green means fails-before, passes-after on every run, and a bench seam can't do that: record it in the project's `docs/testing/bench-seams.md` (create the file on first use — seam, measurement, pass bound) and move on. The slice is done when its unit and sim seams are green and its bench seams are recorded.

## Seams: where tests go

A **seam** is the public boundary you test at: the interface where you observe behavior without reaching inside. Tests live at seams, never against internals.

**Test only at pre-agreed seams.** Before writing any test, write down the seams under test — each tagged unit, sim, or bench — and confirm them with the user. No test is written at an unconfirmed seam. You can't test everything, so agreeing the seams up front is how testing effort lands on the critical paths and complex logic. Ask: "What's the public interface, and which seams should we test?" Re-agree seams each session; the test suite is the durable record.

When the shape of the interface is itself in question: make it **deep** — small surface, large capability behind it — and put the seam where the interface is stable (the command a planner emits, the state a driver reports), not where the code is convenient to reach today.

## Anti-patterns

- **Implementation-coupled**: mocks internal collaborators, tests private state, or verifies through a side channel (reading a node's internals instead of its published output). The tell: the test breaks when you refactor but behavior hasn't changed.
- **Tautological**: the assertion recomputes the expected value the way the code does (a wrench rebuilt with the same Jacobian math, a constant asserted equal to itself), so it passes by construction. Expected values come from an independent source of truth: the project's derivation notes, a datasheet, a worked example.
- **Horizontal slicing**: writing all tests first, then all implementation. Bulk tests verify imagined behavior and commit to test structure before the implementation has taught you anything. Work in **vertical slices**: one test → one implementation → repeat, each test a tracer bullet aimed by the last cycle.

## Rules of the loop

- **Red before green.** Write the failing test first, then only enough code to pass it — no speculative features.
- **One slice at a time.** One seam, one test, one minimal implementation per cycle.
- **Two speeds.** The inner edit-run rhythm runs the unit suite; sim tests gate slice completion — green before the slice is called done.
- **Refactor only on green**, as its own step outside the red → green cycle.
