"""
layout.py — the two gates every module in this model is held to: the code-line
budget, and the truth check.

The rules live in the plugin's `references/model-layout.md`; this file is how
a copied project enforces them without access to the plugin. Stdlib only, so
it runs where SymPy and SciPy do not:

    python analysis/model/layout.py     # the gate table; exit 1 on a violation

`run_all.py` discovers its checks, in `layout_checks.py`, like any other, so
the full run and `pytest` fail on a module over budget, on a milestone's
checks module that carries no truth check and no argued exemption, or on a
margin declared with no `truth=` in a module with no argued exemption. The
drive margins, declared by one call to armature.drive's `margins`, carry
theirs, the resolution check, and the gate reads them so; a `margins(...)`
the module did not import from armature.drive is held as a bare margin. Running one milestone
(`run_all.py kinematics`) leaves them out: a file still being written is not
red-barred mid-work. The same file ships in armature-cad's part template,
where there is no mechanism description and the truth gate stands down.
"""

import ast
import io
import sys
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
# The drive margins (ADR 0006) are declared by one call that returns them all,
# `armature.drive.margins(...)`, and each carries its truth, by construction:
# the resolution check, its worst case re-run at 1 kHz and every event at half
# its timestep. An assignment whose value calls `margins` is read as that, but
# only where the module imports it from there; any other `margins(...)` is a
# look-alike, held to the gate as a margin with no truth.
DRIVE_MARGINS = "margins"
DRIVE_MODULE = "armature.drive"
# What says a directory has a truth model: the mechanism description it is
# compiled from. The truth model itself is the engine's, outside this tree.
DESCRIPTION = "mechanism.py"

HERE = Path(__file__).resolve().parent
# Reported beside the modules for information only; notes carry no budget.
NOTES = HERE.parent / "derivation"

# `truth` is the list of truth checks the gate found, or None where the gate
# does not apply — a module that is not a checks module, or a directory with no
# mechanism description at all. `bare` is the margins the module declares with
# no truth, by name, or None in a directory with no mechanism description.
# `drive` is the drive margins it declares, by name, whose truth is theirs.
Row = namedtuple("Row", "where lines exempt truth truth_exempt bare drive")

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


def _assigned_calls(source, *names):
    """Each module-level assignment whose value calls one of `names` (or
    `x.name`), as (targets, call)."""
    for node in ast.parse(source).body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign)
                   else [])
        call = getattr(node, "value", None)
        if targets and isinstance(call, ast.Call) and (
                getattr(call.func, "id", None)
                or getattr(call.func, "attr", None)) in names:
            yield targets, call


def _drive_imports(source):
    """What the module's own imports bind armature.drive's margins to: the
    names of the function, and the dotted names of the module."""
    functions, modules = set(), set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            for alias in node.names:
                if node.module == DRIVE_MODULE and alias.name == DRIVE_MARGINS:
                    functions.add(alias.asname or alias.name)
                elif node.module == "armature" and alias.name == "drive":
                    modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("armature", DRIVE_MODULE):
                    modules.add(alias.asname if alias.asname and
                                alias.name == DRIVE_MODULE else DRIVE_MODULE)
    return functions, modules


def _drive_calls(source):
    """The module-level `margins(...)` assignments, split into those that
    call armature.drive's and the look-alikes, each by target name."""
    functions, modules = _drive_imports(source)
    found, lookalikes = [], []
    for targets, call in _assigned_calls(source, DRIVE_MARGINS, *functions):
        f = call.func
        ours = (f.id in functions if isinstance(f, ast.Name)
                else ast.unparse(f.value) in modules)
        (found if ours else lookalikes).extend(ast.unparse(t) for t in targets)
    return found, lookalikes


def drive_margins(source):
    """The module-level drive margins, by the name each set is bound to: an
    assignment whose value calls armature.drive's `margins`, as the module
    imports it."""
    return _drive_calls(source)[0]


def bare_margins(source):
    """The module-level margins declared with no `truth=`, by the name each is
    bound to: an assignment whose value calls `Margin` or `armature.Margin`
    with no truth, by keyword or as the fifth argument, or with None; and
    one that calls a `margins` that is not armature.drive's."""
    bare = []
    for targets, call in _assigned_calls(source, MARGIN):
        truth = [k.value for k in call.keywords if k.arg == "truth"] \
            or call.args[4:5]
        if not truth or (isinstance(truth[0], ast.Constant)
                         and truth[0].value is None):
            bare += [ast.unparse(t) for t in targets]
    return bare + _drive_calls(source)[1]


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
    return ((root / DESCRIPTION).is_file() and path.stem.endswith("_checks")
            and not is_review_checks(path))


def is_review_checks(path):
    """
    Whether this file is a review's checks file,
    `review_<date>_<artifact>_checks.py`: one review's recomputations, a
    `test_F<n>_*` per finding it closes (ADR 0011). It pairs with no module
    and makes no claim of its own for a truth check to test, so neither gate
    holds it; `run_all.py` collects it by itself.
    """
    return path.stem.startswith("review_") and path.stem.endswith("_checks")


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
                        else None,
                        drive_margins(source)))
    return rows


def unchecked_claims(rows):
    """The gated checks modules carrying neither a truth check nor a reason."""
    return [row.where for row in rows if row.truth == [] and not row.truth_exempt]


def unconfirmed_margins(rows):
    """The margins, `module: NAME`, declared with no truth in a gated
    directory, in a module that gives no reason."""
    return [f"{row.where}: {name}" for row in rows if not row.truth_exempt
            for name in row.bare or []]


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
        print(f"\n{'note (information only)':<34}{'lines':>11}")
        for note in sorted(NOTES.glob("*.md")):
            lines = len(note.read_text(encoding="utf-8").splitlines())
            print(f"{note.name:<34}{lines:>11}")
    print("")
    from layout_checks import (test_checks_modules_are_paired,
                               test_every_margin_carries_a_truth,
                               test_milestone_checks_carry_a_truth_check,
                               test_modules_within_budget,
                               test_the_truth_gate_has_teeth)
    try:
        test_modules_within_budget()
        test_checks_modules_are_paired()
        test_milestone_checks_carry_a_truth_check()
        test_every_margin_carries_a_truth()
        test_the_truth_gate_has_teeth()
    except AssertionError as failure:
        sys.exit(f"FAIL: {failure}")
