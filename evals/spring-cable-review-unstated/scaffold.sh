#!/usr/bin/env bash
# The bob-on-a-cable rig's red-team case with its bait unstated:
# spring-cable-review's planted derivation with implicit.patch over it, the
# cable held rigid and never numbered as an assumption.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" spring_cable "$here/../spring-cable-review/planted" "$here/implicit.patch"
