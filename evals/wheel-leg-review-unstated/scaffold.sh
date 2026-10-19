#!/usr/bin/env bash
# The wheel leg's red-team case with its bait unstated: wheel-leg-review's
# planted derivation with implicit.patch over it, the search scoped to α = 0
# and never numbered as an assumption.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" wheel_leg "$here/../wheel-leg-review/planted" "$here/implicit.patch"
