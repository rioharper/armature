"""
run_all.py — every milestone's self-tests, in order, end to end.

Two commands run this model's checks, and both find their work here:

    uv run python run_all.py    # the milestone checkpoint command
    uv run pytest               # through test_derivation.py

Discovery is by shape, not by name. A module in this directory, or one level
down in a package, is a milestone module when it or its sibling checks module
(`kinematics.py` -> `kinematics_checks.py`) defines callables named `test_*`;
each of those callables is one check. Nothing in this file lists modules or
tests, so a module added later — a `spring.py` for a plan task — is collected
the moment it lands, and so is a test added to a checks module that already
exists.

That is deliberate. A hardcoded list is a list you forget to add to, and the
self-tests you forget are exactly the ones that then never run.

A margin is discovered the same way, by type: every module-level
`armature.Margin` in a milestone module or its checks module is one more
check, run after the module's `test_*` callables. The check searches it
(`armature.search`), prints the `Worst` row a note cites, and fails where
the margin does not pass, or where its `truth=` disagrees with it beyond
`agree=` at the worst point or the pre-polish best. A check that reads the
same worst calls `searched(margin)`, so each margin is searched once per run.
A module-level tuple of margins is found too, which is how `drive.py`
declares the drive margins (`armature.drive.margins`). A margin whose inputs
are missing is UNCHECKED: its check prints the inputs it lacks and fails,
unless the module's DRIVE_EXEMPT names it with an argued reason, which then
prints in its row in place of FAILS.

Before any of them, and before any milestone module is imported, it runs
`python -m armature.ledger check` on the nearest `ledger.toml` at or above
this folder (ADR 0010), as Milestone 0's first check: a unit slip, an
estimate with no band or a dangling `of` stops the run there, before a model
sizes anything on it. Where there is no ledger, or no engine to check one
with, it says so and goes on.

During development run one milestone by name — a module or a package:

    uv run python run_all.py kinematics

It runs that milestone's checks without rebuilding the symbolic models of the
milestones it isn't checking, and without the code-line budget in `layout.py`,
which only the full run enforces. The same file ships in armature-cad's part
template, where the modules it collects are part files and libraries.
"""

import importlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Run order and headings come from each module's optional module-level
# MILESTONE tuple, (order, title): the int orders the run, the string titles
# it. In a package the tuple lives in `__init__.py` and every submodule
# inherits it, sorting among its siblings by file name. A module without one
# still runs — last, titled by its own name — so the cost of forgetting the
# constant is a worse heading, never a check that silently doesn't run.
DEFAULT_ORDER = float("inf")

# A margin whose inputs are missing is UNCHECKED, and fails. A module lets one
# stand by naming it in a module-level mapping of this name, margin name to
# the reason, argued: `DRIVE_EXEMPT = {"elbow_motor: winding": "..."}`.
UNCHECKED_EXEMPT = "DRIVE_EXEMPT"

LEDGER_TITLE = "Milestone 0: the ledger"


def is_model_module(stem):
    """
    Whether a file stem can be a milestone module. Not: this file, pytest's
    `test_*.py` (they import back into here), anything underscore-prefixed,
    a `*_checks.py` (collected through its module, never on its own), or a
    report renderer (`report.py`, `report_*.py`), which prints and never checks.
    """
    return not (stem == Path(__file__).stem
                or stem.startswith(("_", "test_", "report_"))
                or stem.endswith("_checks")
                or stem == "report")


def checks_in(module):
    """
    Every self-test defined in `module`, in the order the file defines them.

    Filtering on `__module__` keeps a self-test *imported* from an earlier
    milestone (`from kinematics_checks import ...`) from being counted, and
    run, a second time here.
    """
    return [obj for name, obj in vars(module).items()
            if name.startswith("test_")
            and callable(obj)
            and getattr(obj, "__module__", None) == module.__name__]


def margin_type():
    """The engine's `Margin`, or None where the engine does not import: a
    directory that cannot import it declares no margins, and armature-cad's
    part files run with build123d alone."""
    try:
        from armature import Margin
    except ImportError:
        return None
    return Margin


