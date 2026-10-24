# Armature: robotics engineering plugin for Claude Code

Armature turns Claude Code into a robotics engineering team that checks its own work. It takes a robot from a loose idea through a pitch, an engineering spec, a phased plan, kinematics and dynamics, and CAD, the way a disciplined team would: every number written once with its unit, band and source; every sizing claim checked against an independent physics model at its searched worst case; every artifact red-teamed; and nothing merged or bought until the evidence is in the repo.

It is more than a set of prompts. Armature ships a Python **engine** that compiles your mechanism into a MuJoCo truth model, forms its equations of motion symbolically, searches every margin for its worst case, and sizes your motors, drivers and DC bus from a simulated mission. On top of that sit two gates, enforced by a plugin hook, that refuse a merge or a purchase the evidence doesn't support. The plugin itself is measured on golden mechanisms with planted traps before every release.

AI has changed software engineering but barely touched robot design. Armature won't replace a mechanical engineer. It takes over the parts that eat their week: iterating on concepts, keeping specs and budgets consistent, deriving and re-deriving the dynamics, and catching the wrong assumption before it becomes a machined part.

## What sets it apart

**Two independent models of one mechanism.** You describe the mechanism once, in `mechanism.py`: bodies, joints, sites, cables, closed loops, contacts and actuators, every number at one home posture ([ADR 0003](docs/adr/0003-one-mechanism-description-at-the-home-posture.md)). The engine compiles it two ways:
- a **truth model** in MuJoCo, the full description with nothing simplified;
- a **symbolic view** in SymPy, from which `armature.equations` forms M(q), C(q, q̇)q̇ and g(q) by Kane's method, with closed loops, couplings and rigid cables reduced onto the independent coordinates.

The derivation's simplifications are declared by name (`lock`, `couple`, `planar`, `lump`, `rigid`) and each one is sized by releasing it, never argued. A part is sized on the truth model, and the derivation explains and checks the result ([ADR 0012](docs/adr/0012-the-truth-model-sizes-the-derivation-explains.md)). A check of a model against itself can't see a wrong assumption, because the assumption sits on both sides. Two independent models can.

**Worst cases are searched, not picked.** A margin is slack over a named search space: posture, load case and sign, load direction, and every parameter's tolerance band ([ADR 0005](docs/adr/0005-worst-cases-are-searched-once.md)). The engine searches it with a seeded Sobol set, every corner of the space, and a bounded Powell polish, and evaluates each margin twice, by its `fn` and its `check=`, which must agree at the worst point. Nobody reads a torque at a posture they happened to choose.

**Actuators and the bus are sized from a mission.** You write what the robot has to do as moves (jerk-limited, profiled by ruckig), holds, and events, such as an e-stop where each motor coasts, shorts or flux-brakes ([ADR 0006](docs/adr/0006-actuators-and-the-bus-are-sized-from-a-mission.md)). The engine runs it through inverse dynamics to each motor's torque and speed and checks the torque-speed envelope at minimum bus voltage with the winding hot, peak driver current, winding temperature over the duty cycle, and the shared DC bus's voltage through regeneration, brake resistor, flux brakes and trips. It also reports the bus capacitance you need. Every motor constant carries its basis (rms or peak, line or phase), so a √3 or √2 error has nowhere to hide. This runs as early as the spec, on a coarse description ([ADR 0007](docs/adr/0007-actuator-and-bus-feasibility-runs-from-spec.md)).

**Every input number lives once, in the ledger.** `ledger.toml` holds each parameter, requirement threshold, budget line and datasheet figure exactly once, as an SI value with its unit, the quantity as the datasheet printed it, a band, a status, and one of six source kinds, from `estimate` up to `measured` ([ADR 0010](docs/adr/0010-every-input-number-lives-once-in-the-ledger.md)). Unit conversions are checked with pint. The budgets, the BOM, the requirements table and the symbol glossary are generated views of it, so a number changed in one place is changed everywhere, and a breached budget fails its requirement in the traceability matrix.

**Review that can block.** The `armature-red-team` agent reviews every spec, derivation, plan, BOM and part definition from a fresh context, pinned to the commit it read. It recomputes the claims it doubts and ends in a machine-readable findings block. A finding closes only through a kept check (its recomputation, landed as a test that runs at every later merge), a narrow recheck, or your written acceptance.

