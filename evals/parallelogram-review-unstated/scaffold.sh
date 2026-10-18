#!/usr/bin/env bash
# The parallelogram's red-team case with its bait unstated: parallelogram-review's
# own planted derivation, only the brief differs.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" parallelogram "$here/../parallelogram-review/planted"
