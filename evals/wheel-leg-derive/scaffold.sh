#!/usr/bin/env bash
# The wheel leg's derive case: the template's runner, then the golden
# five-bar leg on a wheel over it, as spec §9 hands the project over.
exec bash "$(dirname "$0")/../scaffold.sh" wheel_leg
