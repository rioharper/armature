#!/usr/bin/env bash
# The cable platform's red-team case with its bait unstated: cable-platform-review's
# own planted derivation, only the brief differs.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" cable_platform "$here/../cable-platform-review/planted"
