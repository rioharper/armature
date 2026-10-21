"""The gate (ADR 0011, #155): `armature.gate merge` and `status`, run on
fixture git repos built here.

Answer: each verdict is worked from the fixture by the rule #154 states,
never from the gate's own output. A branch is cut from `main`, given one
change, and the item that change concerns is shown passing, failing and
waived. The trap each mutant of #154's *Testing Decisions* would hide in is
built and named: a review pinned before the branch point, a number moved
after a review and named in no `moves`, a recheck that reopens, a branch
behind `main`, a stamp that survives a new `uv.lock`, and a waiver nobody
confirmed.
"""

import datetime
import json
import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from armature.gate import merge, reviews

TODAY = datetime.date(2026, 10, 21)

LEDGER = """\
[mechanism.l1]
value = 0.3
unit = "m"
source = { kind = "chosen", ref = "spec §3" }

[mechanism.m2]
value = 0.8
unit = "kg"
band = [0.72, 0.88]
status = "candidate"
source = { kind = "estimate", ref = "a 6061 tube, 40 cm" }
"""


class Project:
    """An Armature project in a git repo: a root `ledger.toml`, committed
    on `main`."""

    def __init__(self, root):
        self.root = root
        self.git("init", "-q", "-b", "main")
        self.write("ledger.toml", LEDGER)
        self.commit("the ledger")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=t",
             "-c", "user.email=t@t.invalid", *args], check=True,
            capture_output=True, text=True, encoding="utf-8").stdout.strip()

    def write(self, path, text):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(textwrap.dedent(text), encoding="utf-8")
        return file

    def read(self, path):
        return (self.root / path).read_text(encoding="utf-8")

    def commit(self, message="a change"):
        """Commit everything; the commit's full SHA."""
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def branch(self, name):
        self.git("checkout", "-q", "-b", name)

    def checkout(self, name):
        self.git("checkout", "-q", name)

    def gate(self, **kw):
        kw.setdefault("today", TODAY)
        return merge(self.root, **kw)


@pytest.fixture
def project(tmp_path):
    return Project(tmp_path)


def python(code):
    """`code` run in a fresh interpreter, its stdout."""
    return subprocess.run([sys.executable, "-c", code], check=True,
                          capture_output=True, text=True,
                          encoding="utf-8").stdout


# --- the import cost ---------------------------------------------------------
def test_the_ledger_and_the_gate_import_without_mujoco():
    out = python("import sys, armature.ledger, armature.gate; "
                 "print('mujoco' in sys.modules)")
    assert out.strip() == "False"


def test_a_lazy_name_is_what_it_was_when_the_package_imported_everything():
    out = python("import armature.search, armature, armature.review; "
                 "from armature import symbolic; import armature.contact; "
                 "print(callable(armature.search), callable(armature.review),"
                 " callable(symbolic), callable(armature.contact), "
                 "armature.drive.__name__, armature.Margin.__name__)")
    assert out.split() == ["True", "True", "True", "True", "armature.drive",
                           "Margin"]


# --- 1. fast-forward ---------------------------------------------------------
def test_a_branch_cut_from_main_merges_fast_forward(project):
    project.branch("armature/spec-arm")
    project.write("docs/decisions.md", "# Decisions\n")
    project.commit()
    verdict = project.gate()
    assert verdict["fast-forward"].state == "pass"
    assert verdict.branch == "armature/spec-arm"


def test_a_branch_behind_main_fails_fast_forward(project):
    project.branch("armature/spec-arm")
    project.write("docs/decisions.md", "# Decisions\n")
    project.commit()
    project.checkout("main")
    project.write("docs/notes.md", "on main since\n")
    project.commit()
    verdict = project.gate(branch="armature/spec-arm")
    assert verdict["fast-forward"].state == "fail"
    assert "main" in verdict["fast-forward"].detail
    assert not verdict.passed


# --- 2. ledger check ---------------------------------------------------------
def test_a_ledger_error_at_the_tip_fails_the_ledger_item(project):
    project.branch("armature/spec-arm")
    project.write("ledger.toml", LEDGER.replace('band = [0.72, 0.88]\n', ""))
    project.commit()
    verdict = project.gate()
    assert verdict["ledger"].state == "fail"
    assert "band.missing" in verdict["ledger"].detail
    project.write("ledger.toml", LEDGER)
    project.commit("the band back")
    assert project.gate()["ledger"].state == "pass"


