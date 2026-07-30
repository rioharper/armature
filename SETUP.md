# Setup

Three things, in the order you'll want them: get the plugin loading, start a project with it, and bring an existing project across.

## The two-repo rule

The most common early confusion. **Armature is one repo; each robot is its own repo.** They never mix.

| | Repo | Lives at |
|---|---|---|
| The suite | `armature` | `~/.claude/skills/armature`, published to GitHub |
| A project | `ibex`, `cinewave`, … | wherever you keep code; its own GitHub repo |

The suite is a tool you install once and update occasionally. A project is where the engineering happens. If you ever find yourself committing a robot's spec into the Armature repo, something has gone sideways.

---

## 1. Install the plugin

```bash
git clone <your-armature-repo> ~/.claude/skills/armature
claude plugin validate ~/.claude/skills/armature
```

Restart Claude Code — a skills directory that didn't exist when the session started needs a restart to be watched. After that, editing a `SKILL.md` takes effect immediately; changes under `agents/` need `/reload-plugins`.

Confirm it loaded:

```bash
claude --debug   # look for armature@skills-dir and the eight skills
```

Skills fire on their descriptions, so you shouldn't need to invoke them by name — "help me spec out a two-wheeled camera robot" should reach `armature-spec-design` on its own. You *can* call one explicitly as `/armature:armature-spec-design` if it isn't triggering.

If nothing appears, the cause is almost always directory placement: component folders (`skills/`, `agents/`) belong at the plugin root, not inside `.claude-plugin/`. Only `plugin.json` goes in there.

---

## 2. Start a new project

Make an empty directory, start Claude Code in it, and describe the idea:

```bash
mkdir ~/projects/newbot && cd ~/projects/newbot
claude
```

> I want to build a <one-line description>. Help me figure out whether it's worth building.

`armature-concept-design` should pick that up, grill you about audience and differentiation, then scaffold the repo — `git init`, the directory tree, LFS, the Obsidian config, and the first commit. You don't create any of that by hand.

**Install Git LFS first** if you haven't on this machine (`git lfs install`, once per machine). The scaffolding step tracks CAD binaries with it, and retrofitting LFS later means rewriting history.

From there the pipeline runs itself: concept → spec → plan → derivations → CAD parts, with red-team subagent reviews at the boundaries. Each skill hands off by committing, so you can stop anywhere and pick up in a fresh session — the repo is the state.

To read the docs with equations rendered, open the project folder as an Obsidian vault (**Open folder as vault**, pointed at the repo root, not `docs/`). The config is already committed.

---

## 3. Put the suite on GitHub

You already publish Armature, so this is a new major version of an existing repo rather than a fresh one. Do it on a branch — the layout change is not backward compatible, and anyone using the old `robotics-` skills shouldn't have them yanked out from under them.

```bash
cd ~/.claude/skills/armature
git checkout -b v2-claude-code
# replace contents with the new tree, then:
git add -A
git commit -m "v2: rewrite for Claude Code — plugin layout, subagent review, checked numbers"
git push -u origin v2-claude-code
```

Before merging, edit `.claude-plugin/plugin.json`: `repository` currently says `REPLACE-ME`, and confirm `author`. Then tag the release so installs can pin to it:

```bash
git tag -a v2.0.0 -m "Claude Code edition"
git push origin v2.0.0
```

Keep the old version reachable — tag the pre-rewrite commit `v1.0.0` before you merge, and say in the README that v1 targets claude.ai projects and v2 targets Claude Code. That's the whole migration story for anyone else who found the repo.

If you want others to install it with `/plugin marketplace add <you>/armature`, that needs a `.claude-plugin/marketplace.json` alongside the manifest. I haven't included one — the schema has a few source variants (github, url, git-subdir, with optional commit pinning) and I'd rather you generate it with `claude plugin init` or copy from the current plugins reference than have me guess at fields. Cloning into `~/.claude/skills/` works without it.

---

## 4. Migrate ibex

The temptation is to convert everything by hand from a checklist. Don't — **let the checker write the checklist.** Scaffold, drop the existing files in roughly the right places, run `consistency.py`, and fix findings until it's clean. Its findings *are* the migration to-do list, and it won't miss anything the way a manual pass will.

