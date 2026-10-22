---
name: init
description: Scaffold a standardized Armature robotics project in the current folder (docs/analysis/cad tree, git repo, project CLAUDE.md), then start the pitch interview.
disable-model-invocation: true
---

# Armature Init

The current folder is the project root.

## 1. Guard

If a `ledger.toml` sits here at the root, this is an Armature project: report where it stands, `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" bash "${CLAUDE_PLUGIN_ROOT}/scripts/armature.sh" gate status`, and stop. A `CLAUDE.md` here with no `ledger.toml` beside it is somebody else's file: ask through AskUserQuestion whether to merge the template into it or replace it, and carry that answer into step 4.

The stop carries two repairs. Where `.mcp.json` names a `mcp/solidworks/server.py` path that no longer exists — a plugin update moved it — offer to rewrite that path from the current `${CLAUDE_PLUGIN_ROOT}`; a project that has no `.mcp.json` wanted none. Where `analysis/model/` exists, run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/engine-source.sh" check analysis/model` and report its line, acting on it as armature-derive's checkpoint does. Report and repair is the whole of a re-run.

## 2. Probe the machine

Run the plugin's environment probe and keep its output for the next two steps:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/env-probe.sh"
```

It prints `KEY=VALUE` and exits 0 whatever it finds, because an absence here is
something to plan around rather than an error. `PYTHON` is the invocation that
works on this machine — `py` and `absent` are different answers, and reading
them as the same is what put a stale "python is not on PATH" note in a project
that had python all along. Step 4 writes the result to `docs/environment.md`;
its format and rules are `${CLAUDE_PLUGIN_ROOT}/references/environment-record.md`.

**`GH` is a gate, not a note.** Every other absence the probe reports is
something to plan around; this one stops the scaffold. An Armature project keeps
its plan and its wayfinder maps on GitHub Issues and has no other tracker, so
without `gh` there is nowhere for **armature-plan** to write. Where `GH` is
absent, or `gh auth status` exits non-zero, stop and say which of the two is
missing — install from <https://cli.github.com/>, or run `gh auth login` — and
that re-running init is the whole of the fix. Don't scaffold a project that
cannot be planned.

## 3. Setup interview

Ask through the AskUserQuestion tool:

1. Project name, a one-line description, and the goal behind the project —
   why its builder wants it, which the description does not carry.
2. CAD package: SOLIDWORKS / Fusion 360 / Onshape / undecided.
3. On SOLIDWORKS only: connect the SolidWorks MCP server to this project? It
   lets armature-cad's Done-when checks measure the live model instead of
   asking you to transcribe numbers. Two of its three prerequisites are
   already answered: state Windows and [uv](https://docs.astral.sh/uv/) on PATH
   from step 2's `OS_KIND` and `UV` instead of asking the user to vouch for
   them, and where either is missing, say so and recommend no — the server
   cannot start. The third — SolidWorks running while those checks run — is
   never true in advance, so it stays a question. Yes seeds
   `.mcp.json` in step 4, and Claude Code asks you to approve it on the next
   start. Every other answer leaves the project with no MCP server, which is
   why a Fusion, Onshape, or undecided project never sees one fail.
4. Builder profile: solo or team; fabrication access (printer, machining, hand
   tools); experience level; related work — the other repos or projects of
   theirs this one touches, or none.
5. GitHub repository: create one now (**private**, named for the project), or
   use a remote this folder already has. Say plainly what it is for — the plan,
   its phases and every leaf become issues, so the repo will carry the spec's
   numbers, the BOM and its costs. A public repo publishes all of that, which
   is why private is the recommendation and the default. Where `git remote -v`
   already names an `origin`, offer that instead of creating a second one.

Done when every placeholder in the template below has a value.

## 4. Scaffold

Create (bash):

```bash
mkdir -p docs/00-concept docs/01-spec docs/02-plan docs/testing \
         docs/reviews docs/research docs/datasheets docs/agents docs/orders \
         analysis/derivation analysis/model \
         cad/parts cad/assemblies cad/ots-parts
