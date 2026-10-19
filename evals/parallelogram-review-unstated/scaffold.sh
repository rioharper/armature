#!/usr/bin/env bash
# The camera arm's red-team case with its bait unstated: parallelogram-review's
# planted derivation with implicit.patch over it, the PSU sized for the static
# current and never numbered as an assumption.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" parallelogram "$here/../parallelogram-review/planted" "$here/implicit.patch"
