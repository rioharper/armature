"""`set <name> --from-part <file>`: CAD's mass, COM and inertia written back.

The part file here is a stand-in for a build123d recipe: a script that
prints the export `part.py --mass-properties` prints, so the engine's half
is tested without build123d. The part template's own checks run the real
recipe through the same command.

Answer: each expected value is the literal the stand-in prints, and the
ref is the file's path from the ledger's folder, `@` the revision git gives.
"""

import json
import subprocess
import sys
import textwrap

import numpy as np
import pytest

from armature.ledger import LedgerError, check, load
from armature.ledger.write import set_from_part

PROPS = {
    "mass": 0.1047,
    "com": [0.0, 0.0, 0.0047],
    "inertia": [[5.1e-5, 0.0, 0.0], [0.0, 4.6e-5, 0.0], [0.0, 0.0, 9.3e-5]],
    "point": "ARM-BRK-001's COM",
    "axes": "X along the plate's length, Z up the boss",
    "origin": "the mounting face's centre",
}

LEDGER = """\
# the project's ledger
[mechanism.m2]
value = 0.80  # the forearm, until CAD measures it
unit = "kg"
band = [0.72, 0.88]
status = "confirmed"
source = { kind = "estimate", ref = "the forearm's mass budget" }
"""


def project(tmp_path, props=PROPS, ledger=LEDGER):
    """A project: its ledger at the root, and a part file in cad/parts/
    whose export prints `props`."""
    (tmp_path / "ledger.toml").write_text(ledger, encoding="utf-8")
    parts = tmp_path / "cad" / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    part = parts / "ARM-BRK-001.py"
    part.write_text(textwrap.dedent(f"""\
        import json, sys
        assert sys.argv[1:] == ["--mass-properties"], sys.argv
        print(json.dumps({json.dumps(props)}))
        """), encoding="utf-8")
    return part


def test_set_writes_mass_com_and_inertia_as_cad_candidates(tmp_path):
    part = project(tmp_path)
    set_from_part("part.ARM-BRK-001", part, path=tmp_path)
    ledger = load(path=tmp_path)
    mass, com, inertia = (ledger[f"part.ARM-BRK-001.{k}"]
                          for k in ("mass", "com", "inertia"))
    assert mass.value == 0.1047 and mass.unit == "kg"
    np.testing.assert_array_equal(com.value, [0.0, 0.0, 0.0047])
    assert com.unit == "m"
    np.testing.assert_array_equal(inertia.value, np.diag([5.1e-5, 4.6e-5,
                                                          9.3e-5]))
    assert inertia.unit == "kg*m^2"
    assert (inertia.point, inertia.axes) == ("ARM-BRK-001's COM",
                                             PROPS["axes"])
    for e in (mass, com, inertia):
        assert e.source == {"kind": "cad",
                            "ref": "cad/parts/ARM-BRK-001.py@uncommitted"}
        assert e.status == "candidate"
    assert check(tmp_path) == []


def test_a_second_run_changes_nothing(tmp_path):
    part = project(tmp_path)
    assert len(set_from_part("part.ARM-BRK-001", part, path=tmp_path)) == 3
    first = (tmp_path / "ledger.toml").read_bytes()
    assert set_from_part("part.ARM-BRK-001", part, path=tmp_path) == []
    assert (tmp_path / "ledger.toml").read_bytes() == first


def test_comments_and_order_survive_set(tmp_path):
    part = project(tmp_path)
    set_from_part("part.ARM-BRK-001", part, path=tmp_path)
    text = (tmp_path / "ledger.toml").read_text(encoding="utf-8")
    assert text.startswith(LEDGER)
    # A comment beside an entry set rewrites survives the rewrite.
    text = text.replace('[part.ARM-BRK-001.mass]\nvalue = 0.1047\n',
                        '[part.ARM-BRK-001.mass]  # the bracket, as modeled\n'
                        'value = 0.1047\nnote = "sketch grade"\n')
    moved = project(tmp_path, PROPS | {"mass": 0.1102}, ledger=text)
    assert set_from_part("part.ARM-BRK-001", moved, path=tmp_path) == [
        "part.ARM-BRK-001.mass"]
    after = (tmp_path / "ledger.toml").read_text(encoding="utf-8")
    assert "[part.ARM-BRK-001.mass]  # the bracket, as modeled\n" in after
    assert "value = 0.80  # the forearm, until CAD measures it" in after
    assert after.count(
        'source = { kind = "cad", ref = "cad/parts/ARM-BRK-001.py@uncommitted"'
        ' }\n') == 3
    assert load(path=tmp_path)["part.ARM-BRK-001.mass"].note == "sketch grade"
    assert load("part.ARM-BRK-001", path=tmp_path)["mass"] == 0.1102


SPLIT = LEDGER + """
[part.al-6061-t6.density]
value = 2700.0  # the stock's
unit = "kg/m^3"
source = { kind = "chosen", ref = "spec §6" }

# --- budget: the bracket's line ---

[budget.mass.ARM-BRK-001]
value = 0.105
unit = "kg"
source = { kind = "chosen", ref = "spec §9" }
"""


