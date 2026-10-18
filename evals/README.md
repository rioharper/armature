# Eval cases: the agent measured on golden mechanisms

Tier 2 of [ADR 0008](../docs/adr/0008-the-agent-is-measured-on-golden-mechanisms.md). Each **eval case** runs the plugin's agent through `claude plugin eval` against a **golden mechanism** whose brief states its **bait** outright. Tier 1, the engine against the same mechanisms, is `uv run pytest` in `engine/`.

## The gate

The suite gates every version bump. A partial run, or any case caught in fewer than 2/3 of its runs, blocks the bump.

A run is caught only when every `catch-*` grader passed and no `peeked-*` grader did:
- **A derive case** has two catch graders. `catch-window` is a regex that finds a number inside the answer's **window**, with its unit, in the report the brief fixes. `catch-bait` is an llm rubric that passes only when the bait is visibly rejected or sized. The right number with the bait carried into the decision is not caught.
- **A red-team case** has two catch graders, both on the review the brief fixes. `catch-finding` is an llm rubric that passes only on a BLOCKER or MAJOR finding whose **Where** names the planted location and whose **Finding** carries a number recomputed on the trap's side; a MINOR or QUESTION is not caught. `catch-window` is the same generated window as a derive case's.
- **`false-alarm`**, on a red-team case, is a diagnostic llm rubric that passes when no other BLOCKER or MAJOR finding calls something wrong that the golden derivation shows correct. `score.py` counts a run where it failed as a false alarm and reports the count beside the catch. False alarms never gate.
- **`peeked-*`** passes when a Read, Grep, Glob or Bash call names `golden`, `evals/` or `test_fixture`. The engine's tests, answers included, are readable through the engine path in the case's `pyproject.toml`, so a run that read them is voided.
- **Every other grader is a diagnostic,** reported and never part of the catch: `skill-derive`, `red-team-dispatched` and `ran-the-model`.

The **catch rate** is the share of with-arm runs caught. `score.py` computes it, with the baseline's catch rate, Δ, the `peeked` count and the diagnostics. It exits 1 unless the result is whole and every case is at 2/3 or above. The built-in score is never the gate, because it averages graders and so credits half a catch. That is why `claude plugin eval` runs with `--threshold 0`: its exit code then flags only errors and partial runs.

## Where it runs

On WSL2, on the maintainer's machine. The distro is whichever `wsl -l` lists; the maintainer's is `Ubuntu`, now 26.04, not ADR 0008's `Ubuntu-24.04`. Native Windows refuses any run that grants a shell (#104). Inside the distro you need:
- `claude` 2.1.301 or later, installed natively in the distro (`curl -fsSL https://claude.ai/install.sh | bash`) and logged in there (`claude auth status`). A Windows `claude` from npm is on WSL's PATH through `/mnt/c` and shadows a missing Linux one; it runs the suite on Windows, which scores every case 0 in seconds. Check that `command -v claude` is not under `/mnt/`;
- `bwrap` and `socat`, the sandbox's backend (`sudo apt install bubblewrap socat`);
- `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

Run the suite from a `git archive` copy of the plugin on the distro's own filesystem, such as `~/armature-eval`. From Git Bash, a script runs as `MSYS_NO_PATHCONV=1 wsl -d <distro> -- bash -l <script on /mnt/c/...>`.

**The plugin directory must hold no hard links.** `claude plugin eval` refuses every case, at $0 and before turn 1, if any file in the plugin has more than one name. uv hardlinks a venv's files from its cache, so an `engine/.venv` synced the default way trips it. Sync it with copies instead, `UV_LINK_MODE=copy uv sync` in `engine/`, or run the suite from a `git archive HEAD` copy of the plugin.

## The commands

**The release run,** before every version bump. It costs about $60 of plan usage and takes about 1.5 h:

```
claude plugin eval . --ablation with-without --model claude-opus-5-5 --judge-model claude-sonnet-5-5 \
  --threshold 0 -j 2 --max-cost-usd 90 --allow-tools Bash Write Edit Skill Agent \
  --scaffold --trust-plugin --no-publish --json <out>.json
