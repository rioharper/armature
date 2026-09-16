"""
layout.py — the two gates every module in this model is held to: the code-line
budget, and the truth check.

The rules live in the plugin's `references/model-layout.md`; this file is how
a copied project enforces them without access to the plugin. Stdlib only, so
it runs where SymPy and SciPy do not:

    python analysis/model/layout.py     # the gate table; exit 1 on a violation

`run_all.py` discovers the checks below like any other, so the full run and
`pytest` fail on a module over budget, or on a milestone's checks module that
carries no truth check and no argued exemption. Running one milestone
(`run_all.py kinematics`) leaves them out: a file still being written is not
red-barred mid-work. The same file ships in armature-cad's part template,
where there is no truth package and the truth gate stands down.
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
TRUTH_PACKAGE = "truth"

HERE = Path(__file__).resolve().parent
# Reported beside the modules for information only; notes carry no budget.
NOTES = HERE.parent / "derivation"

# `truth` is the list of truth checks the gate found, or None where the gate
# does not apply — a module that is not a checks module, or a directory with no
# truth package at all.
Row = namedtuple("Row", "where lines exempt truth truth_exempt")

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


def model_files(root=HERE):
    """Every .py in `root` and one level into its packages — discovery's reach."""
    files = sorted(root.glob("*.py"))
    for package in sorted(p for p in root.iterdir() if (p / "__init__.py").is_file()):
        files += sorted(package.glob("*.py"))
    return files


def gated(path, root):
    """
    Whether the truth gate applies to this file.

    Only a checks module, and only outside the truth package: that package *is*
    the truth model, so asking it to check its claims against one is circular.
    A directory with no truth package — a `cad/parts/` tree, a model whose
    truth package has not landed yet — is outside the gate entirely, which is
    what lets this file ship in both templates.
    """
    if not (root / TRUTH_PACKAGE / "__init__.py").is_file():
        return False
    return (path.stem.endswith("_checks")
            and path.relative_to(root).parts[0] != TRUTH_PACKAGE)


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
                                  "truth check")))
    return rows


def unchecked_claims(rows):
    """The gated checks modules carrying neither a truth check nor a reason."""
    return [row.where for row in rows if row.truth == [] and not row.truth_exempt]


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
    Every checks module outside the truth package defines a `test_truth_*`,
    or says why it does not.

    A milestone's self-consistency checks are blind to the assumption sitting
    on both sides of them, so a milestone whose only evidence is
    self-consistency has shown its equations consistent and nothing about this
    machine. This gate is what stops the truth model being skipped in silence,
    which is the only way it ever gets skipped.
    """
    rows = size_table()
    if all(row.truth is None for row in rows):
        print("  [PASS] no truth package here; the truth gate is n/a")
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


def test_the_truth_gate_has_teeth():
    """
    The gate against fixtures: it fails a bare checks module, passes an argued
    one, refuses an unargued exemption, and stands down with no truth package.

    Built in a temporary directory rather than asserted against this one,
    because a gate is only evidence once it has been seen to fail, and this
    directory is meant never to make it fail.
    """
    bare = "def test_something():\n    pass\n"
    argued = 'TRUTH_EXEMPT = "alpha fixes a naming convention, not a claim"\n'
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        checks = root / "alpha_checks.py"
        (root / "alpha.py").write_text("X = 1\n", encoding="utf-8")
        checks.write_text(bare, encoding="utf-8")
        assert all(row.truth is None for row in size_table(root)) \
            and not unchecked_claims(size_table(root)), \
            "the truth gate fired in a directory with no truth package"

        (root / TRUTH_PACKAGE).mkdir()
        (root / TRUTH_PACKAGE / "__init__.py").write_text("", encoding="utf-8")
        assert unchecked_claims(size_table(root)) == ["alpha_checks.py"], \
            "a checks module with no truth check and no exemption passed"

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
    print("  [PASS] the truth gate fails a bare checks module, passes an "
          "argued exemption, and is n/a with no truth package")


if __name__ == "__main__":
    print(f"{'module':<34}{'code lines':>11}   truth checks")
    for row in size_table():
        flag = ("  exempt: " + row.exempt if row.exempt
                else "  OVER BUDGET" if row.lines > BUDGET else "")
        truth = ("n/a" if row.truth is None
                 else str(len(row.truth)) if row.truth
                 else f"exempt: {row.truth_exempt}" if row.truth_exempt
                 else "NONE")
        print(f"{row.where:<34}{row.lines:>11}   {truth}{flag}")
    if NOTES.is_dir():
        print(f"\n{'note (information only)':<34}{'lines':>11}")
        for note in sorted(NOTES.glob("*.md")):
            lines = len(note.read_text(encoding="utf-8").splitlines())
            print(f"{note.name:<34}{lines:>11}")
    print("")
    try:
        test_modules_within_budget()
        test_checks_modules_are_paired()
        test_milestone_checks_carry_a_truth_check()
        test_the_truth_gate_has_teeth()
    except AssertionError as failure:
        sys.exit(f"FAIL: {failure}")
