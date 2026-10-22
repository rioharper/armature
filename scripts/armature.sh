#!/usr/bin/env bash
# The plugin's own engine, run through uv (ADR 0011): the gate and the ledger
# from any project, from `init` on, before a project pins an engine of its
# own. The venv lives under ${CLAUDE_PLUGIN_DATA}, never in the plugin copy.
#
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/armature.sh" gate status
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/armature.sh" ledger check
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/armature.sh" hook   # PreToolUse event
#                                                            # on stdin
# Skills pass CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" ahead of it, since
# the Bash tool's environment has neither variable; hooks get both. With no
# CLAUDE_PLUGIN_DATA the venv goes under ~/.claude/plugins/data/armature-cli.
#
# `hook` is the hook's backstop (hooks/hooks.json). Outside a project (a git
# repo whose root holds ledger.toml) and for a call that names nothing it
# gates, it exits 0 before starting Python. With no uv it denies only what
# looks gated, asking for uv. scripts/armature.ps1 is the same launcher for
# PowerShell, the hook's fallback where there is no Git Bash.
set -u

here=$(cd "$(dirname "$0")" && pwd)
root=$(dirname "$here")
data=${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/armature-cli}
if command -v cygpath >/dev/null 2>&1; then    # Git Bash: C:/... for uv.exe
    root=$(cygpath -m "$root"); data=$(cygpath -m "$data")
fi

find_uv() {
    command -v uv 2>/dev/null && return
    for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" \
                     "$HOME/.local/bin/uv.exe" "$HOME/.cargo/bin/uv.exe"; do
        [ -x "$candidate" ] && { echo "$candidate"; return; }
    done
    return 1
}

engine() {   # engine <uv> <module> [args...]
    local uv=$1; shift
    UV_PROJECT_ENVIRONMENT="$data/venv" PYTHONPYCACHEPREFIX="$data/pycache" \
        "$uv" run --quiet --frozen --no-dev --project "$root/engine" \
        python -m "armature.$@"
}

json_field() {   # json_field <name> <json>: a top-level string, unescaped
    printf '%s' "$2" | tr -d '\n' \
        | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\(\([^\"\\\\]\|\\\\.\)*\)\".*/\1/p" \
        | sed 's/\\\\/\\/g; s/\\"/"/g'
}

in_project() {   # in_project <folder>: its repo's root holds ledger.toml
    local top
    top=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || return 1
    [ -f "$top/ledger.toml" ]
}

deny() {
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
    printf '"permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$1"
}

hook() {
    local event tool cwd file uv
    event=$(cat)
    tool=$(json_field tool_name "$event")
    cwd=$(json_field cwd "$event")
    [ -n "$cwd" ] || cwd=${CLAUDE_PROJECT_DIR:-$PWD}
    case "$tool" in
        Bash|PowerShell)
            # Only git and gh are gated; a cd or -C may reach a project.
            printf '%s' "$event" | grep -qE '(^|[^A-Za-z0-9_.-])(git|gh)([^A-Za-z0-9_-]|$)' \
                || return 0
            in_project "$cwd" \
                || printf '%s' "$event" | grep -qiE '(^|[^A-Za-z0-9_-])(cd|pushd|chdir|set-location|sl|-C)[[:space:]]' \
                || return 0
            gated='(git|gh)[^|;&]*[[:space:]](merge|push|commit)' ;;
        Edit|Write|MultiEdit|NotebookEdit)
            file=$(json_field file_path "$event")
            [ -n "$file" ] || file=$(json_field notebook_path "$event")
            printf '%s' "$file" | grep -qE '(\.armature|ledger\.toml|waivers\.toml|reviews)' \
                || return 0
            gated='\.armature|confirmed|accepted|\[\[ *waiver' ;;
        *) return 0 ;;
    esac
    if ! uv=$(find_uv); then
        if printf '%s' "$event" | grep -qE "$gated"; then
            deny "Armature (ADR 0011): this action is gated, and the gate runs on uv, which is not installed. Install uv (https://docs.astral.sh/uv/getting-started/installation/), then retry."
        fi
        return 0
    fi
    printf '%s' "$event" | engine "$uv" gate.hook
}

case "${1:-}" in
    hook) hook ;;
    ""|-h|--help)
        sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'
        exit 2 ;;
    *)
        uv=$(find_uv) || { echo "error: the engine runs on uv, which is not installed; install uv (https://docs.astral.sh/uv/getting-started/installation/)" >&2; exit 2; }
        engine "$uv" "$@" ;;
esac
