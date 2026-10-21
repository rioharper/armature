"""The hook's decision (ADR 0011, #158): `decide(tool_name, tool_input,
cwd)`, on fixture git repos built here, with the gate itself injected.

Answer: each decision is worked from #154's *The hook* by hand, never from
`decide`'s own output. A merge, `gh pr merge` or push into `main` asks the
gate, and a failing verdict denies with its lines; a commit on `main` is
denied when it touches gated paths outside the rendered sections or does
more to the ledger than add or edit candidate entries; an edit under
`.armature/` is denied; an edit that confirms, accepts or waives is asked
about. Outside a project with a root `ledger.toml` nothing is decided. The
trap: a gated command hidden in a compound, behind `cd`, in `$()`, or after
the `git checkout main` that makes it gated, which a hook reading only the
first word would let through; and a commit message whose heredoc names a
merge, which a hook reading every word would deny.
"""

import json
import subprocess
import sys
import textwrap

import pytest

from armature.gate import Result, Verdict
from armature.gate.hook import decide

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

SPEC = """\
# Spec

The arm lifts 2 kg.

<!-- ledger:req -->
| REQ | value |
|---|---|
<!-- /ledger -->
"""


class Project:
    """An Armature project in a git repo: a root `ledger.toml` and a spec,
    committed on `main`."""

    def __init__(self, root, ledger=True):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")
        if ledger:
            self.write("ledger.toml", LEDGER)
        self.write("docs/01-spec/spec.md", SPEC)
        self.commit("the scaffold")

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
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def branch(self, name):
        self.git("checkout", "-q", "-b", name)

    def checkout(self, name):
        self.git("checkout", "-q", name)

    def work(self, name="armature/spec-arm"):
        """A work branch with one commit, `main` checked out again."""
        self.branch(name)
        self.write("docs/decisions.md", "# Decisions\n")
        self.commit()
        self.checkout("main")
        return name


class Gate:
    """The gate, injected: records each (root, branch) it is asked about
    and answers with the verdict it was given."""

    def __init__(self, passed=False):
        self.passed = passed
        self.asked = []

    def __call__(self, root, branch):
        self.asked.append((root, branch))
        state = "pass" if self.passed else "fail"
        return Verdict("merge", branch, "0" * 40, [
            Result("fast-forward", "pass", "main is an ancestor"),
            Result("closed", state, "docs/reviews/r.md F2 (MAJOR) is open")])


@pytest.fixture
def project(tmp_path):
    return Project(tmp_path / "arm")


def bash(command, cwd, gate=None, **kw):
    return decide("Bash", {"command": command}, str(cwd), gate=gate, **kw)


# --- scope ------------------------------------------------------------------
def test_without_a_root_ledger_nothing_is_decided(tmp_path):
    plain = Project(tmp_path / "plain", ledger=False)
    plain.work()
    gate = Gate()
    assert bash("git merge armature/spec-arm", plain.root, gate) is None
    assert decide("Write", {"file_path": str(plain.root / ".armature/x"),
                            "content": "{}"}, str(plain.root)) is None
    assert gate.asked == []


# --- git merge with main checked out ----------------------------------------
def test_a_merge_into_main_is_denied_with_the_gates_lines(project):
    branch = project.work()
    gate = Gate()
    decision = bash(f"git merge --ff-only {branch}", project.root, gate)
    assert decision.permission == "deny"
    assert "fail closed docs/reviews/r.md F2 (MAJOR) is open" in \
        decision.reason
    assert [b for _, b in gate.asked] == [branch]


def test_a_merge_the_gate_passes_is_left_to_the_user(project):
    branch = project.work()
    assert bash(f"git merge {branch}", project.root, Gate(True)) is None


def test_a_merge_on_a_work_branch_is_not_gated(project):
    branch = project.work()
    project.checkout(branch)
    gate = Gate()
    assert bash("git merge main", project.root, gate) is None
    assert gate.asked == []


@pytest.mark.parametrize("form", [
    "cd {root} && git merge {branch}",
    "git -C {root} merge {branch}",
    "git checkout {branch} && git commit --allow-empty -m wip; "
    "git checkout main && git merge {branch}",
    'echo "merged: $(git merge {branch})"',
    "git status\ngit merge {branch} 2>&1 | tee merge.log",
    "(cd {root}; git merge --no-edit {branch})",
    "bash -c 'git merge {branch}'",
])
def test_a_merge_into_main_in_a_compound_is_still_gated(project, tmp_path,
                                                         form):
    branch = project.work()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    command = form.format(root=project.root.as_posix(), branch=branch)
    gate = Gate()
    decision = bash(command, elsewhere if "{root}" in form else project.root,
                    gate)
    assert decision is not None and decision.permission == "deny", command
    assert branch in [b for _, b in gate.asked]


def test_a_heredoc_that_names_a_merge_is_a_message_not_a_command(project):
    project.work()
    gate = Gate()
    command = ("git commit --allow-empty -m \"$(cat <<'EOF'\n"
               "Merge (the plan\ngit merge armature/spec-arm\nEOF\n)\"")
    assert bash(command, project.root, gate) is None
    assert gate.asked == []


