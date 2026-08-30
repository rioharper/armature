---
name: armature-wayfind
description: Chart an effort too big or foggy for one agent session as a shared map of decision tickets on the project's issue tracker, then resolve them one ticket per session until the way to the destination is clear. Use when an effort outgrows the session, or when the user asks to chart a map or work one of its tickets.
---

# Wayfinding

A loose idea has arrived, too big for one agent session, and wrapped in fog: the way from here to the **destination** isn't visible yet. Wayfinding charts the way as a **shared map** on the project's issue tracker, then works the map's **decision tickets** — questions whose resolution is a decision, not slices of a build — one at a time until the route is clear.

Naming the destination is the first act of charting: it fixes the scope and shapes every ticket. Typical robotics destinations: a spec frozen and ready for **armature-plan**, an actuation architecture locked before CAD hours, a mechanism choice settled before parts are ordered.

A map is an **effort overlay**, not a pipeline stage: the `Stage:` line in `CLAUDE.md` stays as the stage skills left it, and under a map the stage skills keep running — as ticket resolvers (see [Running the pipeline under a map](#running-the-pipeline-under-a-map)).

## Plan, don't do

Each ticket resolves a decision; the map is done when nothing is left to decide before someone builds the thing. The pull to just do the work is the signal you've reached the map's edge — hand off, usually to **armature-plan**. An effort can override this default in its map **Notes**, carrying execution into the map itself.

## Refer by name

Every map and ticket has a **name**: its title. In everything the human reads (narration, Decisions-so-far), refer to it by that name, with the id and URL riding inside the name as its link. A wall of bare `#42, #43` is illegible.

## The tracker

Where the map, its tickets, blocking, and frontier queries physically live is tracker-specific: consult the "Wayfinding operations" section of `docs/agents/issue-tracker.md` before touching the tracker. When that file is missing, create it first from this skill's references: with a GitHub remote (`git remote -v`), offer the user GitHub Issues (`references/issue-tracker-github.md`); otherwise copy `references/issue-tracker-local.md` without asking.

## The Map

The map is the effort's canonical artifact; its tickets are child items of the map. It is an **index**, not a store: it gists each decision and links the ticket that holds the detail, so a decision lives in exactly one place.

### The map body

The whole map at low resolution, loaded once per session. Open tickets are **not** listed here; they are found by frontier query.

```markdown
## Destination

<what reaching the end of this map looks like. One or two lines; every session orients to it before choosing a ticket.>

## Notes

<domain; skills every session should consult; standing preferences for this effort>

## Decisions so far

- [<resolved ticket title>](link): <one-line gist of the answer>

## Not yet specified

<!-- in-scope fog you can't ticket yet; graduates as the frontier advances -->

## Out of scope

<!-- work ruled beyond the destination; never graduates -->
```

### Tickets

Each ticket's body is one question, sized to a single ~100K-token session:

```markdown
## Question

<the decision or investigation this ticket resolves>
```

Each ticket records its type (`research`/`prototype`/`grilling`/`task`) the way the tracker doc prescribes.

A session **claims** a ticket first, before any work, so concurrent sessions skip it. A ticket is **unblocked** when everything blocking it is resolved; the **frontier** is the open, unblocked, unclaimed tickets — the edge of the known.

The answer is recorded on resolution, not in the body. Assets created while resolving (briefs, mockups, test logs) are linked from the ticket, not pasted in.

## Ticket types

Every ticket is **HITL** (worked live with the human, who speaks for themselves — never answer their side) or **AFK** (driven by the agent alone).

- **Research** (AFK): surface a fact a decision waits on from outside the working directory. Resolved by dispatching the matching agent — **armature-librarian** for datasheets, part numbers, and OTS models; **armature-inventor** for papers, novel mechanisms, and prior art — and linking its brief (`docs/research/`, `docs/datasheets/`) as the asset.
- **Prototype** (HITL): raise the fidelity of the discussion with a cheap, rough artifact the human reacts to — a CAD mockup (via **armature-cad**), a cardboard or printed model, a stub script. Use when "how should it look, fit, or behave" is the key question.
- **Grilling** (HITL): conversation — the default. A stage interview is a grilling ticket writ large: "run the concept interview" resolves through **armature-concept**, its brief linked as the asset.
- **Task** (HITL or AFK): manual work that gates a decision — nothing to decide itself, but the discussion is blocked until it's done: a bench measurement a sizing hangs on, ordering a sample part, provisioning access. AFK where the agent can drive it; otherwise hand the human a precise checklist. The answer records what was done and the facts later tickets depend on.

Robotics work maps onto the types:

| Work | Type |
|---|---|
| Trade study | research (librarian / inventor dispatch) |
| Bench characterization, procurement | task |
| CAD mockup, cardboard model | prototype |
| Architecture choice, requirements dispute | grilling |

A red-team pass is part of resolving whichever ticket it stress-tests, or a `task` of its own when its findings gate a decision.

## Fog of war

The map is deliberately incomplete: chart only what you can see. Beyond the live tickets lies the **fog of war** — decisions you can tell are coming but can't pin down yet, because they hang on questions still open. The map's **Not yet specified** section holds that dim view; resolving tickets clears fog, graduating what's now specifiable into fresh tickets until none remain and the way is clear.

**Fog or ticket?** The test is whether you can state the question precisely now, not whether you can answer it. Sharp question → ticket, even if blocked. Too dim to phrase → **Not yet specified**, written as loosely as the view allows and left coarse: one patch may graduate into several tickets, or none.

## Out of scope

The destination fixes the scope; work beyond it is out of scope, not fog. It lands in the map's **Out of scope** section: gist plus why, one line. When an existing ticket turns out to sit past the destination, close it and leave that line linking the closed ticket; Decisions-so-far records only the route actually walked. Out-of-scope work returns only if the destination is redrawn, as a fresh effort.

## Running the pipeline under a map

Wayfinding runs while the spec is unfrozen; once it freezes, **armature-plan** phases the build and the effort leaves the map. A big project's spec phase decomposes onto the map — each trade study a research ticket, the architecture choice a grilling ticket, an envelope question a prototype ticket, a load measurement a task — with "spec frozen" as the destination. The stage skills stay the means; the map only sequences them across sessions.

## Invocation

Two modes. Either way, resolve **one ticket per session** — research tickets, dispatched to agents in parallel, are the exception.

### Chart the map

The user invokes with a loose idea.

1. **Name the destination** with the user: a line or two they confirm. Charting stays light — the deep interviews happen later, as tickets.
2. **Map the frontier breadth-first**: fan out across the space for open decisions and first takeable steps. If no fog surfaces (the whole journey fits one session), skip the map and ask the user how to proceed.
3. **Create the map**: Destination and Notes filled, Decisions-so-far empty, fog sketched into Not yet specified.
4. **Create the tickets you can specify now** as children of the map, then wire blocking in a second pass (tickets need ids before they can reference each other).
5. **Dispatch each research ticket** to its agent, in parallel.
6. Stop: charting hand-resolves nothing.

### Work through the map

The user invokes with a map, and optionally a ticket; without one, you pick the next decision.

1. Load the map: the low-res view, not every ticket body.
2. Take the user's ticket, else the first frontier ticket. Claim it.
3. Resolve it, zooming into related or resolved tickets on demand and loading whatever skills the map's Notes name.
4. Record: post the answer on the ticket, close it, and append a one-liner to **both** indexes — the map's Decisions-so-far (the effort's route) and `docs/decisions.md` (the project chronology).
5. Update the map: graduate fog the answer made specifiable into tickets (create-then-wire, clearing each patch from Not yet specified), rule mis-scoped tickets out of scope, and fix or delete tickets the decision invalidated.

Expect other sessions on the tracker concurrently: the user may run unblocked tickets in parallel.