def margins_in(module):
    """Every module-level `Margin` in `module`, in the order the file binds
    them, and each in a module-level tuple or list of margins, as
    `armature.drive.margins` returns them. Found by type, so one imported
    from another module is found here too; `discover_milestones` keeps each
    margin once, where it is first found in run order."""
    kind = margin_type()
    found = []
    for obj in vars(module).values():
        if kind is None:
            break
        if isinstance(obj, kind):
            found.append(obj)
        elif (isinstance(obj, (tuple, list)) and obj
              and all(isinstance(m, kind) for m in obj)):
            found.extend(obj)
    return found


def exemptions_in(modules):
    """The margins `modules` let stand UNCHECKED, by name, each with its
    reason: their module-level DRIVE_EXEMPT mappings, merged."""
    exempt = {}
    for module in modules:
        exempt.update(getattr(module, UNCHECKED_EXEMPT, None) or {})
    return exempt


_SEARCHED = {}


def searched(margin):
    """`margin`'s worst case, `armature.search(margin)`, searched once per
    process: the margin's own check and any check that reads the same worst
    share one search."""
    if id(margin) not in _SEARCHED:
        from armature import search
        _SEARCHED[id(margin)] = margin, search(margin)
    return _SEARCHED[id(margin)][1]


def exempt_row(worst, exempt):
    """The row an UNCHECKED `worst` prints where `exempt` lets it stand: the
    inputs it lacks and the reason, never the FAILS of its own row, which
    beside [EXEMPT] reads as a contradiction."""
    return (f"{worst.margin}: UNCHECKED (missing "
            f"{', '.join(worst.unchecked)}) because {exempt}")


def margin_check(margin, exempt=None):
    """The check a discovered margin runs as: search it, print its row, and
    fail where it does not pass, or where its truth disagrees beyond
    `agree`. An UNCHECKED margin, whose inputs are missing, fails too,
    unless `exempt` gives the reason it may stand: then its `exempt_row`,
    the inputs it lacks and the reason, prints. The margin rides on the
    check as `.margin`, the reason as `.exempt`."""
    def check():
        worst = searched(margin)
        if worst.unchecked:
            assert exempt, (
                f"a margin is UNCHECKED: {worst}. Give it the data it names, "
                f"or argue in {UNCHECKED_EXEMPT} why it may stand unchecked")
            print(f"  [EXEMPT] {exempt_row(worst, exempt)}")
            return
        assert worst.passes, f"a margin fails: {worst}"
        assert worst.truth is None or worst.truth.agrees, (
            f"a margin's truth disagrees with it: {worst}")
        print(f"  [PASS] {worst}")
    check.__name__ = check.__qualname__ = f"margin[{margin.name}]"
    check.margin, check.exempt = margin, exempt
    return check


def exemptions_check(exempt, margins):
    """The check on a module's DRIVE_EXEMPT: each entry names one of the
    module's margins that is UNCHECKED, with a reason. An entry for a
    margin that has its data is stale, and one with no reason is a claim
    nobody argued."""
    def check():
        named = {margin.name: margin for margin in margins}
        unknown = sorted(n for n in exempt if n not in named)
        assert not unknown, (f"{UNCHECKED_EXEMPT} names {unknown}, which are "
                             f"no margins here; the margins are {sorted(named)}")
        stale = sorted(n for n in exempt if not named[n].unchecked)
        assert not stale, (f"{UNCHECKED_EXEMPT} exempts {stale}, which have "
                           f"their data and are checked; remove the entries")
        bare = sorted(n for n, why in exempt.items()
                      if not (isinstance(why, str) and why.strip()))
        assert not bare, (f"{UNCHECKED_EXEMPT} gives {bare} no reason; an "
                          f"exemption is a non-empty string arguing it")
        print(f"  [PASS] {UNCHECKED_EXEMPT}: {len(exempt)} margin(s) stand "
              f"unchecked, each with its reason")
    check.__name__ = check.__qualname__ = UNCHECKED_EXEMPT
    return check


