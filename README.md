# Armature: robotics engineering plugin for Claude Code

Armature is a robotics engineering pipeline for Claude Code. It walks you from idea to CAD the way an engineering team would: budgets tracked, requirements traced, decisions logged, and a red-team review before anything gets built or bought.

AI has changed software engineering but barely touched robot design. Armature won't replace a mechanical engineer, but it does take a lot of the grind out of iterating on concepts, writing specs, and working through the kinematics and dynamics.

## Quick start

1. **Install.** You need [`gh`](https://cli.github.com/) on PATH and `gh auth login` done, and [uv](https://docs.astral.sh/uv/) for the derivation's model.

   ```
   /plugin marketplace add rioharper/armature
   /plugin install armature@armature-plugins
   ```

2. **Start a project.** Run `/armature:init` in a blank folder. It scaffolds the project, offers to create the GitHub repo, and starts the pitch interview.

3. **Chart a map with `armature-wayfind`.** Once the pitch is done, ask Claude to chart a map. You agree on a destination, usually "spec frozen". Wayfind then breaks the work into decision tickets on GitHub Issues: trade studies, architecture choices, mockups, and bench measurements.

4. **Work one ticket per session.** Say "work the map" and Claude picks the next open ticket. It then calls the right skill or agent for that ticket (`armature-spec`, `armature-derive`, `armature-cad`, the librarian, the inventor, or the red-team) and logs the decision. You don't have to pick which skill to use next. The map keeps track of that.

5. **Plan the build.** Once the spec is frozen, `armature-plan` turns it into phased GitHub issues. From there, `armature-derive`, `armature-cad`, and `armature-bringup` handle the analysis, CAD, and bench tasks as they come due.

For a small project that fits in a few sessions, you can skip the map and run the stages in order:

| Stage | You get |
|---|---|
| `armature-pitch` | Who it's for and why it beats what exists |
| `armature-spec` | Engineering spec, trade studies, BOM, budgets, traceability |
| `armature-plan` | Phased plan as GitHub issues, plus shared frames, symbols, and naming |
| `armature-derive` | Kinematics and dynamics notes plus a re-runnable Python model |
| `armature-cad` | Part definitions and build recipes for your CAD package |

Either way, work lands on a branch and reaches `main` through one of two gates, which the skills run for you:
- **`merge`**: a branch that changes a number, the model, a part, or spec or plan text needs an `armature-red-team` review of it, and every BLOCKER and MAJOR closed by a kept check, a recheck, or your acceptance. The model must also pass.
- **`buy`**: an order, whether parts bought or a drawing sent out, also needs every part it names confirmed by you and priced in the last 90 days.

A plugin hook backs the gates up: it refuses a merge into `main` the gate would refuse, and asks you before anything is recorded as your confirmation. It never touches your own terminal. A gate you disagree with is waived in writing, in `waivers.toml`.

## Where to go

| Your situation | Use |
|---|---|
| New robot idea, blank folder | `/armature:init` |
| Not sure it's worth building, or who it's for | `armature-pitch` |
| Need a spec, trade study, or design review | `armature-spec` |
| Need phases and shared vocabulary | `armature-plan` |
| Adding a machine (sim host, render host, target board) | `armature-plan` on that machine |
| Need equations of motion, Jacobians, workspace, or actuator sizing | `armature-derive` |
| A plan's analysis task is due | `armature-derive` |
| Ready to model a part, or check its mass and inertia | `armature-cad` |
| Want a concept or design decision explained | `armature-teach` |
| Writing firmware, ROS nodes, or control code | `armature-test` (starts on its own) |
| Hardware misbehaving at the bench | `/armature:armature-debug` |
| A plan's bring-up or verification test is due | `armature-bringup` |
| A machinist, vendor, or professor has the answer | Questionnaire via `armature-spec` or `armature-cad` |
| Most projects, after the pitch | `armature-wayfind` |
| Draft done, ready to merge or buy | `armature-red-team` (agent) |
| Design stuck or too conventional | `armature-inventor` (agent) |
| Need a datasheet, price, or vendor CAD model | `armature-librarian` (agent) |
| SolidWorks stopped connecting after a plugin update | `/armature:init` |

Only `/armature:init` and `/armature:armature-debug` have to be typed. Everything else starts on its own.

## Example output

From the Ibex rover, a squatting camera platform built with Armature. Each card comes from the `armature-derive` Python model:

| | |
|---|---|
| ![Hip gravity compensation: worst hold torque drops 9.4x with a gas strut](media/ibex-card-1-gravity.png) | ![Mirror-leg four-bar keeps the wheel under the hip across seven postures](media/ibex-card-2-fourbar.png) |

![Hip hold power over a 45-minute scan mission: 0.38 W vs 431 W uncompensated](media/ibex-card-3-power.png)

## Optional tools

### SolidWorks MCP

Windows and SolidWorks only. Requires [uv](https://docs.astral.sh/uv/) on PATH. Say yes to the SolidWorks question in `/armature:init` and it writes the project's `.mcp.json`. The server doesn't model for you. It measures the live model (mass properties, rebuild checks, interface dimensions, tolerances, title blocks) so `armature-cad` can check it. After a plugin update, re-run `/armature:init` to repoint it. See `mcp/solidworks/`.

### build123d recipes

`armature-cad` can write each part's build recipe as a [build123d](https://github.com/gumyr/build123d) script. That lets you check mass and inertia against the model, catch broken features, render real views, and sweep for interference before opening CAD. It doesn't replace CAD: no assemblies, drawings, GD&T, or FEA. Tested with build123d 0.11.1.

```
uv run --with 'build123d~=0.11' python cad/parts/<PART-ID>.py
```

`cad/parts/run_all.py` runs every part and the interference sweep, so it also needs the model's environment: `uv run --project analysis/model --with 'build123d~=0.11' python cad/parts/run_all.py`. A nonzero exit means a check failed.

## Project layout

`/armature:init` scaffolds this tree:

```
<project>/
  CLAUDE.md                  project constitution
  CONTEXT.md                 glossary (armature-plan)
  ledger.toml                every input number, once, with unit, band and source
  waivers.toml               exemptions from a gate, each confirmed by you
  .armature/                 the gate's cache of model runs (gitignored)
  docs/
    00-concept/concept-brief.md
    01-spec/                 spec, bom, budgets, traceability
    02-plan/draft.md         plan checkpoint, on the plan's branch only (the plan lives in GitHub Issues)
    testing/                 test procedures and reports
    reviews/                 red-team findings, each ending in its findings' closures
    orders/                  one record per order, parts bought or a drawing released
    research/                inventor briefs
    datasheets/              cached datasheets and index
    decisions.md             decision log
    environment.md           what each machine has installed
  analysis/
    derivation/              derive milestone notes
    model/                   re-runnable Python model, in its own uv environment
      mechanism.py           the mechanism description the truth model is compiled from
  cad/
    parts/                   part definitions and optional build recipes
    assemblies/              assembly definitions
    ots-parts/               vendor CAD models and index
  .mcp.json                  SolidWorks projects only (gitignored)
```

## Install details

`armature-derive`'s model depends on the **engine**, the Python package in [`engine/`](engine/) (imported as `armature`, pinned to MuJoCo 3.15). It compiles the project's mechanism description into the MuJoCo truth model every milestone is checked against. The model runs in its own environment through [uv](https://docs.astral.sh/uv/), so uv must be on PATH. A project pins the engine by the git tag of the plugin release it runs and commits `uv.lock` ([ADR 0009](docs/adr/0009-the-engine-reaches-projects-as-a-git-tag.md)), so the model's first `uv sync` needs access to GitHub as well as PyPI. Later syncs work offline from uv's cache.

The gates and the hook run the plugin's own copy of the engine, also through uv, in an environment Claude Code keeps in the plugin's data folder ([ADR 0011](docs/adr/0011-actions-are-gated-not-stages.md)). The first gated call builds it from PyPI, in 15–30 s; after that a merge is checked in about 6 s. Without uv the hook refuses only what it gates, and says to install uv. It acts only in a project whose root holds `ledger.toml`.

Armature keeps the plan on GitHub Issues, so it needs `gh`, `gh auth login`, and a GitHub remote. `/armature:init` checks all three and offers to create the repo (private by default). There is no non-GitHub option. To run from a local copy instead of the marketplace, point `--plugin-dir` at this repo.

## Credits

`armature-wayfind`, `armature-test`, `armature-debug`, `armature-bringup`, the questionnaire template, and the interview, glossary, and writing conventions across the skills adapt material from [Matt Pocock's skills](https://github.com/mattpocock/skills), used under the MIT License. See [`NOTICE.md`](NOTICE.md) for the full notice and [`CHANGELOG.md`](CHANGELOG.md) for release notes.