def test_the_ledger_item_reads_the_tip_not_the_working_tree(project):
    project.branch("armature/spec-arm")
    project.write("ledger.toml", LEDGER.replace('band = [0.72, 0.88]\n', ""))
    project.commit()
    project.checkout("main")
    assert project.gate(branch="armature/spec-arm")["ledger"].state == "fail"


# --- reviews -------------------------------------------------------------------
REVIEW = "docs/reviews/2026-10-21-spec-review.md"
CHECKS = "analysis/model/review_2026-10-21_spec_checks.py"
SPEC = """\
# Arm spec

The arm lifts 2 kg at full reach.

<!-- ledger:req -->
| REQ | Threshold |
|---|---|
| REQ-001 | 2 kg |
<!-- /ledger -->
"""


def finding(id, severity="MAJOR", status="open", closure=None):
    """One `[[finding]]` of a block; `closure` is its TOML inline table."""
    lines = ["", "[[finding]]", f'id = "{id}"']
    if severity is not None:
        lines.append(f'severity = "{severity}"')
    lines.append(f'status = "{status}"')
    if closure is not None:
        lines.append(f"closure = {closure}")
    return "\n".join(lines) + "\n"


def review(project, reviewed, *findings, path=REVIEW,
           artifacts=("docs/01-spec/spec.md",), rechecks=None):
    """Write a review (or, with `rechecks`, a recheck) ending in its
    block."""
    head = [f'reviewed = "{reviewed}"']
    if rechecks:
        head.append(f'rechecks = "{rechecks}"')
    else:
        head.append("artifacts = [" + ", ".join(f'"{a}"' for a in artifacts)
                    + "]")
    text = ("# Arm — Design Review Findings\n\n## Findings\n\nF1 ...\n\n"
            "```toml\n" + "\n".join(head) + "\n" + "".join(findings)
            + "```\n")
    project.write(path, text)


def spec_branch(project):
    """A spec branch whose first commit writes the spec: that commit's SHA,
    the one a review pins."""
    project.write("docs/01-spec/spec.md", SPEC)
    project.commit("the spec on main")
    project.branch("armature/spec-arm")
    project.write("docs/01-spec/spec.md", SPEC.replace("2 kg at", "3 kg at"))
    return project.commit("the spec: 3 kg")


# --- 5. a review where the branch changes what one gates ------------------------
def test_decisions_and_a_report_need_no_review(project):
    project.branch("armature/bench-report")
    project.write("docs/decisions.md", "# Decisions\n\n- D1: ship it\n")
    project.write("docs/testing/2026-10-21-motor-report.md", "# Report\n")
    project.commit()
    verdict = project.gate()
    assert verdict["review"].state == "pass"
    assert "no review needed" in verdict["review"].detail


@pytest.mark.parametrize("path, text", [
    ("analysis/model/kinematics.py", "L1 = 1\n"),
    ("cad/parts/ARM-BRK-001.md", "# ARM-BRK-001 bracket\n"),
    ("docs/02-plan/plan.md", "# Plan\n"),
])
def test_model_code_a_part_definition_or_plan_text_needs_a_review(
        project, path, text):
    project.branch("armature/work")
    project.write(path, text)
    project.commit()
    verdict = project.gate()
    assert verdict["review"].state == "fail"
    assert path in verdict["review"].detail


def test_a_ledger_number_needs_a_review_and_a_note_does_not(project):
    project.branch("armature/spec-arm")
    project.write("ledger.toml", LEDGER.replace(
        'ref = "spec §3" }', 'ref = "spec §3" }\nnote = "upper arm"'))
    project.commit("a note")
    assert project.gate()["review"].state == "pass"
    project.write("ledger.toml", LEDGER.replace("value = 0.3", "value = 0.35"))
    project.commit("a longer arm")
    verdict = project.gate()
    assert verdict["review"].state == "fail"
    assert "mechanism.l1" in verdict["review"].detail


