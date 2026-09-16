#!/usr/bin/env bash
# Drive a wayfinder map through its remaining AFK tickets, one headless claude
# session per ticket (the skill's one-ticket-per-session rule). Re-queries the
# frontier after every session, so tickets that were blocked get picked up as
# their blockers close.
#
# Run from Git Bash at the repo root:   bash scripts/run-wayfinder-afk.sh
#
# Env overrides:
#   REPO=owner/name        default: the repo this clone points at
#   MAP_ISSUE=42           default: the one open issue labelled wayfinder:map
#   EXECUTOR=armature-librarian
#                          only tickets labelled executor:<this>. Unset = any.
#   INCLUDE_HITL=1         also attempt grilling/prototype tickets (they need a
#                          human by definition; off by default)
#   MAX_SESSIONS=12        hard cap on sessions this run
#   CLAUDE_BIN=claude      the claude CLI to invoke
#   DRY_RUN=1              print what would run, don't launch sessions
#   YOLO=1                 pass --dangerously-skip-permissions to each session.
#                          Off by default: with it on, every file edit, commit
#                          and push the agent makes is unreviewed. Only for a
#                          repo you are willing to have changed unattended.

set -uo pipefail

MAX_SESSIONS="${MAX_SESSIONS:-12}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
DRY_RUN="${DRY_RUN:-0}"
EXECUTOR="${EXECUTOR:-}"
INCLUDE_HITL="${INCLUDE_HITL:-0}"
YOLO="${YOLO:-0}"

CLAUDE_FLAGS=()
[ "$YOLO" = "1" ] && CLAUDE_FLAGS+=(--dangerously-skip-permissions)

# gh lives in Program Files on some Windows machines and may not be on PATH.
GH="gh"
if ! command -v gh >/dev/null 2>&1; then
  GH="/c/Program Files/GitHub CLI/gh.exe"
fi
if ! "$GH" auth status >/dev/null 2>&1; then
  echo "gh is not authenticated: run 'gh auth login'." >&2
  exit 1
fi

REPO="${REPO:-$("$GH" repo view --json nameWithOwner --jq .nameWithOwner)}"
if [ -z "$REPO" ]; then
  echo "No GitHub remote found for this clone; set REPO=owner/name." >&2
  exit 1
fi

# The map is the one open wayfinder:map issue unless told otherwise.
if [ -z "${MAP_ISSUE:-}" ]; then
  MAP_ISSUE=$("$GH" issue list -R "$REPO" --label wayfinder:map --state open \
    --json number --jq '.[0].number // empty')
fi
if [ -z "$MAP_ISSUE" ]; then
  echo "No open issue labelled wayfinder:map on $REPO; set MAP_ISSUE=<n>." >&2
  exit 1
fi

# HITL types need the human in the loop; an unattended run skips them.
HITL_TYPES='["wayfinder:grilling","wayfinder:prototype"]'
[ "$INCLUDE_HITL" = "1" ] && HITL_TYPES='[]'

# gh embeds jq but exposes no --arg, so the filters are spliced into the query
# string below. Keep EXECUTOR to label characters so the splice stays a literal.
if [ -n "$EXECUTOR" ] && ! printf '%s' "$EXECUTOR" | grep -Eq '^[A-Za-z0-9_.-]+$'; then
  echo "EXECUTOR must be a bare label suffix, e.g. armature-librarian." >&2
  exit 1
fi
EX_FILTER='.'
[ -n "$EXECUTOR" ] && EX_FILTER="select(\$names | index(\"executor:$EXECUTOR\"))"

LOG_DIR="$(git rev-parse --show-toplevel)/.wayfinder-logs"
mkdir -p "$LOG_DIR"

# Tickets attempted this run that a session left open (it judged the ticket
# HITL after all, or errored). Skipped on later iterations so we advance
# instead of looping on them.
SKIPPED=""
closed_count=0

# Print the lowest-numbered open, unassigned, unblocked, in-scope ticket that
# isn't the map and isn't in SKIPPED. Empty output = frontier exhausted.
next_frontier_ticket() {
  local candidates n blockers query
  query="[ .[]
        | . as \$i
        | (\$i.labels | map(.name)) as \$names
        | select((\$names | index(\"wayfinder:map\")) | not)
        | select(\$names | any(. as \$n | $HITL_TYPES | index(\$n)) | not)
        | $EX_FILTER
        | select(\$i.assignees | length == 0)
        | \$i.number ] | sort | .[]"
  candidates=$("$GH" issue list -R "$REPO" --state open --limit 200 \
    --json number,assignees,labels --jq "$query")

  for n in $candidates; do
    case " $SKIPPED " in *" $n "*) continue ;; esac
    blockers=$("$GH" api "repos/$REPO/issues/$n" \
      --jq '.issue_dependencies_summary.blocked_by // 0' 2>/dev/null || echo "?")
    if [ "$blockers" = "0" ]; then
      echo "$n"
      return 0
    fi
  done
  return 1
}

echo "=== wayfinder AFK driver — map #$MAP_ISSUE on $REPO ==="
[ -n "$EXECUTOR" ] && echo "Executor filter: executor:$EXECUTOR"
[ "$INCLUDE_HITL" = "1" ] && echo "HITL tickets included (they will usually stop and ask)."
if [ "$YOLO" = "1" ]; then
  echo "YOLO=1: sessions run with --dangerously-skip-permissions. Nothing they do is reviewed."
else
  echo "Permission prompts are live. A headless session cannot answer them, so a ticket"
  echo "needing one will stall and be skipped; set YOLO=1 only if that is what you want."
fi
echo "Logs: $LOG_DIR"

session=0
while [ "$session" -lt "$MAX_SESSIONS" ]; do
  ticket=$(next_frontier_ticket) || {
    echo ""
    echo "No open, unassigned, unblocked AFK tickets left. Done."
    break
  }

  session=$((session + 1))
  title=$("$GH" issue view "$ticket" -R "$REPO" --json title --jq .title)
  log="$LOG_DIR/$(date +%Y%m%d-%H%M%S)-ticket-$ticket.log"

  echo ""
  echo "--- session $session/$MAX_SESSIONS: ticket #$ticket — $title ---"

  prompt="/armature:armature-wayfind Work map #$MAP_ISSUE: resolve ticket #$ticket ($title). \
This is an unattended AFK session — resolve exactly this one ticket, then stop. \
Commit and push your work so 'Resolves $REPO#$ticket' auto-closes the ticket. \
If the ticket turns out to genuinely need the human present, post a comment \
explaining why, unassign yourself, and stop without closing it."

  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] $CLAUDE_BIN -p \"$prompt\" ${CLAUDE_FLAGS[*]:-}"
    SKIPPED="$SKIPPED $ticket"
    continue
  fi

  "$CLAUDE_BIN" -p "$prompt" "${CLAUDE_FLAGS[@]:-}" 2>&1 | tee "$log"

  state=$("$GH" issue view "$ticket" -R "$REPO" --json state --jq .state)
  if [ "$state" = "CLOSED" ]; then
    closed_count=$((closed_count + 1))
    echo "--- ticket #$ticket closed ---"
  else
    echo "--- ticket #$ticket still open after its session; skipping it for the rest of this run (see $log) ---"
    SKIPPED="$SKIPPED $ticket"
  fi
done

echo ""
echo "=== run summary ==="
echo "Sessions run: $session, tickets closed: $closed_count"
[ -n "$SKIPPED" ] && echo "Left open (need a look):$SKIPPED"
"$GH" issue list -R "$REPO" --state open --json number,title \
  --jq '.[] | "  still open: #\(.number) \(.title)"'
