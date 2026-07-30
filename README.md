# Armature — Claude Code edition

A suite of skills for robotics engineering: concept, spec, plan, derivations, CAD part definitions, adversarial review, frontier research, and teaching. This is the rewrite for Claude Code and a local repo, replacing the version built for a claude.ai project folder.

## Install

Armature ships as a Claude Code **plugin**, because it bundles a subagent and shared references alongside the skills — things a bare skill folder can't carry.

Clone it into your skills directory and it loads on the next session with no marketplace and no install step:

```bash
git clone https://github.com/<you>/armature.git ~/.claude/skills/armature
claude plugin validate ~/.claude/skills/armature
```

Layout — component folders at the plugin root, only `plugin.json` inside `.claude-plugin/`:

```
~/.claude/skills/armature/
  .claude-plugin/plugin.json
  agents/armature-red-team.md      the review subagent
  skills/
    armature-concept-design/  …  armature-teacher/
    references/                   conventions.md, obsidian.md
    templates/project/            scaffolding copied into new projects
```

`skills/references/` and `skills/templates/` hold no `SKILL.md`, so the scanner skips them — they exist as siblings because each skill reaches them by `../references/`, which is what keeps the shared contract in one place.

Skills invoke their scripts through `${CLAUDE_PLUGIN_ROOT}`. At runtime the working directory is your *project*, not the skill folder, so a relative `scripts/...` path would not resolve.

Editing a `SKILL.md` takes effect in the current session. Changes to `agents/` need `/reload-plugins`.

Per-project, the suite expects a git repo laid out as in `references/conventions.md`, with Git LFS available. **armature-concept-design** scaffolds it on first run, copying `templates/project/` in for the `.gitattributes`, `.gitignore`, Obsidian config, and vault home note.

See `SETUP.md` for first-project, GitHub, and migration walkthroughs.

## What changed from the chat version

**The commit is the handoff.** Every skill used to end by emitting a fenced block for the user to paste into a fresh chat — roughly forty lines each, plus the same five bullets about naming real files and writing in the user's voice repeated six times over. That entire apparatus existed to work around a chat that opens blind. Work now moves through the repo, and the commit message carries what the diff doesn't: decisions made, numbers frozen, questions still open. Removing it cut about 2,300 words of duplication from the five rewritten skills while adding capability.

**Fresh eyes are structural, not procedural.** `armature-red-team` was correct that review needs uncontaminated context and stuck with "tell the user to open a new chat" as the only mechanism — which made the mathematician's three checkpoints three manual handoffs, and therefore the most skippable thing in the suite. It now runs as a subagent with its own context. Read-only is enforced rather than promised: the reviewer writes one file under `reviews/`, so `git status` afterwards is the audit.

**Numbers are checked, not trusted.** `docs/bom.yaml` replaces the markdown BOM table, and every entry that also feeds the model names its `params.py` key. `armature-red-team/scripts/consistency.py` compares them, plus requirement traceability, datasheet provenance, symbol discipline, and whether anything changed since the last freeze tag without a new one. Same check lives in the model's own test suite, so drift turns the tests red the moment it happens instead of waiting for a review.

**Freezes are tags.** `freeze/<project>-m1` makes "the frozen parameters" a checkable object. When a freeze breaks, the diff against the tag is the finding.

**Green or red.** Ad-hoc self-test functions become a pytest suite with milestone markers. A milestone closes when its tests pass, not when the derivation reads well.

**`CLAUDE.md` is the glossary.** Frames, symbol table, part numbering, units. `armature-writing-plans` authors it; Claude Code loads it every session; every other skill inherits it without being told to read it. Status and open questions stay out of it — those live in `.armature/state.md`, read on demand, so the always-loaded file doesn't go stale.

**Geometry has a home.** `cad/` now has a defined layout — natives, assemblies, drawings, read-only COTS, exports split by format, mass-properties JSON, and separate visual/collision meshes for simulation. Binaries are LFS-tracked from the first commit, since retrofitting means rewriting history. Native files keep stable names because assemblies reference them by path; exports carry the rev because they leave the repo for a shop that has no git history to consult. Layout, LFS rules, and the mass-properties schema are in `armature-cad-parts/references/cad-repo-layout.md`.

**The inertia loop is automated.** `check_inertia.py` compares realized CAD mass properties against what the dynamics assumed, and — the part that matters — reconciles the reference point and frame itself: parallel axis when CAD reports about the COM and the derivation used the joint origin, a supplied rotation when the axes differ. That mismatch is why a correct derivation and a correct model appear to disagree, and it's not something a human comparing two tables of six numbers reliably catches. Run `--self-test` to verify the transforms against closed-form results before trusting them.

**The repo is an Obsidian vault.** Every document opens with YAML frontmatter, links are standard relative markdown (so they resolve in Obsidian *and* on GitHub), and the derivation notes render their LaTeX as typeset equations — which needed no format change, since `derivation-standards.md` already mandated `$$`. Vault config, frontmatter fields per document type, and which plugins earn their dependency are in `references/obsidian.md`. Nothing in the suite requires Obsidian; it's a reading layer, and `.armature/state.md` stays readable without it.

## Status

All eight skills rewritten: `concept-design`, `spec-design`, `writing-plans`, `mathematician`, `cad-parts`, `red-team`, `inventor`, `teacher`. Together they went from 12,263 words to 9,994 while gaining two verified scripts, the CAD layout, and the vault layer.

`inventor` and `teacher` were the light passes, as expected — neither carried a handoff block to delete. `inventor` gained real retrieval (papers land in `refs/papers/` with a manifest, same provenance rule as datasheets) and, more usefully, persistence: a parked idea committed to `docs/explorations/` with a revisit trigger is a decision you can revisit from evidence, where before it died with the chat. `teacher` gained project reading and live computation, and one instruction it never needed in a chat — it ships no artifact, which runs against an agent's bias toward using a filesystem it has.

Still open beyond the suite: the four build-side skills — electrical, firmware/controls, simulation, bring-up — that the plan schedules and nothing owns. The simulation one has a clear seam now: `export.py` emits URDF/USD from `params.py`, and `cad/sim/` holds the visual and collision meshes.

## Caveat on the test scaffolding

`scripts/model_template/tests/` defines the module API it expects: `kinematics.forward_kinematics_num`, `geometric_jacobian_num`, `dynamics.mass_matrix_num`, `nonlinear_terms_num`, `total_energy`, `verification.inverse_kinematics`, `worst_case_static_torque`, and `params.TAU_LIMITS`. The existing template modules expose self-test functions rather than these, so they need a small adaptation pass — the tests are written against the interface the modules *should* have, since the old in-module `test_*` functions can't be collected by pytest or run per-milestone. Worth doing on the next ibex derivation rather than as a blind refactor now.

Reference files not rewritten are carried over unchanged: `design-foundations.md`, `spec-template.md`, `derivation-standards.md`, `review-checklist.md`, `concept-brief-template.md`, and the CAD software references. Two of those want edits eventually — `derivation-standards.md` describes the pre-pytest file layout, and `review-checklist.md` could gain a section on what the consistency checker covers so the human reviewer stops duplicating it — but neither is safe to rewrite without reading them properly first.
