---
name: init
description: Initialize a standardized Armature robotics project in the current folder — scaffold the docs/analysis/cad tree, git repo, and project CLAUDE.md, then start the concept interview.
disable-model-invocation: true
---

# Armature Init

Set up a robotics project the way the whole suite expects to find it, then
roll straight into the concept interview. Run in the project's root folder.

## 1. Guard

If `CLAUDE.md` already exists here with a `**Stage:**` line, this is already
an Armature project — say so, report its stage, and stop.

## 2. Setup interview (three questions, then build)

Ask, via the question tool if available:
1. Project name and a one-line description.
2. CAD package: SOLIDWORKS / Fusion 360 / Onshape / undecided.
3. Builder reality, briefly: solo or team; fabrication access (printer,
   machining, hand tools); rough experience level.

## 3. Scaffold

Create (git bash):

```bash
mkdir -p docs/00-concept docs/01-spec docs/02-plan docs/testing \
         docs/reviews docs/research docs/datasheets \
         analysis/derivation analysis/model \
         cad/parts cad/assemblies cad/ots-parts
```

Seed these files:

- `docs/decisions.md`: header `# Decision log` + one column-format line:
  `<!-- date · decision · why · supersedes -->`, plus its first entry — the
  project init itself.
- `docs/datasheets/index.md`: header + empty table
  `| P/N | Manufacturer | Key numbers | Source URL | Retrieved | File |`.
- `cad/ots-parts/index.md`: header + empty table
  `| File | P/N | Datasheet row | Source URL | Retrieved |`.
- `.gitkeep` in every scaffolded directory that gets no seeded file above
  (docs/00-concept, docs/01-spec, docs/02-plan, docs/testing, docs/reviews,
  docs/research, analysis/derivation, analysis/model, cad/parts,
  cad/assemblies) — git doesn't track empty directories, and the tree needs
  to survive the first commit.
- `.gitignore`:

```
__pycache__/
.pytest_cache/
~$*
*.bak
```

- `CLAUDE.md` from the template below, with the setup answers filled in.

Then `git init` (if not already a repo) and commit everything as
`Initialize Armature project scaffold`.

## 4. CLAUDE.md template

```markdown
# <Project Name>

<one-line description>

**Stage:** concept  <!-- concept → spec → plan → analysis → cad → build -->
**Latest artifacts:** none yet

## Glossary

<!-- Frames, symbol table, part numbering, CAD file naming, and definitions
of done are written here by armature-plan. Once set, they are law. -->

- Units: SI internally, always. Imperial in parentheses only if the shop
  works in it.
- Requirement numbering: RC-xxx = concept-level outcome
  (docs/00-concept/); REQ-xxx = verifiable engineering requirement with a
  verification method (docs/01-spec/).

## Standing rules

- Every datasheet number cited anywhere must trace to a row in
  docs/datasheets/index.md (the armature-librarian agent maintains it).
- Red-team review (armature-red-team agent) before CAD hours or purchases.
- Any change to a mass, power draw, or cost updates
  docs/01-spec/budgets.md in the same session.
- Every design decision gets a line in docs/decisions.md.
- OTS CAD models live in cad/ots-parts/ with an index row linking
  model → P/N → datasheet.
- Every artifact write ends in a git commit — the git log plus
  docs/decisions.md is the project history.

## Builder profile

- CAD package: <answer>
- Fabrication: <answer>
- Team: <answer>
```

## 5. Hand off

Tell the user the scaffold is committed, then invoke the **armature-concept**
skill and begin the interview immediately — that's the natural next breath,
not a separate ceremony.
