---
name: armature-debug
description: Bench-debug a hardware/firmware fault — build a red-capable feedback loop before any hypothesis, then probe one variable at a time.
disable-model-invocation: true
---

# Bench Debugging

A discipline for hard bench faults: hardware, firmware, and the seam between them. Skip phases only when explicitly justified.

Before starting, read `CONTEXT.md` (if it exists) and ADRs in the area you're touching; `analysis/model/` and `docs/testing/` hold the project's predicted and measured numbers, which later phases use. Show commands and captured output with secrets replaced by `<REDACTED>`; keep credentials in env vars rather than in what you show.

**Powered-rig guardrail**: before any loop that powers actuators, current-limit the bench supply and confirm the e-stop is in reach — gate it with `confirm` in the human-loop script.

## Phase 1: Build a feedback loop

**This is the skill.** With a **tight** pass/fail signal that goes red on _this_ fault, bisection, hypothesis-testing, and instrumentation all just consume it; without one, no amount of staring at schematics or firmware will save you. Spend disproportionate effort here.

### The ladder — ways to construct one, in roughly this order

1. **Unit or sim test.** If the fault reproduces off the bench, this is the tightest loop there is — build it under armature-test's rules (call the Skill tool with "armature-test").
2. **Serial-log capture harness.** A script that resets (or flashes) the board, captures serial output for a fixed window, and greps tagged prints for the symptom; the exit code is the verdict.
3. **Bench jig script.** Command a stimulus and read the measurement back through a scriptable instrument (SCPI bench supply, USB scope or logic analyzer, DAQ); assert the bound.
4. **Model as oracle.** Re-run `analysis/model/` at the measured operating point and diff prediction against measurement; red is disagreement beyond the derivation's stated tolerance. This is the loop for every "the bench number disagrees with the math" fault.
5. **A/B swap.** Run the same loop with one suspected part exchanged for a known-good unit, so hardware becomes the only variable. The human swaps; the human-loop script structures it.
6. **Human-loop script.** When a human must flash, press, probe, or read the scope, drive _them_: copy the plugin's `scripts/human-loop.template.sh` (two levels above this skill), edit the steps, and run it, so the loop stays structured, gated, and captured. A rung inside any loop above; the whole loop only as a last resort.

### Tighten the loop

Treat the loop as a product. Once you have _a_ loop:

- **Faster**: reset instead of reflash; shorten the capture window; one joint, not six.
- **Sharper**: assert the specific measurement ("bus current < 0.6 A at hold"), not "didn't fault".
- **More deterministic**: fixed pose, defined thermal state (cold start vs. warmed up), same supply limits, pinned firmware build.

### Intermittent faults

Raise the reproduction rate until the fault is debuggable. Intermittent hardware has physical variables: cycle the trigger 100×, heat the suspect area, flex the harness, and log continuously with timestamps so a rare red is still captured.

### When you genuinely cannot build a loop

Stop and say so explicitly. List what you tried. Ask the user for (a) a bench session driven through the human-loop script, (b) a captured artifact (serial log, scope trace, video with timestamps), or (c) permission to leave logging firmware on the rig until the fault recurs. Do **not** proceed to hypothesise without a loop.

### Completion criterion: a tight loop that goes red

Phase 1 is done when you can name **one command** you have **already run at least once** (show the invocation and its output, redacted) that is:

- [ ] **Red-capable**: drives the actual fault path and asserts the user's exact symptom — able to catch this specific fault, not merely "ran without faulting".
- [ ] **Deterministic**: same verdict every run (intermittent faults: a pinned, high reproduction rate).
- [ ] **Fast**: repeatable many times an hour — reset-and-capture, not teardown-and-rebuild.
- [ ] **Runnable on demand**: unattended, or with the human driven by the human-loop script.

No red-capable command, no Phase 2.

## Phase 2: Reproduce + minimise

Run the loop; watch it go red. Confirm:

- [ ] The failure is the one the user described — the right symptom, not a nearby one. Wrong fault = wrong fix.
- [ ] It reproduces across runs at a debuggable rate.
- [ ] The exact symptom is captured (fault code, wrong measurement, timing) so later phases can verify the fix addresses it.

Then shrink to the **smallest rig that still goes red**: disconnect subsystems, unpower peripherals, shorten the harness, drop to one axis, swap battery for bench supply — one cut at a time, re-running the loop after each. Done when every remaining element is load-bearing: removing any one makes the loop go green. The minimal rig shrinks the Phase 3 hypothesis space and becomes the Phase 5 regression setup.

## Phase 3: Hypothesise

Generate **3–5 ranked hypotheses** before testing any of them — "it's probably the ESC" is single-hypothesis anchoring, the failure this phase prevents. Each must be **falsifiable**: state its prediction.

> Format: "If \<X\> is the cause, then \<changing Y\> will make the fault disappear / \<changing Z\> will make it worse."

A hypothesis with no prediction is a vibe: discard or sharpen it. Span domains: at least one hypothesis each in electrical, firmware, and mechanical, unless the loop already rules a domain out.

**Show the ranked list to the user before testing.** They know the rig's history ("that connector's been reworked twice") and re-rank instantly. Don't block on it; proceed with your ranking if the user is AFK.

## Phase 4: Instrument

Each probe maps to a specific Phase 3 prediction, placed where the signal distinguishes hypotheses: PWM correct at the pin means the fault is downstream of the MCU, and half the list is gone. **Change one variable at a time.**

Tool preference:

1. **Debugger halt** (SWD/JTAG) or REPL inspection where the firmware supports it — one breakpoint beats ten prints.
2. **Tagged serial prints** at the distinguishing boundaries, every one tagged with a unique prefix (`[DEBUG-a4f2]`) so cleanup is a single grep. Prints placed only where a prediction says the signal differs — a board-wide sprinkle costs a reflash per iteration and buries the signal.
3. **Physical probes** — meter, scope, logic analyzer — at the distinguishing node, values captured through the human-loop script.

**Timing branch.** For control-loop overruns, jitter, or "it's laggy": measure first — timestamp ISR entry and exit, cycle-count the loop, toggle a spare GPIO and scope it — then bisect. Measure first, fix second.

## Phase 5: Fix + regression test

Write the regression test **before the fix**, at the correct seam:

- If a **unit or sim seam** can exercise the real fault pattern (armature-test's levels), turn the minimised repro into a failing test there: watch it fail, apply the fix, watch it pass.
- If catching it needs a physical measurement, it is a **bench seam**: record it in `docs/testing/bench-seams.md` per armature-test (seam, measurement, pass bound). The record is the regression lock — a shallow unit test that can't replicate the fault chain gives false confidence, so record rather than force one.

Then re-run the Phase 1 loop against the original, un-minimised rig.

## Phase 6: Cleanup

Required before declaring done:

- [ ] Original symptom gone: Phase 1 loop re-run green on the full rig
- [ ] Regression test in the suite, or the bench seam recorded
- [ ] All `[DEBUG-...]` prints removed (grep the prefix) and clean firmware flashed to the rig
- [ ] Throwaway jigs and harness scripts deleted, or promoted to `docs/testing/` as a named procedure
- [ ] Rig restored to its documented configuration: swapped parts returned, or the change logged in `docs/decisions.md`
- [ ] The hypothesis that turned out correct stated in the commit message, so the next debugger learns