**Gates computed from the repo, backed by a hook.** Two actions are gated: `merge` into `main`, and `buy`, an order for parts or a drawing release ([ADR 0011](docs/adr/0011-actions-are-gated-not-stages.md)). The gate recomputes its evidence from git each time it's asked, and never stores a pass. A plugin hook denies a merge or push the gate would refuse, and asks you before anything is recorded as your confirmation.

**CAD closes the loop.** `armature-cad` turns frozen parameters and chosen parts into part definitions and build recipes for SolidWorks, Fusion 360 or Onshape. Optional build123d recipes check each part's mass and inertia against what the dynamics assumed and sweep for interference, and the SolidWorks MCP server measures the live model. Measured mass properties go back into the ledger as `cad` entries, and the model reruns on them.

**The plugin is measured, not trusted.** The engine is tested against six golden mechanisms with independently known answers: a 2R arm, a four-cable platform, a five-bar wheel leg, a balanced parallelogram arm, a mass on a spring and a cable, and a hold-out. Each one has a planted trap, the plausible wrong answer it exists to catch, and a verb matrix holds every engine verb to a known answer on every mechanism. The agent itself is measured by `claude plugin eval` on the same mechanisms ([ADR 0008](docs/adr/0008-the-agent-is-measured-on-golden-mechanisms.md)). Some cases state the trap's bait outright, some only imply it, and one is a frozen hold-out nobody tunes against. A version bump is blocked unless every case is caught in at least 2 of 3 runs. See [`evals/README.md`](evals/README.md).

## Quick start