def test_a_merge_of_a_ref_the_gate_cannot_compute_is_denied(project):
    project.work()
    decision = bash("git merge $(git rev-parse armature/spec-arm)",
                    project.root, Gate(True))
    assert decision.permission == "deny"
    assert "name a local branch" in decision.reason


def test_the_merge_is_read_from_powershell_too(project, tmp_path):
    branch = project.work()
    gate = Gate()
    root = str(project.root)              # backslashes on Windows
    decision = decide("PowerShell", {
        "command": f"Set-Location -Path '{root}'; git merge `\n {branch}"},
        str(tmp_path), gate=gate)
    assert decision.permission == "deny"
    assert [b for _, b in gate.asked] == [branch]


# --- gh pr merge -------------------------------------------------------------
def pr_into(base, head="armature/spec-arm", oid=None):
    def pr(root, ref):
        pr.asked = ref
        return {"head": head, "base": base, "oid": oid}
    return pr


def test_gh_pr_merge_into_main_is_gated(project):
    branch = project.work()
    project.checkout(branch)
    gate = Gate()
    pr = pr_into("main", branch)
    decision = bash("git push -u origin HEAD && gh pr merge 3 --squash "
                    "--delete-branch", project.root, gate, pr=pr)
    assert decision.permission == "deny"
    assert pr.asked == "3"
    assert [b for _, b in gate.asked] == [branch]


def test_gh_pr_merge_into_another_base_is_not(project):
    project.work()
    gate = Gate()
    assert bash("gh pr merge 3", project.root, gate,
                pr=pr_into("armature/plan-arm")) is None
    assert gate.asked == []


def test_gh_pr_merge_of_a_head_the_local_branch_is_not_at_is_denied(
        project):
    branch = project.work()
    decision = bash("gh pr merge", project.root, Gate(True),
                    pr=pr_into("main", branch, oid="f" * 40))
    assert decision.permission == "deny"
    assert "push or pull" in decision.reason


# --- git push to main --------------------------------------------------------
@pytest.mark.parametrize("command, gated", [
    ("git push origin {branch}:main", "{branch}"),
    ("git push origin {branch}:refs/heads/main", "{branch}"),
    ("git checkout {branch}; git push --force origin HEAD:main", "{branch}"),
    ("git push origin main", "main"),
    ("git push", "main"),
    ("git fetch && git push -u origin main 2>/dev/null", "main"),
])
def test_a_push_to_a_main_refspec_is_gated(project, command, gated):
    branch = project.work()
    gate = Gate()
    decision = bash(command.format(branch=branch), project.root, gate)
    assert decision.permission == "deny"
    assert [b for _, b in gate.asked] == [gated.format(branch=branch)]


def test_a_push_of_a_work_branch_is_not_gated(project):
    branch = project.work()
    project.checkout(branch)
    gate = Gate()
    assert bash(f"git push -u origin {branch}", project.root, gate) is None
    assert bash("git push", project.root, gate) is None
    assert gate.asked == []


# --- git commit on main ------------------------------------------------------
CANDIDATE = """
[part.rs02.mass]
value = 0.38
unit = "kg"
status = "candidate"
source = { kind = "datasheet", ref = "rs02", retrieved = 2026-10-01 }
"""


def staged(project, path, text):
    project.write(path, text)
    project.git("add", path)


def test_a_candidate_only_ledger_edit_commits_on_main(project):
    staged(project, "ledger.toml", LEDGER.replace("0.8", "0.82") + CANDIDATE)
    assert bash("git commit -m 'm2 re-estimated; rs02 mass'",
                project.root) is None


def test_a_rendered_section_only_edit_commits_on_main(project):
    staged(project, "docs/01-spec/spec.md", SPEC.replace(
        "|---|---|\n", "|---|---|\n| REQ-1 | 2 kg |\n"))
    project.write("docs/01-spec/.gitkeep", "")
    assert bash("git add -A && git commit -m render", project.root) is None


def test_a_spec_text_edit_on_main_is_denied(project):
    staged(project, "docs/01-spec/spec.md",
           SPEC.replace("2 kg", "3 kg"))
    decision = bash("git commit -m 'lift more'", project.root)
    assert decision.permission == "deny"
    assert "docs/01-spec/spec.md" in decision.reason
    assert "on a branch" in decision.reason


@pytest.mark.parametrize("ledger, named", [
    (LEDGER.replace('status = "candidate"', 'status = "confirmed"'),
     "mechanism.m2"),
    (LEDGER.replace("0.3", "0.35"), "mechanism.l1"),
    (LEDGER.split("[mechanism.m2]")[0], "mechanism.m2"),
    (LEDGER + CANDIDATE.replace("candidate", "confirmed"), "part.rs02.mass"),
])
def test_a_ledger_edit_beyond_candidates_on_main_is_denied(project, ledger,
                                                           named):
    staged(project, "ledger.toml", ledger)
    decision = bash("git commit -m ledger", project.root)
    assert decision.permission == "deny"
    assert named in decision.reason