def checks_for(module):
    """The module's own self-tests, then those in its sibling checks module,
    then a check for each margin either declares."""
    modules = [module]
    sibling = Path(module.__file__).with_name(
        Path(module.__file__).stem + "_checks.py")
    if sibling.is_file():
        modules.append(importlib.import_module(module.__name__ + "_checks"))
    checks = [check for m in modules for check in checks_in(m)]
    margins = []
    for margin in (margin for m in modules for margin in margins_in(m)):
        if all(margin is not kept for kept in margins):
            margins.append(margin)
    exempt = exemptions_in(modules)
    checks += [margin_check(margin, exempt.get(margin.name))
               for margin in margins]
    if any(hasattr(m, UNCHECKED_EXEMPT) for m in modules):
        checks.append(exemptions_check(exempt, margins))
    return checks


def discover_milestones(names=None):
    """
    Every milestone module in this directory, in run order, as
    `(title, module, checks)` triples. `names` limits discovery to the named
    top-level modules and packages, importing nothing else.
    """
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))

    found = []
    for path in sorted(HERE.iterdir()):
        name = path.stem
        if names is not None and name not in names:
            continue
        if (path / "__init__.py").is_file():
            package = importlib.import_module(name)
            order, title = getattr(package, "MILESTONE", (DEFAULT_ORDER, name))
            for sub in sorted(path.glob("*.py")):
                if is_model_module(sub.stem):
                    module = importlib.import_module(f"{name}.{sub.stem}")
                    found.append(((order, title, sub.stem),
                                  f"{title} / {sub.stem}", module))
        elif path.suffix == ".py" and is_model_module(name):
            module = importlib.import_module(name)
            order, title = getattr(module, "MILESTONE", (DEFAULT_ORDER, name))
            found.append(((order, title, ""), title, module))

    found.sort(key=lambda entry: entry[0])
    triples, margins = [], set()
    for _key, title, module in found:
        checks = []
        for check in checks_for(module):
            margin = getattr(check, "margin", None)
            if margin is not None:
                if id(margin) in margins:
                    continue
                margins.add(id(margin))
            checks.append(check)
        triples.append((title, module, checks))
    return [triple for triple in triples if triple[2]]


def discover_margins(names=None):
    """Every discovered margin, in run order, as `(title, margin)` pairs:
    what `report_results.py` prints its table from."""
    return [(title, check.margin)
            for title, _module, checks in discover_milestones(names)
            for check in checks if hasattr(check, "margin")]


def discover_exemptions(names=None):
    """Every discovered margin let stand UNCHECKED, by name, with its
    reason."""
    return {check.margin.name: check.exempt
            for _title, _module, checks in discover_milestones(names)
            for check in checks if getattr(check, "exempt", None)}


def ledger_check():
    """The ledger's check, `python -m armature.ledger check` on the nearest
    `ledger.toml` at or above this folder: it prints every finding and fails
    on an error. None where the engine does not import or no ledger is
    found, which `main` prints."""
    try:
        from armature.ledger import LedgerError, check, find
    except ModuleNotFoundError as e:
        if e.name != "armature":
            raise   # the engine is there, and something it needs is not
        return None
    try:
        path = find(HERE)
    except LedgerError:
        return None

    def ledger():
        findings = check(path)
        for finding in findings:
            print(f"  {finding}")
        errors = [f for f in findings if f.level == "error"]
        assert not errors, (
            f"ledger check: {len(errors)} error(s) in {path}; the first is "
            f"{errors[0]}")
        print(f"  [PASS] ledger check on {os.path.relpath(path, HERE)}: no "
              f"error, {len(findings)} warning(s)")
    return ledger


def _run(title, checks):
    print(f"=== {title} ===")
    for check in checks:
        check()


def main(names=None):
    """Run the named milestones, or every one, in order; the first failure raises."""
    unknown = [name for name in names or []
               if not (HERE / f"{name}.py").is_file()
               and not (HERE / name / "__init__.py").is_file()]
    assert not unknown, f"no module or package named {unknown} in {HERE}"
    ledger = ledger_check()
    _run(LEDGER_TITLE, [ledger] if ledger else [])
    if ledger is None:
        print(f"  no ledger.toml at or above {HERE}, or no engine to check "
              f"one with")
    print("")
    milestones = discover_milestones(names)
    assert milestones, (f"no milestone modules named {names} in {HERE}" if names
                        else f"no milestone modules found in {HERE}")
    for title, _module, checks in milestones:
        _run(title, checks)
        print("")
    print(f"All self-tests passed across {'; '.join(names)}." if names
          else "All self-tests passed across all milestones.")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
