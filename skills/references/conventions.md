# Armature conventions

The contract every skill in the suite shares. Read this once at the start of a session; the skills point here rather than restating it.

## The tree is the state

A robotics project lives in a git repo, and the repo is the project's memory. Nothing important survives only in a transcript — not a frozen parameter, not a review finding, not the reason an option was rejected. When a session ends, whatever wasn't written down is gone.

```
<project>/
  CLAUDE.md                 project glossary — frames, symbols, naming, units
  .gitattributes            LFS rules for CAD binaries
  .obsidian/                vault config — app.json, core-plugins.json committed
  .armature/state.md        where the project is right now
  docs/
    index.md                vault home for humans
    concept-brief.md        armature-concept-design
    spec.md                 armature-spec-design
    bom.yaml                armature-spec-design — structured, machine-read
    plan.md                 armature-writing-plans
    parts/<PART-ID>.md      armature-cad-parts
    explorations/           armature-inventor
    attachments/            pasted images
  analysis/
    <project>_derivation/   00_setup.md … 03_results.md
    <project>_model/        params.py, kinematics.py, dynamics.py, export.py
    tests/                  pytest suite over the model
    pyproject.toml
  cad/                      geometry — layout in armature-cad-parts/references
    parts/ assemblies/ drawings/ cots/
    exports/step/ stl/ dxf/ pdf/
    mass-properties/        JSON for the inertia loop
    sim/visual/ collision/  meshes for URDF/USD
  refs/
    datasheets/             retrieved PDFs + manifest.yaml
    papers/                 retrieved papers + manifest.yaml
  reviews/                  armature-red-team findings, dated
```

Two boundaries inside that tree are worth naming, because crossing them is how projects lose track of what's authoritative. `docs/` holds reasoning; `cad/` holds geometry — a part definition and the solid model it describes are different artifacts with different review needs. And `.armature/state.md` holds status; every other document holds content — when they disagree, the content wins.

## CLAUDE.md is law

The project glossary — coordinate frames, symbol table, part-numbering scheme, file naming, revision scheme, units policy (SI internally, always) — lives in `CLAUDE.md` at the repo root, where Claude Code loads it into every session automatically. `armature-writing-plans` authors it. Every other skill inherits it and reuses it verbatim rather than inventing competing conventions.

A skill that needs a frame or a symbol reads `CLAUDE.md`. A skill that wants to *change* one edits `CLAUDE.md` and says so in the commit — a symbol that means two things in two files is the drift this convention exists to prevent.

## The commit is the handoff

Work moves between skills through the repo, not through a pasted prompt. A skill finishes by committing, and the commit message is the handoff note: what changed, what was decided, what's still open.

```
<scope>: <what changed, imperative>

<why, and what the next skill needs to know that the diff doesn't show>

Freeze: <tag name>            (only when values were frozen)
Findings: F3, F5 resolved     (only when closing review findings)
Open: <what's still unresolved>
```

Scopes: `concept`, `spec`, `bom`, `plan`, `math`, `cad`, `review`, `explore`, `state`.

Commit at every completion criterion — a milestone crossed, a spec accepted, a part defined, a review filed. Small commits, one logical change each. A session that ends with uncommitted work has lost the handoff.

### Freezes are tags

When a set of numbers is frozen — the parameter block at a milestone boundary, the BOM at design lock, the derivation the CAD will be built against — tag it:

```
git tag freeze/<project>-<what>    e.g. freeze/ibex-m1, freeze/ibex-bom
```

Downstream skills reference the tag, so "the frozen parameters" is a checkable thing rather than a memory. When a freeze breaks, the diff against the tag is the finding.

## Green or red

Every claim the model makes is either verified by a passing test or it is unverified. `pytest` from `analysis/` is the arbiter:

- **Green** — the suite passes. A milestone may close, a freeze may be tagged, work may proceed.
- **Red** — something fails. That is a finding, not an inconvenience. Hunt it, fix the thing that's actually wrong, and record in the milestone's `.md` which of the derivation or the code was wrong.

Never tag a freeze or close a milestone while red. Never silence a test to get green — a skipped assertion is red wearing a disguise.

## Fresh eyes come from a subagent

Review is worth something only when it comes from someone who wasn't in the room for the reasoning that produced the work. In Claude Code that's a subagent with its own context: it reads the committed artifacts, knows nothing of the conversation that made them, and cannot inherit the rationalizations.

Launch `armature-red-team` as a subagent at every review point. It reads the repo, writes one findings file to `reviews/`, and touches nothing else. Because the review runs against committed state, `git status` afterwards is the audit — **the diff is the audit**: if the reviewer edited an artifact instead of reporting on it, the working tree shows it.

## .armature/state.md

One file, rewritten as the project moves, answering what a returning session needs and the other documents don't say:

```markdown
# <project> — state
Updated: <date> · HEAD: <short sha>

## Where we are
<phase or milestone, and what's actively being worked>

## Frozen
| What | Value | Tag |

## Open
| ID | What's unresolved | Owner skill |
<F-numbers from reviews, TBDs from the BOM, spec open questions>

## Decided
<decisions whose rationale isn't obvious from the artifact — one line each,
with the commit that carries them>
```

Skills read it first and update it on exit, in the same commit as the work. It is a summary, never a source: when it disagrees with an artifact, the artifact wins and the state file is stale.

## Every document opens with frontmatter

The repo is also an Obsidian vault, so a human can read the derivations with the equations rendered and follow links between documents. Every markdown file a skill writes opens with YAML frontmatter — `type`, `project`, `rev`, `status`, `tags`, plus per-type fields:

```yaml
---
type: spec
project: ibex
rev: 0.3
status: accepted
tags: [armature/spec, ibex]
---
```

Cross-document links use standard markdown with relative paths (`[the spec](../../docs/spec.md)`), never wikilinks — Obsidian resolves both, GitHub only the first. Full conventions, including what to commit from `.obsidian/` and which plugins earn their dependency, are in `obsidian.md`.

Frontmatter is a reading convenience. Git remains the authority on what changed when, and `docs/bom.yaml` and `params.py` remain the authority on numbers — a `rev` in frontmatter that disagrees with `git log` is stale frontmatter, not a second history.

## Binaries go in LFS

CAD natives, STEP, meshes, and PDFs are tracked with Git LFS from the first commit, per the `.gitattributes` template. Retrofitting LFS means rewriting history, so it is not a thing to defer until the repo is slow.

## Datasheets are files

A number that drives a decision traces to a datasheet in `refs/datasheets/`, recorded in `manifest.yaml`:

```yaml
- part: AK60-6
  vendor: CubeMars
  file: cubemars-ak60-6.pdf
  url: <where it came from>
  retrieved: 2026-07-28
  confirmed_by_user: true
```

A remembered spec is not a sourced spec. If a design-critical number can't be traced, it carries status `TBD` and appears in `.armature/state.md` under Open — never a plausible-looking value buried in arithmetic.