def test_an_unstaged_edit_a_compound_stages_is_seen(project):
    project.write("analysis/model/arm.py", "L1 = 0.3\n")
    assert bash("git commit --allow-empty -m nothing-staged",
                project.root) is None
    for command in ("git add -A && git commit -m model",
                    "git commit -am model analysis/model/arm.py",
                    "git add . ; git commit -m model"):
        decision = bash(command, project.root)
        assert decision.permission == "deny", command
        assert "model code analysis/model/arm.py" in decision.reason


def test_a_commit_on_a_work_branch_is_not_the_main_rule(project):
    project.branch("armature/spec-arm")
    staged(project, "docs/01-spec/spec.md", SPEC.replace("2 kg", "3 kg"))
    assert bash("git commit -m 'lift more'", project.root) is None
    project.checkout("main")
    assert bash("git checkout armature/spec-arm && git commit -m x",
                project.root) is None


# --- edits -------------------------------------------------------------------
def edit(project, path, old, new, **kw):
    return decide("Edit", {"file_path": str(project.root / path),
                           "old_string": old, "new_string": new, **kw},
                  str(project.root))


@pytest.mark.parametrize("tool, args", [
    ("Write", {"content": '{"green": true}'}),
    ("Edit", {"old_string": "a", "new_string": "b"}),
    ("MultiEdit", {"edits": [{"old_string": "a", "new_string": "b"}]}),
])
def test_an_edit_under_armature_is_denied(project, tool, args):
    path = project.root / ".armature" / "runs" / "k.json"
    decision = decide(tool, {"file_path": str(path), **args},
                      str(project.root))
    assert decision.permission == "deny"
    assert ".armature/" in decision.reason


def test_setting_an_entry_confirmed_is_asked(project):
    decision = edit(project, "ledger.toml", 'status = "candidate"',
                    'status = "confirmed"')
    assert decision.permission == "ask"
    assert "mechanism.m2" in decision.reason
    assert edit(project, "ledger.toml", "0.72", "0.70") is None


REVIEW = """\
# Spec review

```toml
reviewed = "{sha}"
artifacts = ["docs/01-spec/spec.md"]

[[finding]]
id = "F2"
severity = "MAJOR"
status = "open"
```
"""


def test_accepting_a_finding_is_asked(project):
    path = "docs/reviews/2026-10-21-spec-review.md"
    project.write(path, REVIEW.format(sha="a" * 40))
    decision = edit(project, path, 'status = "open"',
                    'status = "accepted"\nclosure = { reason = "fine" }')
    assert decision.permission == "ask"
    assert "F2" in decision.reason
    written = decide("Write", {
        "file_path": str(project.root / "docs/reviews/2026-10-22-r-review.md"),
        "content": REVIEW.format(sha="b" * 40).replace("open", "accepted")},
        str(project.root))
    assert written.permission == "ask"


def test_adding_a_waiver_is_asked(project):
    project.write("waivers.toml", "# Waivers, each confirmed by the user\n")
    decision = edit(project, "waivers.toml", "user\n", (
        'user\n\n[[waiver]]\ngate = "merge"\nitem = "review"\n'
        'scope = "armature/m0-setup"\nreason = "a template copy"\n'
        'confirmed = 2026-10-21\n'))
    assert decision.permission == "ask"
    assert "merge review, armature/m0-setup" in decision.reason


def test_the_hook_reads_the_event_and_asks_the_real_gate(project):
    """The thin wrapper, end to end: the event on stdin, the decision's
    JSON on stdout, and the gate `merge` itself, verifying. The branch
    changes spec text and no review is pinned on it, so item 5 fails."""
    project.branch("armature/spec-arm")
    project.write("docs/01-spec/spec.md", SPEC.replace("2 kg", "3 kg"))
    project.commit()
    project.checkout("main")

    def hook(event):
        return subprocess.run(
            [sys.executable, "-c", "import sys, armature.gate.hook as h; "
             "r = h.main(); print('mujoco' in sys.modules, file=sys.stderr);"
             " sys.exit(r)"], input=json.dumps(event).encode("utf-8"),
            capture_output=True, check=True)
    run = hook({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                "cwd": str(project.root),
                "tool_input": {"command": "git merge armature/spec-arm"}})
    out = json.loads(run.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    assert "fail review" in out["permissionDecisionReason"]
    assert run.stderr.decode().strip() == "False"
    quiet = hook({"tool_name": "Bash", "cwd": str(project.root),
                  "tool_input": {"command": "git status"}})
    assert quiet.stdout == b""


def test_an_edit_that_confirms_nothing_is_left_alone(project):
    assert edit(project, "docs/01-spec/spec.md", "2 kg", "3 kg") is None
    project.write("waivers.toml", "# Waivers\n")
    assert edit(project, "waivers.toml", "# Waivers", "# The waivers") is None
