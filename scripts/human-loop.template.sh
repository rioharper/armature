#!/usr/bin/env bash
# Human-loop primitive: the agent runs this script; the human follows the
# prompts at the bench. Bash only (Git Bash on Windows).
#
# Copy this file, edit between the markers, and run: bash <copy>.sh
#
# Helpers:
#   step "<instruction>"      show an instruction, wait for Enter
#   confirm "<gate>"          require exactly "y" to continue; anything else aborts
#   capture VAR "<question>"  read the human's answer into VAR
#
# Every captured value prints as KEY=VALUE at the end, where the agent reads
# it — so capture observations (measurements, y/n outcomes), and leave actions
# with nothing to record as a step. Gate irreversible actions (first battery
# connect, first torque command) with confirm.

set -euo pipefail

step() {
  printf '\n>>> %s\n' "$1"
  read -r -p "    [Enter when done] " _
}

confirm() {
  local answer
  printf '\n>>> GATE: %s\n' "$1"
  read -r -p "    [y to proceed, anything else aborts] " answer
  if [ "${answer}" != "y" ]; then
    printf 'ABORTED at gate: %s\n' "$1"
    exit 1
  fi
}

CAPTURED=()

capture() {
  local var="$1" question="$2" answer
  printf '\n>>> %s\n' "$question"
  read -r -p "    > " answer
  printf -v "$var" '%s' "$answer"
  CAPTURED+=("$var")
}

# --- edit below ---------------------------------------------------------

confirm "Bench supply current-limited and e-stop in reach?"

step "Flash the board with the current build."

step "Hold the arm at the zero pose and enable joint 2."

capture HOLD_CURRENT "Bus current at hold, from the supply display (A):"

capture FAULT_LED "Command 30 deg on joint 2. Did the fault LED latch? (y/n)"

# --- edit above ---------------------------------------------------------

printf '\n--- Captured ---\n'
for var in "${CAPTURED[@]}"; do
  printf '%s=%s\n' "$var" "${!var}"
done
