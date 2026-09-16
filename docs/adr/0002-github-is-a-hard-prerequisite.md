# ADR 0002 — GitHub is a hard prerequisite; the local tracker is deleted

2026-09-15 — Status: accepted (supersedes the local-markdown tracker)

Armature projects now require `gh`, an authenticated account, and a GitHub
remote. `init` checks for them, offers `gh repo create --private`, creates the
label taxonomy, and writes `docs/agents/issue-tracker.md`;
`skills/armature-wayfind/references/issue-tracker-local.md` — a complete,
working, 29-line design that kept maps and tickets as markdown under
`docs/efforts/<slug>/` with no network at all — has been deleted. A robotics
plugin demanding a GitHub account before it will plan a build is a surprising
constraint, and the deleted file worked.

It goes because ADR 0001 put the plan on the tracker. Once the plan is issues,
a project on the local tracker can chart a map, work its tickets for a week,
and then be refused by `armature-plan` with no migration path — the divergence
lands one stage later instead of immediately, which is worse. Keeping both
paths alive means every tracker operation is written twice and tested once,
and the untested one is the one a user hits at the worst moment. A single
required path is honest about what the pipeline needs.

The cost accepted: `init` runs at stage `concept`, so a builder is asked to
create a repository for an idea the pitch interview has not yet judged worth
building, and a project that cannot reach GitHub cannot use Armature at all.
Revisit if offline or air-gapped use becomes a real requirement rather than a
hypothetical one — in which case the local tracker returns from this repo's
git history as a first-class path with its own tests, not as a fallback.