```

Seed these files:

- `docs/decisions.md`: header `# Decision log`, one column-format line
  `<!-- date · decision · why · supersedes -->`, and its first entry — the
  project init itself.
- `waivers.toml`, the gates' exemptions, which starts with none:

```toml
# Exemptions from an item of a gate's evidence (merge or buy), one [[waiver]]
# each: gate, item (its id as the gate prints it), scope (a branch, or
# "standing"), reason, and confirmed (the date the user confirmed it). Only
# the user confirms a waiver; one with no confirmed date is ignored.
```
- `ledger.toml`: one comment line, `# Every input number, once: mechanism, drive,
  req, budget.<kind> and part.<pn> entries.`, and no entry.
- `docs/datasheets/index.md`: header, the legend comment
  `<!-- A row holds no number: a part's numbers and prices are its part.<pn>
  entries in ledger.toml, each citing this row's P/N. Clauses read: the
  sections, tables, or pages actually verified, ending "price: quote only"
  where the vendor publishes no price. File: the cached PDF, HTML snapshot, or
  image + transcript; a source with no saveable document points at its survey
  record, docs/datasheets/<task>-<subject>-<slice>.md. -->`,
  and the empty table
  `| P/N | Manufacturer | Clauses read | Source URL | Retrieved | File |`.
- `docs/environment.md` from step 2's output, in the shape
  `references/environment-record.md` gives: one section for this machine,
  headed by hostname, OS, and today's date, closing with the gaps this project
  will actually feel — a missing `uv` blocks **armature-derive**, a
  missing CUDA makes a render host somebody else's machine. No gap left at this
  point stops the scaffold; the one that would have, `gh`, was settled in step 2.
- `docs/agents/issue-tracker.md`, copied verbatim from
  `${CLAUDE_PLUGIN_ROOT}/skills/armature-wayfind/references/issue-tracker-github.md`.
  That reference is the single source — copy it, never retype it, so a later
  diff shows drift instead of hiding it.
- `cad/ots-parts/index.md`: header + empty table
  `| File | P/N | Datasheet row | Source URL | Retrieved |`.
- `.mcp.json`, only where step 3 said yes to the server:
  `{"mcpServers": {"solidworks": {"command": "uv", "args": ["run",
  "<plugin root>/mcp/solidworks/server.py"]}}}`. Write `<plugin root>` as the
  absolute path `${CLAUDE_PLUGIN_ROOT}` holds — a *project* `.mcp.json` is
  read without that substitution, so the placeholder itself would load
  verbatim and fail.
- `.gitkeep` in every scaffolded directory the seeds above leave empty (git
  drops empty directories).
- `.gitignore`:

```
__pycache__/
.pytest_cache/
~$*
*.bak
# absolute path into this machine's plugin install
.mcp.json
# the gate's run_all stamps: a cache on this machine, keyed by content
.armature/
```

- `CLAUDE.md` from the template below, with the setup answers filled in.
  If step 1 chose merge, append the template's sections to the existing
  file, keeping its content above them.

Then `git init -b main` (if not already a repo), stage only the files this
scaffold created or changed, and commit as `Initialize Armature project
scaffold`. The gates merge into `main`: in a repo whose branch has another name,
ask before renaming it with `git branch -m main`. Done when `git ls-files` lists
every scaffolded directory.

## 4a. Bootstrap the tracker

The plan and every wayfinder map live here, so the repo and its labels exist
before any skill needs them.

**The remote.** Where step 3 asked for a new repo:
`gh repo create <name> --private --source=. --remote=origin --push`. Where it
named an existing remote, `git push -u origin main`. Confirm with `gh repo view`;
a failure here stops init the way a missing `gh` does, because everything below
writes to that repo.

