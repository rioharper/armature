# ADR 0009 — The engine reaches projects as a git tag, in lockstep with the plugin

2026-10-20 — Status: accepted (settles ADR 0004's open distribution question)

A project takes the engine from this repository's git tag for the plugin
version it runs:

```toml
[tool.uv.sources]
armature-engine = { git = "https://github.com/rioharper/armature", tag = "vX.Y.Z", subdirectory = "engine" }
```

and commits its `uv.lock`, which records the tag's commit SHA and no machine
path. The engine's version always equals `plugin.json`'s and
`marketplace.json`'s, and one tag `vX.Y.Z` covers all three, so the skills a
project runs and the engine it pins are the pair the release gate measured.
The engine goes from 0.1.0 to 2.0.0 with the bump past 1.3.0, whose
Unreleased changes are breaking.

The template's committed `pyproject.toml` keeps its relative path to
`engine/`, so the template's self-run, the golden tests and the eval scaffold
test the working tree. A script, `scripts/engine-source.sh`, writes the tag
when the template is copied (`pin`), and reports a project as in step, behind
or on a `rev` pin (`check`). It reads the version from its own plugin's
`plugin.json`, because `${CLAUDE_PLUGIN_ROOT}` is not set in the Bash tool.
`check` runs on `init`'s re-run and at every derive milestone checkpoint. A
project behind within a major version is upgraded there and `run_all` re-run;
one behind across a major version is reported and stops, because that is a
migration.

A fix needed between releases reaches a project as `rev = "<sha>"` of a pushed
commit on `main`, and the project returns to a tag at the next release. A
committed `pyproject.toml` never holds a local path. This replaces ADR 0004's
interim editable path into this repository.

A release bumps the three versions in one commit, runs the release run on
that commit, tags that exact commit, and pushes `main` and the tag with
`git push --atomic`. It then smoke-tests the real tag: the template copied
into a scratch directory, `pin`, `uv lock`, `run_all`. A tag once pushed may
already be in someone's lock, so a failure is a patch release, never a moved
tag. The eval scaffold keeps its path to the plugin copy's `engine/`, so the
gate judges the candidate, not the previous release; ADR 0008's workflow is
unchanged.

The plugin cache cannot hold the engine for a project. It is keyed by version,
`${CLAUDE_PLUGIN_ROOT}` changes on every update, and Claude Code deletes the
old version's directory 14 days after an update, so an absolute path into it
breaks a project's lock two weeks after the next release and can never be
committed. `init` already repairs `.mcp.json` paths an update moved; the
engine would have needed the same repair on every project, after the fact.

Rejected:
- **An absolute path into the plugin cache** (derive Step 0 until now). It is
  per machine, moves on every update, and is swept 14 days later.
- **PyPI.** An account, a publish pipeline and a name to hold, for consumers
  who can all reach a public repository. It can be added later without
  changing the import name.
- **A vendored wheel, in the project or in `${CLAUDE_PLUGIN_DATA}`.** The data
  directory is per plugin, not per version, so it cannot hold the different
  engines that projects on different releases pin, and it is deleted on
  uninstall.
- **Separate engine versions and tags**, released on tier 1 alone. A project
  could pin an engine whose API its skills do not describe, and no gate would
  have measured that pair.
- **The script in `bin/`.** Whether `bin/` reaches Git Bash's PATH on Windows
  is unverified; `scripts/` called by its substituted path is how
  `env-probe.sh` already runs. The verbs grilling may move it.

The cost accepted:
- Every engine release is a plugin release, gated by the release run (about
  $85 and 170 min). `rev` pins carry urgent fixes in between.
- A first sync needs GitHub as well as PyPI. Later syncs work offline from
  uv's cache.
- A project lagging its plugin reads skills newer than its engine until
  `check` runs.
- Nothing before the post-release smoke test exercises the git source.

Revisit when a consumer cannot reach GitHub (then PyPI), or when the release
run's cost pushes engine fixes toward separate releases.