The one rule: **your 59 passing self-tests are the thing you must not break.** Keep them runnable at every step.

### Set up alongside, not in place

```bash
mkdir ~/projects/ibex && cd ~/projects/ibex && git init && git lfs install
```

Leave the claude.ai project folder exactly where it is until the new repo is green. This is a migration, not a move.

### Order of operations

**a. Scaffold.** Start Claude Code in the empty repo and ask it to scaffold an Armature project for ibex from the existing files. Copy `templates/project/` in for `.gitattributes`, `.gitignore`, and `.obsidian/`.

**b. `CLAUDE.md` first, before anything else moves.** Your existing derivation already has frames, a symbol table, and conventions somewhere — probably in the front matter of `ibex_derivation.md` or the handoff document. Lift them into `CLAUDE.md` verbatim. Do not improve them during the migration. Every later step reads this file, and a symbol you renamed while moving it is a bug that surfaces three steps later looking like a physics error.

**c. Drop the model in whole, and get the tests running.** Copy `ibex_model.py` to `analysis/ibex_model/` as-is and run it. All 59 self-tests pass before you touch anything. Commit that.

**d. Split the model one module at a time, tests green after each.** `params.py` → `kinematics.py` → `dynamics.py` → `verification.py`, moving the relevant self-tests into `analysis/tests/` as you go. The pytest scaffolding in `armature-mathematician/scripts/model_template/tests/` expects specific function names (`geometric_jacobian_num`, `mass_matrix_num`, `nonlinear_terms_num`, `total_energy`, `inverse_kinematics`, `worst_case_static_torque`) — this split is the natural moment to adopt them, which is why I wrote the tests against that interface rather than guessing at yours. Never move two modules on one red suite.

**e. Split the derivation.** `ibex_derivation.md` → `00_setup.md` / `01_kinematics.md` / `02_dynamics.md` / `03_results.md`. Split at the seams that already exist in the document; don't rewrite prose. Add frontmatter to each. Your numbered assumptions go in `00_setup.md`, and the frozen values — nominal hip angle 45°, spring rate 4.5 kN/m — belong in the parameter table there and in `params.py`, matching exactly.

**f. Build `bom.yaml`.** This is the only genuinely new artifact, and the one that pays off most. For every actuator, gearbox, bearing, and material: the design-driving numbers, the datasheet, and a `params_key` for anything the model also consumes. Download the datasheets to `refs/datasheets/` with a `manifest.yaml` — a link isn't provenance. Anything you can't source gets `status: tbd`, not a plausible number.

**g. Tag the freeze.** Once the model is green and the BOM matches it: `git tag freeze/ibex-m3` (or whichever milestone the re-freeze actually landed on).

**h. Run the checker.**

```bash
A=~/.claude/skills/armature/skills
python "$A/armature-red-team/scripts/consistency.py" --repo .
```

Expect findings on the first run — that's it working. Given the derivation was re-frozen after the `ibex_model.py` alignment, I'd specifically watch for parameter drift between `bom.yaml` and `params.py`, and for symbols in the model that never made it into `CLAUDE.md`.

**i. Then a real review.** Launch `armature-red-team` as a subagent on the whole migrated repo. It has fresh eyes on work you've been living inside for weeks, which is exactly when that's worth the most.

### What you're allowed to skip

`cad/` and `docs/parts/` stay empty until you're doing detail design — the scaffolding creates the directories so nobody has to decide twice where STEP files go, but empty is a valid state. Same for `docs/explorations/`.

### Don't do this during the migration

Fixing the design. If step (h) surfaces something real — a torque that doesn't close, an actuator that's marginal — write it down in `.armature/state.md` under Open and keep migrating. Mixing a structural move with an engineering change means that when the tests go red you won't know which one did it.

---

## Everyday commands

```bash
A=~/.claude/skills/armature/skills

cd analysis && pytest && cd ..                                    # model green or red
python "$A/armature-red-team/scripts/consistency.py" --repo .      # cross-document drift
python "$A/armature-cad-parts/scripts/check_inertia.py" --repo .   # realized vs assumed
python "$A/armature-cad-parts/scripts/check_inertia.py" --self-test
```

Worth putting the first three in a `Makefile` or a `check` script in each project once you've run them a few times by hand.
