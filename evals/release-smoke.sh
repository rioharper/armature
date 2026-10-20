#!/usr/bin/env bash
# release-smoke.sh vX.Y.Z — step 5 of the release procedure (#133, ADR 0009):
# after `git push --atomic origin main vX.Y.Z`, a project's first sync from
# the real tag. Nothing before the release exercises the git source, its
# `subdirectory`, or uv_build packaging the engine from a checkout. It:
#  1. checks that the tag is on origin and is v plus plugin.json's version;
#  2. copies the model template, as committed at HEAD, into a fresh
#     analysis/model/ in a temporary directory, as a project holds it. Spec
#     §9 copies a subset and the project writes the rest; the smoke copies
#     the whole template, which runs as it is. Run it from the tagged commit,
#     as step 5 is; elsewhere it warns, since the template is then HEAD's and
#     the engine the tag's;
#  3. runs scripts/engine-source.sh pin there, with the lock, so uv fetches
#     the engine from the tag;
#  4. runs `uv run python run_all.py` on that engine.
# It exits with the number of the step that failed, and says which, or 64 on
# a usage error. The temporary directory is removed on success and kept on
# failure. It never moves or deletes a tag: a failure after the push is a
# patch release.
set -euo pipefail

[ $# = 1 ] || { echo "usage: release-smoke.sh vX.Y.Z" >&2; exit 64; }
tag="$1"
root="$(cd "$(dirname "$0")/.." && pwd)"
template=skills/armature-derive/scripts/model_template

fail() { echo "release-smoke: step $1 failed: $2" >&2; exit "$1"; }

echo "1. $tag on origin"
version=$(sed -n 's/^ *"version": *"\([^"]*\)".*/\1/p' \
    "$root/.claude-plugin/plugin.json" | head -n 1 | tr -d '\r') \
    && [ -n "$version" ] || fail 1 "no version in .claude-plugin/plugin.json"
[ "$tag" = "v$version" ] \
    || fail 1 "$tag is not v plus plugin.json's version, $version"
git -C "$root" ls-remote --exit-code --tags origin "refs/tags/$tag" \
    >/dev/null || fail 1 "origin has no tag $tag, or could not be reached"

echo "2. the model template into a temporary project"
[ "$(git -C "$root" rev-parse HEAD)" = \
  "$(git -C "$root" rev-parse -q --verify "$tag^{commit}" || true)" ] \
    || echo "release-smoke: HEAD is not $tag; the template is HEAD's" >&2
tmp=$(mktemp -d) || fail 2 "could not make a temporary directory"
model="$tmp/analysis/model"
{ mkdir -p "$model" \
    && git -C "$root" archive "HEAD:$template" | tar -x -C "$model"; } \
    || fail 2 "could not copy $template into $model; kept at $tmp"

echo "3. pin the engine to $tag"
bash "$root/scripts/engine-source.sh" pin "$model" \
    || fail 3 "engine-source.sh pin; the project is kept at $tmp"

echo "4. run_all.py on the engine at $tag"
( cd "$model" && unset VIRTUAL_ENV && uv run python run_all.py ) \
    || fail 4 "run_all.py; the project is kept at $tmp"

rm -rf "$tmp"
echo "release-smoke: $tag passed"
