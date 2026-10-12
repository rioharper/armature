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

During development run one milestone by name — a module or a package:

    uv run python run_all.py kinematics

It runs that milestone's checks without rebuilding the symbolic models of the
milestones it isn't checking, and without the code-line budget in `layout.py`,
which only the full run enforces. The same file ships in armature-cad's part
template, where the modules it collects are part files and libraries.
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
    them. Found by type, so one imported from another module is found here
    too; `discover_milestones` keeps each margin once, where it is first
    found in run order."""
    kind = margin_type()
    return [obj for obj in vars(module).values()
            if kind is not None and isinstance(obj, kind)]


_SEARCHED = {}


def searched(margin):
    """`margin`'s worst case, `armature.search(margin)`, searched once per
    process: the margin's own check and any check that reads the same worst
    share one search."""
    if id(margin) not in _SEARCHED:
        from armature import search
        _SEARCHED[id(margin)] = margin, search(margin)
    return _SEARCHED[id(margin)][1]


def margin_check(margin):
    """The check a discovered margin runs as: search it, print its row, and
    fail where it does not pass, or where its truth disagrees beyond
    `agree`. The margin rides on the check as `.margin`."""
    def check():
        worst = searched(margin)
        assert worst.passes, f"a margin fails: {worst}"
        assert worst.truth is None or worst.truth.agrees, (
            f"a margin's truth disagrees with it: {worst}")
        print(f"  [PASS] {worst}")
    check.__name__ = check.__qualname__ = f"margin[{margin.name}]"
    check.margin = margin
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
    return checks + [margin_check(margin) for margin in margins]


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
