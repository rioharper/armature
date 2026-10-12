"""
layout.py — the two gates every module in cad/parts/ is held to: the code-line
budget, and the truth check.

The rules live in the plugin's `references/model-layout.md`; this file is how
a copied project enforces them without access to the plugin. Stdlib only, so
it runs where build123d does not:

    python cad/parts/layout.py     # the gate table; exit 1 on a violation

`run_all.py` discovers the checks below like any other, so the full run
fails on a module over budget. Running one module or package
(`run_all.py check`) leaves them out: a file still being written is not
red-barred mid-work. The same file ships in armature-derive's model template;
a part directory has no mechanism description, so the truth gate stands down
here and reports n/a.
"""


import ast
import io
import sys
import tempfile
import tokenize
from collections import namedtuple
from pathlib import Path

MILESTONE = (99, "Layout: the gates")

BUDGET = 250
EXEMPT = "LAYOUT_EXEMPT"
# The truth-check gate. A checks module beside a milestone module either
# defines a `test_truth_*` callable or says, in an argued string, why its
# claims need none. The convention is a *name* because this file imports
# nothing but the standard library — it has to run where SymPy, MuJoCo and
# build123d do not — so the only thing it can learn about a check is what the
# source says it is called.
TRUTH_EXEMPT = "TRUTH_EXEMPT"
TRUTH_PREFIX = "test_truth_"
# A margin is held to the same gate: every module-level `Margin(...)` call in a
# gated directory, in any module, passes `truth=`, or its module says in
# TRUTH_EXEMPT why its claims need none. Read from the source like the prefix:
# an assignment whose value calls `Margin` or `armature.Margin`.
MARGIN = "Margin"
# What says a directory has a truth model: the mechanism description it is
# compiled from. The truth model itself is the engine's, outside this tree.
DESCRIPTION = "mechanism.py"

HERE = Path(__file__).resolve().parent
# Reported beside the modules for information only; part definitions carry
# no budget.
NOTES = HERE

# `truth` is the list of truth checks the gate found, or None where the gate
# does not apply — a module that is not a checks module, or a directory with no
# mechanism description at all. `bare` is the margins the module declares with
# no truth, by name, or None in a directory with no mechanism description.
Row = namedtuple("Row", "where lines exempt truth truth_exempt bare")

_NOT_CODE = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
             tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER}
_HAS_DOCSTRING = (ast.Module, ast.ClassDef, ast.FunctionDef,
                  ast.AsyncFunctionDef)


def code_lines(source):
    """
    Lines of `source` that carry code: not blank, not comment-only, and not
    part of a docstring. A string that is data rather than a docstring counts
    on every line it spans.
    """
    tree = ast.parse(source)
    lines = source.splitlines()

    def chars(row, byte_col):   # ast columns are UTF-8 bytes; tokenize's are chars
        return len(lines[row - 1].encode()[:byte_col].decode(errors="ignore"))

    spans = []
    for node in ast.walk(tree):
        if not isinstance(node, _HAS_DOCSTRING) or not node.body:
            continue
        doc = node.body[0]
        if (isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant)
                and isinstance(doc.value.value, str)):
            spans.append(((doc.lineno, chars(doc.lineno, doc.col_offset)),
                          (doc.end_lineno,
                           chars(doc.end_lineno, doc.end_col_offset))))

    rows = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in _NOT_CODE:
            continue
        if tok.type == tokenize.STRING and any(
                start <= tok.start and tok.end <= end for start, end in spans):
            continue
        rows.update(range(tok.start[0], tok.end[0] + 1))
    return len(rows)


def exemption(source, where, name=EXEMPT, demand=None):
    """
    The module's stated reason for standing outside a gate, or None.

    An exemption is a module-level `<name> = "<why>"`. Anything else assigned
    to that name — True, an empty string, a number — raises, so an exemption
    cannot be claimed without being argued. `demand` completes the sentence the
    error asks for, which is what lets one reader serve both gates.
    """
    demand = demand or f"the reason this module stays over {BUDGET} code lines"
    for node in ast.parse(source).body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign)
                   else [])
        if not any(isinstance(t, ast.Name) and t.id == name for t in targets):
            continue
        value = node.value
        if (isinstance(value, ast.Constant) and isinstance(value.value, str)
                and value.value.strip()):
            return " ".join(value.value.split())
        raise ValueError(f"{where}: {name} must be a non-empty string giving "
                         f"{demand}")
    return None


def truth_checks(source):
    """The module's `test_truth_*` callables, by name."""
    return [node.name for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith(TRUTH_PREFIX)]