def test_new_entries_go_at_the_end_under_no_one_elses_comment(tmp_path):
    part = project(tmp_path, ledger=SPLIT)
    set_from_part("part.ARM-BRK-001", part, path=tmp_path)
    text = (tmp_path / "ledger.toml").read_text(encoding="utf-8")
    assert text.startswith(SPLIT + "\n[part.ARM-BRK-001.mass]\n"), text
    assert "\n\n[part.ARM-BRK-001.com]\n" in text
    assert "value = [\n" in text   # a tensor a row a line
    # The part's entries now sit either side of the budget: a moved
    # measurement still lands in its own entry, and nothing else moves.
    moved = project(tmp_path, PROPS | {"mass": 0.1102}, ledger=text)
    assert set_from_part("part.ARM-BRK-001", moved, path=tmp_path) == [
        "part.ARM-BRK-001.mass"]
    after = (tmp_path / "ledger.toml").read_text(encoding="utf-8")
    assert after == text.replace("value = 0.1047\n", "value = 0.1102\n")
    assert check(tmp_path) == []


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_the_files_line_endings_are_kept(tmp_path, newline):
    part = project(tmp_path)
    (tmp_path / "ledger.toml").write_bytes(
        SPLIT.replace("\n", newline).encode("utf-8"))
    set_from_part("part.ARM-BRK-001", part, path=tmp_path)
    data = (tmp_path / "ledger.toml").read_bytes()
    bare = data.replace(b"\r\n", b"")
    assert b"\n" not in bare and b"\r" not in bare if newline == "\r\n" \
        else b"\r" not in data, data
    assert data.startswith(SPLIT.replace("\n", newline).encode("utf-8"))


def test_a_moved_measurement_is_a_candidate_again(tmp_path):
    part = project(tmp_path)
    set_from_part("part.ARM-BRK-001", part, path=tmp_path)
    path = tmp_path / "ledger.toml"
    confirmed = path.read_text(encoding="utf-8").replace(
        'status = "candidate"', 'status = "confirmed"')
    path.write_text(confirmed, encoding="utf-8")
    # The same measurement from the same rev keeps the user's confirmation.
    assert set_from_part("part.ARM-BRK-001", part, path=tmp_path) == []
    assert load(path=tmp_path)["part.ARM-BRK-001.mass"].status == "confirmed"
    moved = project(tmp_path, PROPS | {"mass": 0.1102}, ledger=confirmed)
    set_from_part("part.ARM-BRK-001", moved, path=tmp_path)
    ledger = load(path=tmp_path)
    assert ledger["part.ARM-BRK-001.mass"].status == "candidate"
    assert ledger["part.ARM-BRK-001.com"].status == "confirmed"


@pytest.mark.parametrize("field", ["point", "axes", "origin"])
def test_a_measurement_without_its_frame_is_refused(tmp_path, field):
    part = project(tmp_path, {k: v for k, v in PROPS.items() if k != field})
    with pytest.raises(LedgerError, match=f"frame.*'{field}' is missing"):
        set_from_part("part.ARM-BRK-001", part, path=tmp_path)
    assert (tmp_path / "ledger.toml").read_text(encoding="utf-8") == LEDGER


def test_a_tensor_the_ledger_refuses_leaves_the_ledger_as_it_was(tmp_path):
    skew = PROPS | {"inertia": [[5e-5, 1e-6, 0], [0, 5e-5, 0], [0, 0, 9e-5]]}
    part = project(tmp_path, skew)
    with pytest.raises(LedgerError, match="not symmetric"):
        set_from_part("part.ARM-BRK-001", part, path=tmp_path)
    assert (tmp_path / "ledger.toml").read_text(encoding="utf-8") == LEDGER


def test_set_writes_only_a_parts_entries(tmp_path):
    part = project(tmp_path)
    with pytest.raises(LedgerError, match="part.<pn>"):
        set_from_part("mechanism.m2", part, path=tmp_path)


def test_a_failing_export_is_refused_with_its_error(tmp_path):
    part = project(tmp_path)
    part.write_text("raise SystemExit('no build123d here')\n",
                    encoding="utf-8")
    with pytest.raises(LedgerError, match="no build123d here"):
        set_from_part("part.ARM-BRK-001", part, path=tmp_path)


def test_the_ref_names_the_commit_the_part_file_was_measured_at(tmp_path):
    part = project(tmp_path)
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t",
           "-c", "user.email=t@t.invalid"]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "cad"], check=True)
    subprocess.run(git + ["commit", "-qm", "the bracket"], check=True)
    rev = subprocess.run(git + ["rev-parse", "--short", "HEAD"], check=True,
                         capture_output=True, text=True).stdout.strip()
    set_from_part("part.ARM-BRK-001", part, path=tmp_path)
    ref = load(path=tmp_path)["part.ARM-BRK-001.mass"].source["ref"]
    assert ref == f"cad/parts/ARM-BRK-001.py@{rev}"
    part.write_text(part.read_text() + "# edited\n")
    set_from_part("part.ARM-BRK-001", part, path=tmp_path)
    ref = load(path=tmp_path)["part.ARM-BRK-001.mass"].source["ref"]
    assert ref == f"cad/parts/ARM-BRK-001.py@{rev}+dirty"


def ledger(*args, cwd):
    return subprocess.run([sys.executable, "-m", "armature.ledger", *args],
                          cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8")


def test_set_from_the_shell_prints_what_it_set_and_exits_0(tmp_path):
    project(tmp_path)
    args = ("set", "part.ARM-BRK-001", "--from-part",
            "cad/parts/ARM-BRK-001.py")
    run = ledger(*args, cwd=tmp_path)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == [
        f"set part.ARM-BRK-001.{k}" for k in ("mass", "com", "inertia")]
    run = ledger(*args, cwd=tmp_path)
    assert (run.returncode, run.stdout) == (0, "part.ARM-BRK-001: "
                                                "unchanged\n")


def test_a_refused_set_from_the_shell_exits_1_saying_why(tmp_path):
    project(tmp_path, {k: v for k, v in PROPS.items() if k != "axes"})
    run = ledger("set", "part.ARM-BRK-001", "--from-part",
                 "cad/parts/ARM-BRK-001.py", cwd=tmp_path)
    assert run.returncode == 1 and "'axes' is missing" in run.stderr
