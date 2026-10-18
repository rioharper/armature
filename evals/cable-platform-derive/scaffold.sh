#!/usr/bin/env bash
# The cable platform's derive case: the template's runner, then the golden
# platform on four cables over it, as spec §9 hands the project over.
exec bash "$(dirname "$0")/../scaffold.sh" cable_platform
