"""
check/ledger_checks.py — self-tests for ledger.py: the nearest ledger is
found walking up, an entry is named as the engine names it, an `of` line
reads `qty` times what it names through any number of hops, a broken link
raises rather than reading as something else, and the module imports
nothing a part file would have to install. Each is written to FAIL if the
guard it covers is removed.
"""

import ast
import sys
import tempfile
from pathlib import Path

from check import ledger

LEDGER = """\
[part."moteus-r4.11".mass]
value = 0.0142
unit = "kg"

[part.bracket.com]
value = [0.0, 0.0, 0.004]
unit = "m"

[budget.mass.drives]
of = "budget.mass.drive"
qty = 2

[budget.mass.drive]
of = "part.moteus-r4.11.mass"
"""


def _raised(exc_type, fn, *args, **kwargs):
    """The exception `fn` raised, or None. A check that cannot fail is
    not a check, so every use of this is asserted truthy."""
    try:
        fn(*args, **kwargs)
    except exc_type as exc:
        return exc
    return None


def _ledger(tmp, text=LEDGER):
    path = Path(tmp, ledger.FILENAME)
    path.write_text(text, encoding="utf-8")
    return path


def test_the_nearest_ledger_is_found_walking_up():
    with tempfile.TemporaryDirectory() as tmp:
        deep = Path(tmp, "cad", "parts")
        deep.mkdir(parents=True)
        path = _ledger(tmp)
        assert ledger.find(deep) == path.resolve()
        # One nearer wins: the copy beside a part shadows the project's.
        nearer = _ledger(deep)
        assert ledger.find(deep) == nearer.resolve()
    print("  [PASS] the nearest ledger.toml, walking up")


def test_entries_are_named_as_the_engine_names_them():
    with tempfile.TemporaryDirectory() as tmp:
        found = ledger.entries(_ledger(tmp))
        # A P/N with a dot in it is one key, so splitting a name on "." is
        # not how an entry is found: the section's depth is.
        assert list(found) == ["part.moteus-r4.11.mass", "part.bracket.com",
                               "budget.mass.drives", "budget.mass.drive"]
        assert ledger.value(found, "part.bracket.com")[0] == [0.0, 0.0, 0.004]
        assert _raised(ValueError, ledger.entries,
                       _ledger(tmp, "[mass]\nvalue = 1.0\n"))
    print("  [PASS] entries named by their section's depth")


def test_an_of_line_reads_qty_times_through_every_hop():
    with tempfile.TemporaryDirectory() as tmp:
        found = ledger.entries(_ledger(tmp))
        value, end = ledger.value(found, "budget.mass.drives")
        # 2 x 14.2 g: qty ignored reads 0.0142, a hop dropped raises.
        assert value == 2 * 0.0142 and end is found["part.moteus-r4.11.mass"]
        assert ledger.scaled([[1.0, 2.0]], 3.0) == [[3.0, 6.0]]
        assert _raised(KeyError, ledger.value, found, "budget.mass.wheels")
        loop = LEDGER.replace('of = "part.moteus-r4.11.mass"',
                              'of = "budget.mass.drives"')
        assert "loops" in str(_raised(ValueError, ledger.value,
                                      ledger.entries(_ledger(tmp, loop)),
                                      "budget.mass.drives"))
        dangling = LEDGER.replace('"part.moteus-r4.11.mass"', '"part.x.mass"')
        assert _raised(KeyError, ledger.value,
                       ledger.entries(_ledger(tmp, dangling)),
                       "budget.mass.drives")
    print("  [PASS] of lines read qty times their target, hop by hop")


def test_the_reader_is_standard_library_only():
    # The engine writes and checks the ledger; a part file only reads it,
    # and needs build123d and nothing else to do that.
    tree = ast.parse(Path(ledger.__file__).read_text(encoding="utf-8"))
    imported = {alias.name.split(".")[0] for node in ast.walk(tree)
                if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                 if isinstance(node, ast.ImportFrom) and node.level == 0}
    assert imported and imported <= sys.stdlib_module_names, imported
    print("  [PASS] ledger.py imports the standard library alone")
