# ADR 0011 — Actions are gated, not stages

2026-10-21 — Status: accepted

A project no longer records where it is. The `**Stage:**` and
`**Latest artifacts:**` lines leave the `CLAUDE.md` template, and no skill
advances anything. Instead two actions are gated, and each gate is computed
from the repo every time it is asked:

- **`merge`**: a work branch (`armature/<kind>-<name>`: a spec revision, a
  plan, a derive milestone, a CAD batch) merging into `main`.
- **`buy`**: money leaving the project, which is the merge of an
  `armature/order-<name>` branch adding an order record,
  `docs/orders/<date>-<name>.toml`. A purchase is `kind = "purchase"`; a
  drawing, DXF, quote request or fit print sent out is `kind = "release"`.

"Stage" stays a word for a pipeline step (pitch, spec, plan, derive, CAD,
build). Only the marker goes. Starting CAD hours is not a third gate: the CAD
skill checks, as a precondition, that derive's last milestone passed `merge`.

A gate is `armature.gate`, a module of the engine (ADR 0004), with the verbs
`merge`, `buy` and `status`. It prints each item of evidence, passing or
missing, and exits 0 or 1. Nothing stores a pass. The only stored inputs are
reviews, waivers, order records, and a cache of `run_all` results keyed by
content.

**What `merge` demands at the branch tip:**
1. `main` is an ancestor of the tip, so the merge is a fast-forward and the
   tree checked is the tree `main` becomes.
2. `ledger check` reports no error.
3. Every `run_all.py` in the project (the model and each part) has a green
   stamp for its current content.
4. Each model directory's `engine-source.sh check` is `in-step`.
5. A review, when the branch changes a ledger number, model code, a part
   definition, or spec or plan text. Its reviewed SHA is on the branch, at or
   after the branch point. A branch that changes none of those needs no
   review. That one rule covers Milestone 0's template copy and derive's
   unchanged re-run report.
6. Every BLOCKER and MAJOR finding of every such review is closed.
7. Every ledger number changed after a review's SHA is named in the `moves`
   of some finding's closure.

**`buy` adds three items:**
- Every entry under each ordered `part.<pn>` is `confirmed`, and none has the
  source kind `estimate`.
- Every price a line uses (the largest `price_at_<qty>` tier at or below its
  qty) is no older than 90 days.
- A review names the order record in its `artifacts`. An order has no
  review-free exemption.

A release also requires each part's `still_placeholder()` to be empty, and
each part's and the model's `run_all.py` to be stamped green. The model's run
carries the tolerance-corner bands.

**Reviews.** A review ends in one fenced `toml` block:

```toml
reviewed = "<sha>"
artifacts = ["docs/01-spec/spec.md", "ledger.toml"]

[[finding]]
id = "F3"
severity = "MAJOR"           # BLOCKER | MAJOR | MINOR | QUESTION
status = "fixed"             # open | fixed | accepted
closure = { check = "analysis/model/review_2026-10-21_spec_checks.py::test_F3_spring_rate", moves = ["part.rs02.torque_peak"] }
```

The red team writes every finding `open`. A BLOCKER or MAJOR closes in one of
three ways:
- `fixed` with a `check`: a test the review's recomputation landed as, which
  passes at the tip;
- `fixed` with a `recheck`: a narrow red-team pass over the fix diff, in its
  own file `docs/reviews/<date>-<artifact>-recheck.md` with its own SHA, which
  marks the finding `holds` or `reopened`;
- `accepted` with a reason, on the user's word only.

A review's checks live in `review_<date>_<artifact>_checks.py`, one file per
review, in the folder whose `run_all.py` discovers them: `analysis/model/` for
spec, plan and derive findings, and a part's folder for CAD findings. Every
merge therefore re-runs every earlier review's recomputations.

**Waivers.** An exemption from a gate's evidence is a `[[waiver]]` in a root
`waivers.toml`, with `gate`, `item`, `scope` (a branch or `standing`),
`reason` and `confirmed` (the date the user confirmed it). The gate prints
each waiver it applies, and the red team challenges each waiver in scope.
Acceptance of a single finding stays in its review.

**Enforcement.** The stage skills call the gate before the action. A plugin
hook (`hooks/hooks.json`) is the backstop:
- On `Bash|PowerShell`, it watches `git merge` into `main`, `git commit` on
  `main`, `gh pr merge`, and `git push` to a `main` refspec. Plumbing such as
  `update-ref` is not chased.
- A commit on `main` may touch gated paths (spec, plan, derivation, model,
  part definitions) only inside rendered ledger sections. It may change the
  ledger only by adding or editing `candidate` entries. Everything else
  happens on a branch.
- The hook verifies only, so it stays fast. It reads `ledger check`, the
  review blocks, git ancestry and the stamps, and denies with the gate's
  output. It never runs `run_all`. It runs with `timeout: 60` and
  `onFailure: block`.
- It denies Edit and Write under `.armature/`, where the stamps live.
- It asks the user (`permissionDecision: "ask"`) before an Edit or Write
  that sets `accepted`, sets `status = "confirmed"` or adds a waiver.
- It runs the plugin's own engine, with its venv in `${CLAUDE_PLUGIN_DATA}`,
  so it works from `init` on, before spec §9 pins a model engine.
- It acts only where a root `ledger.toml` marks an Armature project. Init's
  guard reads the same marker.

No git hook is installed. The user's own terminal is never policed, because
the user is the authority on every exemption.

Why:
- **The Stage line controlled nothing.** Only init's guard read it. Ibex's
  archive ran derive Milestones 0–2 under `Stage: plan`, and Plumb wrote an
  "Execution override" (`decisions.md:47`).
- **Every gate was prose,** and fixes self-certified.
  - Every review in Plumb and in Ibex's archive was followed by fixes 10–15
    minutes later, then a merge, and none was re-reviewed.
  - Two reviews landed in the same commit as their fixes.
  - Plumb's wrong 0.85 N·m/rad reached ticket #9.
  - In the 2.0.0 release run, derive dispatched the red team in only 12 of
    27 runs.
- **Ibex's archive staged a purchase on a spec review.** The RobStride 02's
  rated torque was marked CONFLICT, and a price came from a "flash sale"
  page.
- **Reviews recomputed numbers 45 times and kept none of it.**

Rejected:
- **Keeping the Stage line as a label.** It would drift again.
- **Gating every commit.** That adds friction to work in progress and catches
  nothing a merge doesn't.
- **A stored pass.** It goes stale with the next number.
- **Skills alone.** That is what failed.
- **A git hook.** It would block the user.
- **Re-reviewing the whole artifact after every fix.** That is too costly; a
  recheck covers only judgment findings.
- **Findings in a TOML file beside the review.** It breaks the red team's
  "exactly one file".
- **Waivers in the ledger or decisions.md.** The ledger holds numbers, and
  decisions.md is prose the gate can't parse.

The cost accepted:
- Spec and plan work move onto branches.
- A branch brings `main` in before merging.
- The user clicks a prompt at each confirmation.
- Hooks see Claude's Edit and Write tools only. A shell edit to `ledger.toml`
  gets past the `ask`, and the red team checks the provenance of `confirmed`
  entries.
- Nothing sees whether a cleared order was actually placed.
- The hook stays active in `claude plugin eval`, so evals measure what users
  get.
- This is a breaking release.

This amends ADR 0010's "this ADR installs no hook". Revisit when the
plan-vs-map decision reopens ADR 0001, or when a gated action happens outside
a merge.
