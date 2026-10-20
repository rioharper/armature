#!/usr/bin/env bash
# The engine source of a project's model directory (ADR 0009): the git tag of
# the plugin this script ships in.
#
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/engine-source.sh" pin [--no-lock] <model-dir>
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/engine-source.sh" check <model-dir>
#
# as a SKILL.md calls it, the path substituted when the skill loads. The
# version is this plugin's own, read from the plugin.json beside this script,
# since CLAUDE_PLUGIN_ROOT is not set in the Bash tool.
#
# check prints one line, its first word the state: in-step, behind (minor or
# major), ahead, rev (in the tag, unreleased, or unknown when gh fails) or
# path. It exits 0 only when in-step, and changes nothing.
#
# pin rewrites the armature-engine source line to the plugin's tag, then runs
# `uv lock --upgrade-package armature-engine` unless --no-lock. It pins a path,
# an older tag on the same major, or a rev the tag contains; anything else, a
# migration, a newer tag or an uncontained rev, it refuses with exit 2, as it
# does every error that leaves the project untouched. A failed lock exits 1.
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

usage="usage: engine-source.sh pin [--no-lock] <model-dir> | check <model-dir>"
cmd="${1:-}"; shift || true
lock=1 model=
for arg; do
  case "$arg" in
    --no-lock) [ "$cmd" = pin ] || die "--no-lock is pin's alone; $usage"
               lock=0 ;;
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

field() { printf '%s' "$current" | sed -n "s/.*[{ ]$1 = \"\([^\"]*\)\".*/\1/p"; }

# The parts of a vX.Y.Z tag, into the array PARTS.
parts() {
  [[ "$1" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || die "'$1' is not a vX.Y.Z tag"
  PARTS=("${BASH_REMATCH[@]:1}")
}

# in, unreleased or unknown: whether the plugin's tag contains commit $1.
containment() {
  local status
  status=$(gh api "repos/rioharper/armature/compare/$tag...$1" --jq .status \
      2>/dev/null | tr -d '\r') || { echo unknown; return; }
  case "$status" in
    behind|identical) echo in ;;
    ahead|diverged)   echo unreleased ;;
    *)                echo unknown ;;
  esac
}

# The project's state: the line `check` prints, its first word the state.
state() {
  local theirs
  if theirs=$(field tag) && [ -n "$theirs" ]; then
    local a b i
    parts "$theirs"; a=("${PARTS[@]}")
    parts "$tag"; b=("${PARTS[@]}")
    for i in 0 1 2; do
      if (( 10#${a[i]} < 10#${b[i]} )); then
        local kind=minor
        (( 10#${a[0]} < 10#${b[0]} )) && kind=major
        echo "behind $theirs -> $tag ($kind)"; return
      fi
      if (( 10#${a[i]} > 10#${b[i]} )); then
        echo "ahead $theirs > $tag"; return
      fi
    done
    echo "in-step $tag"
  elif theirs=$(field rev) && [ -n "$theirs" ]; then
    local where
    where=$(containment "$theirs")
    [ "$where" = in ] && where="in $tag"
    echo "rev $theirs ($where)"
  elif theirs=$(field path) && [ -n "$theirs" ]; then
    echo "path $theirs"
  else
    die "the engine source $current is not a tag, a rev or a path"
  fi
}

case "$cmd" in
  check)
    line=$(state)
    echo "$line"
    [ "${line%% *}" = in-step ]
    ;;
  pin)
    line=$(state)
    case "$line" in
      in-step*|path*|behind*"(minor)"|rev*"(in $tag)") ;;
      behind*) die "$line is a migration across a major version; read the" \
                   "plugin's CHANGELOG.md, then pin by hand" ;;
      ahead*) die "$line: this plugin is out of date; update it, then pin" ;;
      rev*"(unreleased)") die "$line: $tag does not contain that commit;" \
                              "pin again once a release does" ;;
      *) die "$line: could not tell whether $tag contains that commit" \
             "(gh api failed)" ;;
    esac
    sed -bi "s|^armature-engine = {[^}]*}|armature-engine = $want|" "$pyproject"         || die "could not rewrite $pyproject"
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
    ;;
  *) die "unknown subcommand '$cmd'; use pin or check" ;;
esac
