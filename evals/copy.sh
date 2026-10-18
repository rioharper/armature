#!/usr/bin/env bash
# copy.sh <dest> [<tree-ish>] — makes the copy of the plugin an eval runs
# from, by `git archive` of <tree-ish> (HEAD by default) into an empty <dest>.
#
# The agent reads the plugin through the engine path its project's
# pyproject.toml names, so the copy holds no engine/tests/: the fixture tests
# and the golden answers are not there to read (#128). The golden projects go
# to evals/golden/<mechanism>/ instead, where scaffold.sh finds them and the
# harness masks them from the agent. An archive holds no hard links, which
# `claude plugin eval` refuses.
set -euo pipefail

dest="${1:?usage: copy.sh <dest> [<tree-ish>]}"
tree="${2:-HEAD}"
root="$(cd "$(dirname "$0")/.." && pwd)"
if [ -e "$dest" ] && [ -n "$(ls -A "$dest")" ]; then
    echo "$dest is not empty" >&2; exit 1
fi
mkdir -p "$dest/evals/golden"

git -C "$root" archive "$tree" -- . ':(exclude)engine/tests' \
    | tar -x -C "$dest"
# The golden projects alone: not answers.py, matrix.py or the package.
git -C "$root" archive "$tree" -- ':(glob)engine/tests/golden/*/*.py' \
    | tar -x -C "$dest/evals/golden" --strip-components=3
