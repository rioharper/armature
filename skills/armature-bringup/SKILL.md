---
name: armature-bringup
description: Turn a bench test or bring-up task into an executable bash procedure, run it with the operator at the bench, and record the measurements in its docs/testing/ report. Use when a plan's bring-up or verification test task comes due, when the user asks to bring up or bench-test hardware, or to promote a debug jig into a named procedure.
---

# Bring-up

A **procedure** is a bash script under `docs/testing/` that walks the operator through a bench test stage by stage, gates the irreversible, and records every measurement into the test's report. The plan's phase 5–6 tasks name these procedure/report files; this skill makes them executable. Bash only (Git Bash on Windows).

The runner UX is already solved by [procedure.template.sh](procedure.template.sh): stage N-of-M progress, the step/confirm/capture human-loop primitive, and report writing — completed and aborted runs both land in the report's Data section, and every captured value prints as `KEY=VALUE` at the end for you to read. Your job is only to scope the procedure and author its stages. The library above the STAGES marker is identical in every procedure: never hand-edit it.

## 1. Scope

Read the plan task and what it settles — the REQ-xxx or prototype kill criterion, the predicted values in `analysis/model/`, any matching seam in `docs/testing/bench-seams.md`. Then list, in run order:

- every **measurement**: instrument, test point, units, and the pass bound with its source — a bound with no source comes from the model or gets flagged as a guess;
- every **irreversible action** to gate with `confirm`: first battery connect, first torque command, anything not cheaply un-done. A procedure that powers actuators opens with the template's bench-safety gate (supply current-limited, e-stop in reach).

Show the user the stage list and what each captures; they may add, drop, or reorder. Where you don't know the bench — a test point's location, a connector name, which display shows bus current — read the CAD/electrical docs or ask; write only steps that exist on this rig.

**Done when** every measurement has instrument + bound + source, every irreversible action has a gate, and the user has seen the list.

## 2. Author

Copy `procedure.template.sh` to the plan-named path (default `docs/testing/<test-id>.sh`) and edit below the STAGES marker only: set `TEST_ID` / `TEST_NAME` / `REPORT` / `TOTAL_STAGES`, then write one `stage` per bench task, small enough that nothing the operator needs scrolls away. Helper contract and an example are in the template header.

Verify statically — the script blocks on a human, so trace it instead of rehearsing it:

- `bash -n <script>`; `shellcheck` if available; `chmod +x`.
- Every scoped measurement is a `capture`, every scoped gate a `confirm`, `TOTAL_STAGES` matches the stages written.

## 3. Run and report

Run the script with the operator at the bench: `bash docs/testing/<test-id>.sh`. It blocks on their prompts; the run ends with the captured `KEY=VALUE` block and the report path.

Then close the loop on the report (`references/test-report-template.md` in **armature-plan** is the shape; the runner has already written the header and Data):

- Fill Setup and Purpose if this was the first run.
- Judge each captured value against its pass bound and write **Result**: pass/fail stated with the number.
- Write **Feeds** and make the updates it names: the traceability row, the measured value into `params.py`, the budget line.

**Done when** the report's Result states pass/fail with the number and every Feeds row is updated or marked n/a. An aborted run is done too — its abort is in the Data section, and the Result says what stopped it.

Procedures are repo artifacts, not scratch: commit the script and report so the next run starts from the recorded one.
