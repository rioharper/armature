#!/usr/bin/env bash
# The wheel leg's red-team case: the golden five-bar leg on a wheel, then the
# planted derivation over it, which checks first contact only at alpha = 0.
here="$(dirname "$0")"
exec bash "$here/../planted.sh" wheel_leg "$here/planted"