def bare_margins(source):
    """The module-level margins declared with no `truth=`, by the name each is
    bound to: an assignment whose value calls `Margin` or `armature.Margin`
    with no truth, by keyword or as the fifth argument, or with None."""
    bare = []
    for node in ast.parse(source).body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign)
                   else [])
        call = getattr(node, "value", None)
        if not (targets and isinstance(call, ast.Call) and MARGIN == (
                getattr(call.func, "id", None)
                or getattr(call.func, "attr", None))):
            continue
        truth = [k.value for k in call.keywords if k.arg == "truth"] \
            or call.args[4:5]
        if not truth or (isinstance(truth[0], ast.Constant)
                         and truth[0].value is None):
            bare += [ast.unparse(t) for t in targets]
    return bare


def model_files(root=HERE):
    """Every .py in `root` and one level into its packages — discovery's reach."""
    files = sorted(root.glob("*.py"))
    for package in sorted(p for p in root.iterdir() if (p / "__init__.py").is_file()):
        files += sorted(package.glob("*.py"))
    return files


def gated(path, root):
    """
    Whether the truth gate applies to this file: a checks module, in a
    directory with a mechanism description.

    The description is what the truth model is compiled from, so a directory
    that has one has a truth model to check against, and every checks module
    in it — the description's own among them — is held to the gate. A
    directory without one — a `cad/parts/` tree, a model whose description has
    not landed yet — is outside the gate entirely, which is what lets this
    file ship in both templates.
    """
    return (root / DESCRIPTION).is_file() and path.stem.endswith("_checks")


def size_table(root=HERE):
    """One `Row` per file: its code lines, and where each gate stands on it."""
    rows = []
    for path in model_files(root):
        source = tokenize.open(path).read()
        where = path.relative_to(root).as_posix()
        rows.append(Row(where, code_lines(source),
                        exemption(source, where),
                        truth_checks(source) if gated(path, root) else None,
                        exemption(source, where, TRUTH_EXEMPT,
                                  "the reason this module's claims need no "
                                  "truth check"),
                        bare_margins(source) if (root / DESCRIPTION).is_file()
                        else None))
    return rows


def unchecked_claims(rows):
    """The gated checks modules carrying neither a truth check nor a reason."""
    return [row.where for row in rows if row.truth == [] and not row.truth_exempt]


def unconfirmed_margins(rows):
    """The margins, `module: NAME`, declared with no truth in a gated
    directory, in a module that gives no reason."""
    return [f"{row.where}: {name}" for row in rows if not row.truth_exempt
            for name in row.bare or []]


def test_modules_within_budget():
    over = [f"{row.where} ({row.lines} code lines)" for row in size_table()
            if row.lines > BUDGET and row.exempt is None]
    assert not over, (
        f"over the {BUDGET}-code-line budget: {', '.join(over)}; split along "
        f"the note's sections, or declare {EXEMPT} with the reason it cannot")
    print(f"  [PASS] every module within {BUDGET} code lines or exempt with a reason")


def test_checks_modules_are_paired():
    """A checks module whose module was renamed away — or is a report
    renderer, which discovery never collects — never runs; say so."""
    orphans = []
    for path in model_files():
        if path.stem.endswith("_checks"):
            stem = path.stem[:-len("_checks")]
            if (stem == "report" or stem.startswith("report_")
                    or not path.with_name(stem + ".py").is_file()):
                orphans.append(path.relative_to(HERE).as_posix())
    assert not orphans, f"checks modules no discovered module pairs with: {orphans}"
    print("  [PASS] every checks module pairs with a module")


def test_milestone_checks_carry_a_truth_check():
    """
    Every checks module beside a mechanism description defines a
    `test_truth_*`, or says why it does not.

    A milestone's self-consistency checks are blind to the assumption sitting
    on both sides of them, so a milestone whose only evidence is
    self-consistency has shown its equations consistent and nothing about this
    machine. This gate is what stops the truth model being skipped in silence,
    which is the only way it ever gets skipped.
    """
    rows = size_table()
    if all(row.truth is None for row in rows):
        print("  [PASS] no mechanism description here; the truth gate is n/a")
        return
    missing = unchecked_claims(rows)
    assert not missing, (
        f"checks modules with no {TRUTH_PREFIX}* check: {', '.join(missing)}; "
        f"add one, or declare {TRUTH_EXEMPT} with the reason this module's "
        f"claims need none")
    found = sum(len(row.truth or []) for row in rows)
    excused = [row.where for row in rows if row.truth == [] and row.truth_exempt]
    print(f"  [PASS] {found} truth check(s) across the gated checks modules"
          + (f"; exempt with a reason: {', '.join(excused)}" if excused else ""))


