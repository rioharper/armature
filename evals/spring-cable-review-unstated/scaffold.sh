#!/usr/bin/env bash
# The spring and cable's red-team case with its bait unstated: spring-cable-review's
# own planted derivation, only the brief differs.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" spring_cable "$here/../spring-cable-review/planted"
