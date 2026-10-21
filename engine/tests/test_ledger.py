"""The ledger (ADR 0010): load, check and show, against ledgers written here.

Answer: each expected value is worked from the fixture's inputs by hand,
in derivation-standards.md's checks rule: two of a 14.2 g part are
2 × 0.0142 kg, and 88.4 V/krpm is 88.4·60/(2000π) V·s/rad. A literal is an
input or a tolerance. Each finding is shown firing on an entry built to
trip it and silent on the same entry put right.
"""

import datetime
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

from armature.ledger import (Finding, LedgerError, check, load, render,
                              show)


def write(tmp_path, text, name="ledger.toml"):
    path = tmp_path / name
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


ARM = """\
[mechanism.l1]
value = 0.30
unit = "m"
as_written = "300 mm"
source = { kind = "measured", ref = "docs/testing/arm.md" }
status = "confirmed"

[mechanism.m2]
value = 0.80
unit = "kg"
band = [0.72, 0.88]
status = "candidate"
source = { kind = "estimate", ref = "aluminium tube, 1.6 mm wall" }

[mechanism.g]
value = 9.81
unit = "m/s^2"
as_written = "9.81 m/s^2"
source = { kind = "standard", ref = "ISO 80000-3" }
"""


# --- load -----------------------------------------------------------------------
def test_load_returns_a_section_as_plain_si_floats(tmp_path):
    p = load("mechanism", path=write(tmp_path, ARM))
    assert p == {"l1": 0.30, "m2": 0.80, "g": 9.81}
    assert all(type(v) is float for v in p.values())


def test_load_finds_the_nearest_ledger_walking_up(tmp_path, monkeypatch):
    write(tmp_path, ARM)
    deep = tmp_path / "analysis" / "model"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)
    assert load("mechanism")["l1"] == 0.30
    assert load("mechanism", path=deep)["l1"] == 0.30


def test_load_with_no_ledger_above_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(LedgerError, match="ledger.toml"):
        load("mechanism", path=tmp_path)


PART = """\
[part."moteus-r4.11".mass]
value = 0.0142
unit = "kg"
as_written = "14.2 g"
status = "confirmed"
source = { kind = "datasheet", ref = "moteus-r4.11", retrieved = 2026-10-01 }

[part."moteus-r4.11".price]
value = 109.0
unit = "USD"
as_written = "109 USD"
status = "confirmed"
source = { kind = "datasheet", ref = "moteus-r4.11", retrieved = 2026-10-01 }

[budget.mass.allocation]
value = 0.10
unit = "kg"
source = { kind = "chosen", ref = "REQ-04" }

[budget.mass.drivers]
of = "part.moteus-r4.11.mass"
qty = 2

[budget.mass.spares]
of = "budget.mass.drivers"
qty = 3
"""


# PART's inputs, and its budget worked from them: each line is its qty
# times what it reads, and the margin the allocation less their total.
MASS, ALLOCATION = 0.0142, 0.10
DRIVERS = 2 * MASS
SPARES = 3 * DRIVERS
TOTAL = DRIVERS + SPARES
MARGIN = ALLOCATION - TOTAL
KE = 88.4 * 60 / (2000 * np.pi)   # 88.4 V/krpm, in V·s/rad


def shown(x):
    """`x` as the ledger prints it: 6 significant figures."""
    return f"{x:.6g}"


def test_load_resolves_of_with_qty_through_a_two_hop_chain(tmp_path):
    lines = load("budget.mass", path=write(tmp_path, PART))
    assert lines["drivers"] == pytest.approx(DRIVERS, rel=1e-12)
    assert lines["spares"] == pytest.approx(SPARES, rel=1e-12)
    assert lines["allocation"] == ALLOCATION
    assert load("part.moteus-r4.11", path=tmp_path)["mass"] == MASS


def test_load_returns_vectors_and_tensors_as_arrays(tmp_path):
    path = write(tmp_path, """\
        [mechanism.com2]
        value = [0.125, 0.0, 0.0]
        unit = "m"
        source = { kind = "cad", ref = "cad/forearm.py@3" }
        status = "candidate"

        [mechanism.I2]
        value = [[0.00016, 0.0, 0.0], [0.0, 0.006, 1e-5], [0.0, 1e-5, 0.006]]
        unit = "kg*m^2"
        point = "com2"
        axes = "base"
        source = { kind = "cad", ref = "cad/forearm.py@3" }
        status = "candidate"

        [mechanism.I2_twice]
        of = "mechanism.I2"
        qty = 2
        """)
    p = load("mechanism", path=path)
    np.testing.assert_array_equal(p["com2"], [0.125, 0.0, 0.0])
    assert p["I2"].shape == (3, 3) and p["I2"][1, 2] == 1e-5
    np.testing.assert_array_equal(p["I2_twice"], 2 * p["I2"])


def test_load_returns_bands_by_key(tmp_path):
    ledger = load(path=write(tmp_path, ARM))
    assert ledger.bands("mechanism") == {"m2": (0.72, 0.88)}