1. **Install.** You need [`gh`](https://cli.github.com/) on PATH with `gh auth login` done, and [uv](https://docs.astral.sh/uv/) for the engine.

   ```
   /plugin marketplace add rioharper/armature
   /plugin install armature@armature-plugins
   ```

2. **Start a project.** Run `/armature:init` in a blank folder. It scaffolds the project, offers to create the GitHub repo, records what your machine has installed, and starts the pitch interview.

3. **Chart a map with `armature-wayfind`.** Once the pitch is done, ask Claude to chart a map. You agree on a destination, usually "spec frozen". Wayfind then breaks the work into decision tickets on GitHub Issues: trade studies, architecture choices, mockups, and bench measurements.

4. **Work one ticket per session.** Say "work the map" and Claude picks the next open ticket. It calls the right skill or agent for that ticket (`armature-spec`, `armature-derive`, `armature-cad`, the librarian, the inventor, or the red team) and logs the decision. You don't have to pick which skill to use next. The map keeps track of that.

5. **Plan the build.** Once the spec is frozen, `armature-plan` turns it into phased GitHub issues, each leaf sized to one session, with shared frames, symbols and naming. From there, `armature-derive`, `armature-cad`, `armature-test` and `armature-bringup` handle the analysis, CAD, software and bench tasks as they come due.

For a small project that fits in a few sessions, you can skip the map and run the stages in order:

| Stage | You get |
|---|---|
| `armature-pitch` | Who it's for, why it beats what exists, and what success looks like |
| `armature-spec` | Engineering spec, trade studies, BOM, budgets and traceability, all read from the ledger, with actuator and bus feasibility run on a coarse model |
| `armature-plan` | Phased plan as GitHub issues, the machine split, and the project's frames, symbols and naming |
| `armature-derive` | Milestone notes (setup, kinematics, dynamics, verification) plus a re-runnable Python model checked against the MuJoCo truth model |
| `armature-cad` | Part definitions and build recipes for your CAD package, checked back against the dynamics |

Either way, work lands on a branch and reaches `main` through one of two gates, which the skills run for you:
- **`merge`**: a branch that changes a number, the model, a part, or spec or plan text needs an `armature-red-team` review of it, and every BLOCKER and MAJOR closed by a kept check, a recheck, or your acceptance. The model must also pass.
- **`buy`**: an order, whether parts bought or a drawing sent out, also needs every part it names confirmed by you and priced in the last 90 days, and a released drawing's model and recipe stamped green with no placeholder left.

A gate you disagree with is waived in writing, in `waivers.toml`, and the red team challenges every waiver in scope. The hook never touches your own terminal.

## Where to go

| Your situation | Use |
|---|---|
| New robot idea, blank folder | `/armature:init` |
| Not sure it's worth building, or who it's for | `armature-pitch` |
| Need a spec, trade study, or design review | `armature-spec` |
| Need phases and shared vocabulary | `armature-plan` |
| Adding a machine (sim host, render host, target board) | `armature-plan` on that machine |
| Need equations of motion, Jacobians, workspace, natural frequencies, or actuator sizing | `armature-derive` |
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

The three agents run in their own contexts. The **red team** reviews adversarially and runs on your session's model, because a missed finding costs CAD hours and purchases. The **librarian** finds datasheets and vendor CAD models, verifies the exact part number, caches them with provenance, and stages their numbers as ledger entries. The **inventor** searches recent papers and builds for unconventional mechanisms, actuators, materials and sensing, filtered against your project's physics.

## Example output

From the Ibex rover, a squatting camera platform built with Armature. Each card comes from the `armature-derive` Python model:

| | |
|---|---|
| ![Hip gravity compensation: worst hold torque drops 9.4x with a gas strut](media/ibex-card-1-gravity.png) | ![Mirror-leg four-bar keeps the wheel under the hip across seven postures](media/ibex-card-2-fourbar.png) |

![Hip hold power over a 45-minute scan mission: 0.38 W vs 431 W uncompensated](media/ibex-card-3-power.png)

## The engine

The engine is the Python package in [`engine/`](engine/), imported as `armature` and pinned to MuJoCo 3.15. A project pins it by the plugin's release tag rather than copying it, so a fix reaches every project as a version bump ([ADR 0004](docs/adr/0004-model-machinery-is-a-pinned-package.md), [ADR 0009](docs/adr/0009-the-engine-reaches-projects-as-a-git-tag.md)).

| Module | What it does |
|---|---|
| `elements`, `description`, `compiler` | The mechanism description and its compiler to MuJoCo: closed loops, couples, cables, contacts, springs, a floating base |
| `state` | Truth-model queries at a state: site poses, Jacobians, inverse dynamics, body wrenches, settling under load, releasing a reduction, linearisation |
| `contact` | Wheels and feet: which contacts touch, the force each carries, and its friction-cone margin |
| `variants`, `symbolic`, `equations` | Named reductions, the SymPy view of a variant, and its equations of motion by Kane's method |
| `sampler`, `search` | Seeded sampling of valid configurations, and the worst-case search every margin runs on |
| `drive` | Motors, gearboxes, drivers, thermal models, missions, events, the DC bus, and the drive margins |
| `ledger` | Load, check, show, render and set the project's ledger, with units checked by pint |
| `gate` | The `merge` and `buy` gates, run stamps, and the hook's decision |
| `review` | The Milestone 0 review artifact: a frames table and skeleton renders for the red team to check against the sketch |

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
      drive.py               motors, drivers, gearboxes and the bus, sized from missions
  cad/
    parts/                   part definitions and optional build recipes
    assemblies/              assembly definitions
    ots-parts/               vendor CAD models and index
  .mcp.json                  SolidWorks projects only (gitignored)
```

## Install details

`armature-derive`'s model runs in its own environment through [uv](https://docs.astral.sh/uv/), so uv must be on PATH. A project pins the engine by the git tag of the plugin release it runs and commits `uv.lock`, so the model's first `uv sync` needs access to GitHub as well as PyPI. Later syncs work offline from uv's cache.

The gates and the hook run the plugin's own copy of the engine, also through uv, in an environment Claude Code keeps in the plugin's data folder. The first gated call builds it from PyPI, in 15–30 s; after that a merge is checked in about 6 s. Without uv the hook refuses only what it gates, and says to install uv. It acts only in a project whose root holds `ledger.toml`.

Armature keeps the plan on GitHub Issues, so it needs `gh`, `gh auth login`, and a GitHub remote ([ADR 0002](docs/adr/0002-github-is-a-hard-prerequisite.md)). `/armature:init` checks all three and offers to create the repo (private by default). There is no non-GitHub option. To run from a local copy instead of the marketplace, point `--plugin-dir` at this repo.

## Design records

Every structural decision is recorded in [`docs/adr/`](docs/adr/), and the plugin's own vocabulary in [`CONTEXT.md`](CONTEXT.md). [`CHANGELOG.md`](CHANGELOG.md) holds the release notes, with the measurements behind each change.

## Credits

`armature-wayfind`, `armature-test`, `armature-debug`, `armature-bringup`, the questionnaire template, and the interview, glossary, and writing conventions across the skills adapt material from [Matt Pocock's skills](https://github.com/mattpocock/skills), used under the MIT License. See [`NOTICE.md`](NOTICE.md) for the full notice.
