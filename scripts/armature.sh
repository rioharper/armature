#!/usr/bin/env bash
# The plugin's own engine, run through uv: the check and the ledger from any
# project, from `init` on, before a project pins an engine of its own. The
# venv lives under ${CLAUDE_PLUGIN_DATA}, never in the plugin copy.
#
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/armature.sh" check
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/armature.sh" check analysis/model
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/armature.sh" ledger check
#
# Skills pass CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" ahead of it, since
# the Bash tool's environment has neither variable. With no
# CLAUDE_PLUGIN_DATA the venv goes under ~/.claude/plugins/data/armature-cli.
# scripts/armature.ps1 is the same launcher for PowerShell.
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

case "${1:-}" in
    ""|-h|--help)
        # The header comment: from line 2 to the first line not a comment.
        awk 'NR > 1 && !/^#/ { exit } NR > 1' "$0" | sed 's/^# \{0,1\}//'
        exit 2 ;;
esac
uv=$(find_uv) || { echo "error: the engine runs on uv, which is not installed; install uv (https://docs.astral.sh/uv/getting-started/installation/)" >&2; exit 2; }
module=$1; shift
UV_PROJECT_ENVIRONMENT="$data/venv" PYTHONPYCACHEPREFIX="$data/pycache" \
    exec "$uv" run --quiet --frozen --no-dev --project "$root/engine" \
    python -m "armature.$module" "$@"