def test_spec_text_needs_a_review_and_a_rendered_section_does_not(project):
    project.write("docs/01-spec/spec.md", SPEC)
    project.commit("the spec")
    project.branch("armature/spec-arm")
    project.write("docs/01-spec/spec.md", SPEC.replace("| 2 kg |", "| 3 kg |"))
    project.commit("rendered")
    assert project.gate()["review"].state == "pass"
    project.write("docs/01-spec/spec.md", SPEC.replace("2 kg at", "3 kg at"))
    project.commit("written")
    assert project.gate()["review"].state == "fail"


def test_a_review_pinned_on_the_branch_counts(project):
    sha = spec_branch(project)
    review(project, sha, finding("F1", "MINOR"))
    project.commit("the review")
    verdict = project.gate()
    assert verdict["review"].state == "pass"
    assert REVIEW in verdict["review"].detail


def test_a_review_pinned_before_the_branch_point_does_not_count(project):
    project.write("docs/01-spec/spec.md", SPEC)
    before = project.commit("the spec on main")
    project.write("docs/notes.md", "since\n")
    project.commit("main moves on")
    project.branch("armature/spec-arm")
    project.write("docs/01-spec/spec.md", SPEC.replace("2 kg at", "3 kg at"))
    project.commit("the spec: 3 kg")
    review(project, before, finding("F1", "MINOR"))
    project.commit("a review of the old spec")
    verdict = project.gate()
    assert verdict["review"].state == "fail"
    assert "before the branch point" in verdict["review"].detail


def test_a_review_whose_block_will_not_parse_fails(project):
    sha = spec_branch(project)
    review(project, sha, finding("F1", "SEVERE"))
    project.commit("the review")
    verdict = project.gate()
    assert verdict["review"].state == "fail"
    assert "SEVERE" in verdict["review"].detail


def test_a_staging_file_is_no_review(project):
    sha = spec_branch(project)
    review(project, sha, finding("F1", "MINOR"),
           path="docs/reviews/staging/2026-10-21-spec-physics.md")
    project.commit("a pass")
    assert project.gate()["review"].state == "fail"


# --- 6. every BLOCKER and MAJOR closed ------------------------------------------
def test_an_open_major_fails_and_an_open_minor_or_question_does_not(project):
    sha = spec_branch(project)
    review(project, sha, finding("F1", "MINOR"), finding("F2", "QUESTION"))
    project.commit("the review")
    assert project.gate()["closed"].state == "pass"
    review(project, sha, finding("F1", "MINOR"), finding("F2", "MAJOR"))
    project.commit("a major")
    verdict = project.gate()
    assert verdict["closed"].state == "fail"
    assert "F2" in verdict["closed"].detail


def test_a_major_closes_on_a_check_in_the_reviews_checks_file(project):
    sha = spec_branch(project)
    project.write("analysis/model/run_all.py", "print('ok')\n")
    project.write(CHECKS, "def test_F2_payload():\n    assert 3 > 2\n")
    review(project, sha, finding("F2", "BLOCKER", "fixed",
                                 f'{{ check = "{CHECKS}::test_F2_payload" }}'))
    project.commit("the review, F2 closed")
    assert project.gate()["closed"].state == "pass"


@pytest.mark.parametrize("check, why", [
    (f"{CHECKS}::test_F2_missing", "test_F2_missing"),
    ("analysis/model/other_checks.py::test_F2_payload", "checks file"),
])
def test_a_check_that_is_not_in_the_reviews_checks_file_closes_nothing(
        project, check, why):
    sha = spec_branch(project)
    project.write("analysis/model/run_all.py", "print('ok')\n")
    project.write(CHECKS, "def test_F2_payload():\n    assert 3 > 2\n")
    project.write("analysis/model/other_checks.py",
                  "def test_F2_payload():\n    assert 3 > 2\n")
    review(project, sha, finding("F2", "MAJOR", "fixed",
                                 f'{{ check = "{check}" }}'))
    project.commit("the review")
    verdict = project.gate()
    assert verdict["closed"].state == "fail"
    assert why in verdict["closed"].detail


def test_an_acceptance_closes_with_a_reason_and_not_without(project):
    sha = spec_branch(project)
    review(project, sha, finding("F2", "MAJOR", "accepted",
                                 '{ reason = "the margin is thin by 2 %" }'))
    project.commit("accepted")
    assert project.gate()["closed"].state == "pass"
    review(project, sha, finding("F2", "MAJOR", "accepted"))
    project.commit("accepted, no reason")
    assert project.gate()["closed"].state == "fail"


