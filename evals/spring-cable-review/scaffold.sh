#!/usr/bin/env bash
# The spring and cable's red-team case: the golden mass on a cable, then the
# planted derivation over it, which releases A3 only on the static sag.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" spring_cable "$here/planted"