@pytest.mark.parametrize("entry, words", [
    ('[mechanism.a]\nunit = "m"\nsource = { kind = "chosen", ref = "§3" }',
     ["mechanism.a", "value"]),
    ('[mechanism.a]\nvalue = 1.0\nsource = { kind = "chosen", ref = "§3" }',
     ["mechanism.a", "unit"]),
    ('[mechanism.a]\nvalue = 1.0\nunit = "m"', ["mechanism.a", "source"]),
    ('[mechanism.a]\nvalue = 1.0\nunit = "m"\nsource = { kind = "guess" }',
     ["mechanism.a", "source.kind"]),
    ('[mechanism.a]\nvalue = 1.0\nunit = "m"\nvlaue = 2.0\n'
     'source = { kind = "chosen", ref = "§3" }', ["mechanism.a", "vlaue"]),
    ('[mechanism.a]\nvalue = 1.0\nunit = "m"\nstatus = "TBD"\n'
     'source = { kind = "chosen", ref = "§3" }', ["mechanism.a", "status"]),
    ('[mechanism.a]\nvalue = "1.0"\nunit = "m"\n'
     'source = { kind = "chosen", ref = "§3" }', ["mechanism.a", "value"]),
    ('[mechanism.a]\nvalue = [1.0, 2.0]\nunit = "m"\n'
     'source = { kind = "chosen", ref = "§3" }', ["mechanism.a", "value"]),
    ('[mechanism.a]\nvalue = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]\n'
     'unit = "kg*m^2"\npoint = "com"\n'
     'source = { kind = "cad", ref = "a.py@1" }', ["mechanism.a", "axes"]),
    ('[mechanism.a]\nvalue = [[1.0, 0.5, 0], [0, 1.0, 0], [0, 0, 1.0]]\n'
     'unit = "kg*m^2"\npoint = "com"\naxes = "base"\n'
     'source = { kind = "cad", ref = "a.py@1" }', ["mechanism.a", "symmetric"]),
    ('[mechanism.a]\nvalue = 1.0\nunit = "m"\nband = [1.1, 0.9]\n'
     'source = { kind = "chosen", ref = "§3" }', ["mechanism.a", "band"]),
    ('[mechanism.a]\nvalue = 1.0\nunit = "m"\n'
     'source = { kind = "datasheet", ref = "X", retrieved = "last week" }',
     ["mechanism.a", "retrieved"]),
    ('[mechanism.a]\nof = "mechanism.b"\nvalue = 1.0', ["mechanism.a",
                                                       "both"]),
    ('[motor.a]\nvalue = 1.0', ["motor", "section"]),
])
def test_a_malformed_entry_raises_naming_the_entry_and_field(tmp_path, entry,
                                                             words):
    with pytest.raises(LedgerError) as raised:
        load(path=write(tmp_path, entry))
    for word in words:
        assert word in str(raised.value)


@pytest.mark.parametrize("text, word", [
    ('[mechanism.a]\nof = "mechanism.b"', "names no entry"),
    ('[mechanism.a]\nof = "mechanism.b"\n[mechanism.b]\nof = "mechanism.a"',
     "loops"),
])
def test_load_refuses_an_of_it_cannot_resolve(tmp_path, text, word):
    with pytest.raises(LedgerError, match=word):
        load("mechanism", path=write(tmp_path, text))


def test_load_of_a_missing_section_names_the_ones_there(tmp_path):
    with pytest.raises(LedgerError, match="mechanism"):
        load("drive", path=write(tmp_path, ARM))


# --- check ----------------------------------------------------------------------
TODAY = datetime.date(2026, 10, 20)


def codes(tmp_path, text):
    """Each finding on the ledger `text` as (code, entry)."""
    return [(f.code, f.entry) for f in check(write(tmp_path, text),
                                             today=TODAY)]


def entry(name="mechanism.a", **fields):
    """One entry's TOML, `fields` written as TOML values already."""
    return f"[{name}]\n" + "".join(f"{k} = {v}\n" for k, v in fields.items())


DATASHEET = '{ kind = "datasheet", ref = "X-1", retrieved = 2026-10-01 }'
ESTIMATE = '{ kind = "estimate", ref = "a hand sum" }'


def test_a_clean_ledger_has_no_findings(tmp_path):
    # PART's lines, 113.6 g, sum past its 100 g; 120 g holds them.
    within = PART.replace("value = 0.10\n", "value = 0.12\n")
    assert codes(tmp_path, ARM + "\n" + within) == []


# The template's own entries' units, each as its datasheet prints it, worked
# by hand: 1 krpm is 1000·2π/60 rad/s, so 88.4 V/krpm is 88.4·60/(2000π)
# V·s/rad and 8 rpm/V is 8·2π/60 rad/(s·V).
TEMPLATE = [
    ("193 g", "kg", "0.193"),
    ("300 mm", "m", "0.3"),
    ("88.4 V/krpm", "V*s/rad", "0.84415781815941283"),
    ("8 rpm/V", "rad/s/V", "0.83775804095727813"),
    ("1.2 K/W", "K/W", "1.2"),
    ("300 J/K", "J/K", "300.0"),
    ("10 mF", "F", "0.01"),
    ("120 degC", "degC", "120.0"),
]


@pytest.mark.parametrize("written, unit, value", TEMPLATE)
def test_the_template_units_convert_as_worked_by_hand(tmp_path, written,
                                                      unit, value):
    text = entry(value=value, unit=f'"{unit}"', as_written=f'"{written}"',
                 status='"confirmed"', source=DATASHEET)
    assert codes(tmp_path, text) == []


