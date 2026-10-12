"""
run_all.py — every self-test in cad/parts/, in order, end to end.

    uv run --project analysis/model --with 'build123d~=0.11' python cad/parts/run_all.py

Exits nonzero on the first failing check, which is what makes it a
pre-commit hook or CI step. `--project analysis/model` runs it in the
model's environment, which has the engine the sweep poses its envelopes
with; the part files need only build123d and analysis/model/params.py.

Discovery is by shape, not by name. A module in this directory, or one level
down in a package, is collected when its sibling checks module
(`part.py` -> `part_checks.py`, `check/mass.py` -> `check/mass_checks.py`)
defines callables named `test_*`; each of those callables is one check.
Nothing in this file lists modules or tests, so a part file added later is
collected the moment its `<PART-ID>_checks.py` lands.

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


def checks_for(module):
    """The module's own self-tests, then those in its sibling checks module."""
    checks = checks_in(module)
    sibling = Path(module.__file__).with_name(
        Path(module.__file__).stem + "_checks.py")
    if sibling.is_file():
        checks += checks_in(importlib.import_module(module.__name__ + "_checks"))
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
    triples = [(title, module, checks_for(module)) for _key, title, module in found]
    return [triple for triple in triples if triple[2]]


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