RECHECK = "docs/reviews/2026-10-21-spec-recheck.md"
RECHECK_2 = "docs/reviews/2026-10-21-spec-recheck-2.md"


def fixed_by_recheck(project, sha, recheck=RECHECK):
    review(project, sha, finding("F2", "MAJOR", "fixed",
                                 f'{{ recheck = "{recheck}" }}'))


def test_a_major_closes_on_a_recheck_that_holds(project):
    sha = spec_branch(project)
    review(project, sha, finding("F2"))
    project.commit("the review")
    project.write("docs/01-spec/spec.md", SPEC.replace("2 kg at", "2.5 kg at"))
    fix = project.commit("the fix")
    review(project, fix, finding("F2", None, "holds"), path=RECHECK,
           rechecks=REVIEW)
    fixed_by_recheck(project, sha)
    project.commit("rechecked")
    assert project.gate()["closed"].state == "pass"


def test_a_reopened_recheck_leaves_the_finding_open(project):
    sha = spec_branch(project)
    review(project, sha, finding("F2"))
    fix = project.commit("the review")
    review(project, fix, finding("F2", None, "reopened"), path=RECHECK,
           rechecks=REVIEW)
    fixed_by_recheck(project, sha)
    project.commit("rechecked: reopened")
    verdict = project.gate()
    assert verdict["closed"].state == "fail"
    assert "reopened" in verdict["closed"].detail


def test_a_later_recheck_that_reopens_overrides_one_that_held(project):
    sha = spec_branch(project)
    review(project, sha, finding("F2"))
    first = project.commit("the review")
    review(project, first, finding("F2", None, "holds"), path=RECHECK,
           rechecks=REVIEW)
    fixed_by_recheck(project, sha)
    second = project.commit("rechecked: holds")
    review(project, second, finding("F2", None, "reopened"), path=RECHECK_2,
           rechecks=REVIEW)
    project.commit("rechecked again: reopened")
    verdict = project.gate()
    assert verdict["closed"].state == "fail"
    assert RECHECK_2 in verdict["closed"].detail


# --- 7. a number moved after a review is named in a closure's moves ------------
def moved_after_review(project, closure):
    sha = spec_branch(project)
    review(project, sha, finding("F2", "MAJOR", "accepted", closure))
    project.commit("the review")
    project.write("ledger.toml", LEDGER.replace("value = 0.3", "value = 0.35"))
    project.commit("a longer arm, after the review")
    return project.gate()


def test_a_number_moved_after_the_review_and_named_in_moves_passes(project):
    verdict = moved_after_review(
        project, '{ reason = "r", moves = ["mechanism.l1"] }')
    assert verdict["moves"].state == "pass"


def test_a_number_moved_after_the_review_and_named_nowhere_fails(project):
    verdict = moved_after_review(
        project, '{ reason = "r", moves = ["mechanism.m2"] }')
    assert verdict["moves"].state == "fail"
    assert "mechanism.l1" in verdict["moves"].detail


def test_a_number_moved_before_the_review_needs_no_moves(project):
    project.branch("armature/spec-arm")
    project.write("ledger.toml", LEDGER.replace("value = 0.3", "value = 0.35"))
    sha = project.commit("a longer arm")
    review(project, sha, finding("F1", "MINOR"), artifacts=["ledger.toml"])
    project.commit("the review")
    verdict = project.gate()
    assert verdict["review"].state == "pass"
    assert verdict["moves"].state == "pass"


# --- the red team's own examples (agents/red-team.md, #156) ----------------------
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "gate"
PLACEHOLDER = re.compile(r'reviewed = "[0-9a-f]{40}"')


def example(name, sha):
    """The red team's example file `name`, pinned to `sha`."""
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return PLACEHOLDER.sub(f'reviewed = "{sha}"', text)


def test_the_parser_reads_the_red_teams_examples():
    sha = "0" * 40
    found = reviews.parse(example("review_example.md", sha), REVIEW)
    assert found.reviewed == sha
    assert found.artifacts[-1] == "ledger.toml"
    assert [(f.id, f.severity, f.status) for f in found.findings] == [
        ("F1", "BLOCKER", "open"), ("F2", "MAJOR", "open"),
        ("F3", "MINOR", "open"), ("F4", "QUESTION", "open")]
    recheck = reviews.parse(example("recheck_example.md", sha), RECHECK)
    assert recheck.rechecks == REVIEW
    assert recheck.findings == {"F1": "holds", "F2": "reopened"}


