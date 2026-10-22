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

# set -u, and neither -e nor pipefail: the hook's tests are commands that
# fail as a matter of course (a grep -q that finds nothing, git outside a
# repo, grep -q closing a pipe early), and its handler is onFailure: block,
# so a script that exited on one would block every call it should let by.
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
        | awk '{ out = ""
                 for (i = 1; i <= length($0); i++) {
                     c = substr($0, i, 1)
                     if (c == "\\") {
                         c = substr($0, ++i, 1)
                         if (c == "n") c = "\n"; else if (c == "t") c = "\t"
                     }
                     out = out c
                 }
                 printf "%s", out }'
}

in_project() {   # in_project <folder>: its repo's root holds ledger.toml
    local top
    top=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || return 1
    [ -f "$top/ledger.toml" ]
}

slashed() {   # slashed <path>: with forward slashes, as git and Git Bash read
    printf '%s' "$1" | tr '\\' /
}

resolve() {   # resolve <path> <folder>: the path, read from the folder
    case "$1" in
        "~") printf '%s' "$HOME" ;;
        "~/"*) printf '%s/%s' "$HOME" "${1#"~/"}" ;;
        /*|[A-Za-z]:/*) printf '%s' "$1" ;;
        *) printf '%s/%s' "$2" "$1" ;;
    esac
}

# A cd (PowerShell's too) or git -C and the folder it names, plain or quoted.
CHDIR="(^|[^A-Za-z0-9_-])([Cc][Dd]|[Pp][Uu][Ss][Hh][Dd]|[Cc][Hh][Dd][Ii][Rr]\
|[Ss][Ee][Tt]-[Ll][Oo][Cc][Aa][Tt][Ii][Oo][Nn]|[Ss][Ll]|-C)[[:space:]]+\
(-[A-Za-z]*[Pp][Aa][Tt][Hh][[:space:]]+)?(\"[^\"]*\"|'[^']*'|[^[:space:];&|()]+)"

reaches_project() {   # reaches_project <folder> <command>: the command runs
    # in a project, from the folder or one a cd or git -C on it names. A
    # folder the line does not spell out (a variable, a substitution)
    # reaches none, as the engine's own reading of the line has it.
    local dir=$1 found verb target
    in_project "$dir" && return 0
    while IFS= read -r found; do
        verb=$(printf '%s' "$found" | sed -E 's/^[^A-Za-z-]*([A-Za-z-]+).*/\1/')
        target=$(printf '%s' "$found" | sed -E \
            's/^[^A-Za-z-]*[A-Za-z-]+[[:space:]]+(-[A-Za-z]*[Pp][Aa][Tt][Hh][[:space:]]+)?//')
        target=${target#[\"\']}; target=${target%[\"\']}
        case "$target" in *'$'*|*'`'*|'') continue ;; esac
        target=$(resolve "$(slashed "$target")" "$dir")
        in_project "$target" && return 0
        [ "$verb" = "-C" ] || dir=$target
    done < <(printf '%s' "$2" | grep -oE "$CHDIR")
    return 1
}

edit_project() {   # edit_project <folder> <file>: the file, read from the
    # folder, is in a project
    local folder
    folder=$(dirname "$(resolve "$(slashed "$2")" "$(slashed "$1")")")
    while [ ! -d "$folder" ]; do
        [ "$(dirname "$folder")" = "$folder" ] && return 1
        folder=$(dirname "$folder")
    done
    in_project "$folder"
}

written() {   # written <event>: the text an edit writes, one field a line
    printf '%s' "$1" | tr -d '\n' | grep -oE \
        '"(new_string|content|new_source)"[[:space:]]*:[[:space:]]*"([^"\\]|\\.)*"'
}

deny() {
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
    printf '"permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$1"
}

hook() {
    local event tool cwd file subject gated uv
    event=$(cat)
    tool=$(json_field tool_name "$event")
    cwd=$(json_field cwd "$event")
    [ -n "$cwd" ] || cwd=${CLAUDE_PROJECT_DIR:-$PWD}
    cwd=$(slashed "$cwd")
    case "$tool" in
        Bash|PowerShell)   # git and gh, run in a project
            subject=$(json_field command "$event")
            printf '%s' "$subject" | grep -qE '(^|[^A-Za-z0-9_.-])(git|gh)([^A-Za-z0-9_-]|$)' \
                || return 0
            reaches_project "$cwd" "$subject" || return 0
            gated='(git|gh)[^|;&]*[[:space:]](merge|push|commit)' ;;
        Edit|Write|MultiEdit|NotebookEdit)
            file=$(json_field file_path "$event")
            [ -n "$file" ] || file=$(json_field notebook_path "$event")
            file=$(slashed "$file")
            # By file, what the edit writes that is gated: a stamp, a
            # confirmation (written, or a kind confirmed by default), a
            # waiver, an acceptance.
            case "$file" in
                .armature/*|*/.armature/*) gated=always ;;
                ledger.toml|*/ledger.toml)
                    gated="confirmed|kind[[:space:]]*=[[:space:]]*[\\\\\"']*(chosen|standard)" ;;
                waivers.toml|*/waivers.toml) gated='confirmed|\[\[ *waiver' ;;
                reviews/*|*/reviews/*) gated=accepted ;;
                *) return 0 ;;
            esac
            edit_project "$cwd" "$file" || return 0
            subject=$(written "$event") ;;
        *) return 0 ;;
    esac
    if ! uv=$(find_uv); then
        if [ "$gated" = always ] || printf '%s' "$subject" | grep -qE "$gated"; then
            deny "Armature (ADR 0011): this action is gated, and the gate runs on uv, which is not installed. Install uv (https://docs.astral.sh/uv/getting-started/installation/), then retry."
        fi
        return 0
    fi
    printf '%s' "$event" | engine "$uv" gate.hook
}

case "${1:-}" in
    hook) hook ;;
    ""|-h|--help)
        # The header comment: from line 2 to the first line not a comment.
        awk 'NR > 1 && !/^#/ { exit } NR > 1' "$0" | sed 's/^# \{0,1\}//'
        exit 2 ;;
    *)
        uv=$(find_uv) || { echo "error: the engine runs on uv, which is not installed; install uv (https://docs.astral.sh/uv/getting-started/installation/)" >&2; exit 2; }
        engine "$uv" "$@" ;;
esac
