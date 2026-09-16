# The interview — design tree, frontier, rounds

**armature-pitch**, **armature-spec** and **armature-plan** each open with an interview
run by these rules. Skills point here; they don't restate it.

## The design tree and the frontier

Map the subject as a **design tree**: every decision branches into the decisions that hang
off it. The **frontier** is every question whose prerequisites are already settled; a
question hanging on an answer still open belongs to a later round. Settled answers unblock
the questions that hung on them, so the frontier is recomputed after every round.

## Rounds

Each round, ask the frontier through the AskUserQuestion tool, your recommended answer as
the first option labeled "(Recommended)", so a single word can accept it. The tool takes
four questions per call, so a larger frontier spans consecutive calls within the round.
Between rounds, reflect back what you've learned in a sentence or two so the user can
correct you, then recompute the frontier.

**Facts are your job; decisions are the user's.** When a frontier question turns on a
lookupable fact, dispatch the **armature-librarian** agent and keep asking the rest of the
frontier while it runs; only the questions downstream of that fact wait for it. Several at
once go in waves (`subagent-dispatch.md`, beside this file).

## Checkpoint each round

After reflecting a round back, write the artifact as it stands to its draft path, opening
with a `> Draft — open questions: …` line carrying the live frontier. If that Draft line is
already in the file on invocation, resume from it: settled content stands, and its open
questions seed the frontier.

| Skill | Draft path |
|---|---|
| armature-pitch | `docs/00-concept/concept-brief.md` |
| armature-spec | `docs/01-spec/spec.md` |
| armature-plan | `docs/02-plan/draft.md` |

The interview is done when the frontier is empty: nothing useful left to ask.