def test_the_red_teams_examples_close_f1_and_leave_f2_open(project):
    sha = spec_branch(project)
    project.write(REVIEW, example("review_example.md", sha))
    reviewed = project.commit("the review")
    assert "F1" in project.gate()["closed"].detail
    text = example("review_example.md", sha).replace(
        'id = "F1"\nseverity = "BLOCKER"\nstatus = "open"',
        f'id = "F1"\nseverity = "BLOCKER"\nstatus = "fixed"\n'
        f'closure = {{ recheck = "{RECHECK}" }}')
    project.write(REVIEW, text)
    project.write(RECHECK, example("recheck_example.md", reviewed))
    project.commit("rechecked")
    detail = project.gate()["closed"].detail
    assert "F1" not in detail
    assert "F2 (MAJOR)" in detail


# --- 3. green stamps for every run_all.py ---------------------------------------
PASSING = "print('All self-tests passed across all milestones.')\n"
FAILING = "raise AssertionError('F2: payload 2.9 kg < 3 kg')\n"


class Runner:
    """Runs a `run_all.py` with this Python, recording each run as
    (folder, the folder whose environment it ran in)."""

    def __init__(self):
        self.runs = []

    def __call__(self, folder, project):
        self.runs.append((folder, project))
        run = subprocess.run([sys.executable, "run_all.py"], cwd=folder,
                             capture_output=True, text=True,
                             encoding="utf-8")
        return run.returncode == 0, run.stdout + run.stderr


def model(project, run_all=PASSING, lock="version = 1\n"):
    project.branch("armature/m1-kinematics")
    project.write("analysis/model/run_all.py", run_all)
    project.write("analysis/model/uv.lock", lock)
    review(project, project.commit("m1"), finding("F1", "MINOR"))
    project.commit("the review")


def stamps(project):
    return sorted((project.root / ".armature" / "runs").glob("*.json"))


def test_no_run_all_passes_the_stamps_item(project):
    assert project.gate(verify=True)["stamps"].state == "pass"


def test_a_passing_run_writes_a_stamp_that_verify_reads(project):
    model(project)
    runner = Runner()
    assert project.gate(runner=runner)["stamps"].state == "pass"
    assert len(runner.runs) == 1 and len(stamps(project)) == 1
    assert project.gate(verify=True)["stamps"].state == "pass"
    assert project.gate(runner=runner)["stamps"].state == "pass"
    assert len(runner.runs) == 1, "a stamp matching the content is reused"
    project.gate(runner=runner, fresh=True)
    assert len(runner.runs) == 2, "--fresh ignores the cache"


def test_verify_never_runs_and_fails_without_a_stamp(project):
    model(project)
    runner = Runner()
    verdict = project.gate(verify=True, runner=runner)
    assert verdict["stamps"].state == "fail"
    assert "analysis/model" in verdict["stamps"].detail
    assert runner.runs == []


def test_a_failing_run_fails_and_writes_no_stamp(project):
    model(project, run_all=FAILING)
    verdict = project.gate(runner=Runner())
    assert verdict["stamps"].state == "fail"
    assert "payload 2.9 kg" in verdict["stamps"].detail
    assert stamps(project) == []


@pytest.mark.parametrize("path, text", [
    ("analysis/model/uv.lock", "version = 2\n"),
    ("ledger.toml", LEDGER.replace('ref = "spec §3" }',
                                   'ref = "spec §3" }\nnote = "arm"')),
    ("analysis/model/kinematics.py", "L1 = 1\n"),
])
def test_a_stamp_misses_on_a_new_lock_ledger_or_folder(project, path, text):
    model(project)
    project.gate(runner=Runner())
    project.write(path, text)
    project.commit("a change the stamp is keyed on")
    assert project.gate(verify=True)["stamps"].state == "fail"


def test_a_dirty_tree_is_run_and_never_stamped(project):
    model(project)
    project.write("analysis/model/scratch.py", "x = 1\n")
    verdict = project.gate(runner=Runner())
    assert verdict["stamps"].state == "fail"
    assert "uncommitted" in verdict["stamps"].detail
    assert stamps(project) == []


