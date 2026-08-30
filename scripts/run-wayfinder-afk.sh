#!/usr/bin/env bash
# Drive the wayfinder map (rioharper/armature#1) through all remaining AFK
# tickets, one headless claude session per ticket (the skill's one-ticket-per-
# session rule). Re-queries the frontier after every session so tickets that
# were blocked (#18 behind #17, #21 behind #20, #10 behind everything) get
# picked up as their blockers close.
#
# Run from Git Bash at the repo root:   bash scripts/run-wayfinder-afk.sh
#
# Env overrides:
#   MAX_SESSIONS=12        hard cap on sessions this run
#   CLAUDE_BIN=claude      the claude CLI to invoke
#   DRY_RUN=1              print what would run, don't launch sessions

set -uo pipefail

REPO="rioharper/armature"
MAP_ISSUE=1
MAX_SESSIONS="${MAX_SESSIONS:-12}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
DRY_RUN="${DRY_RUN:-0}"

# gh lives in Program Files on this machine and may not be on PATH.
GH="gh"
if ! command -v gh >/dev/null 2>&1; then
  GH="/c/Program Files/GitHub CLI/gh.exe"
fi

LOG_DIR="$(git rev-parse --show-toplevel)/.wayfinder-logs"
mkdir -p "$LOG_DIR"

# Tickets attempted this run that a session left open (e.g. it judged the
# ticket HITL after all, or errored). Skipped on later iterations so we
# advance instead of looping on them.
SKIPPED=""

closed_count=0

# Print the lowest-numbered open, unassigned, unblocked ticket that isn't the
# map and isn't in SKIPPED. Empty output = frontier exhausted (for us).
next_frontier_ticket() {
  local candidates n blockers
  candidates=$("$GH" issue list -R "$REPO" --state open \
    --json number,assignees,labels \
    --jq '[ .[]
            | select((.labels | map(.name) | index("wayfinder:map")) | not)
            | select(.assignees | length == 0)
            | .number ] | sort | .[]')

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
echo "Logs: $LOG_DIR"

session=0
while [ "$session" -lt "$MAX_SESSIONS" ]; do
  ticket=$(next_frontier_ticket) || {
    echo ""
    echo "No open, unassigned, unblocked tickets left. Done."
    break
  }

  session=$((session + 1))
  title=$("$GH" issue view "$ticket" -R "$REPO" --json title --jq .title)
  log="$LOG_DIR/$(date +%Y%m%d-%H%M%S)-ticket-$ticket.log"

  echo ""
  echo "--- session $session/$MAX_SESSIONS: ticket #$ticket — $title ---"

  prompt="/mattpocock-skills:wayfinder Work map #$MAP_ISSUE: resolve ticket #$ticket ($title). \
This is an unattended AFK session — resolve exactly this one ticket, then stop. \
Commit and push your work so 'Resolves $REPO#$ticket' auto-closes the ticket. \
If the ticket turns out to genuinely need the human present, post a comment \
explaining why, unassign yourself, and stop without closing it."

  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] $CLAUDE_BIN -p \"$prompt\" --dangerously-skip-permissions"
    SKIPPED="$SKIPPED $ticket"
    continue
  fi

  # Headless sessions can't answer permission prompts; AFK work needs git,
  # gh, and file edits, hence skip-permissions.
  "$CLAUDE_BIN" -p "$prompt" --dangerously-skip-permissions 2>&1 | tee "$log"

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
