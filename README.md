# Armature — robotics engineering skill suite

Snapshot taken 2026-07-30 from the installed skill set. Eight skills, 23 files.

## The pipeline

Five skills form the main path, each handing off to the next:

| Stage | Skill | Produces |
|---|---|---|
| 1 | `robotics-concept-design` | Concept brief — who it's for, why it beats what exists. Interrogates *why*, not *how*. |
| 2 | `robotics-spec-design` | Engineering spec, trade studies, design-driver BOM. Assumes the concept question is settled. |
| 3 | `robotics-writing-plans` | Phased implementation plan plus shared vocabulary (frames, symbols, naming) that keeps later sessions grounded. |
| 4 | `robotics-mathematician` | Milestone-sized derivation notes and a re-runnable parameterized Python model, cross-verified in SymPy/SciPy. |
| 5 | `robotics-cad-parts` | Per-part definitions — interfaces, loads, material, datums, tolerances, inertia targets — plus a build recipe for the chosen CAD package. |

Three are cross-cutting, pulled in at any stage:

| Skill | Role |
|---|---|
| `robotics-red-team` | Adversarial review of an existing artifact. Finds gaps and routes fixes; never authors the spec itself. Run before locking CAD or spending money. |
| `robotics-teacher` | Explains a concept, equation, or design decision. Analogy first, then formalism. |
| `robotics-inventor` | Researches papers, novel mechanisms, unusual actuators/materials, emerging products when the obvious solution isn't good enough. |

## Contents

```
skills/
  robotics-concept-design/     SKILL.md + concept-brief-template.md
  robotics-spec-design/        SKILL.md + spec-template, bom-template, design-foundations
  robotics-writing-plans/      SKILL.md
  robotics-mathematician/      SKILL.md + derivation-standards
                               scripts/model_template/ — params, kinematics,
                               dynamics, verification, run_all
  robotics-cad-parts/          SKILL.md + documentation-standards
                               references/solidworks.md, fusion360.md, onshape.md
                               (SKILL.md routes to one via references/<package>.md)
  robotics-red-team/           SKILL.md + review-checklist.md
  robotics-teacher/            SKILL.md
  robotics-inventor/           SKILL.md
```

Every `references/` and `scripts/` path named inside a SKILL.md resolves to a file
present in this archive — verified at snapshot time.

## Install

**As a plugin.** Keep the layout as-is; the `.claude-plugin/plugin.json` at the root
makes the directory loadable as a plugin.

**As loose skills.** Copy the eight directories out of `skills/` straight into
`~/.claude/skills/` (or `%USERPROFILE%\.claude\skills\` on Windows). Each skill
directory is self-contained.

## Two caveats

**`plugin.json` is reconstructed, not recovered.** Installed skills carry only `name`
and `description` in frontmatter — no version, no author, no plugin manifest. The
manifest here was written fresh for this archive with `version: 0.0.0`. Replace it with
the real one from the git repo rather than trusting this copy.

**This is the installed state, which may lag the repo.** `MANIFEST.md5` holds checksums
for all 23 files so you can diff this snapshot against the working tree and see whether
anything drifted.
