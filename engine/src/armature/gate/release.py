"""A release's two items (ADR 0011): each part's stubs gone, and each
part's and the model's `run_all.py` stamped green.

`stubs.still_placeholder()` sees only the stubs built in its own process,
and an empty list from a process that built nothing proves nothing. So the
check runs in the part's folder, in the environment its `run_all.py` runs
in: it loads the part's build recipe, calls its `build()`, and asks the
`stubs` that build imported. A recipe with no `build()` fails; a part with
no recipe (modeled by hand in CAD) has no stub to build. A pass is cached
like a stamp, under a key of the folder's stamp key and the recipe, so
`verify` reads it and runs nothing.
"""

import hashlib
import json

from . import orders, stamps

MODEL = stamps.MODEL
TAIL = stamps.TAIL
# Run in the part's folder as `python -B -c PROBE <recipe>`: no bytecode,
# so a pass leaves the tree as clean as it found it.
PROBE = """\
import importlib.util, json, sys
from pathlib import Path
file = Path(sys.argv[1])
sys.path.insert(0, str(file.resolve().parent))
spec = importlib.util.spec_from_file_location(file.stem, file)
module = importlib.util.module_from_spec(spec)
sys.modules[file.stem] = module
spec.loader.exec_module(module)
if not callable(getattr(module, "build", None)):
    print(json.dumps({"error": f"{file.name} defines no build()"}))
    sys.exit(1)
module.build()
stubs = sys.modules.get("stubs")
print(json.dumps({"placeholders": stubs.still_placeholder() if stubs
                  else []}))
"""


def _release(ctx):
    """(order, None) for a release, else (None, the item's result)."""
    return orders.of_kind(ctx, "release", "sends out no part")


def _parts(ctx, found):
    """Each line's part, as (definition, Part or None)."""
    return [(line.definition, orders.part(ctx.files, line.definition))
            for line in found.lines]


def key(ctx, part):
    k = stamps.key(ctx.repo, ctx.tip, ctx.files, part.folder)
    return hashlib.sha256(f"placeholders\n{k}\n{part.recipe}"
                          .encode("utf-8")).hexdigest()


def placeholders(ctx):
    """Each part the release names has no stub left: its recipe's
    `build()`, run in its folder, leaves `still_placeholder()` empty."""
    found, result = _release(ctx)
    if found is None:
        return result
    runnable = (not ctx.verify and ctx.repo.head == ctx.tip
                and ctx.repo.head_branch == ctx.branch)
    failed, notes = [], []
    for definition, part in _parts(ctx, found):
        if part is None:
            failed.append(f"{definition}: no part definition "
                          f"{definition}.md")
            continue
        if part.recipe is None:
            notes.append(f"{definition}: no build recipe, so no stub")
            continue
        k = key(ctx, part)
        if stamps.stamped(ctx.repo.root, k) and not (ctx.fresh
                                                     and not ctx.verify):
            notes.append(f"{definition}: no stub, checked for its content")
            continue
        why = _check(ctx, part, k, runnable)
        if why:
            failed.append(f"{definition}: {why}")
        else:
            notes.append(f"{definition}: built, no stub left")
    if failed:
        return False, "; ".join(failed)
    return True, "; ".join(notes)


def _check(ctx, part, k, runnable):
    """Why `part` cannot show it has no stub left, or None, caching a
    pass."""
    if ctx.verify:
        return ("its stubs are not checked for its content; run "
                "py -m armature.gate buy")
    if not runnable:
        return f"not checked, and {ctx.branch} is not checked out to check it"
    dirty = ctx.repo.dirty()
    if dirty:
        return (f"not checked, and the tree has uncommitted changes "
                f"({', '.join(dirty[:3])}); commit them, then run the gate")
    root = ctx.repo.root
    project = stamps.environment(ctx.files, part.folder)
    runner = ctx.runner or stamps.run_all
    passed, output = runner(root / part.folder, root / project,
                            "-B", "-c", PROBE,
                            part.recipe.rsplit("/", 1)[-1])
    got = _last_json(output)
    if not passed or got is None or "placeholders" not in got:
        error = (got or {}).get("error")
        return error or f"its build fails: {stamps.tail(output)}"
    if got["placeholders"]:
        return (f"still a placeholder: {', '.join(got['placeholders'])}; "
                f"replace each with vendor geometry or a drawing from the "
                f"datasheet")
    changed = ctx.repo.dirty()
    if changed:
        return (f"its build changed {', '.join(changed[:3])}; commit that, "
                f"then run the gate")
    stamps.write(root, k, part.folder, ctx.tip)
    return None


def _last_json(output):
    for line in reversed(output.splitlines()):
        try:
            got = json.loads(line)
        except ValueError:
            continue
        if isinstance(got, dict):
            return got
    return None


def stamped(ctx):
    """Each named part's `run_all.py` and the model's are stamped green for
    their content: the model's run carries the tolerance-corner bands the
    part's loads come from."""
    found, result = _release(ctx)
    if found is None:
        return result
    folders, failed = {}, []
    for definition, part in _parts(ctx, found):
        if part is None:
            failed.append(f"{definition}: no part definition "
                          f"{definition}.md")
        else:
            folders.setdefault(part.folder, definition)
    folders[MODEL] = "the model"
    notes = []
    for folder, whose in folders.items():
        run_all = stamps.within(folder, stamps.RUN_ALL)
        if run_all not in ctx.files:
            failed.append(f"{whose}: no {run_all}")
        elif not stamps.stamped(ctx.repo.root, stamps.key(
                ctx.repo, ctx.tip, ctx.files, folder)):
            failed.append(f"{folder}: no green stamp for its content (see "
                          f"stamps)")
        else:
            notes.append(f"{folder} stamped")
    if failed:
        return False, "; ".join(failed)
    return True, "; ".join(notes)
