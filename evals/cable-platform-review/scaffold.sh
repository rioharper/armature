#!/usr/bin/env bash
# The cable platform's red-team case: the golden platform on four cables, then
# the planted derivation over it, which releases A3 only at the room centre.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" cable_platform "$here/planted"
