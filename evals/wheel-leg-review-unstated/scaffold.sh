#!/usr/bin/env bash
# The wheel leg's red-team case with its bait unstated: wheel-leg-review's
# own planted derivation, only the brief differs.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" wheel_leg "$here/../wheel-leg-review/planted"
