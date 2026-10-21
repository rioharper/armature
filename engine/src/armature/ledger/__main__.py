"""`py -m armature.ledger check [--json]`, `show <prefix>` and `render`,
on the ledger nearest the working directory, or the one `--path` names.
`check` prints one finding per line, `<level> <code> <entry>: <message>`,
or a JSON list with `--json`, and exits 1 on any error; a ledger it cannot
read is an error too. `render` prints each file it rewrote.

`set <name> --from-part <file>` runs the part file's `--mass-properties`
export with this Python, writes its mass, COM and inertia as `cad`
candidates, and prints each entry it changed; run it where the part file's
imports are, `uv run --with 'build123d~=0.11'` for a build123d recipe."""

import argparse
import json
import sys

from .check import check
from .entries import LedgerError, find
from .show import show
from .views import render
from .write import set_from_part

PATH_HELP = ("the ledger, or a folder at or below it (default: the working "
             "directory)")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m armature.ledger")
    verbs = parser.add_subparsers(dest="verb", required=True)
    for verb in ("check", "show", "render"):
        verbs.add_parser(verb)
    verbs.add_parser("set", help="write a part file's measured mass, COM "
                     "and inertia as cad candidates")
    for sub in verbs.choices.values():
        sub.add_argument("--path", help=PATH_HELP)
    verbs.choices["check"].add_argument("--json", action="store_true")
    verbs.choices["show"].add_argument("prefix")
    put = verbs.choices["set"]
    put.add_argument("name", help="the part's entries, part.<pn>")
    put.add_argument("--from-part", required=True, metavar="FILE",
                     help="the part file whose --mass-properties export "
                     "this runs")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):   # a Windows pipe is cp1252
        stream.reconfigure(encoding="utf-8")
    try:
        if args.verb == "render":
            return _render(args.path)
        if args.verb == "set":
            changed = set_from_part(args.name, args.from_part,
                                    path=args.path)
            print("\n".join(f"set {name}" for name in changed)
                  or f"{args.name}: unchanged")
            return 0
        if args.verb == "show":
            print(show(args.prefix, path=args.path))
            return 0
        findings = check(args.path)
    except LedgerError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    else:
        for f in findings:
            print(f)
    return int(any(f.level == "error" for f in findings))


def _render(path):
    """Rewrite the project's views, printing each file it changed."""
    root = find(path).parent
    for file in render(path):
        print(f"rendered {file.relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
