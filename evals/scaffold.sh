#!/usr/bin/env bash
# scaffold.sh <mechanism> — lays down a spec-stage project for an eval case.
#
# A case's own scaffold.sh execs this with its golden mechanism's name. It runs
# unsandboxed, as the operator, in the run's empty workspace, with no
# CLAUDE_PLUGIN_ROOT, so the plugin is reached from this file's own path. It:
#  1. copies the model template's runner (run_all.py, test_derivation.py and
#     pyproject.toml) into analysis/model/, then the golden project over it:
#     the description, params.py, and drive.py and missions.py where the
#     mechanism has them. The rest of the template is derive's to copy at
#     Milestone 0. The golden project is evals/golden/<mechanism>/ in the
#     copy copy.sh makes, which holds no engine/tests/ (#128), and
#     engine/tests/golden/<mechanism>/ in a checkout, for evals/tests;
#  2. points pyproject.toml's engine at this plugin's engine/, by absolute path;
#  3. runs `uv sync` with a persistent cache of its own, so the agent's
#     sandboxed `uv run` needs no network grant (#112);
#  4. commits the lot, so the project has the history a spec stage leaves.
set -euo pipefail

mechanism="${1:?usage: scaffold.sh <mechanism>}"
evals="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$evals")"
template="$root/skills/armature-derive/scripts/model_template"
golden="$evals/golden/$mechanism"
[ -d "$golden" ] || golden="$root/engine/tests/golden/$mechanism"
[ -f "$golden/mechanism.py" ] || { echo "no golden project at $golden" >&2; exit 1; }
# uv reads a Windows path under Git Bash, a POSIX one elsewhere.
engine="$(cd "$root/engine" && { pwd -W 2>/dev/null || pwd; })"

model=analysis/model
mkdir -p "$model" docs/testing
cp "$template/run_all.py" "$template/test_derivation.py" "$model/"
cp "$golden"/*.py "$model/"
sed "s|^armature-engine = { path = \"[^\"]*\"|armature-engine = { path = \"$engine\"|" \
    "$template/pyproject.toml" > "$model/pyproject.toml"
grep -qF "path = \"$engine\"" "$model/pyproject.toml" \
    || { echo "pyproject.toml's engine path was not rewritten" >&2; exit 1; }

# /var/tmp outlives the run and reboots; the sandbox hides it from the agent,
# which never needs it once the venv is synced. Never download a Python into
# the run's temporary home: the system's 3.12 is the one the venv is built on.
# ARMATURE_EVAL_UV_CACHE is for evals/tests, which runs this where /var/tmp
# is not writable (Git Bash); an eval run's scaffold never sees it.
( cd "$model" && UV_CACHE_DIR="${ARMATURE_EVAL_UV_CACHE:-/var/tmp/armature-eval-uv}" \
    UV_PYTHON_DOWNLOADS=never uv sync --quiet )

printf '.venv/\n__pycache__/\n.pytest_cache/\nreview/\n' > .gitignore
git init -q
git add -A
git -c user.name="Armature eval" -c user.email=eval@armature.invalid \
    commit -qm "Spec stage: the mechanism description and its parameters"
