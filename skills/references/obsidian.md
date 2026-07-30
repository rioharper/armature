# Obsidian as the reading layer

The project repo doubles as an Obsidian vault. Claude Code writes the markdown; Obsidian is where a human reads it, follows links between documents, and sees the equations rendered instead of as raw LaTeX.

This is a reading and navigation layer, not a second source of truth. Obsidian never becomes the place a number lives — `docs/bom.yaml` and `params.py` keep that job, because scripts can check them and a rendered note can't.

## The vault is the repo root

Open the project folder itself as the vault, not `docs/`. Derivation notes live in `analysis/<project>_derivation/`, findings in `reviews/`, part definitions in `docs/parts/` — a vault scoped to `docs/` would cut the graph in half and make a finding unable to link to the equation it disputes.

## What you get for free

Three things already work with the markdown the suite writes, no configuration needed:

**Equations render.** `derivation-standards.md` already mandates LaTeX in markdown — `$...$` inline and `$$...$$` displayed — so Obsidian's MathJax renders M(q)q̈ + C(q,q̇)q̇ + g(q) = τ as typeset math. This is the single biggest reason to bother: a derivation note read as rendered equations is a document you can actually check, and the same file stays plain text for git and for Claude Code.

Keep manual equation numbering — `(1)`, `(2)` in the prose, as the standards require. MathJax's `\tag{}` renders in Obsidian but not on GitHub, and manual numbers survive both.

**Mermaid renders.** Kinematic chains, frame trees, and state machines can go inline in a note as a ```mermaid block. Useful in `00_setup.md` for the frame tree, which is otherwise the hardest thing in the whole derivation to hold in your head from prose.

**Callouts render.** `> [!warning]` and friends. Worth adopting in two places: numbered assumptions in `00_setup.md` (an assumption that looks like a warning gets re-read when it starts carrying weight), and blockers in a findings report.

## Links: markdown, not wikilinks

Use standard markdown links with relative paths — `[the spec](../../docs/spec.md)` — not `[[wikilinks]]`.

Obsidian resolves both and builds its graph from both. GitHub only resolves the first. Since project repos get published and the suite itself lives on GitHub, the format that works in both wins; there is no capability you give up by choosing it. Set **Settings → Files & Links → New link format: Relative path to file** and turn off **Use [[Wikilinks]]** so Obsidian's own link insertion matches.

Link deliberately rather than exhaustively. The links worth having are the ones that answer "where did this number come from": a part definition to the derivation result its loads came from, a finding to the equation it disputes, `03_results.md` to the REQ it collides with. The graph view is then a provenance map, which is genuinely useful. A graph where everything links to everything is decoration.

## Frontmatter

Every markdown document the suite writes opens with YAML frontmatter. Obsidian reads it as properties and can filter and query on it; git sees plain text; the consistency checker ignores it.

```yaml
---
type: spec              # concept-brief | spec | plan | derivation | part-definition | review | exploration
project: ibex
rev: 0.3
status: accepted        # draft | accepted | superseded
frozen_at: freeze/ibex-bom
tags: [armature/spec, ibex]
---
```

Per-type additions: derivation notes carry `milestone: 1`; part definitions carry `part_id`, `material`, `cad_package`, `loads_from`; reviews carry `reviewed_sha`, `verdict`, and `findings: [F1, F2]`; explorations carry `verdict: pursue | prototype-first | park`.

`status` and `rev` in frontmatter are a convenience for reading and filtering. Git remains the authority on what changed when — frontmatter that disagrees with `git log` is stale frontmatter, not a second history.

## Configuration

Commit `.obsidian/app.json` and `core-plugins.json` so the link format, exclusions, and enabled plugins are shared rather than re-set per machine. Gitignore `workspace.json`, `workspace-mobile.json`, `appearance.json`, and `hotkeys.json` — pane layout, theme, font size, and key bindings are per-person, and committing them means a conflict on every pull over whose font is right.

Exclude from search and graph, via `userIgnoreFilters` in `app.json`: `analysis/**/*.py` (Obsidian can't render Python and it clutters search), `cad/`, `refs/datasheets/`, and `.git/`. The code and the geometry are Claude Code's domain; the vault is for the prose about them.

Set the attachment folder to `docs/attachments` so a pasted screenshot lands somewhere predictable instead of beside whatever note was focused.

## Optional plugins worth the dependency

**Dataview** turns the frontmatter into queries, which is where the properties start paying for themselves. An index note can list every open finding across every review, or every part definition still at `status: defined` rather than `modeled`:

````markdown
```dataview
TABLE verdict, findings, reviewed_sha
FROM "reviews"
WHERE type = "review"
SORT file.name DESC
```
````

Useful, but understand the tradeoff: a Dataview query renders as a code block on GitHub and in Claude Code. Keep them confined to `docs/index.md`, which exists for humans, and out of documents that carry engineering content.

**Excalidraw** for mechanism sketches during a spec interview. Its `.excalidraw.md` files are markdown-wrapped, so they commit cleanly — worth it if you sketch, skip it if you don't.

Nothing in the suite requires either plugin. `.armature/state.md` remains the authoritative answer to "where is this project," readable without Obsidian at all.
