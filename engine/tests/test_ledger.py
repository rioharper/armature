"""The ledger (ADR 0010): load, check and show, against ledgers written here.

Answer: each expected value is a literal worked by hand from the entry it
reads: a 14.2 g part is 0.0142 kg and two of it 0.0284 kg, and 88.4 V/krpm
is 88.4·60/(2000π) V·s/rad. Each finding is shown firing on an entry built
to trip it and silent on the same entry put right.
"""

import datetime
import json
import subprocess
import sys
import textwrap

import numpy as np
import pytest

from armature.ledger import Finding, LedgerError, check, load, show


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


def test_load_resolves_of_with_qty_through_a_two_hop_chain(tmp_path):
    lines = load("budget.mass", path=write(tmp_path, PART))
    assert lines["drivers"] == pytest.approx(0.0284, rel=1e-12)
    assert lines["spares"] == pytest.approx(0.0852, rel=1e-12)
    assert lines["allocation"] == 0.10
    assert load("part.moteus-r4.11", path=tmp_path)["mass"] == 0.0142


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
    assert codes(tmp_path, ARM + "\n" + PART) == []


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
    # 2 × 14.2 g = 28.4 g, 3 × that = 85.2 g; 113.6 g against 100 g.
    tail = [line.split() for line in out.splitlines()[-5:]]
    assert tail == [["drivers", "0.0284", "kg"], ["spares", "0.0852", "kg"],
                    ["total", "0.1136", "kg"], ["allocation", "0.1", "kg"],
                    ["margin", "-0.0136", "kg"]]


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
