# Dispatching subagents — waves, not fan-out

Every dispatch site in the plugin runs under this rule: **armature-spec**'s inventors and
librarians, **armature-derive**'s Step 0 lookups, **armature-plan**'s frontier lookups,
**armature-wayfind**'s research tickets, **armature-cad**'s part lookups, and any
**armature-red-team** pass. Skills point here; they don't restate it.

## The wave

Send **two or three at a time**, and let a wave land before the next one goes out.

Each subagent spends the dispatching session's budget — its own context window, its tool
calls, and a share of the account's session limit — and spends it whether it succeeds or
dies. Five at once is not five times faster; it is five times the burn, and a run killed
mid-hunt takes its findings with it. In the armature demo, five librarians went out
together: four hit the platform's 600 s stall watchdog, and two re-dispatches then hit the
session limit.

**Name the cost before the wave.** A wave is the user's spend, so say how many agents are
going and that fan-out burns the session budget fast, then dispatch on their word. One
lookup mid-interview needs no such ceremony; it is the wave that does.

## Agent tier

Which model an agent runs on is its **tier**, pinned in `agents/*.md` frontmatter so it
holds whatever the main session is running — otherwise every subagent inherits the
session's model, and a fleet of librarians hunting part numbers burns the budget of the
model you chose for the hard thinking.

| Agent | Tier | Why |
|---|---|---|
| `armature-librarian` | `sonnet` | search, verify the P/N, transcribe the numbers; what guards a mistranscription is the cached document and the index row that cites it, not a bigger model |
| `armature-inventor` | `sonnet` | reads widely and writes a brief that the red-team and the user both review before anything is built on it |
| `armature-red-team` | `inherit` | a missed finding costs CAD hours and purchases, so it runs on whatever you deliberately chose |

A pin is a **default, not a guarantee**: a model named at dispatch wins over frontmatter,
and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` in the environment overrides every pin here.

**Override upward, never down, and say why in the dispatch.** The inventor goes up for a
design tension where the constraint numbers have ruled out the obvious idea families and
the brief has to find a non-obvious one — a trade study with no surviving candidate, not
merely a hard one. The librarian stays where it is: a lookup that feels too hard for it is
a lookup scoped too wide, and the fix is a narrower run, not a bigger model.

## Size each run to survive

- **One part, or one slice of a field, per run.** A prompt carrying five parts makes a run
  long enough to hit the stall watchdog, and the whole run dies together.
- **Prefer the agent that writes as it goes.** The librarian opens its run file before its
  first fetch and appends every row, entry and cached file the moment it exists (`Open the run file`
  in `agents/librarian.md`), so a killed run still leaves what it found. The inventor and
  the red-team write once at the end: a dead run leaves nothing, so keep an inventor's idea
  family narrow and re-run rather than resume it.
- **Read the wreckage before re-hunting.** A file left in `docs/datasheets/staging/` is an
  unmerged run: read it, merge what stands, and re-dispatch only the gaps.

## Splitting a red-team review

A red-team pass reads whole artifacts, so a large set — every milestone note with its
modules, or a spec with its BOM, budgets and traceability — puts one run near its context
ceiling, where it starts summarising instead of checking. **Split when a single pass would
read more than roughly 40k tokens of source, or more than three substantial artifacts.**
Below that, one pass is cheaper than the overhead of splitting.

**Split by input partition, not by checklist family.** Families 1, 2, 3 and 7 of the
review checklist each need the whole document set, so a family split runs the same big
read seven times and saves nothing. Cut into disjoint file sets instead, each carrying the
question it was cut to answer, so no pass holds files its question does not need —
**armature-derive**'s Milestone 3 checkpoint is the worked example. The saving is real
only if the partitions are genuinely disjoint: overlapping sets re-read the same files and
cost more in total than one run would have.

**Run the passes sequentially, and don't chain them.** Sequential because concurrency is
what burns the session budget and trips the stall watchdog. Not chained because feeding
one pass's findings into the next re-inflates the context the split just cut, and biases
the second pass toward confirming the first. Each pass writes its own staging file under
`docs/reviews/staging/`.

**Close with the merge pass**, the one chained step, which reads findings rather than
sources: it takes the staging files, adds what only a whole-set view can see, drops the
duplicates several passes raised, writes the single report, and deletes what it merged.
**Routing stays here** — the report names each fix's owner, and only the dispatching
conversation can act on them.

A wave is done when every part of it is merged, re-dispatched, or carried back to the user
as an open question — never when the agents simply stopped returning.