@pytest.mark.parametrize("written", [
    "193 kg",           # a g/kg slip: the value is 1000 times too small
    "0.1932 kg",        # 1e-3 relative, inside a 1e-2 tolerance
    "193.0002 g",       # 1e-6 relative
    "193 mm",           # no such conversion
])
def test_as_written_disagreeing_with_the_value_is_found(tmp_path, written):
    text = entry(value="0.193", unit='"kg"', as_written=f'"{written}"',
                 status='"confirmed"', source=DATASHEET)
    assert codes(tmp_path, text) == [("unit.as-written", "mechanism.a")]


def test_a_vector_as_written_converts_whole(tmp_path):
    good = entry(value="[0.125, 0.0, -0.02]", unit='"m"',
                 as_written='"[125, 0, -20] mm"', status='"confirmed"',
                 source='{ kind = "measured", ref = "docs/testing/t1.md" }')
    assert codes(tmp_path, good) == []
    bad = good.replace("-20]", "-21]")
    assert codes(tmp_path, bad) == [("unit.as-written", "mechanism.a")]


@pytest.mark.parametrize("unit, written", [("mOhm", "200 mohm"),
                                           ("ohm", "200 mOhm"),
                                           ("ohm", "two hundred mohm")])
def test_a_unit_pint_cannot_parse_is_found(tmp_path, unit, written):
    text = entry(value="0.2", unit=f'"{unit}"', as_written=f'"{written}"',
                 status='"confirmed"', source=DATASHEET)
    assert codes(tmp_path, text) == [("unit.unparsed", "mechanism.a")]


@pytest.mark.parametrize("unit, si", [
    ("g", False), ("mm", False), ("rpm", False), ("degF", False),
    ("W*h", False), ("deg", False), ("kg", True), ("rad/s", True),
    ("degC", True), ("V*s/rad", True), ("kg*m^2", True), ("1", True),
    ("USD", True), ("ohm", True)])
def test_a_unit_that_is_not_si_is_found_and_degc_is_excepted(tmp_path, unit,
                                                             si):
    text = entry(value="1.0", unit=f'"{unit}"',
                 source='{ kind = "chosen", ref = "§3" }')
    assert codes(tmp_path, text) == (
        [] if si else [("unit.not-si", "mechanism.a")])


def test_an_estimate_without_a_band_is_found(tmp_path):
    text = entry(value="0.8", unit='"kg"', status='"candidate"',
                 source=ESTIMATE)
    assert codes(tmp_path, text) == [("band.missing", "mechanism.a")]
    assert codes(tmp_path, text + "band = [0.72, 0.88]\n") == []


@pytest.mark.parametrize("value, found", [("0.72", False), ("0.88", False),
                                          ("0.80", False), ("0.719", True),
                                          ("0.95", True)])
def test_a_nominal_outside_its_band_is_found(tmp_path, value, found):
    text = entry(value=value, unit='"kg"', band="[0.72, 0.88]",
                 status='"candidate"', source=ESTIMATE)
    assert codes(tmp_path, text) == (
        [("band.nominal-outside", "mechanism.a")] if found else [])


@pytest.mark.parametrize("fields", [
    dict(source='{ kind = "chosen" }'),
    dict(source='{ kind = "datasheet", ref = "X-1" }', as_written='"1 m"',
         status='"confirmed"'),
    dict(source=DATASHEET, status='"confirmed"'),
    dict(source='{ kind = "standard", ref = "ISO 80000-3" }'),
    dict(source='{ kind = "measured", ref = "docs/testing/t1.md" }',
         as_written='"1 m"'),
    dict(source='{ kind = "cad", ref = "cad/a.py@1" }'),
])
def test_a_field_its_kind_requires_missing_is_found(tmp_path, fields):
    text = entry(value="1.0", unit='"m"', **fields)
    assert codes(tmp_path, text) == [("source.citation", "mechanism.a")]


@pytest.mark.parametrize("fields", [
    dict(source='{ kind = "chosen", ref = "REQ-04" }'),
    dict(source='{ kind = "standard", ref = "ISO 80000-3" }',
         as_written='"1 m"'),
    dict(source='{ kind = "cad", ref = "cad/a.py@1" }',
         status='"candidate"'),
    dict(source='{ kind = "measured", ref = "docs/testing/t1.md" }',
         as_written='"1000 mm"', status='"confirmed"'),
])
def test_each_kind_with_its_citation_is_clean(tmp_path, fields):
    assert codes(tmp_path, entry(value="1.0", unit='"m"', **fields)) == []


CHAIN = """\
[part.X-1.mass]
value = 0.5
unit = "kg"
as_written = "500 g"
status = "{status}"
source = {{ kind = "datasheet", ref = "X-1", retrieved = 2026-10-01 }}

[budget.mass.pair]
of = "part.X-1.mass"
qty = 2

[budget.mass.arm]
of = "budget.mass.pair"
status = "confirmed"
"""


@pytest.mark.parametrize("status, found", [("candidate", True),
                                           ("confirmed", False)])
