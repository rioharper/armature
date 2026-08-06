# armature-cad rigor modes — Design

2026-08-06 · Approved in brainstorming session

## Problem

For simple parts, armature-cad's output is far heavier than the modeling
work it describes. Example: IbexRobot's IBX-HIP-001 (a flat five-sided
laser-cut plate with seven holes) produced a ~210-line part dossier, a
~190-line click-by-click tutorial, and a staged skeleton part with its own
ledger, tutorial, and equations export. The actual modeling content is
~25 lines. The current SKILL.md says "nothing padded to look thorough,"
but its mandatory 10-section template + tutorial companion forces the
exhaustive shape regardless. Users who are quickly ideating want the
25 lines; a certain kind of mechanical engineer still wants the dossier.

## Decision

One skill, two registers, selected by a project-level flag.

### Mode selection

- CLAUDE.md's Glossary gains one line: `Rigor: ideation | release`.
- armature-cad reads it during input gathering. **Absent → ideation.**
- Per-request override in either direction ("do this one fully" /
  "just sketch this out") always wins over the flag.
- armature-plan / init may be taught to write the line when they write
  the Glossary; beyond a one-line mention this is out of scope here.

### Ideation output

One file per part, `cad/parts/<PART-ID>.md`, target 40–60 lines, three
blocks in order:

1. **Header** — 2–3 lines: shape named as a familiar primitive, envelope
   dimensions, material/process, qty. ASCII/inline sketch only if the
   profile isn't obvious from words.
2. **Must be exact** — short table of interface-controlled dimensions
   only: fits (e.g. Ø12 H7), bolt patterns with BCD and source P/N,
   positioned holes with coordinates. Interface errors are unrecoverable
   even when ideating, so this block survives from release mode.
3. **Build** — numbered feature steps (sketch, extrude, holes, patterns)
   with every dimension inline as typed numbers. Ends with a one-line
   load sanity note only where a load actually sized a section ("fine in
   4 mm 6061 for ~600 N"). No Loads section, no FoS table, no provenance
   citations.

Not produced in ideation mode:

- No separate tutorial file — the per-package software reference supplies
  where tools live, consulted on demand.
- No done-when checklist beyond "rebuilds cleanly and the must-be-exact
  dims measure."
- No skeleton part, equations export, or driven dimensions, unless 3+
  parts share moving geometry **and** the user opts in when offered.

### Ideation process

All surrounding ceremony becomes on-request only: red-team dispatch,
mass/inertia loop closure, assembly definitions, per-batch branches,
release gates, budgets.md updates. The skill may close with a single
one-line offer ("want a design review / mass check?") and does nothing
unless asked.

The input gate softens: missing loads are no longer a hard block routing
to armature-math — the skill states its assumption inline ("assuming
~500 N here; re-run armature-math to sharpen") and proceeds. Missing
COTS interface data is still fetched via armature-librarian when the
part can't be drawn without it (a guessed bolt pattern wastes ideation
time too), but with no confirm-then-cache ceremony beyond a source note.

### Release mode

Today's behavior, unchanged: full 10-section template, tutorial
companion, documentation-standards depth, earn-the-skeleton rule,
red-team / loop-closure / branch workflow.

## Files touched

- `skills/armature-cad/SKILL.md` — add the mode check to input
  gathering; add the ideation register (output shape + process rules,
  defined inline — it is short); scope the existing template, tutorial,
  and ceremony sections to release mode.
- `skills/armature-cad/references/documentation-standards.md` — one
  paragraph up top noting it is release-mode depth (ideation mode reads
  only the fits table when picking a fit).
- Nothing else. Other skills (armature-spec, armature-math) are out of
  scope; they can adopt the same flag later if wanted.

## Out of scope

- Changing armature-spec / armature-math / armature-plan output depth.
- Regenerating existing IbexRobot part docs.
- Any new files, agents, or references.