def test_every_margin_carries_a_truth():
    """
    Every margin declared beside a mechanism description passes `truth=`, or
    its module says why its claims need none.

    A margin computed from the derivation is the derivation's claim at the
    point the search found, and the worst point is the one place a wrong
    assumption costs the most. `run_all.py` confirms it there in the truth
    model, within the margin's `agree`; this gate is what stops a margin
    being declared without one in silence.
    """
    rows = size_table()
    if all(row.bare is None for row in rows):
        print("  [PASS] no mechanism description here; the margin gate is n/a")
        return
    missing = unconfirmed_margins(rows)
    assert not missing, (
        f"margins with no truth=: {', '.join(missing)}; pass truth= and agree=, "
        f"or declare {TRUTH_EXEMPT} in the module with the reason its claims "
        f"need none")
    excused = [f"{row.where}: {name}" for row in rows if row.truth_exempt
               for name in row.bare or []]
    print("  [PASS] every margin carries a truth"
          + (f"; exempt with a reason: {', '.join(excused)}" if excused else ""))


def test_the_truth_gate_has_teeth():
    """
    The gate against fixtures: it fails a bare checks module and a margin with
    no truth, passes an argued exemption for each, refuses an unargued one,
    and stands down with no mechanism description.

    Built in a temporary directory rather than asserted against this one,
    because a gate is only evidence once it has been seen to fail, and this
    directory is meant never to make it fail.
    """
    bare = "def test_something():\n    pass\n"
    argued = 'TRUTH_EXEMPT = "alpha fixes a naming convention, not a claim"\n'
    margin = "A = armature.Margin('a', f, 'N', S{})\nB = 1\n"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        checks = root / "alpha_checks.py"
        module = root / "alpha.py"
        module.write_text(margin.format(""), encoding="utf-8")
        checks.write_text(bare, encoding="utf-8")
        assert all(row.truth is None and row.bare is None
                   for row in size_table(root)) \
            and not unchecked_claims(size_table(root)), \
            "the truth gate fired in a directory with no mechanism description"

        (root / DESCRIPTION).write_text("def mechanism(p):\n    return []\n",
                                        encoding="utf-8")
        assert unchecked_claims(size_table(root)) == ["alpha_checks.py"], \
            "a checks module with no truth check and no exemption passed"
        for truthless in ("", ", truth=None", ", None, None"):
            module.write_text(margin.format(truthless), encoding="utf-8")
            assert unconfirmed_margins(size_table(root)) == ["alpha.py: A"], \
                f"a margin declared with {truthless or 'no truth'} passed"
        for confirmed in (", truth=t, agree=1e-9", ", t, 1e-9"):
            module.write_text(margin.format(confirmed), encoding="utf-8")
            assert not unconfirmed_margins(size_table(root)), \
                f"a margin declared with {confirmed} did not clear the gate"
        module.write_text(argued + margin.format(""), encoding="utf-8")
        assert not unconfirmed_margins(size_table(root)), \
            "an argued TRUTH_EXEMPT did not clear a margin"

        checks.write_text(argued + bare, encoding="utf-8")
        assert not unchecked_claims(size_table(root)), \
            "an argued TRUTH_EXEMPT did not clear the gate"

        checks.write_text(f"{TRUTH_PREFIX}settle = None\n"
                          f"def {TRUTH_PREFIX}settle_():\n    pass\n",
                          encoding="utf-8")
        assert [row.truth for row in size_table(root) if row.where ==
                "alpha_checks.py"] == [[f"{TRUTH_PREFIX}settle_"]], \
            "the gate counted a name that is not a callable"

        for unargued in ("TRUTH_EXEMPT = True\n", 'TRUTH_EXEMPT = ""\n'):
            checks.write_text(unargued + bare, encoding="utf-8")
            try:
                size_table(root)
            except ValueError:
                continue
            raise AssertionError(f"{unargued.strip()} passed as a reason")
    print("  [PASS] the truth gate fails a bare checks module and a margin with "
          "no truth, passes an argued exemption, and is n/a with no mechanism "
          "description")


if __name__ == "__main__":
    print(f"{'module':<34}{'code lines':>11}   truth checks")
    for row in size_table():
        flag = ("  exempt: " + row.exempt if row.exempt
                else "  OVER BUDGET" if row.lines > BUDGET else "")
        truth = ("n/a" if row.truth is None
                 else str(len(row.truth)) if row.truth
                 else f"exempt: {row.truth_exempt}" if row.truth_exempt
                 else "NONE")
        if row.bare and not row.truth_exempt:
            truth += f"; MARGINS WITH NO TRUTH: {', '.join(row.bare)}"
        print(f"{row.where:<34}{row.lines:>11}   {truth}{flag}")
    if NOTES.is_dir():
        print(f"\n{'document (information only)':<34}{'lines':>11}")
        for note in sorted(NOTES.glob("*.md")):
            lines = len(note.read_text(encoding="utf-8").splitlines())
            print(f"{note.name:<34}{lines:>11}")
    print("")
    try:
        test_modules_within_budget()
        test_checks_modules_are_paired()
        test_milestone_checks_carry_a_truth_check()
        test_every_margin_carries_a_truth()
        test_the_truth_gate_has_teeth()
    except AssertionError as failure:
        sys.exit(f"FAIL: {failure}")