def test_a_confirmed_line_reaching_a_candidate_two_hops_down_is_found(
        tmp_path, status, found):
    # `pair` states no status, so it counts as confirmed and is found too;
    # `arm` reaches the candidate only through `pair`.
    assert codes(tmp_path, CHAIN.format(status=status)) == (
        [("status.candidate-cited", "budget.mass.pair"),
         ("status.candidate-cited", "budget.mass.arm")] if found else [])


def test_a_confirmed_line_citing_a_candidate_directly_is_found(tmp_path):
    text = CHAIN.format(status="candidate").replace(
        'qty = 2\n', 'qty = 2\nstatus = "confirmed"\n')
    assert codes(tmp_path, text) == [
        ("status.candidate-cited", "budget.mass.pair"),
        ("status.candidate-cited", "budget.mass.arm")]


def test_an_of_naming_nothing_is_found(tmp_path):
    text = entry("budget.mass.arm", of='"part.X-1.mass"')
    assert codes(tmp_path, text) == [("of.dangling", "budget.mass.arm")]


def test_an_of_that_loops_is_found(tmp_path):
    text = (entry("budget.mass.a", of='"budget.mass.b"')
            + entry("budget.mass.b", of='"budget.mass.a"'))
    assert codes(tmp_path, text) == [("of.cycle", "budget.mass.a"),
                                     ("of.cycle", "budget.mass.b")]


@pytest.mark.parametrize("retrieved, unit, found", [
    ("2026-07-22", "USD", False),       # 90 days
    ("2026-07-21", "USD", True),        # 91 days
    ("2025-01-01", "kg", False),        # old, but not a price
])
def test_a_price_retrieved_more_than_90_days_ago_is_a_warning(
        tmp_path, retrieved, unit, found):
    text = entry(value="109.0", unit=f'"{unit}"', as_written=f'"109 {unit}"',
                 status='"confirmed"',
                 source=f'{{ kind = "datasheet", ref = "X-1", '
                        f'retrieved = {retrieved} }}')
    findings = check(write(tmp_path, text), today=TODAY)
    assert [(f.code, f.level) for f in findings] == (
        [("price.old", "warning")] if found else [])


def test_a_finding_prints_on_one_line_with_its_level_and_code():
    f = Finding("band.missing", "error", "mechanism.a", "an estimate ...")
    assert str(f) == "error band.missing mechanism.a: an estimate ..."


# --- show -----------------------------------------------------------------------
def test_show_prints_one_line_per_entry_under_a_prefix(tmp_path):
    out = show("part.moteus-r4.11", path=write(tmp_path, PART)).splitlines()
    assert len(out) == 2
    assert out[0].split() == ["part.moteus-r4.11.mass", "0.0142", "kg", "-",
                              "datasheet", "confirmed"]
    banded = show("mechanism.m2", path=write(tmp_path, ARM)).split()
    assert banded == ["mechanism.m2", "0.8", "kg", "[0.72,", "0.88]",
                      "estimate", "candidate"]


def test_show_of_a_budget_sums_its_lines_against_the_allocation(tmp_path):
    out = show("budget.mass", path=write(tmp_path, PART))
    tail = [line.split() for line in out.splitlines()[-5:]]
    assert tail == [[key, shown(x), "kg"] for key, x in [
        ("drivers", DRIVERS), ("spares", SPARES), ("total", TOTAL),
        ("allocation", ALLOCATION), ("margin", MARGIN)]]


def test_show_of_nothing_raises(tmp_path):
    with pytest.raises(LedgerError, match="drive"):
        show("drive", path=write(tmp_path, ARM))


