#!/usr/bin/env bash
# planted.sh <mechanism> <planted> — lays down a red-team case's project: the
# derivation under review, golden-correct but for its one planted trap.
#
# A red-team case's scaffold.sh execs this with its golden mechanism's name and
# its own planted/ directory. It runs as scaffold.sh does, unsandboxed, in the
# run's empty workspace, and:
#  1. runs scaffold.sh <mechanism>: the spec-stage project, synced and
#     committed;
#  2. copies the model template's gates and review artifact (layout.py,
#     layout_checks.py, report_truth.py) into analysis/model/, as derive's
#     Milestone 0 does;
#  3. copies <planted> over the workspace: the notes, model modules and
#     report the derivation adds, laid out as they sit in the project. The
#     description stays the golden project's, so it has one source;
#  4. commits the derivation on top of the spec stage.
set -euo pipefail

mechanism="${1:?usage: planted.sh <mechanism> <planted>}"
planted="$(cd "${2:?usage: planted.sh <mechanism> <planted>}" && pwd)"
evals="$(cd "$(dirname "$0")" && pwd)"
template="$(dirname "$evals")/skills/armature-derive/scripts/model_template"

bash "$evals/scaffold.sh" "$mechanism"
cp "$template/layout.py" "$template/layout_checks.py" \
   "$template/report_truth.py" analysis/model/
cp -R "$planted/." .

git add -A
git -c user.name="Armature eval" -c user.email=eval@armature.invalid \
    commit -qm "Derive: the derivation and its decision report"