uv run --project engine python evals/score.py <out>.json
```

A move to a new model is its own deliberate release run, recorded in the CHANGELOG. Raise `-j` only after a release run stays inside the Max window: a usage-limit error scores a run 0 without marking the result partial, and so reads as a missed trap.

**On demand,** while editing `armature-derive`, the red-team agent or `review-checklist.md`. These runs are advisory:

```
claude plugin eval . --case spring-cable-derive --runs 1 --ablation none \
  --model claude-opus-5-5 --judge-model claude-sonnet-5-5 --threshold 0 \
  --allow-tools Bash Write Edit Skill Agent --scaffold --keep-temp \
  --trust-plugin --no-publish --max-cost-usd 15 --json <out>.json
uv run --project engine python evals/score.py <out>.json
```

Never run it per commit.

## Reading a kept workspace

`--keep-temp` prints each run's directory, `/tmp/claude-eval-XXXXXX/`. Its `sealed/` is mode 000, so open it first:

```
chmod 700 /tmp/claude-eval-XXXXXX /tmp/claude-eval-XXXXXX/sealed
```

The agent's workspace is `sealed/home/cwd/`, and the session's trace is `out/trace.jsonl`. Don't run git, or anything else that loads configuration from its working directory, inside the kept directory.

**Read it before the distro stops.** WSL empties `/tmp` when the distro shuts down, which it does soon after its last process exits. Chain the reading onto the eval in the same script, or keep a WSL shell open while you read. Once it is gone, the judge's `evidence` in `results/<timestamp>/aggregate-result.json` still holds the text of each file an llm grader read.

## A case's files

```
evals/
  scaffold.sh             lays down a case's spec-stage project
  planted.sh              lays down a red-team case's: scaffold.sh, then its planted/
  generate.py             writes every case's graders from its golden Answer
  score.py                the catch rate, from --json
  tests/                  uv run --project engine pytest evals/tests
  <case>/
    case.yaml             its name and its scaffold
    prompt.md             its brief, and its settings in the frontmatter
    scaffold.sh           execs ../scaffold.sh (or ../planted.sh) with its golden mechanism
    planted/              a red-team case's derivation, laid out as in the project
    graders/              generated: never edit them by hand
```

**The scaffold** runs unsandboxed, as you, in the run's empty workspace. It has no `CLAUDE_PLUGIN_ROOT`, so it reaches the plugin from its own path. It copies the model template's runner into `analysis/model/`, then `engine/tests/golden/<mechanism>/` over it. It points `pyproject.toml` at this plugin's `engine/` by absolute path, runs `uv sync` against the persistent cache `/var/tmp/armature-eval-uv`, and commits. The agent's sandboxed `uv run` then needs no network grant.

**A red-team case's scaffold** is `planted.sh`. It runs `scaffold.sh`, copies the template's gates and review artifact (`layout.py`, `layout_checks.py`, `report_truth.py`) beside the runner, then the case's `planted/` over the workspace, and commits the derivation on top of the spec stage. `planted/` holds only what the derivation adds, its notes, model modules and decision report, written by hand: golden-correct but for one trap, planted where derive's own gates let it through. The description is never in it, so it keeps one source. `evals/tests/test_planted.py` assembles each case through its own `scaffold.sh` and holds three things: `run_all.py` passes; the planted report's number, `claim` in `CASES`, lies outside the window and the golden value inside; and no number inside the window appears in the planted derivation or in what its run prints, so a review cannot copy it. It is marked slow, and on Windows runs the scaffold under Git's bash with uv's own cache (`ARMATURE_EVAL_UV_CACHE`).

**The graders are generated.** `generate.py` holds each case's answer, report path and bait conditions in `CASES`, and writes its graders from the named `Answer` in `engine/tests/golden/answers.py`. The window's regex comes from the golden value and is never written by hand. After a change to a golden project's parameters, or to `CASES`, re-run:

```
uv run --project engine python evals/generate.py
```

The generated files are checked in, because `claude plugin eval` reads their frontmatter statically. `evals/tests/test_generate.py` regenerates them and fails on any difference.
