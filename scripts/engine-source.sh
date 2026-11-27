#!/usr/bin/env bash
# The engine source of a project's model directory (ADR 0009): the git tag of
# the plugin this script ships in.
#
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/engine-source.sh" pin [--no-lock] <model-dir>
#
# as a SKILL.md calls it, the path substituted when the skill loads. The
# version is this plugin's own, read from the plugin.json beside this script,
# since CLAUDE_PLUGIN_ROOT is not set in the Bash tool.
#
# pin rewrites the armature-engine source line to the plugin's tag, whatever
# it held, prints the old source and the new, then runs
# `uv lock --upgrade-package armature-engine` unless --no-lock. An error that
# leaves the project untouched exits 2; a failed lock exits 1.
set -euo pipefail

REPO=https://github.com/rioharper/armature

die() { echo "engine-source: $*" >&2; exit 2; }

manifest="$(dirname "$0")/../.claude-plugin/plugin.json"
[ -f "$manifest" ] || die "no plugin.json at $manifest"
version=$(sed -n 's/^ *"version": *"\([^"]*\)".*/\1/p' "$manifest" \
    | head -n 1 | tr -d '\r')
[ -n "$version" ] || die "no version in $manifest"
tag="v$version"
want="{ git = \"$REPO\", tag = \"$tag\", subdirectory = \"engine\" }"

usage="usage: engine-source.sh pin [--no-lock] <model-dir>"
[ "${1:-}" = pin ] || die "$usage"
shift
lock=1 model=
for arg; do
  case "$arg" in
    --no-lock) lock=0 ;;
    *) [ -z "$model" ] || die "$usage"; model="$arg" ;;
  esac
done
[ -n "$model" ] || die "$usage"
pyproject="$model/pyproject.toml"
[ -f "$pyproject" ] || die "no pyproject.toml in $model"

# The `{ … }` of the armature-engine source line, without a CR.
current=$(sed -n 's/^armature-engine = \({[^}]*}\).*/\1/p' "$pyproject" \
    | head -n 1 | tr -d '\r')
[ -n "$current" ] || die "no armature-engine = { … } line in $pyproject"

# GNU sed's -b keeps a CRLF file's line ends on Windows; BSD sed (macOS)
# has no -b and keeps them anyway.
rewrite="s|^armature-engine = {[^}]*}|armature-engine = $want|"
{ sed -b "$rewrite" "$pyproject" > "$pyproject.new" 2>/dev/null \
      || sed "$rewrite" "$pyproject" > "$pyproject.new"; } \
    && mv "$pyproject.new" "$pyproject" \
    || die "could not rewrite $pyproject"
grep -qF "armature-engine = $want" "$pyproject" \
    || die "the engine source in $pyproject was not rewritten"
echo "old: $current"
echo "new: $want"
[ "$lock" = 1 ] || exit 0
( cd "$model" && uv lock --upgrade-package armature-engine ) || {
  echo "engine-source: uv lock failed in $model; its pyproject.toml now" \
       "names $tag" >&2
  exit 1
}
