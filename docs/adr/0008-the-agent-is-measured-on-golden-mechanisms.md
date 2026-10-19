# ADR 0008 — The agent is measured on golden mechanisms by `claude plugin eval`, on WSL2, before every version bump

2026-10-16 — Status: accepted (reverses #48's "one seam": the template's own `run_all.py` and pytest, with no plugin eval harness)

The plugin is tested at two seams, each against the same five **golden
mechanisms**: the 2R arm, a cable platform, a five-bar leg on a wheel, a
balanced parallelogram arm, and a mass on a spring and on a cable.

- **Tier 1, the engine.** `uv run pytest` in `engine/` fills the **verb
  matrix**: every golden mechanism against every engine verb, each cell a
  known answer from a closed form or an independent computation, covered
  elsewhere by a named cell, or not applicable. Every **trap** is shown
  failing beside the verb that catches it.
- **Tier 2, the agent.** `claude plugin eval` runs eight **eval cases**: a
  derive plan task and a red-team review on each golden mechanism but the 2R
  arm. Each brief states its **bait** outright. A run is caught only when its
  report states the known answer inside the case's **window** and the bait is
  visibly rejected or sized. A case passes at a **catch rate** of at least 2/3
  over 3 runs, and the suite passes when all eight do.

The golden descriptions live once, as project-form directories in
`engine/tests/golden/`, which tier 1 loads and each case's scaffold copies.
Their answers sit beside them, never inside, and generate each case's catch
graders.

#48 chose the template's self-run as the single seam, and that is why fitting
to one shape went unseen. Every fixture was the 2R arm or a three-cable hang,
none had a spring, a loop or a wheel, and the 0 N/m stiffness bug shipped. On
2026-10-15 the engine's own verbs still barely left the 2R arm: `margins` ran
on one golden mechanism, `charge` on none, and the parallelogram's regeneration
trap was unbuilt. Nothing measured the agent at all. #48's manual acceptance,
re-running Plumb's Milestone 1 by hand, ran once.

Tier 2 runs on WSL2 (`Ubuntu-24.04`) on the maintainer's machine, on the Max
plan, as a gate before every version bump. A partial run or any failing case
blocks the bump. It does not run in CI, which is why the repo has no
`.github/`:
- **Native Windows** refuses every run that grants a shell, because its
  sandbox's feature gate is off, and both case families need Bash to run
  `run_all.py`. Measured on 2026-10-15 (#104).
- **GitHub Actions** needs `ANTHROPIC_API_KEY`, which makes every suite about
  $60 of real API spend, for a suite that is only ever started by hand.
- **On WSL2** a shell-granting case runs end to end under the sandbox, with
  bubblewrap, socat and uv installed (#112).

Release runs keep the no-plugin baseline arm, pin Opus 5.5 and a Sonnet 5.5
judge, and cap spend at $90 for an estimate of about $60.

Rejected:
- **The template self-run alone** (#48). It measures the 2R arm and never the
  agent.
- **The built-in score as the gate.** It averages graders, so a run with the
  right number that still carries the bait scores 0.5.
- **A checker that re-runs the model in kept workspaces.** The workspaces are
  sealed (mode 000 on WSL), and it would duplicate the graders.
- **Hiding the answers from the agent.** The engine path is readable from the
  case's own `pyproject.toml`. A `peeked` grader voids a run that read them
  instead.
- **A 2R tier-2 case.** The derive template is the 2R arm, so the case would
  measure copying.

The cost accepted:
- Every release costs about $60 of plan usage and 1.5 h of wall time.
- The gate depends on one machine's WSL2 setup.
- A usage-limit error scores a run 0 without marking the result partial, so
  it reads as a missed trap.
- An llm judge decides half of every catch.

Revisit when the native-Windows sandbox gate turns on, when the suite's track
record supports raising the gate to 3 of 3 (with 5 runs per case), or when
Overhaul 05 changes how a project reaches the engine.

**Amended 2026-10-18 (#131):** the first release run's baseline caught all
24 of its runs (#124), so with every bait stated outright the suite could not
show that the plugin is what catches the trap. Each case now has an
**unstated variant**, `<case>-unstated`, whose brief only implies the bait,
and the suite runs sixteen cases. A red-team variant's derivation uses the
bait without numbering it, so the review must find it as well. The variants gate on the same 2/3 with-arm
catch rate as the rest. A release now costs about $80 of plan usage and
2.7 h of wall time.