# --- the command line -----------------------------------------------------------
def ledger(*args, cwd):
    return subprocess.run([sys.executable, "-m", "armature.ledger", *args],
                          cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8")


def test_check_from_the_shell_prints_each_finding_and_exits_1(tmp_path):
    write(tmp_path, ARM + entry(value="0.193", unit='"g"', as_written='"193 g"',
                                status='"confirmed"', source=DATASHEET))
    run = ledger("check", cwd=tmp_path)
    assert run.returncode == 1
    assert run.stdout.startswith("error unit.not-si mechanism.a: ")
    run = ledger("check", "--json", cwd=tmp_path)
    found = json.loads(run.stdout)
    assert [f["code"] for f in found] == ["unit.not-si", "unit.as-written"]
    assert set(found[0]) == {"code", "level", "entry", "message"}


def test_check_from_the_shell_exits_0_on_warnings_alone(tmp_path):
    old = '{ kind = "datasheet", ref = "X-1", retrieved = 2020-01-01 }'
    write(tmp_path, entry(value="109.0", unit='"USD"',
                          as_written='"109 USD"', status='"confirmed"',
                          source=old))
    run = ledger("check", cwd=tmp_path)
    assert run.returncode == 0
    assert run.stdout.startswith("warning price.old mechanism.a: ")
    write(tmp_path, ARM)
    run = ledger("check", cwd=tmp_path)
    assert (run.returncode, run.stdout) == (0, "")


def test_a_malformed_ledger_from_the_shell_exits_1_naming_it(tmp_path):
    write(tmp_path, '[mechanism.a]\nvalue = 1.0\nunit = "m"\n')
    run = ledger("check", cwd=tmp_path)
    assert run.returncode == 1 and "mechanism.a: source" in run.stderr


def test_show_from_the_shell_prints_the_budget(tmp_path):
    write(tmp_path, PART)
    run = ledger("show", "budget.mass", cwd=tmp_path)
    assert run.returncode == 0 and "margin" in run.stdout


def test_a_message_outside_ascii_reaches_a_pipe_intact(tmp_path):
    write(tmp_path, entry("budget.mass.a", of='"budget.mass.b"')
          + entry("budget.mass.b", of='"budget.mass.a"'))
    run = ledger("check", cwd=tmp_path)
    assert "budget.mass.a → budget.mass.b → budget.mass.a" in run.stdout


def test_a_dimensionless_as_written_converts(tmp_path):
    text = entry(value="0.95", unit='"1"', as_written='"95 percent"',
                 status='"confirmed"', source=DATASHEET)
    assert codes(tmp_path, text) == []
    assert codes(tmp_path, text.replace('"95 percent"', '"0.95"')) == []


def test_a_line_with_no_status_counts_as_confirmed_until_it_says_otherwise(
        tmp_path):
    text = CHAIN.format(status="candidate").replace(
        'status = "confirmed"\n', "")
    assert codes(tmp_path, text) == [
        ("status.candidate-cited", "budget.mass.pair"),
        ("status.candidate-cited", "budget.mass.arm")]
    owned = text.replace('qty = 2\n', 'qty = 2\nstatus = "candidate"\n')
    assert codes(tmp_path, owned) == [
        ("status.candidate-cited", "budget.mass.arm")]


VECTOR = entry("mechanism.com2", value="[0.125, 0.0, 0.0]", unit='"m"',
               status='"candidate"', source=ESTIMATE)


def test_a_vector_estimate_carries_a_band_element_by_element(tmp_path):
    assert codes(tmp_path, VECTOR) == [("band.missing", "mechanism.com2")]
    banded = VECTOR + "band = [[0.12, -0.005, 0.0], [0.13, 0.005, 0.0]]\n"
    assert codes(tmp_path, banded) == []
    lo, hi = load(path=tmp_path).bands("mechanism")["com2"]
    np.testing.assert_array_equal(lo, [0.12, -0.005, 0.0])
    np.testing.assert_array_equal(hi, [0.13, 0.005, 0.0])
    outside = VECTOR + "band = [[0.12, 0.001, 0.0], [0.13, 0.005, 0.0]]\n"
    assert codes(tmp_path, outside) == [("band.nominal-outside",
                                         "mechanism.com2")]
    with pytest.raises(LedgerError, match="mechanism.com2: band"):
        load(path=write(tmp_path, VECTOR + "band = [0.12, 0.13]\n"))


def test_show_reads_a_unit_spelled_another_way_as_the_same(tmp_path):
    text = PART.replace('[budget.mass.allocation]\nvalue = 0.10\nunit = "kg"',
                        '[budget.mass.allocation]\nvalue = 0.10\n'
                        'unit = "kilogram"')
    assert "margin" in show("budget.mass", path=write(tmp_path, text))


# --- render and the views -------------------------------------------------------
BUDGETS = "docs/01-spec/budgets.md"
TRACE = "docs/01-spec/traceability.md"


def project(tmp_path, ledger_text, files):
    """A project at `tmp_path`: its ledger, and each markdown file in
    `files`, {path below the root: text}."""
    write(tmp_path, ledger_text)
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def marked(view, body=""):
    """A file holding one marked section, `body` inside it."""
    return (f"Prose above.\n\n<!-- ledger:{view} -->\n{body}"
            f"<!-- /ledger -->\n\nProse below.\n")


def found(root, code):
    """The entries `check` finds `code` on."""
    return [f.entry for f in check(root, today=TODAY) if f.code == code]


def table(text):
    """Each row of the markdown tables in `text`, as stripped cells, the
    separator rows left out."""
    rows = [[c.strip() for c in line.strip()[1:-1].split("|")]
            for line in text.splitlines() if line.startswith("|")]
    return [r for r in rows if set("".join(r)) - set("-: ")]


def test_render_writes_a_budget_whole_and_check_is_then_clean(tmp_path):
    root = project(tmp_path, PART, {BUDGETS: marked("budget.mass")})
    assert found(root, "view.stale") == ["budget.mass"]
    render(path=root)
    text = (root / BUDGETS).read_text(encoding="utf-8")
    assert text.startswith("Prose above.\n\n<!-- ledger:budget.mass -->\n|")
    assert text.endswith("|\n<!-- /ledger -->\n\nProse below.\n")
    rows = table(text)
    assert rows[0] == ["Line item", "Entry", "Budget (kg)",
                       "Current estimate (kg)", "Margin (kg)", "Source",
                       "Status"]
    assert [r[3] for r in rows[1:]] == [shown(x)
                                        for x in (DRIVERS, SPARES, TOTAL)]
    assert rows[-1][2] == shown(ALLOCATION)
    assert rows[-1][4].startswith(shown(MARGIN))
    assert found(root, "view.stale") == []


PROJECT = PART + """
[part."moteus-r4.11".kt]
of = "part.moteus-r4.11.ke"
note = "shoulder driver's torque constant, read off its Ke"

[part."moteus-r4.11".ke]
value = 0.8441578181594128
unit = "V*s/rad"
basis = { per = "V_rms", between = "line" }
as_written = "88.4 V/krpm"
status = "candidate"
source = { kind = "datasheet", ref = "moteus-r4.11", retrieved = 2026-10-01 }
note = "the shoulder winding"

[req.REQ-04]
value = 0.10
unit = "kg"
source = { kind = "chosen", ref = "REQ-04" }
note = "Must, by inspection: the drivers weigh no more than this"

[mechanism.l1]
value = 0.30
unit = "m"
as_written = "300 mm"
source = { kind = "measured", ref = "docs/testing/arm.md" }
status = "confirmed"
note = "upper link length | shoulder to elbow"

[drive.m2]
of = "mechanism.m2"
qty = 2

[mechanism.m2]
value = 0.80
unit = "kg"
band = [0.72, 0.88]
status = "candidate"
source = { kind = "estimate", ref = "aluminium tube, 1.6 mm wall" }
"""

VIEWS = {"budget.mass": BUDGETS, "bom": "docs/01-spec/bom.md",
         "req": "docs/01-spec/spec.md", "symbols": "CONTEXT.md"}


@pytest.mark.parametrize("view", VIEWS)
def test_render_round_trips_each_view_and_check_finds_a_hand_edit(tmp_path,
                                                                  view):
    root = project(tmp_path, PROJECT, {VIEWS[view]: marked(view)})
    assert found(root, "view.stale") == [view]
    assert render(path=root) == [root / VIEWS[view]]
    assert found(root, "view.stale") == []
    assert render(path=root) == []
    file = root / VIEWS[view]
    text = file.read_text(encoding="utf-8")
    edited = text.replace(" |\n<!-- /ledger -->",
                          " (edited) |\n<!-- /ledger -->")
    assert edited != text
    file.write_text(edited, encoding="utf-8")
    assert found(root, "view.stale") == [view]
    message = next(f.message for f in check(root, today=TODAY)
                   if f.code == "view.stale")
    assert message.startswith(f"{VIEWS[view]}:3: ")
    render(path=root)
    assert found(root, "view.stale") == []
    assert file.read_text(encoding="utf-8") == text


def test_a_budget_row_reads_its_note_and_cites_what_it_reads(tmp_path):
    text = PART.replace('qty = 2\n', 'qty = 2\nnote = "two motor drivers"\n')
    root = project(tmp_path, text, {BUDGETS: marked("budget.mass")})
    render(path=root)
    rows = table((root / BUDGETS).read_text(encoding="utf-8"))
    assert rows[1][:2] == ["two motor drivers", "`budget.mass.drivers`"]
    assert rows[1][5] == ("2 × `part.moteus-r4.11.mass` → datasheet: "
                          "moteus-r4.11, retrieved 2026-10-01")
    assert rows[2][0] == "spares"     # no note: the line's own name
    assert rows[3] == ["Total", "`budget.mass.allocation`",
                       shown(ALLOCATION), shown(TOTAL),
                       f"{shown(MARGIN)}, breached", "chosen: REQ-04",
                       "confirmed"]


def test_the_bom_has_a_row_per_part_entry_and_names_what_it_drives(
        tmp_path):
    root = project(tmp_path, PROJECT, {"docs/01-spec/bom.md": marked("bom")})
    render(path=root)
    rows = table((root / "docs/01-spec/bom.md").read_text(encoding="utf-8"))
    assert rows[0] == ["Item", "Part / spec", "Parameter", "Value",
                       "As written", "Source", "Status", "Drives"]
    by = {r[2]: r for r in rows[1:]}
    assert list(by) == ["mass", "price", "kt", "ke"]
    assert by["mass"][3:5] == ["0.0142 kg", "14.2 g"]
    assert by["mass"][7] == ("REQ-04, `budget.mass.drivers`, "
                             "`budget.mass.spares`")
    assert by["ke"] == [
        "the shoulder winding", "moteus-r4.11", "ke", f"{shown(KE)} V*s/rad",
        "88.4 V/krpm (per V_rms, between line)",
        "datasheet: moteus-r4.11, retrieved 2026-10-01", "candidate",
        "`part.moteus-r4.11.kt`"]
    # An of line in the BOM reads its entry: the value and the source.
    assert by["kt"][3] == f"{shown(KE)} V*s/rad"
    assert by["kt"][5].startswith("`part.moteus-r4.11.ke` → datasheet")


def test_the_req_view_takes_its_value_column_from_the_ledger(tmp_path):
    root = project(tmp_path, PROJECT, {"docs/01-spec/spec.md": marked("req")})
    render(path=root)
    rows = table((root / "docs/01-spec/spec.md").read_text(encoding="utf-8"))
    assert rows == [
        ["ID", "Requirement", "Value / Threshold", "Source", "Status"],
        ["REQ-04", "Must, by inspection: the drivers weigh no more than "
         "this", "0.1 kg", "chosen: REQ-04", "confirmed"]]


def test_the_symbols_view_is_the_mechanism_and_drive_entries(tmp_path):
    root = project(tmp_path, PROJECT, {"CONTEXT.md": marked("symbols")})
    render(path=root)
    text = (root / "CONTEXT.md").read_text(encoding="utf-8")
    assert "upper link length \\| shoulder to elbow" in text  # | escaped
    rows = table(text.replace("\\|", "/"))
    assert rows[0] == ["Symbol", "Meaning", "Value", "Unit", "Band",
                       "Source", "Status"]
    assert [r[0] for r in rows[1:]] == ["`l1`", "`m2`", "`m2`"]
    assert rows[1][2:5] == ["0.3", "m", ""]
    # In the ledger's order, a section's entries together: mechanism.m2,
    # then drive.m2, which reads 2 × it, and so does its band.
    assert rows[2][2:5] == ["0.8", "kg", "[0.72, 0.88]"]
    assert rows[3][2:5] == ["1.6", "kg", "[1.44, 1.76]"]
    assert rows[3][5] == ("2 × `mechanism.m2` → estimate: aluminium tube, "
                          "1.6 mm wall")


def test_a_tensor_names_the_point_and_axes_it_is_about(tmp_path):
    root = project(tmp_path, entry(
        "mechanism.I2", value="[[1e-4, 0, 0], [0, 6e-3, 0], [0, 0, 6e-3]]",
        unit='"kg*m^2"', point='"com2"', axes='"base"', status='"candidate"',
        source='{ kind = "cad", ref = "cad/forearm.py@3" }'),
        {"CONTEXT.md": marked("symbols")})
    render(path=root)
    rows = table((root / "CONTEXT.md").read_text(encoding="utf-8"))
    assert rows[1][2] == ("[[0.0001, 0, 0], [0, 0.006, 0], [0, 0, 0.006]], "
                          "about com2 in base axes")


def test_render_leaves_the_prose_a_fence_and_crlf_alone(tmp_path):
    fenced = ("```markdown\n<!-- ledger:budget.mass -->\nan example\n"
              "<!-- /ledger -->\n```\n")
    root = project(tmp_path, PART, {})
    file = root / BUDGETS
    file.parent.mkdir(parents=True)
    file.write_bytes((fenced + marked("budget.mass")).replace(
        "\n", "\r\n").encode("utf-8"))
    render(path=root)
    raw = file.read_bytes().decode("utf-8")
    assert "\n" not in raw.replace("\r\n", "")
    assert raw.startswith(fenced.replace("\n", "\r\n") + "Prose above.")
    assert raw.endswith("<!-- /ledger -->\r\n\r\nProse below.\r\n")
    assert found(root, "view.stale") == []


def test_a_budget_with_no_entries_renders_an_empty_table(tmp_path):
    root = project(tmp_path, ARM, {BUDGETS: marked("budget.power")})
    render(path=root)
    rows = table((root / BUDGETS).read_text(encoding="utf-8"))
    assert rows == [["Line item", "Entry", "Budget", "Current estimate",
                     "Margin", "Source", "Status"]]


def test_render_skips_a_folder_with_a_ledger_of_its_own(tmp_path):
    root = project(tmp_path, PART, {"vendor/kit/notes.md":
                                    marked("budget.mass")})
    write(root / "vendor" / "kit", ARM)
    assert render(path=root) == []
    assert found(root, "view.stale") == []


@pytest.mark.parametrize("text, words", [
    (marked("budgets"), ["a.md:3", "ledger:budgets is not a view"]),
    ("<!-- ledger:bom -->\n", ["a.md:1", "never closed"]),
    ("<!-- /ledger -->\n", ["a.md:1", "closes nothing"]),
    ("<!-- ledger:bom -->\n<!-- ledger:req -->\n<!-- /ledger -->\n",
     ["a.md:2", "opens inside"]),
])
def test_a_marker_that_cannot_be_read_is_refused(tmp_path, text, words):
    root = project(tmp_path, PART, {"a.md": text})
    with pytest.raises(LedgerError) as raised:
        render(path=root)
    for word in words:
        assert word in str(raised.value)
    findings = [f for f in check(root, today=TODAY)
                if f.code == "view.stale"]
    assert len(findings) == 1 and words[1] in findings[0].message


# --- budget.breach and trace.unfailed -------------------------------------------
OVER = """\
[budget.mass.allocation]
of = "req.REQ-004"

[budget.mass.arm]
value = 0.90
unit = "kg"
band = [0.85, 0.95]
status = "candidate"
source = { kind = "estimate", ref = "the arm's CAD at rev 2, by hand" }

[budget.mass.reserve]
value = 0.15
unit = "kg"
source = { kind = "chosen", ref = "REQ-012" }
note = "held for the wrist, which REQ-012 wants room for"

[req.REQ-004]
value = 1.0
unit = "kg"
source = { kind = "chosen", ref = "REQ-004" }
"""


def trace(**statuses):
    """A traceability table with a row for each REQ, at its status."""
    rows = "".join(f"| {req} | | | | | {status} |\n"
                   for req, status in statuses.items())
    return ("# Requirements traceability\n\n| REQ | Requirement (short) | "
            "Design element | Analysis | Test | Status |\n| --- | --- | --- "
            "| --- | --- | --- |\n" + rows)


def test_a_budget_over_its_allocation_is_a_breach(tmp_path):
    # OVER's arm and reserve against its REQ-004.
    total, allocation = 0.90 + 0.15, 1.0
    findings = check(project(tmp_path, OVER, {}), today=TODAY)
    assert [(f.code, f.entry) for f in findings] == [
        ("budget.breach", "budget.mass")]
    assert findings[0].message == (
        f"its lines sum to {shown(total)} kg, past its allocation of "
        f"{shown(allocation)} kg by {shown(total - allocation)} kg; "
        f"it fails REQ-004, REQ-012")


def test_a_budget_line_in_another_unit_is_an_error_not_skipped(tmp_path):
    # A price line in a mass budget: 109 USD against 0.1 kg is no sum.
    text = PART + '\n[budget.mass.cost]\nof = "part.moteus-r4.11.price"\n'
    findings = check(project(tmp_path, text, {}), today=TODAY)
    assert [(f.code, f.level, f.entry) for f in findings] == [
        ("budget.unit", "error", "budget.mass.cost")]
    assert "USD" in findings[0].message and "kg" in findings[0].message
    assert ledger("check", cwd=tmp_path).returncode == 1


def test_a_budget_line_whose_of_names_nothing_is_reported_once(tmp_path):
    text = PART + '\n[budget.mass.cost]\nof = "part.nothing.mass"\n'
    root = project(tmp_path, text, {})
    assert [f.code for f in check(root, today=TODAY)] == ["of.dangling"]


@pytest.mark.parametrize("arm, breached", [("0.85", False), ("0.849", False),
                                           ("0.851", True)])
def test_a_budget_level_with_its_allocation_holds(tmp_path, arm, breached):
    text = OVER.replace("value = 0.90\n", f"value = {arm}\n")
    root = project(tmp_path, text, {})
    assert bool(found(root, "budget.breach")) == breached


def test_a_breached_req_is_unfailed_until_its_row_reads_failed(tmp_path):
    root = project(tmp_path, OVER, {TRACE: trace(**{
        "REQ-004": "open", "REQ-012": "open (budget row failed)"})})
    assert found(root, "trace.unfailed") == ["REQ-004", "REQ-012"]
    (root / TRACE).write_text(trace(**{"REQ-004": "**failed**: the arm",
                                       "REQ-012": "failed"}),
                              encoding="utf-8")
    assert found(root, "trace.unfailed") == []
    assert found(root, "budget.breach") == ["budget.mass"]


def test_a_breached_req_with_no_traceability_row_is_unfailed(tmp_path):
    root = project(tmp_path, OVER, {TRACE: trace(**{"REQ-004": "failed"})})
    findings = [f for f in check(root, today=TODAY)
                if f.code == "trace.unfailed"]
    assert [f.entry for f in findings] == ["REQ-012"]
    assert "is missing" in findings[0].message


def test_trace_unfailed_is_skipped_without_a_traceability_file(tmp_path):
    root = project(tmp_path, OVER, {})
    assert found(root, "trace.unfailed") == []


def test_a_budget_within_its_allocation_fails_no_req(tmp_path):
    text = OVER.replace("value = 0.15\n", "value = 0.10\n")
    root = project(tmp_path, text, {TRACE: trace(**{"REQ-004": "open"})})
    assert [f.code for f in check(root, today=TODAY)] == []


SPEC = Path(__file__).resolve().parents[2] / "skills" / "armature-spec" \
    / "references"


@pytest.mark.parametrize("name, views", [
    ("budgets-template.md", ["budget.mass", "budget.power", "budget.cost"]),
    ("bom-template.md", ["bom"]),
    ("spec-template.md", ["req"]),
])
def test_each_template_carries_its_views_as_render_writes_them(
        tmp_path, name, views):
    # A project's copy is the template's fenced structure, unfenced, beside
    # a ledger with nothing in it yet.
    text = (SPEC / name).read_text(encoding="utf-8")
    copied = "\n".join(line for line in text.splitlines()
                       if not line.startswith("```"))
    root = project(tmp_path, "", {"docs/01-spec/copy.md": copied})
    assert [f for f in check(root, today=TODAY)] == []
    assert render(path=root) == []
    assert re.findall(r"^<!-- ledger:(\S+) -->$", copied, re.M) == views


LIBRARIAN = Path(__file__).resolve().parents[2] / "agents" / "librarian.md"


def test_the_librarians_staged_entries_check_clean_once_merged(tmp_path):
    # Merge appends a section's toml block to the project's ledger as
    # written, so the worked one must load and check clean there.
    text = LIBRARIAN.read_text(encoding="utf-8")
    blocks = re.findall(r"^```toml\n(.*?)^```$", text, re.M | re.S)
    assert blocks, "librarian.md shows no staged ledger entries"
    root = project(tmp_path, "# seeded by init\n\n" + "\n".join(blocks), {})
    staged = list(load(path=root))
    assert staged
    for e in staged:
        assert e.section.startswith("part."), e.name
        assert (e.kind, e.status) == ("datasheet", "candidate"), e.name
        assert e.as_written and "retrieved" in e.source, e.name
    assert [f for f in check(root, today=TODAY) if f.level == "error"] == []


def test_render_from_the_shell_rewrites_the_views(tmp_path):
    root = project(tmp_path, PART, {BUDGETS: marked("budget.mass")})
    run = ledger("render", cwd=root)
    assert run.returncode == 0
    assert run.stdout.strip() == "rendered docs/01-spec/budgets.md"
    assert ledger("render", cwd=root).stdout == ""
    run = ledger("check", cwd=root)
    assert "view.stale" not in run.stdout
    assert "error budget.breach budget.mass: " in run.stdout
