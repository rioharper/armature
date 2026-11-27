# ADR 0013 — One check, and reviews that advise

2026-11-21 — Status: accepted. Supersedes [ADR 0011](0011-actions-are-gated-not-stages.md).

The `merge` and `buy` gates are removed, with everything that existed to
feed them: the plugin hook, the stamps under `.armature/`, the rule that
gated paths change only on an `armature/<kind>-<name>` branch, `waivers.toml`,
order records, the findings block that ends a review, closures, `moves`, and
recheck mode.

What stays:

- **One check.** `armature.sh check` (`armature.check`) runs `ledger check`
  and every `run_all.py`, streaming each run's output, and exits nonzero on
  any failure. A folder named on the command line runs alone. Nothing is
  cached and git is never read. A stage skill runs it before it commits.
- **Reviews that advise.** The red team is dispatched when a spec is
  finished, before money or a drawing leaves the project, and when the user
  asks. Its report is prose with severities. The dispatching conversation
  fixes what it agrees with and takes the rest to the user. No fix is
  re-reviewed. A number a review recomputed can still be kept as a
  `test_F<n>_*` in a `review_<date>_<artifact>_checks.py`, which `run_all.py`
  collects as before.
- **The user's confirmations.** A `confirmed` ledger entry is still written
  only on the user's word. Nothing prompts for it.

Why:

- **The gate cost more than the mistakes it caught.** On Ibex one gate run
  reached two hours (#216), any edit in a model folder or the ledger re-ran
  all of it, and touching the tree during a run voided it (#207). Four weeks
  produced 67 review files, more rechecks than reviews, several findings
  reaching a third recheck.
- **Its own bookkeeping became the work.** About 27 of the open issues are
  defects in the gate's record keeping rather than in a robot: reviews that
  stop counting after `git merge main` (#214), a patch release that blocks
  every merge (#252), waivers too coarse to use (#254), a hook that misparses
  shell (#182, #229, #230).
- **A project has one user.** ADR 0011 guarded against a session
  self-certifying its fixes. The user reading a findings report and deciding
  is a sufficient guard for projects of this size.

The cost accepted:

- A review can be skipped, and a fix can be wrong without anyone checking it.
  ADR 0011 recorded derive dispatching the red team in 12 of 27 runs when
  only prose asked for it; that will recur.
- Nothing stops a purchase resting on an unconfirmed number except the spec
  skill saying so.
- A full check re-runs every folder every time. Name a folder to run less.
- A project made under 3.x or 4.x keeps a dead `waivers.toml`, `docs/orders/`
  and `.armature/`. They can be deleted.

Revisit if a wrong number reaches a purchase or a drawing that a gate item
would have stopped.