def test_a_cad_folder_runs_in_the_models_environment_and_keys_its_lock(
        project):
    """The model's uv.lock is in the model folder's own tree, so only a
    folder that borrows the model's environment shows a key that left the
    lock out."""
    model(project)
    project.write("cad/parts/run_all.py", PASSING)
    project.commit("the parts")
    runner = Runner()
    assert project.gate(runner=runner)["stamps"].state == "pass"
    cad = [project_ for folder, project_ in runner.runs
           if folder.name == "parts"]
    assert cad == [project.root / "analysis" / "model"]
    project.write("analysis/model/uv.lock", "version = 2\n")
    project.commit("a new lock")
    detail = project.gate(verify=True)["stamps"].detail
    assert "cad/parts" in detail and "analysis/model" in detail


def test_a_branch_not_checked_out_is_not_run(project):
    model(project)
    project.checkout("main")
    runner = Runner()
    verdict = project.gate(branch="armature/m1-kinematics", runner=runner)
    assert verdict["stamps"].state == "fail"
    assert runner.runs == []


# --- 4. the engine source in step ---------------------------------------------
PLUGIN = Path(__file__).resolve().parents[2] / ".claude-plugin" / "plugin.json"
VERSION = json.loads(PLUGIN.read_text(encoding="utf-8"))["version"]
SOURCE = ('{{ git = "https://github.com/rioharper/armature", tag = "{}", '
          'subdirectory = "engine" }}')


def pinned(project, source):
    project.branch("armature/m0-setup")
    project.write("analysis/model/run_all.py", PASSING)
    project.write("analysis/model/pyproject.toml", f"""\
        [project]
        name = "arm-model"
        version = "0.1.0"
        dependencies = ["armature-engine"]

        [tool.uv.sources]
        armature-engine = {source}
        """)
    project.commit("the model's engine")
    return project.gate(verify=True)["engine"]


def test_no_model_directory_passes_the_engine_item(project):
    assert project.gate(verify=True)["engine"].state == "pass"


def test_a_model_on_the_plugins_tag_is_in_step(project):
    result = pinned(project, SOURCE.format(f"v{VERSION}"))
    assert result.state == "pass"
    assert f"in-step v{VERSION}" in result.detail


def test_a_model_behind_the_plugins_tag_fails(project):
    result = pinned(project, SOURCE.format("v0.9.0"))
    assert result.state == "fail"
    assert "behind v0.9.0" in result.detail


def test_a_path_pin_passes_as_a_path_pin(project):
    result = pinned(project, '{ path = "../../engine", editable = true }')
    assert result.state == "pass"
    assert "path pin" in result.detail


# --- waivers --------------------------------------------------------------------
def waiver(item="review", scope="armature/work", confirmed="2026-10-20",
           gate="merge"):
    lines = ["[[waiver]]", f'gate = "{gate}"', f'item = "{item}"',
             f'scope = "{scope}"',
             'reason = "a template copy: nothing in it is a claim"']
    if confirmed:
        lines.append(f"confirmed = {confirmed}")
    return "\n".join(lines) + "\n"


def unreviewed(project, *waivers):
    project.branch("armature/work")
    project.write("analysis/model/kinematics.py", "L1 = 1\n")
    if waivers:
        project.write("waivers.toml", "\n".join(waivers))
    project.commit()
    return project.gate()


def test_a_confirmed_waiver_waives_its_item_with_its_reason(project):
    verdict = unreviewed(project, waiver())
    assert verdict["review"].state == "waived"
    assert "a template copy" in verdict["review"].detail
    assert verdict.passed


def test_a_standing_waiver_applies_on_any_branch(project):
    assert unreviewed(project, waiver(scope="standing"))["review"].state \
        == "waived"


@pytest.mark.parametrize("kw", [{"scope": "armature/other"},
                                {"gate": "buy"}, {"item": "closed"}])
def test_a_waiver_for_another_branch_gate_or_item_does_not_apply(
        project, kw):
    assert unreviewed(project, waiver(**kw))["review"].state == "fail"


