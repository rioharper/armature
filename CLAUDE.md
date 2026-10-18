# Armature

Robotics engineering pipeline packaged as a Claude Code plugin: five pipeline stages, `init`, and five cross-cutting skills in `skills/`; three agents in `agents/`; a SolidWorks MCP server in `mcp/solidworks/`.

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues via the `gh` CLI, including wayfinder maps and their tickets. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root, both created lazily. See `docs/agents/domain.md`.

## Releasing

A version bump is gated on the full eval suite. The rule and the commands are in `evals/README.md`. An edit to `skills/armature-derive/`, `agents/red-team.md` or `references/review-checklist.md` is checked on demand with `claude plugin eval --case`, as that README says. Keep pointers at `evals/` and `engine/tests/golden/` out of those files: the agent reads them, and a run that reads the answers is voided.
