# Eval cases: the agent measured on golden mechanisms

Tier 2 of [ADR 0008](../docs/adr/0008-the-agent-is-measured-on-golden-mechanisms.md). Each **eval case** runs the plugin's agent through `claude plugin eval` against a **golden mechanism** whose brief states its **bait** outright, or, in the case's **unstated variant**, only implies it. Tier 1, the engine against the same mechanisms, is `uv run pytest` in `engine/`.

## The gate

The suite gates every version bump. A partial run, or any case caught in fewer than 2/3 of its runs, blocks the bump. The hold-out is the one case that never gates (below).

A run is caught only when every `catch-*` grader passed and no `peeked-*` grader did:
- **A derive case** has two catch graders. `catch-window` is a regex that finds a number inside the answer's **window**, with its unit, in the report the brief fixes. `catch-bait` is an llm rubric that passes only when the bait is visibly rejected or sized. The right number with the bait carried into the decision is not caught.
- **A red-team case** has two catch graders, both on the review the brief fixes. `catch-finding` is an llm rubric that passes only on a BLOCKER or MAJOR finding whose **Where** names the planted location and whose **Finding** carries a number recomputed on the trap's side; a MINOR or QUESTION is not caught. `catch-window` is the same generated window as a derive case's.
- **`false-alarm`**, on a red-team case, is a diagnostic llm rubric that passes when no other BLOCKER or MAJOR finding calls something wrong that the golden derivation shows correct. It fails only on a finding it quotes, with the listed item it contradicts; a robustness point beside a listed item, or a finding on the trap's own check, is not a false alarm. `score.py` counts a run where it failed as a false alarm and reports the count beside the catch. False alarms never gate.
- **`peeked-*`** passes when a Read, Grep, Glob or Bash call names `golden`, `evals/` or `test_fixture`, inside quoted code too, other than as an exclusion: an argument to `-not -path`, `! -path`, `--exclude` or `--exclude-dir`, or a glob opening with `!`. The agent reads the plugin through the engine path in the case's `pyproject.toml`. The copy a run starts from holds no `engine/tests/` (#128), but a run that reaches the answers some other way, such as through a checkout, is still voided.
- **An unstated variant**, `<case>-unstated`, is its case with the bait taken out of the brief's numbered assumptions: no A3, the assumption implied only by the spec's prose. It has its case's answer, window, trap and graders, with only the bait's wording changed, so it measures finding the assumption and not only rejecting it. A red-team variant reviews its case's derivation reworded the same way: the bait used, never numbered as an assumption. It gates like every other case. #124's baseline caught all 24 of its runs with the bait stated, so the stated cases alone cannot show the plugin is what catches the trap; the variant's Δ is the one to read.
- **An unstated-only trap case**, also named `-unstated`, is a derive case with no stated twin, since stating its bait states the question its trap tests (#137). Its trap survives a passing `run_all.py`: the scaffolded run exposes nothing of it, and only a question a skill rule makes the agent ask finds it. Its bait is the default reading its brief implies. It gates on the same 2/3, and a golden mechanism may have any number of them beside its case and variant.
- **Every other grader is a diagnostic,** reported and never part of the catch: `skill-derive`, `red-team-dispatched` and `ran-the-model`.

The **catch rate** is the share of with-arm runs caught. `score.py` computes it, with the baseline's catch rate, Δ, the `peeked` count and the diagnostics. It exits 1 unless the result is whole and every case but the hold-out is at 2/3 or above. The built-in score is never the gate, because it averages graders and so credits half a catch. That is why `claude plugin eval` runs with `--threshold 0`: its exit code then flags only errors and partial runs.

## The hold-out

Every case above is one we tune briefs, rubrics and skills against, so a rise in its catch rate may be fitting rather than improvement. The **hold-out**, `evals/holdout/turret-derive/`, is a derive case nobody tunes against (#132). Its golden mechanism, the geared turret, has no other case, and its trap is of a class no tuned case uses. Its brief only implies the bait, as an unstated variant's does.

- **It runs in every release run and never gates.** `claude plugin eval` finds every `case.yaml` under `evals/`, so the release run's command is unchanged. `score.py` reports the hold-out in its own section beside the gate, with its catch rate, baseline, Δ, `peeked` count and diagnostics, and its exit code is the same with the hold-out caught, missed or absent. A case is held out by living under `evals/holdout/`.
- **It is frozen.** What is the case's own is written once: its brief, `case.yaml`, scaffold and `catch-*` graders, its golden project and its `Answer`. `evals/tests/test_holdout.py` pins a SHA-256 over those alone, line endings read as LF, and fails on any edit. The `peeked-*` and diagnostic graders every case shares are left out of the pin, so a fix to their wording, such as #130's, reaches the hold-out with the rest. A deliberate edit bumps the pin, with a CHANGELOG entry saying why, and is never a response to the hold-out's results.
- **Don't open it while tuning.** Read its results as they come and change nothing because of them. Never run it on demand while editing `armature-derive`, the red-team agent or `review-checklist.md`. What else the agent reads may say a hold-out exists and nothing more: the CHANGELOG and `docs/adr/` ship in `copy.sh`'s copy, so neither names its case, its mechanism, its report, its `Answer` or a number inside its window. `test_holdout.py` holds that over every file the copy ships outside `evals/`.

Its graders are generated like every case's (`HOLDOUT` in `generate.py`), and its `peeked-*` are every case's, so a run that reads `evals/` or `golden` is voided.

## Where it runs

On WSL2, on the maintainer's machine. The distro is whichever `wsl -l` lists; the maintainer's is `Ubuntu-24.04`. Native Windows refuses any run that grants a shell (#104). Inside the distro you need:
- `claude` 2.1.301 or later, installed natively in the distro (`curl -fsSL https://claude.ai/install.sh | bash`) and logged in there (`claude auth status`). A Windows `claude` from npm is on WSL's PATH through `/mnt/c` and shadows a missing Linux one; it runs the suite on Windows, which scores every case 0 in seconds. Check that `command -v claude` is not under `/mnt/`;
- `bwrap` and `socat`, the sandbox's backend (`sudo apt install bubblewrap socat`);
- `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

Run the suite from the copy of the plugin that `evals/copy.sh` makes on the distro's own filesystem. In the distro, from the main checkout (WSL's git can't follow a worktree's `.git`):

```
bash /mnt/c/<checkout>/evals/copy.sh ~/armature-eval
```

It writes a `git archive` of HEAD into an empty directory, so commit first. It leaves out `engine/tests/`, the fixture tests and the golden answers the agent could otherwise read through the engine path (#128). The golden projects go to `evals/golden/` instead, which the harness masks from the agent. From Git Bash, a script runs as `MSYS_NO_PATHCONV=1 wsl -d <distro> -- bash -l <script on /mnt/c/...>`.

**The plugin directory must hold no hard links.** `claude plugin eval` refuses every case, at $0 and before turn 1, if any file in the plugin has more than one name. uv hardlinks a venv's files from its cache, so an `engine/.venv` synced the default way trips it. `copy.sh`'s copy has no venv, so it holds none.

## The commands

**The release run,** before every version bump. It costs about $106 of plan usage and takes about 233 min: 2.0.0's $100 and 220 min (#137), plus about $6 and 13 min for the braking trap's six runs (#150). That is over twice #124's $39 and 79 min now that every case has its unstated variant and the hold-out runs beside them:

```
claude plugin eval . --ablation with-without --model claude-opus-5-5 --judge-model claude-sonnet-5-5 \
  --threshold 0 -j 2 --max-cost-usd 180 --allow-tools Bash Write Edit Skill Agent \
  --scaffold --trust-plugin --no-publish --json <out>.json
uv run --project engine python evals/score.py <out>.json
```

**The release procedure.** The engine's version, `plugin.json`'s and `marketplace.json`'s are one version and one tag `vX.Y.Z` names all three ([ADR 0009](../docs/adr/0009-the-engine-reaches-projects-as-a-git-tag.md)), so a tag must point at the exact commit the release run gated:

1. Bump the three versions in one commit. `engine/tests/test_version.py` fails until all three agree.
2. Run the release run above on that commit.
3. If it passes, tag that commit `vX.Y.Z`. If it fails, the fix is a new commit and the run is repeated on it; no tag points at an ungated commit.
4. Push `main` and the tag together: `git push --atomic origin main vX.Y.Z`.
5. Run `bash evals/release-smoke.sh vX.Y.Z` from the tagged commit. It is the one test of the git source a project syncs from: the tag on origin, `engine-source.sh pin` with the lock, then `run_all.py` on the fetched engine.

A tag once pushed may already be in a project's `uv.lock`, so it is never moved or deleted: a failure after the push is a patch release, the next patch version through the same five steps.

A move to a new model is its own deliberate release run, recorded in the CHANGELOG. Raise `-j` only after a release run stays inside the Max window: a usage-limit error scores a run 0 without marking the result partial, and so reads as a missed trap.

**On demand,** while editing `armature-derive`, the red-team agent or `review-checklist.md`. These runs are advisory:

```
claude plugin eval . --case spring-cable-derive --runs 1 --ablation none \
  --model claude-opus-5-5 --judge-model claude-sonnet-5-5 --threshold 0 \
  --allow-tools Bash Write Edit Skill Agent --scaffold --keep-temp \
  --trust-plugin --no-publish --max-cost-usd 15 --json <out>.json
uv run --project engine python evals/score.py <out>.json
```

Never run it per commit. Keep paths into `evals/` and `engine/tests/golden/` out of those three files, and out of anything else the agent reads: a run that reads the answers is voided, and a pointer in its context invites the read.

## Reading a kept workspace

`--keep-temp` prints each run's directory, `/tmp/claude-eval-XXXXXX/`. Its `sealed/` is mode 000, so open it first:

```
chmod 700 /tmp/claude-eval-XXXXXX /tmp/claude-eval-XXXXXX/sealed
```

The agent's workspace is `sealed/home/cwd/`, and the session's trace is `out/trace.jsonl`. Don't run git, or anything else that loads configuration from its working directory, inside the kept directory.

**Keep the workspaces off `/tmp`.** WSL's `/tmp` is a RAM disk (7.6 GB on a 16 GB machine), and a kept run is about 300 MB, so a full release run with `--keep-temp` fills it. The scaffolds then fail, and later runs fail to start with `ENOSPC`, while `--json` still reports `partial: false`. The harness keeps its workspaces under `TMPDIR`, so point it at the distro's disk (`export TMPDIR=~/eval-tmp`), and clear old `claude-eval-*` directories first.

**Read it before the distro stops.** WSL empties `/tmp` when the distro shuts down, which it does soon after its last process exits. Chain the reading onto the eval in the same script, or keep a WSL shell open while you read. Once it is gone, the judge's `evidence` in `results/<timestamp>/aggregate-result.json` still holds the text of each file an llm grader read.

## A case's files

```
evals/
  copy.sh                 makes the copy of the plugin a run starts from
  scaffold.sh             lays down a case's spec-stage project
  planted.sh              lays down a red-team case's: scaffold.sh, then its planted/
  generate.py             writes every case's graders from its golden Answer
  score.py                the catch rate, from --json
  release-smoke.sh        a project's first sync from a pushed release tag
  tests/                  uv run --project engine pytest evals/tests
  <case>/
    case.yaml             its name and its scaffold
    prompt.md             its brief, and its settings in the frontmatter
    scaffold.sh           execs ../scaffold.sh (or ../planted.sh) with its golden mechanism
    planted/              a red-team case's derivation, laid out as in the project
    graders/              generated: never edit them by hand
  <case>-unstated/        its unstated variant: the same files, but no planted/
    implicit.patch        a red-team variant's: its case's planted/ with the bait never numbered
  <trap>-unstated/        an unstated-only trap case: a derive case's files, with no stated twin
  holdout/
    turret-derive/        the hold-out: a derive case's files, frozen; don't open it while tuning
```

**The scaffold** runs unsandboxed, as you, in the run's empty workspace. It has no `CLAUDE_PLUGIN_ROOT`, so it reaches the plugin from its own path. It copies the model template's runner into `analysis/model/`, then the golden project over it: `evals/golden/<mechanism>/` in `copy.sh`'s copy, `engine/tests/golden/<mechanism>/` in a checkout. It places the golden project's `ledger.toml` at the workspace's root, where a project keeps its ledger and `params.py`'s `load` finds it walking up from `analysis/model/`. It points `pyproject.toml` at this plugin's `engine/` by absolute path, runs `uv sync` against the persistent cache `/var/tmp/armature-eval-uv`, and commits. The agent's sandboxed `uv run` then needs no network grant.

**A red-team case's scaffold** is `planted.sh`. It runs `scaffold.sh`, copies the template's gates and review artifact (`layout.py`, `layout_checks.py`, `report_truth.py`) beside the runner, then the case's `planted/` over the workspace, and commits the derivation on top of the spec stage. `planted/` holds only what the derivation adds, its notes, model modules and decision report, written by hand: golden-correct but for one trap, planted where derive's own gates let it through. The description is never in it, so it keeps one source. **An unstated red-team variant** has no `planted/` of its own: its `scaffold.sh` passes its case's to `planted.sh` with its own `implicit.patch`, which `planted.sh` applies with `git apply` over it. The patch takes the bait out of the derivation's numbered assumptions and its A3 out of every file, the trap left in place, so the derivation under review has one source. Edit a stated `planted/` and its variant's patch may no longer apply; `test_planted.py` then fails. Both stay LF (`.gitattributes`), since `git apply` matches line endings exactly. `evals/tests/test_planted.py` assembles every red-team case, variants included, through its own `scaffold.sh` and holds five things: `run_all.py` passes; the planted report's number, `claim` in `CASES`, lies outside the window and the golden value inside; no number inside the window appears in the planted derivation or in what its run prints, so a review cannot copy it; every figure `sound` quotes is in the derivation as laid down; and a variant's derivation names no A3. It is marked slow, and on Windows runs the scaffold under Git's bash with uv's own cache (`ARMATURE_EVAL_UV_CACHE`).

**The graders are generated.** `generate.py` holds each case's answer, report path and bait conditions in `CASES`, and writes its graders from the named `Answer` in `engine/tests/golden/answers.py`. An unstated variant's entry is its case's, with `bait` replaced by the assumption the prose implies (`IMPLIED`, by its case's name) and `stated` false, and a red-team variant's `claim`, `where` and `sound` worded on its patched derivation (`IMPLICIT`); its brief is written by hand, like every brief. An unstated-only trap case's entry is written in `CASES` as it is: a `Derive` with `stated` false, its name ending `-unstated`, no stated twin, and its `bait` the default reading its brief implies. `generate.py` refuses any other unstated entry in `CASES`. The window's regex comes from the golden value and is never written by hand. After a change to a golden project's parameters, or to `CASES`, re-run:

```
uv run --project engine python evals/generate.py
```

The generated files are checked in, because `claude plugin eval` reads their frontmatter statically. `evals/tests/test_generate.py` regenerates them and fails on any difference.