def test_a_waiver_with_no_confirmed_date_is_ignored_with_a_warning(project):
    verdict = unreviewed(project, waiver(confirmed=None))
    assert verdict["review"].state == "fail"
    assert any("confirmed" in w for w in verdict.warnings)
    assert any(line.startswith("warning ") for line in verdict.lines())


@pytest.mark.parametrize("item", ["fast-forward", "ledger", "stamps",
                                  "engine", "review", "closed", "moves"])
def test_every_item_can_be_waived(project, item):
    """A branch failing every item it can at once: all but `review`, or,
    with no review, `review`. Its one waiver waives its item alone."""
    project.branch("armature/work")
    project.write("waivers.toml", waiver(item=item))
    project.commit()
    project.checkout("main")
    project.write("docs/notes.md", "main moves on\n")
    project.commit()
    project.checkout("armature/work")
    project.write("ledger.toml", LEDGER.replace('band = [0.72, 0.88]\n', ""))
    project.write("analysis/model/run_all.py", PASSING)
    project.write("analysis/model/pyproject.toml", "[tool.uv.sources]\n"
                  f"armature-engine = {SOURCE.format('v0.9.0')}\n")
    sha = project.commit("everything wrong")
    if item != "review":
        review(project, sha, finding("F1"))
        project.commit("an open major")
        project.write("ledger.toml", LEDGER.replace(
            'band = [0.72, 0.88]\n', "").replace("value = 0.3", "value = 0.4"))
        project.commit("moved after the review")
    verdict = project.gate(verify=True)
    assert verdict[item].state == "waived"
    assert "a template copy" in verdict[item].detail
    assert [r.state for r in verdict.results].count("waived") == 1
    assert [r.state for r in verdict.results].count("pass") == (
        2 if item == "review" else 1)   # closed and moves; or review


# --- the CLI --------------------------------------------------------------------
LINE = re.compile(r"(pass|fail|waived) [a-z-]+ .+")


def gate(*args, cwd):
    return subprocess.run([sys.executable, "-m", "armature.gate", *args],
                          cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8")


def test_merge_prints_a_line_per_item_and_exits_1_on_a_failure(project):
    project.branch("armature/work")
    project.write("analysis/model/kinematics.py", "L1 = 1\n")
    project.commit()
    run = gate("merge", cwd=project.root)
    lines = run.stdout.splitlines()
    assert [line.split()[1] for line in lines] == [
        "fast-forward", "ledger", "stamps", "engine", "review", "closed",
        "moves"]
    assert all(LINE.fullmatch(line) for line in lines)
    assert run.returncode == 1
    assert lines[4].startswith("fail review")


def test_merge_exits_0_when_every_item_passes(project):
    project.branch("armature/work")
    project.write("docs/decisions.md", "# Decisions\n")
    project.commit()
    run = gate("merge", cwd=project.root)
    assert run.returncode == 0, run.stdout + run.stderr


def test_a_detached_head_with_no_branch_named_is_an_error(project):
    project.git("checkout", "-q", "--detach")
    run = gate("status", cwd=project.root)
    assert run.returncode == 2
    assert "--branch" in run.stderr


STATUS = """\
import json, runpy, sys, time
sys.argv = ["armature.gate", "status", "--json"]
start = time.perf_counter()
try:
    runpy.run_module("armature.gate", run_name="__main__")
except SystemExit as e:
    code = e.code
print(json.dumps({"code": code, "seconds": time.perf_counter() - start,
                  "mujoco": "mujoco" in sys.modules}), file=sys.stderr)
"""


def test_status_with_stamps_is_fast_and_loads_no_mujoco(project):
    model(project)
    project.gate(runner=Runner())
    start = time.perf_counter()
    run = subprocess.run([sys.executable, "-c", STATUS], cwd=project.root,
                         capture_output=True, text=True, encoding="utf-8")
    seconds = time.perf_counter() - start
    report = json.loads(run.stderr.strip().splitlines()[-1])
    assert report["mujoco"] is False
    assert seconds < 5
    verdicts = json.loads(run.stdout)
    assert [v["gate"] for v in verdicts] == ["merge"]
    assert verdicts[0]["branch"] == "armature/m1-kinematics"
    states = {i["item"]: i["state"] for i in verdicts[0]["items"]}
    assert states["stamps"] == "pass"
    assert report["code"] == 0, run.stdout
