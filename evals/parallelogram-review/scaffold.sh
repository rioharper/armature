#!/usr/bin/env bash
# The parallelogram's red-team case: the golden balanced arm, its drive and
# its stop, then the planted derivation over it, which checks regeneration
# only on a slow stop.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" parallelogram "$here/planted"
