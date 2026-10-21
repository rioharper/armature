"""
run_all.py — every self-test in cad/parts/, in order, end to end.

    uv run --project analysis/model --with 'build123d~=0.11' python cad/parts/run_all.py

Exits nonzero on the first failing check, which is what makes it a
pre-commit hook or CI step. `--project analysis/model` runs it in the
model's environment, which has the engine the sweep poses its envelopes
with; the part files need only build123d and the ledger.

Discovery is by shape, not by name. A module in this directory, or one level
down in a package, is collected when its sibling checks module
(`part.py` -> `part_checks.py`, `check/mass.py` -> `check/mass_checks.py`)
defines callables named `test_*`; each of those callables is one check.
Nothing in this file lists modules or tests, so a part file added later is
collected the moment its `<PART-ID>_checks.py` lands. A review's checks
file, `review_<date>_<artifact>_checks.py`, has no module beside it and is
collected by itself, last (ADR 0011). A module-level
`armature.Margin`, or a tuple of them, is collected too, searched and held
to passing as in the model template, an UNCHECKED one failing unless
DRIVE_EXEMPT argues it; run without the engine, as a part file is, there are
none.

During development run one module or package by name:

    python cad/parts/run_all.py check

It runs that name's checks without the code-line budget in `layout.py`,
which only the full run enforces. The same file ships in armature-derive's
model template, where the modules it collects are milestones.
"""

import importlib
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


def is_review_checks(path):
    """
    Whether `path` is a review's checks file,
    `review_<date>_<artifact>_checks.py`: one review's recomputations, a
    `test_F<n>_*` per finding it closes (ADR 0011). It has no module of its
    own beside it, so it is collected as a module by itself, and a
    `fixed` closure's `check` passes when this run does.
    """
    stem = path.stem
    return (path.suffix == ".py" and stem.startswith("review_")
            and stem.endswith("_checks")
            and not path.with_name(stem[:-len("_checks")] + ".py").is_file())


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
        elif path.suffix == ".py" and (is_model_module(name)
                                       or is_review_checks(path)):
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
