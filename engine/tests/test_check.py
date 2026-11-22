"""`armature.check` (ADR 0013): `ledger check`, then every `run_all.py`,
run when asked, with nothing cached. The runner is swapped for one that
records its calls, so no test starts uv.
"""

import textwrap

import pytest

from armature import check

LEDGER = """\
[mechanism.l1]
value = 0.30
unit = "m"
as_written = "300 mm"
source = { kind = "chosen", ref = "docs/decisions.md" }
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "ledger.toml").write_text(LEDGER, encoding="utf-8")
    for folder in ("analysis/model", "cad/parts/ARM-001", ".venv/lib"):
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "run_all.py").write_text("", encoding="utf-8")
    (tmp_path / "analysis/model/pyproject.toml").write_text(
        "", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def runner(failing=()):
    calls = []

    def run(root, folder):
        calls.append(folder)
        return folder not in failing
    return run, calls


def test_it_finds_each_run_all_and_skips_dot_folders(project):
    assert check.folders(project) == ["analysis/model", "cad/parts/ARM-001"]


def test_a_part_folder_runs_in_the_models_environment(project):
    assert check.environment(project, "analysis/model") == "analysis/model"
    assert check.environment(project, "cad/parts/ARM-001") == "analysis/model"


def test_everything_green_exits_0_with_a_line_per_item(project, capsys):
    run, calls = runner()
    assert check.main([], runner=run) == 0
    assert calls == ["analysis/model", "cad/parts/ARM-001"]
    assert capsys.readouterr().out.splitlines()[-3:] == [
        "pass ledger", "pass analysis/model", "pass cad/parts/ARM-001"]


def test_a_failing_run_fails_the_check_and_the_rest_still_run(project, capsys):
    run, calls = runner(failing=["analysis/model"])
    assert check.main([], runner=run) == 1
    assert calls == ["analysis/model", "cad/parts/ARM-001"]
    assert "fail analysis/model" in capsys.readouterr().out


def test_a_named_folder_runs_alone(project):
    run, calls = runner()
    assert check.main(["cad/parts/ARM-001/"], runner=run) == 0
    assert calls == ["cad/parts/ARM-001"]


def test_a_folder_with_no_run_all_is_an_error(project, capsys):
    run, calls = runner()
    assert check.main(["docs"], runner=run) == 1
    assert calls == []
    assert "no run_all.py in docs" in capsys.readouterr().err


def test_a_ledger_error_fails_the_check(project, capsys):
    (project / "ledger.toml").write_text(textwrap.dedent("""\
        [mechanism.l1]
        value = 0.30
        unit = "m"
        as_written = "310 mm"
        source = { kind = "chosen", ref = "docs/decisions.md" }
        """), encoding="utf-8")
    run, _ = runner()
    assert check.main([], runner=run) == 1
    assert "fail ledger" in capsys.readouterr().out