**The labels.** Create all sixteen from the table in the tracker doc you just
copied, each with its colour and description:

```bash
gh label create "plan:leaf" --color BFD4F2 --description "Plan leaf (one session of known work)"
```

`gh label create` fails on a label that already exists, which is the right
behaviour on a re-run — pass `--force` only to repair a colour or description,
never to blank one. Done when `gh label list` shows all sixteen.

**Sub-issues and dependencies.** Check once that both are available on this
repo, since the plan's three-level shape and its blocking edges rest on them.
Where either is not, say so and note in `docs/environment.md` that the project
runs on the task-list and `Blocked by:` fallbacks the tracker doc describes —
it is a degradation, not a failure.

## 5. CLAUDE.md template

```markdown
# <Project Name>

<one-line description>

Where the project stands is computed, never written here: run
`bash "<plugin root>/scripts/armature.sh" gate status`, `<plugin root>` being
the Armature plugin's folder, the one every Armature skill's paths start from.

## Purpose

<why this project exists for its builder — the goal behind it, which the
one-line description above does not carry. One to three lines. A recurring
instruction it implies belongs in Standing rules, not here.>

## Glossary

The project glossary is `CONTEXT.md` at the repo root — frames, symbol
table, part numbering, CAD file naming, each term with an `_Avoid_:` line
naming the synonyms it displaces; armature-plan writes it. Challenge any
term, the user's or your own, that conflicts with `CONTEXT.md` the moment
it appears.

- Units: SI internally; imperial in parentheses when the shop works in it.
- Requirement numbering: RC-xxx = concept-level outcome
  (docs/00-concept/); REQ-xxx = verifiable engineering requirement with a
  verification method (docs/01-spec/).

## Standing rules

- Every input number lives once, as an entry in ledger.toml, and is cited
  from it, never from memory. A datasheet number is a part.<pn> entry, its
  row in docs/datasheets/index.md saying what was verified. An entry whose
  `status` is `candidate` carries no decision until the user confirms it.
- After a number changes, edit its ledger entry, the one place it is written,
  then run `py -m armature.ledger render`, then `py -m armature.ledger check`,
  and settle every error before anything reads the number.
- Two actions are gated: `merge`, a work branch into main, and `buy`, the
  merge of an order branch adding docs/orders/<date>-<name>.toml. Work that
  touches a ledger number, the model, the derivation, a part definition, spec
  or plan text, or an order lands on a branch, armature/<kind>-<name>, and
  merges only when its gate passes; the stage skills name the call, and the
  plugin's references/gates.md routes what fails. A commit on main only
  re-renders the ledger's sections or adds and edits candidate entries.
- A `confirmed` ledger entry, an `accepted` review finding and a waiver in
  waivers.toml are the user's decisions: write one only on the user's word.
- A plan leaf's Executor names the skill that works it: call the Skill tool
  with that name before starting the leaf.
- The plan and every wayfinder map are GitHub Issues, never a markdown file.
  Read docs/agents/issue-tracker.md before touching the tracker.
- A change to a mass, power draw, or cost is debited in the same session;
  docs/01-spec/budgets.md's header carries the debit and reserve rules.
- Every design decision gets a line in docs/decisions.md. One that is hard to
  reverse, surprising without context, and a real trade-off also gets a
  paragraph-long ADR in docs/adr/NNNN-slug.md, linked from that line.
- docs/environment.md records what each machine has installed. Read it before
  assuming a tool; refresh it with the plugin's scripts/env-probe.sh.
- Every artifact write ends in a git commit.

## Builder profile

- CAD package: <answer>
- Fabrication: <answer>
- Team: <answer>
- Experience: <answer>
- Related work: <repos or projects this one touches, and how each relates —
  or none>
```

## 6. Hand off

Report the scaffold commit, the repo URL and its visibility, and any gap
`docs/environment.md` names, then call the Skill tool with "armature-pitch"
and begin the interview in this session.
