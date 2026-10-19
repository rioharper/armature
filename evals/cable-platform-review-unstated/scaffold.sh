#!/usr/bin/env bash
# The cable platform's red-team case with its bait unstated:
# cable-platform-review's planted derivation with implicit.patch over it, the
# platform held level and never numbered as an assumption.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" cable_platform "$here/../cable-platform-review/planted" "$here/implicit.patch"
