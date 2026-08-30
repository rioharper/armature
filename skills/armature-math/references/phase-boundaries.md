# Phase boundaries

A phase ends when you think "ok, we're done with that" — a milestone branch merged, an interview finished, a review's findings resolved. The boundary between two phases is the only place to decide what happens to the session's context. Mid-phase there is no decision: continue, or split remaining work into subagents. Compacting mid-phase loses the thread.

## The five options, judged in order

Work top to bottom at the boundary; the first yes wins.

1. **Continue** — stay in the session. Yes when the next phase needs this one as a **primary source** (the reasoning verbatim, not a summary of it — derivation → the results note built on it is the standard case), or when enough context window remains for the next phase to fit (~150k tokens). Continue costs nothing and loses nothing, so rule it out before anything else.
2. **Clear** (`/clear`) — empty the window, start fresh. Yes when everything in the session — exploration, dead ends, decisions already committed to disk — is disposable. The cheapest move on the board, and the repo layout is built for it: files committed, tests green, branch merged means a fresh session resumes from disk alone. But it's one-way: clear a *relevant* context and the why behind the work is gone; reading the diff back won't return it.
3. **Hand off** — write a portable markdown summary (state, open questions, which skills the next agent should load, pointers to artifacts on disk — never their content restated) and seed a fresh session with it. Yes only when something must travel: a different harness, a different directory or repo, a colleague, or a side task forked without derailing this one. Nothing travelling means no handoff.
4. **Subagent** — send the task to its own context window and take a report back, leaving this session untouched. Yes when the task is scoped tightly enough to run unsteered — the red-team review is the standard case.
5. **Compact** (`/compact`) — compress this context and continue on the summary. The landing spot when the four above all said no: relevant context, same place, user still in the loop. Pass an instruction (`/compact we derive dynamics next`) so the summary keeps what the next phase needs. It sits last because every option above it is cheaper or more precise; starting here produces a session confidently wrong about a decision the summary flattened.

Every option except Continue trades the session as it happened for a summary of it — less noise, more room, lossy. That is why Continue is question 1: pay the lossiness only when staying costs more than it saves.
